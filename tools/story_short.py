"""
A Short from its own script (owner, 2026-10-22): not cut from the long
video's narration, written for the Short and voiced fresh, each line telling
something new over a picture that shows it. Shorts are where the channel
gets found, so they get their own story:

    1. the collapse, once, briefly: both views at the same time
    2. what was built: the 3D model alone
    3. why it failed: the 2D drawings alone
    4. the people: the real photos, the toll counting up, where the full
       story is (YouTube then replays the Short into its first frame)

The pictures come from the finished episode (its 3D frames and photos) and
from the kit, drawn fresh. The script is a JSON file of lines:

    {"hook": "ONE ROD CHANGED.|114 PEOPLE DIED.",
     "lines": [
       {"say": "In 1981, ...", "show": "collapse"},
       {"say": "Each walkway ...", "show": "3d", "shot": "load_path"},
       {"say": "The original ...", "show": "2d", "clip": "compare", "from": "show", "to": "loads",
        "hook": "THE CHANGE|THAT DOUBLED THE LOAD"},
       {"say": "The fabricator ...", "show": "2d", "clip": "compare", "hold": "loads",
        "zoom": [1.0, 1.7], "focus": [0.75, 0.42]},
       {"say": "It held ...", "show": "2d", "clip": "physics", "from": "panel", "to": "slip",
        "cue": {"thirty": "panel", "tore": "slip"}, "hit": "tore"},
       {"say": "Sixteen hundred ...", "show": "photos", "toll": "fourteen"}]}

"from"/"to" are the kit clip's beats (kits/*.py Beats), played across the
line; "cue" pins a beat to the word that names it; "hold" keeps the frame
just before a beat; "zoom" and "focus" move the camera across the line.

    python tools/story_short.py PREP EPISODE_MP4 SCRIPT OUT

Writes OUT/short.mp4 and OUT/short.json (length, script, music credits).
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

import highlight_short as hs                                    # noqa: E402
from highlight_short import (EH, EP_ROWS, FPS, PH, PW, SH, SOLO_H, SR, SW, WHITE,  # noqa: E402
                             Episode, _beats_drop, _fit, _kit_focus, _panel, _uncaption, chunks, compose,
                             motion)

LEAD = 0.2                  # the first words start this far in
GAP = 0.22                  # breath between lines
END_HOLD = 1.9              # after the last word: the toll and where the full story is
WIDE_H = SW * 9 // 16      # a 2D drawing alone: its own 16:9, whole
WIDE_Y = 200                # down from the hook, so the words sit just under it
MUSIC = ("Volatile Reaction - Kevin MacLeod.mp3", "Man Down - Kevin MacLeod.mp3")
MUSIC_LEVEL = 0.3


def _wide(img, zoom=1.0, cx=0.5, cy=0.5):
    """A 2D drawing on the tall picture: its whole width at zoom 1 (labels
    and both sides of a comparison), closer on its focus as zoom grows;
    set a little down, the words under it."""
    cw, ch = img.width / zoom, img.height / zoom
    x = min(img.width - cw, max(0.0, cx * img.width - cw / 2))
    y = min(img.height - ch, max(0.0, cy * img.height - ch / 2))
    ground = img.getpixel((4, 4))
    out = Image.new("RGB", (SW, SOLO_H), ground)
    d = ImageDraw.Draw(out)                              # the blueprint's grid, on past the drawing
    line = tuple(min(255, c + 9) for c in ground)
    for gx in range(0, SW, 54):
        d.line([(gx, 0), (gx, SOLO_H)], fill=line)
    for gy in range(0, SOLO_H, 54):
        d.line([(0, gy), (SW, gy)], fill=line)
    out.paste(img.resize((SW, WIDE_H), Image.LANCZOS, box=(x, y, x + cw, y + ch)), (0, WIDE_Y))
    return out


def voice(lines, out_dir):
    """Each line voiced; returns [(start, wav, seconds, words)] on the Short's clock."""
    import narration
    took = narration.record({"shots": [{"clip": f"l{i}", "narration": ln["say"]} for i, ln in enumerate(lines)]},
                            out_dir)
    placed, t = [], LEAD
    for i, ln in enumerate(lines):
        take = took[f"l{i}"]
        words = [(w["word"], t + w["start"], t + w.get("end", w["start"] + 0.3))
                 for w in narration.words_of(ln["say"], take["wav"])]
        placed.append((t, take["wav"], take["seconds"], words))
        t += take["seconds"] + GAP
    return placed


