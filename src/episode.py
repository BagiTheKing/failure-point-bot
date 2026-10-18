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
from kits.coldopen import cold_open
from kits.blueprint import FPS, render_clip
from kits.blueprint import Frame
import narration
import score

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


def record_hook(sheet, out_dir, voice=None):
    """Voices the cold open's hook lines, one take each (hook_0, hook_1...),
    so the montage can breathe between them."""
    lines = (sheet.get("hook") or {}).get("lines") or []
    fake = {"shots": [{"clip": f"hook_{i}", "narration": line} for i, line in enumerate(lines)]}
    return narration.record(fake, os.path.join(out_dir, "voice"), voice)


def write_hook(sheet, pool, call):
    """The writer's cold open for an existing sheet: a title and 3 to 5
    short lines that make a viewer stay, every figure taken from the
    sheet's own narration. None if it cannot be had."""
    from sheet_writer import hook_problems
    source = "\n".join(sh.get("narration", "") for sh in sheet["shots"])
    system = ("You write the cold open of a documentary about an engineering disaster: the "
              "first lines a viewer hears over fast footage and tense music. Plain, factual, "
              "gripping, present tense, no hype words, no questions to the viewer. JSON only.")
    user = (f"Story: {sheet['disaster'].get('place', '')} ({sheet['disaster'].get('place_date', '')})\n\n"
            f"FACTS (the only ones you may use, figures written the same way):\n{source}\n\n"
            "Write {\"title\": \"THE ... COLLAPSE (under 32 characters, capitals)\", "
            "\"lines\": [3 to 5 lines, each under 90 characters, 60 words in all at most]}. "
            "Open on the moment (date, time, place), then what happened in one hard image, "
            "the toll, and close on the question the episode answers: a hidden cause, "
            "stated as a fact, not a question.")
    for _ in range(2):
        reply = call(pool, system, user, max_tokens=800, expect={"title": str, "lines": list})
        if isinstance(reply, dict) and not hook_problems(reply, source):
            return {"title": reply["title"].strip().upper(), "lines": [str(x).strip() for x in reply["lines"]],
                    "sub": sheet["disaster"].get("place_date", "").split("·")[0].strip()}
    return None


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


def gather_photos(sheet, out_dir, limit=16, pool=None, call=None):
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
        if other_structure(c.get("title", ""), title):
            print(f"  another structure, dropped: {c.get('title')}")
            continue
        path = os.path.join(out_dir, "photos", f"{len(got):02d}.jpg")
        if download_archival_image(c, path, 2560, 1440):
            got.append({**c, "path": path, "credit": format_credit(c)})
    print(f"{len(got)} photo(s) for {title!r}")
    picked = None
    if pool is not None and call is not None and got:
        try:
            picked = pick_photos(sheet, got, pool, call)
        except Exception as e:
            print(f"  photo picking by the writer failed ({type(e).__name__}: {e}): by title")
    picked = picked or assign(sheet, got)
    shots = {k: [{"path": c["path"], "credit": c["credit"], "title": c.get("title", "")} for c in v]
             for k, v in picked.items()}
    json.dump(shots, open(os.path.join(out_dir, "photos.json"), "w"), indent=1, ensure_ascii=False)
    return shots


def other_structure(photo_title, story_title):
    """True when a photo is named after a different road or structure than
    the story's: the I-35W article carries a picture of the I-40 bridge
    disaster, which ended up in the first episode."""
    ids = lambda s: set(re.findall(r"\b(?:i|interstate|us|sr|route|highway)[- ]?(\d+)", s.lower()))
    mine, theirs = ids(story_title), ids(photo_title)
    return bool(theirs and mine and not (theirs & mine))


