"""
Steps 5b and 5c: one full 8-10 minute episode from an animation sheet.

    prepare(sheet, out)      voice every shot (am_echo), give each shot its
                             slot, time the kits and the 3D camera to it;
                             writes out/timed_sheet.json for the 3D render
    gather_footage(sheet, out) real footage for part 1, security cameras first
    gather_photos(sheet, out) real photos for the archive shots
    build(...)               cuts the 16 shots together (sheet_writer.SHOTS)
                             with the channel's transitions and lays the
                             voice along them

The 3D model is rendered from the timed sheet (kits/render3d.py), and the AI
collapse, when asked for, is made from its frame timemap.ai_start_frame(timed
sheet), between prepare and build. By default the 3D fall itself is the
collapse (owner, 2026-10-18: it proved better than the AI clip), and the
dramatization's narration runs over it.
"""

import json
import os
import re
import shutil
import subprocess

from kits import common, timemap
from kits.assemble import (DISSOLVE, find_frame, frames_of, render_3d_part, dramatization,
                           held, reel, to_mp4, xfade_join)
from kits.blueprint import FPS, render_clip
import narration

AI_BLEND = 0.27             # the 3D wide shot runs on into the AI clip
ARCHIVE = ("photo", "photos_disaster", "aftermath", "investigation", "today_photos")


def kit_class(variant):
    from kits.hanging_walkway import HangingWalkways
    from kits.truss_bridge import TrussBridge
    return {"hanging_walkways": HangingWalkways, "truss_bridge": TrussBridge}[variant]


# --------------------------------------------------------------------------
# 1. The voice, and the slots it sets
# --------------------------------------------------------------------------

def timing(sheet, slots, ai=False):
    """Writes the slots into the sheet: the 3D shot lengths (time map), the
    kit clip lengths, each shot's seconds. A clip that dissolves into the
    next runs DISSOLVE longer than its slot, so the slots alone add up to
    the episode and each voice starts with its own shot."""
    d = DISSOLVE
    if ai:
        # the fall shot runs from the pull-back to the AI start (canonical
        # 20 -> 21.8): pull 20-21.4 and two thirds of the hold 21.4-22
        fall = slots["fall"] + AI_BLEND
        pull, hold = fall * 1.4 / 1.8, fall * 0.6 / 1.8
    else:
        # the 3D fall (owner, 2026-10-18: better than the AI's): the pull-back
        # and hold fill the fall shot, so the span drops just as the
        # dramatization's narration begins; the drop slows a little, up to
        # half again, to carry it
        pull, hold = slots["fall"] * 1.4 / 2.0, slots["fall"] * 0.6 / 2.0
    sheet.setdefault("model_3d", {})["shot_seconds"] = {
        "establish": slots["establish"] + d,
        "load_path": slots["load_path"],
        "connection": slots["connection"] + d,
        "pull": pull,
        "hold": hold,
        "drop": min(9.0, max(6.0, slots["dramatization"])),
    }
    sheet["timing"] = {"slots": slots, "dissolve": d, "ai": ai,
                       "kit": {"build": slots["build"] + d, "physics": slots["physics"] + d,
                               "compare": slots["compare"] + d}}
    for sh in sheet["shots"]:
        sh["seconds"] = round(slots[sh["clip"]], 2)
    return sheet


def prepare(sheet, out_dir, voice=None, ai=False):
    """Voices the shots and times the sheet. Returns (timed sheet, voiced).
    ai: time the fall for an AI collapse clip instead of the 3D fall."""
    voiced = narration.record(sheet, os.path.join(out_dir, "voice"), voice)
    sheet = timing(sheet, narration.slots_of(sheet, voiced), ai)
    json.dump(voiced, open(os.path.join(out_dir, "voiced.json"), "w"), indent=1)
    json.dump(sheet, open(os.path.join(out_dir, "timed_sheet.json"), "w"), indent=2, ensure_ascii=False)
    total = sum(sheet["timing"]["slots"].values())
    print(f"episode: {total / 60:.1f} min, 3D: {timemap.of(sheet).total:.0f} s "
          f"({int(timemap.of(sheet).total * FPS)} frames)")
    return sheet, voiced


# --------------------------------------------------------------------------
# 2. Real photos for the archive shots
# --------------------------------------------------------------------------

