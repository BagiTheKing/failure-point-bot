"""
A full episode from an animation sheet, in two halves around the 3D render
(.github/workflows/episode_sample.yml):

    python tools/episode_sample.py prepare SHEET OUT [--ai]   # voice, timing, photos
    python tools/episode_sample.py recut OUT [--hook "line | line"] [--title T]
    python tools/episode_sample.py assemble OUT RAW3D [--ai CLIP]

prepare writes OUT/timed_sheet.json (render the 3D model from it), the voice
takes, OUT/photos.json and OUT/shards.json (the render matrix). assemble
writes OUT/episode.mp4 and OUT/episode.json (length, chapters, credits).
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

FRAMES_PER_SHARD = 80


def _writer():
    """The free writers' pool and call, or (None, None) without keys."""
    try:
        from llm_provider import get_pool
        from longform_llm import _call
        return get_pool(), _call
    except Exception as e:
        print(f"no writer ({type(e).__name__}: {e})")
        return None, None


def _hook(sheet, out, hook_text="", title=""):
    """The cold open's lines: given by hand (lines split by |), the
    sheet's own, or written now from its narration; then voiced."""
    import episode
    if hook_text.strip():
        sheet["hook"] = {"lines": [x.strip() for x in hook_text.split("|") if x.strip()],
                         "title": (title or (sheet.get("hook") or {}).get("title", "")).upper(),
                         "sub": sheet["disaster"].get("place_date", "")}
    elif not (sheet.get("hook") or {}).get("lines"):
        pool, call = _writer()
        hook = episode.write_hook(sheet, pool, call) if pool else None
        if hook:
            sheet["hook"] = hook
    if title:
        sheet.setdefault("hook", {})["title"] = title.upper()
    if (sheet.get("hook") or {}).get("lines"):
        print("cold open:", sheet["hook"]["title"], "|", " / ".join(sheet["hook"]["lines"]))
        return episode.record_hook(sheet, out)
    print("no cold open")
    return {}


def _report(sheet, report="", credit=""):
    """The investigation report whose pictures join the photos."""
    if report.strip():
        sheet["disaster"]["report"] = {"url": report.strip(), "credit": credit.strip() or "Investigation report"}


def _pictures(sheet, out, name):
    import episode
    try:
        episode.gather_footage(sheet, out, owner_dir=os.path.join("footage", name) if name else None)
    except Exception as e:                 # footage is a bonus: photos carry part 1
        print(f"no footage ({type(e).__name__}: {e})")
        json.dump([], open(os.path.join(out, "footage.json"), "w"))
    try:
        pool, call = _writer()
        episode.gather_photos(sheet, out, pool=pool, call=call)
    except Exception as e:                 # photos are a bonus: 3D stills stand in
        print(f"no photos ({type(e).__name__}: {e})")
        json.dump({}, open(os.path.join(out, "photos.json"), "w"))


def _drop_excluded(sheet, out):
    """Pictures of a kept cut that the sheet has since ruled out, taken away
    (the rest of the cut stays as approved)."""
    import episode
    path = os.path.join(out, "photos.json")
    if not os.path.exists(path):
        return
    photos = json.load(open(path))
    kept = {k: [c for c in v if not episode._excluded(c, sheet)] for k, v in photos.items()}
    gone = sum(len(v) for v in photos.values()) - sum(len(v) for v in kept.values())
    for k, v in kept.items():
        for c in v:
            print(f"  {k}: {c.get('title', '')[:90]}")
    if gone:
        print(f"  {gone} picture(s) ruled out since: taken away")
        json.dump(kept, open(path, "w"), indent=1, ensure_ascii=False)
    json.dump(sheet, open(os.path.join(out, "timed_sheet.json"), "w"), indent=2, ensure_ascii=False)


SHOTS_3D = ("establish", "load_path", "connection", "fall", "dramatization")


def revoice(sheet, later, out):
    """Shots whose narration the repo's sheet has since changed are voiced
    again; the rest keep their takes. A shot over the 3D keeps its slot, so
    the rendered frames still fit: its new take must not run longer (it is
    read a little faster, at most 12 %, if it would)."""
    import episode
    import narration
    voiced = json.load(open(os.path.join(out, "voiced.json")))
    new = {s["clip"]: s for s in later.get("shots", [])}
    slots = dict(sheet["timing"]["slots"])
    before = json.dumps(sheet.get("model_3d", {}).get("shot_seconds"), sort_keys=True)
    for sh in sheet["shots"]:
        c = sh["clip"]
        if c not in new or new[c].get("narration", "") == sh.get("narration", ""):
            continue
        sh["narration"], sh["caption"] = new[c].get("narration", ""), new[c].get("caption", sh.get("caption", ""))
        one = {"shots": [sh]}
        took = narration.record(one, os.path.join(out, "voice"))
        if c in SHOTS_3D and c in took and c in voiced:
            room = voiced[c]["seconds"]
            if took[c]["seconds"] > room:
                took = narration.record(one, os.path.join(out, "voice"),
                                        speed=min(1.12, took[c]["seconds"] / room * 1.01))
            if took[c]["seconds"] > room + 0.05:
                raise SystemExit(f"{c}: the new take ({took[c]['seconds']:.1f} s) does not fit its 3D "
                                 f"({room:.1f} s): shorten the line")
            print(f"  {c}: new take {took[c]['seconds']:.1f} s in its {room:.1f} s")
            voiced[c] = took[c]                      # the slot stays as rendered
        elif c in took:
            voiced[c] = took[c]
            slots[c] = narration.slots_of(one, took)[c]
    sheet = episode.timing(sheet, slots, sheet["timing"].get("ai", False))
    if json.dumps(sheet.get("model_3d", {}).get("shot_seconds"), sort_keys=True) != before:
        raise SystemExit("re-voicing changed the 3D timing: the rendered frames would not fit")
    json.dump(voiced, open(os.path.join(out, "voiced.json"), "w"), indent=1)
    return sheet