def pick_photos(sheet, got, pool, call):
    """The writer matches photos to the archive shots by what each photo
    shows (its title and description) against what each shot says, and
    turns away photos that fit none. A shot no photo fits gets none: our
    own 3D stills stand in, rather than a crowd under "investigators"."""
    shots = {sh["clip"]: sh for sh in sheet["shots"]}
    brief = {k: {"caption": shots.get(k, {}).get("caption", ""),
                 "narration": (shots.get(k, {}).get("narration", "") or "")[:400]} for k in ARCHIVE}
    items = [{"id": i, "title": c.get("title", ""), "about": (c.get("about") or "")[:300],
              "year": c.get("year"),
              "shape": "portrait" if (c.get("height") or 0) > (c.get("width") or 1) else "landscape"}
             for i, c in enumerate(got)]
    system = ("You pick archive photographs for a documentary about an engineering disaster. "
              "Match each photo to the shot whose words it actually shows. A photo of a "
              "different place or event, or one that fits no shot, is rejected. Prefer "
              "landscape photos. Reply with JSON only.")
    user = (f"Story: {sheet['disaster'].get('place', '')}, {sheet['disaster'].get('place_date', '')}\n\n"
            f"SHOTS:\n{json.dumps(brief, indent=1, ensure_ascii=False)}\n\n"
            f"PHOTOS:\n{json.dumps(items, indent=1, ensure_ascii=False)}\n\n"
            "Reply as {\"photo\": [ids], \"photos_disaster\": [ids], \"aftermath\": [ids], "
            "\"investigation\": [ids], \"today_photos\": [ids], \"reject\": [ids]}: best first, "
            "each photo in one list at most; \"photo\" is the single strongest image of the "
            "event; \"today_photos\" only what the place looks like after (a replacement, a "
            "memorial).")
    reply = call(pool, system, user, max_tokens=1500,
                 expect={k: list for k in (*ARCHIVE, "reject")})
    if not isinstance(reply, dict):
        return None
    used, out = set(), {}
    for k in ARCHIVE:
        out[k] = []
        for i in reply.get(k) or []:
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(got) and i not in used:
                used.add(i)
                out[k].append(got[i])
    if not out["photo"]:
        return None
    print("  photos picked by the writer: " + ", ".join(f"{k} {len(v)}" for k, v in out.items())
          + f", rejected {len(got) - len(used)}")
    return out


CCTV = r"cctv|surveillance|security cam|camera footage|dash ?cam|webcam|traffic cam|caught on"


def owner_footage(folder, out_dir, longest=24.0):
    """Footage the owner chose and put in footage/<episode>/ (any .mp4/.webm/
    .mov), each with an optional same-name .txt holding its credit line. Used
    first, ahead of anything searched for. The owner answers for its rights
    (a US government camera, like the Corps of Engineers' at I-35W, is public
    domain)."""
    from archive_engine import _clip_seconds
    out = []
    if not folder or not os.path.isdir(folder):
        return out
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith((".mp4", ".webm", ".mov", ".mkv")):
            continue
        src = os.path.join(folder, f)
        txt = os.path.splitext(src)[0] + ".txt"
        credit = open(txt).read().strip() if os.path.exists(txt) else ""
        # silent, at most `longest` seconds: the cold open cuts it into pieces
        path = os.path.join(out_dir, "footage", f"owner_{len(out):02d}.mp4")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-t", str(longest), "-an",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                            path], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  owner footage unreadable: {f}: {r.stderr.strip()[-160:]}")
            continue
        secs = _clip_seconds(path)
        out.append({"path": path, "seconds": round(secs, 2), "credit": credit,
                    "cctv": bool(re.search(CCTV, (f + " " + credit).lower())), "title": f, "owner": True})
        print(f"  owner footage: {f} ({secs:.0f} s)")
    return out