BUCKETS = [
    ("today_photos", r"replacement|new bridge|memorial|reopen|rebuilt|today|present|current"),
    ("investigation", r"ntsb|investigat|diagram|gusset|plate|fractur|report|inspect|detail|"
                      r"drawing|test|model|schematic|connection|beam|rod|hanger"),
    ("aftermath", r"collaps|wreck|debris|rescue|aftermath|damage|ruin|recover|after|fallen|"
                  r"remains|search"),
]


def _year(sheet):
    m = re.search(r"(1[89]\d\d|20\d\d)", sheet["disaster"].get("place_date", ""))
    return int(m.group(1)) if m else None


def assign(sheet, cands):
    """Shares downloaded photos among the archive shots: the article's lead
    image opens the episode; others go where their title or date says
    (wreckage to the aftermath, diagrams to the investigation, anything
    taken years after to today); what is left fills the empty shots."""
    year = _year(sheet)
    shots = {k: [] for k in ARCHIVE}
    rest = []
    for i, c in enumerate(cands):
        if i == 0:
            shots["photo"].append(c)
            continue
        title = (c.get("title") or "").lower()
        later = year and c.get("year") and c["year"] > year + 1
        for name, pat in BUCKETS:
            if name == "today_photos" and later:
                shots[name].append(c)
                break
            if re.search(pat, title) and not (name != "today_photos" and later):
                shots[name].append(c)
                break
        else:
            rest.append(c)
    # before-the-fall pictures (no wreck, no diagram) open the story
    shots["photos_disaster"] += rest
    order = ["photos_disaster", "aftermath", "investigation", "today_photos"]
    for name in order:                      # an empty shot borrows from the fullest
        if not shots[name]:
            donor = max(order, key=lambda k: len(shots[k]))
            if len(shots[donor]) > 1:
                shots[name].append(shots[donor].pop())
    return shots


def gather_photos(sheet, out_dir, limit=16):
    """Downloads free photos from the event's Wikipedia article (Commons),
    falling back to a Commons / Library of Congress search. Writes
    out_dir/photos.json: {shot: [{"path", "credit"}]}."""
    import time
    from archive_engine import (article_images, article_lead_image, download_archival_image,
                                format_credit, search_archives)
    title = sheet["disaster"].get("photo_article") or sheet["disaster"].get("place", "")
    cands = []
    for attempt in range(3):               # Wikipedia sometimes answers empty: retry
        cands = [c for c in [article_lead_image(title)] + article_images(title) if c]
        if cands:
            break
        time.sleep(10 * (attempt + 1))
    if len(cands) < 4:
        cands += search_archives(title.replace(" collapse", ""), limit=10)
    seen, got = set(), []
    os.makedirs(os.path.join(out_dir, "photos"), exist_ok=True)
    for c in cands:
        if len(got) >= limit or c.get("url") in seen:
            continue
        seen.add(c.get("url"))
        path = os.path.join(out_dir, "photos", f"{len(got):02d}.jpg")
        if download_archival_image(c, path, 2560, 1440):
            got.append({**c, "path": path, "credit": format_credit(c)})
    print(f"{len(got)} photo(s) for {title!r}")
    shots = {k: [{"path": c["path"], "credit": c["credit"], "title": c.get("title", "")} for c in v]
             for k, v in assign(sheet, got).items()}
    json.dump(shots, open(os.path.join(out_dir, "photos.json"), "w"), indent=1, ensure_ascii=False)
    return shots


CCTV = r"cctv|surveillance|security cam|camera footage|dash ?cam|webcam|traffic cam|caught on"