def recut(out, hook_text="", title="", name="", report="", report_credit="", keep=False, redo_voice=False):
    """A new cut of an episode already voiced and rendered: keeps the
    timed sheet, the voice takes and the 3D frames; adds or redoes the cold
    open, and fetches the pictures again."""
    sheet = json.load(open(os.path.join(out, "timed_sheet.json")))
    # the repo's sheet of the same name may since have pinned or ruled out pictures
    repo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "kits", "sheets", f"{name}.json")
    if name and os.path.exists(repo):
        later = json.load(open(repo))
        for k in ("photo_pins", "photo_exclude", "timeline"):     # none of these changes the timing
            if later.get(k):
                sheet[k] = later[k]
        if redo_voice:
            sheet = revoice(sheet, later, out)
    if keep:                               # an approved cut, assembled again as it is
        print("keeping the cold open and the pictures")
        _drop_excluded(sheet, out)
        return
    voiced = json.load(open(os.path.join(out, "voiced.json")))
    voiced = {k: v for k, v in voiced.items() if not k.startswith("hook_")}
    voiced.update(_hook(sheet, out, hook_text, title))
    _report(sheet, report, report_credit)
    json.dump(voiced, open(os.path.join(out, "voiced.json"), "w"), indent=1)
    json.dump(sheet, open(os.path.join(out, "timed_sheet.json"), "w"), indent=2, ensure_ascii=False)
    _pictures(sheet, out, name)


def prepare(sheet_path, out, ai=False, name="", report="", report_credit=""):
    import episode
    from kits import timemap
    from kits.blueprint import FPS
    os.makedirs(out, exist_ok=True)
    sheet = json.load(open(sheet_path))
    sheet, voiced = episode.prepare(sheet, out, ai=ai)
    voiced.update(_hook(sheet, out))
    _report(sheet, report, report_credit)
    json.dump(voiced, open(os.path.join(out, "voiced.json"), "w"), indent=1)
    json.dump(sheet, open(os.path.join(out, "timed_sheet.json"), "w"), indent=2, ensure_ascii=False)
    frames = int(math.ceil(timemap.of(sheet).total * FPS)) + 1
    shards = list(range(int(math.ceil(frames / FRAMES_PER_SHARD))))
    json.dump({"frames": frames, "per": FRAMES_PER_SHARD, "shards": shards},
              open(os.path.join(out, "shards.json"), "w"))
    _pictures(sheet, out, name)


def assemble(out, raw3d, ai):
    import episode
    sheet = json.load(open(os.path.join(out, "timed_sheet.json")))
    voiced = json.load(open(os.path.join(out, "voiced.json")))
    photos = json.load(open(os.path.join(out, "photos.json"))) if os.path.exists(
        os.path.join(out, "photos.json")) else {}
    fp = os.path.join(out, "footage.json")
    footage = json.load(open(fp)) if os.path.exists(fp) else []
    info = episode.build(sheet, raw3d, photos, voiced, os.path.join(out, "episode.mp4"),
                         os.path.join(out, "_work"), ai, footage)
    info["credits"] = sorted({p["credit"] for v in photos.values() for p in v if p.get("credit")} |
                             {c["credit"] for c in footage if c.get("credit")})
    info["ai_clip"] = bool(ai and os.path.exists(ai))
    info["hook"] = sheet.get("hook")
    json.dump(info, open(os.path.join(out, "episode.json"), "w"), indent=1, ensure_ascii=False)
    print("\n".join(info["chapters"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("sheet")
    p.add_argument("out")
    p.add_argument("--ai", action="store_true", help="time the fall for an AI clip")
    p.add_argument("--name", default="", help="footage/<name>/ holds owner-supplied footage")
    p.add_argument("--report", default="", help="the investigation report's PDF (its pictures)")
    p.add_argument("--report-credit", default="")
    r = sub.add_parser("recut")
    r.add_argument("out")
    r.add_argument("--hook", default="", help="cold-open lines, split by |")
    r.add_argument("--title", default="")
    r.add_argument("--name", default="")
    r.add_argument("--report", default="")
    r.add_argument("--report-credit", default="")
    r.add_argument("--keep", action="store_true", help="keep the cold open and the pictures as they are")
    r.add_argument("--revoice", action="store_true", help="voice again the lines the repo's sheet has changed")
    a = sub.add_parser("assemble")
    a.add_argument("out")
    a.add_argument("raw3d")
    a.add_argument("--ai", default="")
    args = ap.parse_args()
    if args.cmd == "prepare":
        prepare(args.sheet, args.out, args.ai, args.name, args.report, args.report_credit)
    elif args.cmd == "recut":
        recut(args.out, args.hook, args.title, args.name, args.report, args.report_credit, args.keep,
              args.revoice)
    else:
        assemble(args.out, args.raw3d, args.ai)