def gather_footage(sheet, out_dir, limit=3, longest=24.0, owner_dir=None):
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
    got = owner_footage(owner_dir, out_dir, longest)
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
    got.sort(key=lambda c: (not c.get("owner"), not c["cctv"]))
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
    texts = {sh["clip"]: sh.get("narration", "") for sh in sheet["shots"]}
    frames = lambda s: int(round(s * FPS))
    # when each word is spoken, so pictures can land on the words that name them
    words = {c: narration.words_of(texts[c], v["wav"]) for c, v in voiced.items() if texts.get(c)}
    toll_shot, toll_t = toll_moment(sheet, words)
    # each shot is queued as a job, then all of them render side by side on
    # every core the runner has: [(make() -> (mp4, frames), transition, shots)]
    jobs = []

    def add2d(name, fn, seconds, trans, shots):
        mp4 = os.path.join(work, f"{name}.mp4")
        if toll_shot and toll_shot != "photo" and toll_shot in [c for c, _ in shots]:
            fn = with_toll(fn, sheet, toll_t + dict(shots)[toll_shot])

        def make():
            render_clip(fn, seconds, mp4)
            return mp4, frames(seconds)
        jobs.append((make, trans, shots))

    def add3d(name, a, b, trans, shots, fill_to=None):
        def make():
            files = render_3d_part(sheet, raw3d, anchors, a, b, os.path.join(work, name))
            if fill_to:
                files = held(files, fill_to, os.path.join(work, name + "_hold"))
            out = to_mp4(files, os.path.join(work, f"{name}.mp4"))
            shutil.rmtree(os.path.join(work, name), ignore_errors=True)
            shutil.rmtree(os.path.join(work, name + "_hold"), ignore_errors=True)
            return out
        jobs.append((make, trans, shots))

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

    # the cold open: a ~30 s montage under the hook lines and thriller music
    hook = sheet.get("hook") or {}
    takes = [voiced[k] for k in sorted((k for k in voiced if k.startswith("hook_")),
                                       key=lambda k: int(k.split("_")[1]))]
    hook_T = 0.0
    if hook.get("lines") and takes:
        lines, hook_T = hook_schedule(hook["lines"], takes)
        f0, f1 = tm.frame(20.0), tm.frame(28.0)
        fall3d = [p for p in (find_frame(raw3d, n) for n in range(f0, f1 + 1)) if p]
        pics = (pictures("photo") + (photos.get("aftermath") and pictures("aftermath") or [])
                + (photos.get("photos_disaster") and pictures("photos_disaster") or []))[:8]
        items = ([{**c, "kind": "footage"} for c in clips] + pics
                 + ([{"frames": fall3d, "kind": "3d"}] if fall3d else []))
        add2d("hook", cold_open(sheet, items, [(a, b, txt) for a, b, txt in lines], hook_T,
                                hook.get("title", ""), hook.get("sub", "")),
              hook_T, "cut", [(f"hook_{i}", a - narration.PAD_IN) for i, (a, _, _) in enumerate(lines)])

    # part 1: real footage first (security cameras before anything), then photos
    seconds = slots["photo"] + d
    add2d("photo", common.photo(sheet, reel(clips[:1] + pictures("photo"), seconds), tint_out=False,
                                toll_at=(narration.PAD_IN + toll_t) if toll_shot == "photo" else None),
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

        def make_ai():
            files = dramatization(ai_clip, os.path.join(work, "ai"), caps.get("fall", ""),
                                  frames(slots["dramatization"] + d))
            return to_mp4(files, os.path.join(work, "ai.mp4"))
        jobs.append((make_ai, "dissolve", [("dramatization", 0)]))
    else:
        # the accurate 3D fall, its settle held while the narration runs
        add3d("fall", tm.real(20.0), tm.real(28.0), "dissolve",
              [("fall", 0), ("dramatization", tm.real(22.0) - tm.real(20.0))],
              fill_to=frames(slots["fall"] + slots["dramatization"] + d))
    archive("aftermath", "dissolve")
    add2d("timeline", common.timeline(sheet, timeline_reveal(sheet, words.get("timeline"))),
          slots["timeline"] + d, "dissolve", [("timeline", 0)])
    archive("investigation", "dissolve")
    add2d("compare", kit.compare, D["compare"], "dissolve", [("compare", 0)])
    archive("today_photos", "dissolve")
    add2d("today", common.today(sheet), slots["today"], "cut", [("today", 0)])

    made = run_parallel([make for make, _, _ in jobs])
    segs = [(mp4, n, trans, shots) for (mp4, n), (_, trans, shots) in zip(made, jobs)]
    joined = os.path.join(work, "reel.mp4")
    from kits.brand import watermark
    starts = xfade_join([(m, n, tr) for m, n, tr, _ in segs], joined,
                        overlay=watermark(os.path.join(work, "watermark.png")))
    total = (starts[-1] + segs[-1][1]) / FPS
    placed = [(starts[i] / FPS + off, voiced[clip]["wav"])
              for i, (_, _, _, shots) in enumerate(segs) for clip, off in shots if clip in voiced]
    wav = narration.track(placed, total, os.path.join(work, "voice.wav"))
    part_starts = part_times(segs, starts)
    mixed = os.path.join(work, "mix.wav")
    music_credits = score.mix(wav, score_plan(part_starts, hook_T, total), total, mixed)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-i", mixed, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac",
                    "-b:a", "192k", "-ar", "48000", out_mp4], check=True)
    chapters = [f"{int(t) // 60}:{int(t) % 60:02d} {PARTS[p]}" if i else f"0:00 {PARTS[p]}"
                for i, (p, t) in enumerate(part_starts)]
    print(f"{out_mp4}: {total / 60:.1f} min")
    return {"seconds": total, "chapters": chapters, "music_credits": music_credits}


_JOBS = []


def _run_job(i):
    return _JOBS[i]()


def run_parallel(makes, workers=None):
    """Runs make() functions on every core (forked workers inherit them, so
    closures need no pickling); results in order."""
    global _JOBS
    import multiprocessing
    n = min(len(makes), workers or os.cpu_count() or 1)
    if n <= 1:
        return [m() for m in makes]
    _JOBS = makes
    try:
        with multiprocessing.get_context("fork").Pool(n) as pool:
            return pool.map(_run_job, range(len(makes)), chunksize=1)
    finally:
        _JOBS = []