def gather_footage(sheet, out_dir, limit=3, longest=24.0):
    """Real moving footage of the event for part 1, security-camera (CCTV)
    footage first (owner, 2026-10-18), from Wikimedia Commons only, so it is
    free to reuse. Writes out_dir/footage.json: [{"path", "seconds",
    "credit", "cctv"}], best first; [] when there is none (most older
    disasters), and the photos carry part 1 alone."""
    from archive_engine import (fetch_commons_video, footage_matches, format_credit, is_static,
                                search_commons_video, _clip_seconds)
    d = sheet["disaster"]
    # the short name ("I-35W Mississippi River bridge"), not the full place
    # line ("..., Minneapolis, Minnesota"), or every word must match
    article = d.get("photo_article") or d.get("place", "").split(",")[0]
    name = re.sub(r"\s+(collapse|disaster|explosion|failure)$", "", article.strip(), flags=re.I)
    year = _year(sheet)
    queries = [f"{name} {w}" for w in ("collapse surveillance", "security camera", "CCTV",
                                        "collapse video", "collapse")] + [article]
    seen, cands = set(), []
    for q in queries:
        for c in search_commons_video(q, era=year):
            if c["url"] in seen or not footage_matches(name, c["about"]):
                continue
            seen.add(c["url"])
            c["cctv"] = bool(re.search(CCTV, c["about"]))
            cands.append(c)
    cands.sort(key=lambda c: not c["cctv"])             # security cameras first, stably
    os.makedirs(os.path.join(out_dir, "footage"), exist_ok=True)
    got = []
    for c in cands:
        if len(got) >= limit:
            break
        path = os.path.join(out_dir, "footage", f"{len(got):02d}.mp4")
        # a short camera clip plays whole, from its first second
        start = 0.0 if c["duration"] <= longest + 2 else None
        if not fetch_commons_video(c, path, seconds=min(longest, c["duration"]), start=start):
            continue
        if is_static(path):
            print(f"  still pictures, not footage: {c['title']}")
            continue
        got.append({"path": path, "seconds": round(_clip_seconds(path), 2),
                    "credit": format_credit(c), "cctv": c["cctv"], "title": c["title"]})
        print(f"  footage: {c['title']} ({got[-1]['seconds']:.0f} s{', CCTV' if c['cctv'] else ''})")
    print(f"{len(got)} footage clip(s) for {name!r}")
    json.dump(got, open(os.path.join(out_dir, "footage.json"), "w"), indent=1, ensure_ascii=False)
    return got


def _short_credit(credit):
    """'Title — Artist — CC BY-SA 3.0 (via Wikimedia Commons)' -> 'Photo: Artist · CC BY-SA 3.0'."""
    parts = [p.strip() for p in re.sub(r"\s*\(via [^)]*\)$", "", credit or "").split(" — ")]
    who = parts[1] if len(parts) > 2 else ""
    lic = parts[-1] if len(parts) > 1 else ""
    return "Photo: " + " · ".join(p for p in (who, lic) if p) if (who or lic) else ""


# --------------------------------------------------------------------------
# 3. The cut
# --------------------------------------------------------------------------