def _word_at(words, needle, after=0.0):
    """When the first word matching needle (after a second) starts and ends."""
    key = re.sub(r"[^\w]", "", needle.lower())
    for w, a, b in words:
        if a >= after and re.sub(r"[^\w]", "", w.lower()).startswith(key):
            return a, b
    return None


def _kit_time(beats, ln, t0, t1, words):
    """The kit clip's second for each moment of a line [t0, t1): from its
    "from" beat to its "to" beat, with "cue" beats pinned to their words."""
    a = beats.start(ln["from"]) if ln.get("from") else 0.0
    b = beats.end(ln["to"]) + 0.4 if ln.get("to") else beats.total
    knots = [(t0, a)]
    for word, beat in (ln.get("cue") or {}).items():
        hit = _word_at(words, word, t0)
        if hit and beat in beats.at:
            knots.append((hit[0], beats.start(beat)))
    knots.append((t1, min(beats.total - 1 / FPS, b)))
    knots = sorted(knots)
    xs, ys = [k[0] for k in knots], list(np.maximum.accumulate([k[1] for k in knots]))
    return lambda t: float(np.interp(t, xs, ys))


def build(prep, episode_mp4, script, out_dir, starts=None, sheet=None):
    import soundfile as sf
    import score
    from episode import kit_class
    from kits import timemap
    os.makedirs(out_dir, exist_ok=True)
    sheet = sheet or json.load(open(os.path.join(prep, "timed_sheet.json")))
    lines = script["lines"]
    order = [s["clip"] for s in sheet["shots"]]
    if starts is None:
        need = ["fall", "aftermath"] + [ln["shot"] for ln in lines if ln.get("shot")]
        starts = hs.shot_starts(prep, episode_mp4, need)
    kit = kit_class(sheet["kit"]["variant"])(sheet)
    kit.captions = {}                                   # the Short has its own words on screen
    kit.sheet = {**kit.sheet, "numbers": []}             # and its own toll
    toll = script.get("toll") or (sheet.get("numbers") or [{}])[0]

    # the voice, line by line, and the clock it sets
    placed = voice(lines, os.path.join(out_dir, "voice"))
    spans = [(p[0], (placed[i + 1][0] if i + 1 < len(placed) else p[0] + p[2] + END_HOLD))
             for i, p in enumerate(placed)]
    spans[0] = (0.0, spans[0][1])
    total = spans[-1][1]
    n_total = int(round(total * FPS))
    words = [w for p in placed for w in p[3]]
    track = np.zeros(int(total * SR) + 1, np.float32)
    for t, wav, _, _ in placed:
        v, vsr = sf.read(wav, dtype="float32")
        if vsr != SR:
            v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR * vsr, np.arange(len(v)), v).astype(np.float32)
        a = int(t * SR)
        track[a:a + len(v)] += v[: len(track) - a]
    vwav = os.path.join(out_dir, "voice.wav")
    sf.write(vwav, track, SR)

    # the picture plan, line by line
    tm = timemap.of(sheet)
    fs = starts.get("fall", 0.0)
    drop = fs + tm.real(22.0) - tm.real(20.0)
    _, _, path = motion(episode_mp4, drop - 0.8, drop + 4.0, track=True)
    follow = lambda t: path[min(len(path) - 1, max(0, int(round((t - drop + 0.8) * FPS))))]
    fb = kit.FALL
    kd = fb.start(_beats_drop(fb))
    kx = _kit_focus(kit, "fall", kd - 0.3, kd + 1.5)[0]
    plan = []                     # per frame: (layout, top, bottom, tag, line index)
    sfx = []                      # (second, sound)
    for i, (ln, (t0, t1)) in enumerate(zip(lines, spans)):
        f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
        n = f1 - f0
        show = ln["show"]
        if show == "collapse":
            for k in range(n):
                t = drop - 0.8 + k / FPS
                plan.append(("split", ("ep", t, 1.3, follow(t)),
                             ("kit", "fall", min(fb.total - 1 / FPS, kd - 0.8 + k / FPS), 1.5, (kx, 0.72)),
                             "3D MODEL", i))
            sfx.append((t0 + 0.75, score.boom(6) * 0.5))
        elif show == "3d":
            shot = ln["shot"]
            nxt = order[order.index(shot) + 1]
            a, e = starts[shot] + hs.DISSOLVE, starts[nxt]
            times, diff, focus = motion(episode_mp4, a, e)
            still = max(0.25, 0.03 * (diff.max() if len(diff) else 0))
            moving = [t for t, d in zip(times, diff) if d > still] or list(times)
            shown = _fit(moving, n, keep=ln.get("keep", "tail"))
            focus = tuple(min(0.7, max(0.3, v)) for v in focus)
            for k in range(n):
                z = 1.0 + 0.12 * max(0, k - len(shown)) / max(1, n)
                plan.append(("solo", ("ep", shown[min(k, len(shown) - 1)], z, focus), None, "3D MODEL", i))
        elif show == "2d":
            clip = ln["clip"]
            beats = getattr(kit, kit.CLIPS[clip])
            if ln.get("hold"):
                kt = lambda t, h=max(0.0, beats.start(ln["hold"]) - 0.05): h
            else:
                kt = _kit_time(beats, ln, t0, t1, words)
            z = ln.get("zoom", 1.0)
            z0, z1 = (z, z) if not isinstance(z, list) else z
            fx, fy = ln.get("focus", [0.5, 0.5])
            for k in range(n):
                u = k / max(1, n - 1)
                zz = z0 + (z1 - z0) * (1 - (1 - u) ** 2)
                plan.append(("wide", ("kit", clip, kt(t0 + k / FPS), zz, (fx, fy)), None, "2D DRAWING", i))
            if ln.get("hit"):
                hit = _word_at(words, ln["hit"], t0)
                if hit:
                    sfx.append((hit[0] - 0.05, score.crash() * 0.4))
        elif show == "photos":
            nxt = order[order.index("aftermath") + 1]
            a, e = starts["aftermath"] + hs.DISSOLVE, starts[nxt]
            frames = [a + k / FPS for k in range(int((e - a) * FPS))]
            shown = _fit(frames, n, speed_max=1.6, keep="head")
            for k in range(n):
                t = shown[min(k, len(shown) - 1)]
                plan.append(("end", ("ep", t, 1.05 + 0.1 * k / max(1, n), (0.5, 0.45)), None, "PHOTO", i))
            sfx.append((t0 - 0.3, score.riser(1.2, 7) * 0.12))
        if i and show != lines[i - 1]["show"]:
            sfx.append((max(0.0, t0 - 0.2), score.whoosh(20 + i) * 0.3))
    plan = plan[:n_total] + [plan[-1]] * max(0, n_total - len(plan))

    # the toll counts up to the word that says it; the full story after the last word
    toll_line = next((i for i, ln in enumerate(lines) if ln.get("toll")), None)
    toll_from = toll_to = cta_at = None
    if toll_line is not None and toll.get("value"):
        hit = _word_at(words, lines[toll_line]["toll"], spans[toll_line][0])
        toll_to = hit[1] if hit else spans[toll_line][0] + 1.5
        toll_from = toll_to - 1.0
        cta_at = placed[-1][0] + placed[-1][2] + 0.15
        sfx.append((toll_to - 0.05, score.boom(7) * 0.45))

    # the sound: the voice over the score (ducked), the sounds on their moments
    people = next((spans[i][0] for i, ln in enumerate(lines) if ln["show"] == "photos"), total)
    mixed = os.path.join(out_dir, "mix.wav")
    credits = score.mix(vwav, [(0.0, people, MUSIC[0], MUSIC_LEVEL, 0.05),
                               (people, total, MUSIC[1], MUSIC_LEVEL, 0.6)], total, mixed)
    score.add_sfx(mixed, sfx, mixed)
    even = score.even_loudness(mixed, os.path.join(out_dir, "short_even.wav"), target=-14.0)

    # the picture
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-i", even,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest",
                            os.path.join(out_dir, "short.mp4")], stdin=subprocess.PIPE)
    ep = Episode(episode_mp4)
    cache = {}

    def kit_frame(clip, t):
        key = (clip, round(t * FPS))
        if key not in cache:
            cache.clear() if len(cache) > 8 else None
            fn = getattr(kit, clip)
            cache[key] = fn(t, None, lead=False) if clip == "physics" else fn(t)
        return cache[key]

    def picture(src, size, rows=EP_ROWS):
        if src[0] == "ep":
            _, t, z, (cx, cy) = src
            return _panel(_uncaption(ep.at(t)), z, cx, cy, rows, size=size)
        _, clip, t, z, (fx, fy) = src
        if size == "wide":
            return _wide(kit_frame(clip, t), z, fx, fy)
        return _panel(kit_frame(clip, t), z, fx, fy, pad=160, size=size)

    groups = chunks(words)
    hook = script.get("hook", "")
    prev_view, flash_from = None, -99
    for n, (layout, top, bot, tag, li) in enumerate(plan):
        now = n / FPS
        hook = next((ln["hook"] for ln in reversed(lines[:li + 1]) if ln.get("hook")), script.get("hook", ""))
        g = next((g for g in groups if g[0][1] - 0.05 <= now < g[-1][2] + 0.15), None)
        cap = (g, now) if g else None
        tol = None
        if toll_from is not None and now >= toll_from:
            count = min(1.0, (now - toll_from) / (toll_to - toll_from))
            cta = min(1.0, (now - cta_at) / 0.3) if now >= cta_at else 0.0
            tol = (str(toll["value"]), toll.get("label", ""), count, cta)
            cap = None
        if layout == "split":
            img = compose("split", picture(top, (PW, PH)), picture(bot, (PW, PH)), hook, cap, tag=tag)
        elif layout == "wide":
            img = compose("solo", picture(top, "wide"), None, hook, cap, tag=tag)
        else:
            rows = (EP_ROWS[0], EH - 92) if layout == "end" else EP_ROWS
            img = compose("end" if layout == "end" else "solo", picture(top, (SW, SOLO_H), rows), None,
                          hook, cap, tag=tag, toll=tol)
        view = (layout, top[0], top[1] if top[0] == "kit" else "", li if layout == "solo" else -1)
        if prev_view is not None and view[:3] != prev_view[:3]:
            flash_from = n
        prev_view = view
        if n - flash_from < 4:
            img = Image.blend(img, Image.new("RGB", img.size, WHITE), 0.45 * (1 - (n - flash_from) / 4))
        enc.stdin.write(img.tobytes())
        if n % 150 == 0:
            print(f"  {n}/{n_total} frames", flush=True)
    enc.stdin.close()
    enc.wait()
    info = {"seconds": round(total, 2), "top": script.get("hook", ""), "script": script,
            "music_credits": credits, "parts": []}
    json.dump(info, open(os.path.join(out_dir, "short.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{out_dir}/short.mp4: {total:.1f} s")
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("prep")
    ap.add_argument("episode")
    ap.add_argument("script")
    ap.add_argument("out")
    a = ap.parse_args()
    build(a.prep, a.episode, json.load(open(a.script)), a.out)