# --------------------------------------------------------------------------
# Moments that land on the narration
# --------------------------------------------------------------------------

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n):
    """13 -> 'thirteen', 145 -> 'one hundred forty five' (as narrators say)."""
    n = int(n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return _ONES[n // 100] + " hundred" + ("" if not rest else " " + number_words(rest))
    return str(n)


def toll_moment(sheet, words):
    """(shot, seconds into its take) where the narration first says the
    death toll, or (None, None). The counter rolls up at that word."""
    from sheet_writer import SHOTS
    nums = sheet.get("numbers") or []
    if not nums or not re.search(r"KILL|DEAD|DIED|DEATH|LIVES", nums[0].get("label", "").upper()):
        return None, None
    digits = re.sub(r"[^0-9]", "", str(nums[0]["value"]))
    if not digits:
        return None, None
    needles = [digits, f"{int(digits):,}", number_words(digits)]
    for _, _, clip, _ in SHOTS:
        t = narration.find_word(words.get(clip) or [], *needles)
        if t is not None:
            return clip, t
    return None, None


def with_toll(fn, sheet, at):
    """Wraps a clip so the death-toll counter rolls up at `at` seconds into
    it (narration.PAD_IN later: the take starts after the shot's breath)."""
    nums = sheet["numbers"][0]
    at = at + narration.PAD_IN

    def clip(t, T):
        img = fn(t, T)
        if -0.3 <= t - at <= 7.0:
            from PIL import Image
            from kits.blueprint import W, H, SS
            f = Frame()
            f.img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
            from PIL import ImageDraw
            f.d = ImageDraw.Draw(f.img, "RGBA")
            common.toll(f, nums["value"], nums["label"], t - at)
            layer = f.img.resize(img.size, Image.LANCZOS)
            img = img.convert("RGBA")
            img.alpha_composite(layer)
            img = img.convert("RGB")
        return img
    return clip


def timeline_reveal(sheet, words):
    """The second each timeline event appears: when the narrator says its
    date (its year, or month and year), in order; None if the dates cannot
    be found in the narration."""
    if not words:
        return None
    out, last = [], 0.0
    for e in sheet.get("timeline") or []:
        date = str(e.get("date", ""))
        years = re.findall(r"\b(1[89]\d\d|20\d\d)\b", date)
        t = None
        if years:
            later = [w for w in words if w["start"] >= last - 0.01]
            t = narration.find_word(later, f"{date.title()}", years[0])
        if t is None:
            return None
        last = max(last, t)
        out.append(narration.PAD_IN + last)
    return out


def hook_schedule(lines, takes, start=1.4, gap=0.85, tail=1.8, shortest=24.0):
    """[(start, end, text)] for the hook lines and the cold open's length:
    the lines one after another with a breath between, stretched apart if
    the open would run under `shortest` seconds."""
    durs = [t["seconds"] for t in takes[:len(lines)]]
    natural = start + sum(durs) + gap * (len(durs) - 1) + tail
    if natural < shortest and len(durs) > 1:
        gap += (shortest - natural) / (len(durs) - 1)
    out, t = [], start
    for text, dur in zip(lines, durs):
        out.append((t, t + dur, text))
        t += dur + gap
    return out, max(shortest, out[-1][1] + tail) if out else shortest


def part_times(segs, starts):
    """[(part, start seconds)] for the 7 parts, in order."""
    from sheet_writer import SHOTS
    part = {clip: p for p, _, clip, _ in SHOTS}
    out, seen = [], set()
    for i, (_, _, _, shots) in enumerate(segs):
        for clip, off in shots:
            p = part.get(clip)
            if p and p not in seen:
                seen.add(p)
                out.append((p, starts[i] / FPS + max(0.0, off)))
    return out


def score_plan(part_starts, hook_T, total):
    """The cold open's thriller track, then one quiet bed per part."""
    plan = []
    if hook_T:
        plan.append((0.0, hook_T + 1.0, score.COLD_OPEN, score.OPEN_LEVEL))
    for i, (p, t) in enumerate(part_starts):
        end = part_starts[i + 1][1] if i + 1 < len(part_starts) else total
        start = max(t, hook_T + 1.0) if i == 0 and hook_T else t
        if end > start:
            plan.append((start, end, score.PARTS[p], score.BED_LEVEL))
    return plan


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