def build(sheet, raw3d, photos, voiced, out_mp4, work, ai_clip=None, footage=None):
    """Cuts the episode together and lays the voice under it. footage
    (gather_footage) opens part 1, ahead of the photos."""
    os.makedirs(work, exist_ok=True)
    slots, d = sheet["timing"]["slots"], sheet["timing"]["dissolve"]
    kit = kit_class(sheet["kit"]["variant"])(sheet)
    kit.fit(sheet["timing"]["kit"])
    D = kit.durations()
    tm = timemap.of(sheet)
    anchors = {}
    for p in sorted(os.listdir(raw3d)):
        if p.startswith("anchors_"):
            anchors.update(json.load(open(os.path.join(raw3d, p))))
    caps = {sh["clip"]: sh.get("caption", "") for sh in sheet["shots"]}
    frames = lambda s: int(round(s * FPS))
    segs = []                                # (mp4, frames, transition, [(clip, offset s)])

    def add2d(name, fn, seconds, trans, shots):
        mp4 = os.path.join(work, f"{name}.mp4")
        render_clip(fn, seconds, mp4)
        segs.append((mp4, frames(seconds), trans, shots))

    def add3d(name, a, b, trans, shots, fill_to=None):
        files = render_3d_part(sheet, raw3d, anchors, a, b, os.path.join(work, name))
        if fill_to:
            files = held(files, fill_to, os.path.join(work, name + "_hold"))
        segs.append((*to_mp4(files, os.path.join(work, f"{name}.mp4")), trans, shots))
        shutil.rmtree(os.path.join(work, name), ignore_errors=True)
        shutil.rmtree(os.path.join(work, name + "_hold"), ignore_errors=True)

    def stills_3d(*canon):
        out = [find_frame(raw3d, tm.frame(c)) for c in canon]
        return [{"path": p, "credit": ""} for p in out if p]

    def stand_in(name):                    # no free photo: our own 3D frames stand in
        return {"aftermath": stills_3d(28.0), "investigation": stills_3d(17.0, 15.0),
                "today_photos": stills_3d(1.0, 4.0)}.get(name) or stills_3d(2.0, 5.0)

    def pictures(name):
        return [{"path": p["path"], "credit": _short_credit(p["credit"])}
                for p in (photos.get(name) or stand_in(name))]

    clips = []                               # the footage, decoded once
    for i, c in enumerate(footage or []):
        frames_dir = os.path.join(work, f"footage_{i}")
        clips.append({"frames": frames_of(c["path"], frames_dir, cover=True),
                      "credit": _short_credit(c["credit"]).replace("Photo:", "Footage:"),
                      "tag": "SECURITY CAMERA FOOTAGE" if c.get("cctv") else "ARCHIVE FOOTAGE"})

    def archive(name, trans, lead_clips=()):
        seconds = slots[name] + (d if trans != "cut" else 0)
        add2d(name, reel(list(lead_clips) + pictures(name), seconds, caps.get(name, "")),
              seconds, trans, [(name, 0)])

    # part 1: real footage first (security cameras before anything), then photos
    seconds = slots["photo"] + d
    add2d("photo", common.photo(sheet, reel(clips[:1] + pictures("photo"), seconds), tint_out=False),
          seconds, "dissolve", [("photo", 0)])
    archive("photos_disaster", "dissolve", clips[1:])
    e1 = tm.real(7.0)
    add3d("establish", 0, e1, "dissolve", [("establish", 0)])
    add2d("build", kit.build, D["build"], "dissolve", [("build", 0)])
    add3d("closeup", e1, tm.real(20.0), "dissolve",
          [("load_path", 0), ("connection", tm.real(13.0) - e1)])
    add2d("physics", lambda t, T: kit.physics(t, T, lead=False), D["physics"], "dissolve",
          [("physics", 0)])
    add2d("clock", common.clock(sheet), slots["clock"], "cut", [("clock", 0)])
    use_ai = bool(ai_clip and os.path.exists(ai_clip) and sheet["timing"].get("ai"))
    if use_ai:
        # the 3D shot stops on the very frame the AI clip was made from
        add3d("fall", tm.real(20.0), timemap.ai_start_frame(sheet) / FPS, ("dissolve", AI_BLEND),
              [("fall", 0)])
        files = dramatization(ai_clip, os.path.join(work, "ai"), caps.get("fall", ""),
                              frames(slots["dramatization"] + d))
        segs.append((*to_mp4(files, os.path.join(work, "ai.mp4")), "dissolve",
                     [("dramatization", 0)]))
    else:
        # the accurate 3D fall, its settle held while the narration runs
        add3d("fall", tm.real(20.0), tm.real(28.0), "dissolve",
              [("fall", 0), ("dramatization", tm.real(22.0) - tm.real(20.0))],
              fill_to=frames(slots["fall"] + slots["dramatization"] + d))
    archive("aftermath", "dissolve")
    add2d("timeline", common.timeline(sheet), slots["timeline"] + d, "dissolve", [("timeline", 0)])
    archive("investigation", "dissolve")
    add2d("compare", kit.compare, D["compare"], "dissolve", [("compare", 0)])
    archive("today_photos", "dissolve")
    add2d("today", common.today(sheet), slots["today"], "cut", [("today", 0)])

    joined = os.path.join(work, "reel.mp4")
    starts = xfade_join([(m, n, tr) for m, n, tr, _ in segs], joined)
    total = (starts[-1] + segs[-1][1]) / FPS
    placed = [(starts[i] / FPS + off, voiced[clip]["wav"])
              for i, (_, _, _, shots) in enumerate(segs) for clip, off in shots if clip in voiced]
    wav = narration.track(placed, total, os.path.join(work, "voice.wav"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-i", wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac",
                    "-b:a", "192k", "-ar", "48000", out_mp4], check=True)
    chapters = chapters_of(sheet, segs, starts)
    print(f"{out_mp4}: {total / 60:.1f} min")
    return {"seconds": total, "chapters": chapters}


PARTS = {1: "The disaster", 2: "The structure and its weak point", 3: "The physics",
         4: "Second by second", 5: "The warnings and the investigation",
         6: "How it should have worked", 7: "Could it happen today?"}


def chapters_of(sheet, segs, starts):
    """YouTube chapters, one per part of the 7-part structure."""
    from sheet_writer import SHOTS
    part = {clip: p for p, _, clip, _ in SHOTS}
    out, seen = [], set()
    for i, (_, _, _, shots) in enumerate(segs):
        for clip, off in shots:
            p = part.get(clip)
            if p and p not in seen:
                seen.add(p)
                t = int(starts[i] / FPS + off) if out else 0
                out.append(f"{t // 60}:{t % 60:02d} {PARTS[p]}")
    return out
