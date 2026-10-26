"""
A Short made for the phone (owner, 2026-10-22): its own script, voiced
fresh, and its own pictures, not cut from the long video. Four scenes, one
continuous shot each, nothing shown twice and nothing standing still:

    1. "fall"   the collapse, once, from the 3D model's tall fall camera
    2. "close"  the best 3D moment: down the rod to the connection, the nut
                heating, held while it pulls through (the tall close camera)
    3. "stack"  the best 2D moment: "what it needed" above "as built", both
                drawn from nothing at once, the change stamped on, the load
                doubling, then the built one falls while the other holds
    4. "photo"  the real photo, the toll counting from its first frame to
                the word that says it, then where the full story is

The 3D frames are rendered for the Short (kits/*_3d.py short_camera, the
short3d workflow), the 2D drawn by the kit (side()). The script:

    {"hook": "ONE ROD CHANGED.|114 PEOPLE DIED.",
     "toll": {"value": "114", "label": "PEOPLE KILLED"},
     "scenes": [
       {"show": "fall", "say": "..."},
       {"show": "close", "say": "...", "cue": "tore", "label": {"text": "ONE NUT", "from": "one", "to": "tore"}},
       {"show": "stack", "say": "...",
        "sides": {"needed": {"walls": ["start", 0, 1.0], "rods": ["rod", 0, 0.8], "verdict": ["end", 1.3, 0.4]},
                  "built": {"walls": ["start", 0, 1.0], "rods": ["split", 0, 0.8], "stamp": ["approved", 0, 0.35],
                            "stamp_text": "APPROVED BY PHONE", "fall": ["end", 0.3, 0.9]}},
        "sounds": [{"at": ["approved", 0], "sound": "lock"}, {"at": ["end", 0.3], "sound": "crash"}]},
       {"show": "photo", "photo": "photo.jpg", "say": "...", "toll": "fourteen"}]}

    python tools/story_short.py SHEET FRAMES3D SCRIPT OUT [--photo P]

Every scene is as long as its motion (owner, 2026-10-26: "if nothing is
happening for over 3 s, people just leave"; they stay for 3D objects
moving and 2D sheets built line by line). The words are written to fit:
  "lead"  (fall)  seconds before the break the scene starts: the roof, the
                  walkway, the span going within the first second
  "skip"  (close) [from, to] canonical seconds the camera stands parked,
                  cut out: the move runs straight into the pull-through
  "tail"  (any)   seconds after the scene's last word (else the defaults)
  "end": "loop"   (script) no card at the end: the last scene ends moving,
                  a small line points to the full story, and the Short
                  runs straight back into its first frame

FRAMES3D holds fall/ and close/ (frames and anchors_*.json). Writes
OUT/short.mp4 and OUT/short.json (length, script, music credits).
tools/stillness.py checks the result: no picture held still for 1.5 s.
"""

import argparse
import glob
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

from highlight_short import RED, WHITE, _brand, _font, _text, chunks     # noqa: E402

SW, SH, FPS, SR = 1080, 1920, 30, 48000
HOOK_H = 290
LEAD = 0.2                  # each scene's words start this far in
GAP = 0.25                  # breath after a scene's words
DISSOLVE = 0.3              # one scene into the next
END_HOLD = 2.6              # after the last word: the full story's card (owner, 2026-10-22: the old one, grey, on a hit)
END_LOOP = 0.7              # after the last word, when the Short loops: no card, a moment, then frame one
STACK_TAIL = 2.2            # after the stack's words: the fall and the verdict
PANEL_H = SW * 9 // 16      # a 2D side, whole, full width
STACK_Y = (300, 300 + PANEL_H + 92)          # the two sides; the words between them
CAP_Y = {"stack": 300 + PANEL_H + 46, "photo": 1360}
CAP_DEFAULT = 1250          # the words: clear of YouTube's title and buttons below
MUSIC = ("Volatile Reaction - Kevin MacLeod.mp3", "Man Down - Kevin MacLeod.mp3")
MUSIC_LEVEL = 0.3
CYAN, NAVY = (90, 200, 255), (8, 18, 34)


def voice(scenes, out_dir):
    """Each scene's words voiced; [(wav, seconds, words from the take's start)]."""
    import narration
    took = narration.record({"shots": [{"clip": f"s{i}", "narration": sc["say"]}
                                       for i, sc in enumerate(scenes)]}, out_dir)
    out = []
    for i, sc in enumerate(scenes):
        take = took[f"s{i}"]
        words = [(w["word"], w["start"], w.get("end", w["start"] + 0.3))
                 for w in narration.words_of(sc["say"], take["wav"])]
        out.append((take["wav"], take["seconds"], words))
    return out


def _word_at(words, needle, after=0.0):
    """When the first word matching needle (after a second) starts and ends."""
    key = re.sub(r"[^\w]", "", needle.lower())
    for w, a, b in words:
        if a >= after and re.sub(r"[^\w]", "", w.lower()).startswith(key):
            return a, b
    return None


def _ramp(t, a, length):
    return 0.0 if t <= a else 1.0 if t >= a + length else (t - a) / length


class Renders:
    """The Short's 3D frames: <dir>/<camera>/NNNN.(png|jpg), canonical second
    s at frame round(s * 30) + 1, and their anchors (screen 0..1, y down)."""

    def __init__(self, root):
        self.root, self.anchors, self.last = root, {}, None
        for p in glob.glob(os.path.join(root, "*", "anchors_*.json")):
            cam = os.path.basename(os.path.dirname(p))
            self.anchors.setdefault(cam, {}).update({int(k): v for k, v in json.load(open(p)).items()})

    def _file(self, cam, n):
        for d in range(0, 40):                         # the nearest rendered frame
            for k in (n - d, n + d):
                for ext in ("png", "jpg"):
                    p = os.path.join(self.root, cam, f"{k:04d}.{ext}")
                    if os.path.exists(p):
                        return p
        return None

    def frame(self, cam, sec):
        p = self._file(cam, int(round(sec * FPS)) + 1)
        if not p:
            return self.last or Image.new("RGB", (SW, SH))
        img = Image.open(p).convert("RGB")
        if img.size != (SW, SH):
            img = img.resize((SW, SH), Image.LANCZOS)
        self.last = img
        return img

    def anchor(self, cam, sec, name):
        row = self.anchors.get(cam, {}).get(int(round(sec * FPS)) + 1)
        return row.get(name) if row else None


def _moving(segs, sec):
    """Seconds of moving shot before canonical second sec (segs: the kept spans)."""
    u = 0.0
    for x0, x1 in segs:
        if sec <= x1:
            return u + max(0.0, sec - x0)
        u += x1 - x0
    return u


def _canonical(segs, u):
    """The canonical second u seconds into the moving shot."""
    for x0, x1 in segs:
        if u <= x1 - x0:
            return x0 + u
        u -= x1 - x0
    return segs[-1][1]


def _grid_canvas():
    out = Image.new("RGB", (SW, SH), NAVY)
    d = ImageDraw.Draw(out)
    for gx in range(0, SW, 54):
        d.line([(gx, 0), (gx, SH)], fill=(16, 30, 50))
    for gy in range(0, SH, 54):
        d.line([(0, gy), (SW, gy)], fill=(16, 30, 50))
    return out


def _cover(img, w, h, zoom=1.0, cx=0.5, cy=0.5):
    ch = min(img.height, img.width * h / w) / max(1.0, zoom)    # never wider than the picture
    cw = ch * w / h
    x = max(0.0, min(img.width - cw, cx * img.width - cw / 2))
    y = max(0.0, min(img.height - ch, cy * img.height - ch / 2))
    return img.resize((w, h), Image.LANCZOS, box=(x, y, x + cw, y + ch))


def _words(d, caption, y):
    words, now = caption
    size = 92
    line = " ".join(w for w, _, _ in words).upper()
    while _font("InterDisplay-Black.otf", size).getlength(line) > SW - 90 and size > 44:
        size -= 4
    fnt = _font("InterDisplay-Black.otf", size)
    x = (SW - fnt.getlength(line)) / 2
    lit = max((i for i, (_, a, _) in enumerate(words) if a <= now), default=None)
    for i, (w, a, b) in enumerate(words):
        d.text((x, y), w.upper(), font=fnt, fill=(255, 214, 64) if i == lit else WHITE, anchor="lm",
               stroke_width=8, stroke_fill=(0, 0, 0))
        x += fnt.getlength(w.upper() + " ")


def _overlay(img, hook, caption, cap_y, tags=(), toll=None, label=None):
    """The hook's band, the scene's tags, a label on a part, the words, the toll."""
    d = ImageDraw.Draw(img, "RGBA")
    if label:
        text, (x, y), a = label
        px, py = x * SW, y * SH
        tx, ty = max(60.0, px - 470), py - 230
        col = RED + (int(255 * a),)
        d.line([(tx + 200, ty + 34), (px - 14, py - 10)], fill=col, width=5)
        d.ellipse([px - 16, py - 16, px + 16, py + 16], outline=col, width=5)
        f = _font("InterDisplay-Black.otf", 54)
        d.rounded_rectangle([tx - 18, ty - 34, tx + f.getlength(text) + 18, ty + 34], 16,
                            fill=(4, 10, 20, int(200 * a)))
        d.text((tx, ty), text, font=f, fill=WHITE + (int(255 * a),), anchor="lm")
    for text, (x, y), col in tags:
        f = _font("Inter-Bold.otf", 30)
        w = f.getlength(text)
        d.rounded_rectangle([x, y - 26, x + w + 36, y + 26], 26, fill=(4, 10, 20, 190))
        d.text((x + 18, y), text, font=f, fill=col, anchor="lm")
    d.rectangle([0, 0, SW, HOOK_H], fill=(4, 10, 20, 255))
    d.rectangle([0, HOOK_H - 4, SW, HOOK_H], fill=RED + (255,))
    _brand(d)
    for i, line in enumerate([x.strip() for x in hook.split("|") if x.strip()][:2]):
        _text(d, line, SW / 2, 160 + i * 84, 76, WHITE if i == 0 else RED)
    if toll:
        value, what, count, card = toll
        fade = int(255 * (1 - min(1.0, card * 3)))             # the count gives way to the card
        if fade > 0:
            outline = 6 if card == 0 else 0
            _text(d, counted(value, count), SW / 2, 820, 300, RED + (fade,), stroke=outline)
            _text(d, what.upper(), SW / 2, 1020, 64, WHITE + (fade,), "InterDisplay-Bold.otf",
                  stroke=4 if outline else 0)
        if card > 0:
            # the full story's card, as the cut-down Shorts ended: the picture greys over, the words land
            k = min(1.0, card)
            shade = Image.new("RGBA", img.size, (4, 10, 20, int(200 * k)))
            img.paste(shade, (0, 0), shade)
            d = ImageDraw.Draw(img, "RGBA")
            a = int(255 * max(0.0, (k - 0.33) / 0.67))           # its words once the count has gone
            _text(d, "THE FULL STORY", SW / 2, 820, 96, (255, 255, 255, a))
            _text(d, "HOW IT FAILED, STEP BY STEP", SW / 2, 930, 52, RED + (a,), "InterDisplay-Bold.otf")
            _text(d, "full video on the channel", SW / 2, 1060, 44, (170, 190, 220, a), "Inter-Bold.otf")
            _brand(d)
    if caption:
        _words(d, caption, cap_y)
    return img


def counted(value, count):
    """The toll as shown while it counts up (0..1), fast then settling."""
    digits = re.sub(r"\D", "", value)
    if not digits:
        return value
    n = int(round(int(digits) * (1 - (1 - min(1.0, count)) ** 3)))
    return f"{n:,}" if "," in value else str(n)


def tick(k=0.0):
    """One number going up: a short bright click, higher as the count climbs (k 0..1)."""
    n = int(0.035 * SR)
    t = np.arange(n) / SR
    f = 900 + 900 * k
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.007)
    x += np.random.default_rng(int(k * 1000)).normal(0, 0.4, n) * np.exp(-t / 0.0015)
    x = (x / max(1e-6, np.abs(x).max())).astype(np.float32)
    return np.stack([x, x], axis=1)


def build(sheet, frames3d, script, out_dir, photo=None):
    import soundfile as sf
    import score
    from episode import kit_class
    os.makedirs(out_dir, exist_ok=True)
    scenes = script["scenes"]
    kit = kit_class(sheet["kit"]["variant"])(sheet)
    toll = script.get("toll") or (sheet.get("numbers") or [{}])[0]
    renders = Renders(frames3d)
    from kits import timemap                             # pure Python: no Blender needed here
    cams = timemap.SHORT[sheet["kit"]["variant"]]
    t_fall = timemap.T_FALL

    # the clock: each scene as long as its words and what follows them
    takes = voice(scenes, os.path.join(out_dir, "voice"))
    loop = script.get("end") == "loop"
    starts, t = [], 0.0
    for i, (sc, (_, secs, _)) in enumerate(zip(scenes, takes)):
        starts.append(t)
        tail = STACK_TAIL if sc["show"] == "stack" else \
            (END_LOOP if loop else END_HOLD) if i == len(scenes) - 1 else GAP
        t += LEAD + secs + sc.get("tail", tail)
    total = t
    n_total = int(round(total * FPS))
    words = [(w, s0 + LEAD + a, s0 + LEAD + b) for s0, (_, _, ws) in zip(starts, takes) for w, a, b in ws]
    track = np.zeros(int(total * SR) + 1, np.float32)
    for s0, (wav, _, _) in zip(starts, takes):
        v, vsr = sf.read(wav, dtype="float32")
        if vsr != SR:
            v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR * vsr, np.arange(len(v)), v).astype(np.float32)
        a = int((s0 + LEAD) * SR)
        track[a:a + len(v)] += v[: len(track) - a]
    vwav = os.path.join(out_dir, "voice.wav")
    sf.write(vwav, track, SR)

    def span(i):
        return starts[i], (starts[i + 1] if i + 1 < len(scenes) else total)

    def voice_end(i):
        return starts[i] + LEAD + takes[i][1]

    sfx = [(max(0.0, starts[i] - 0.2), score.whoosh(20 + i) * 0.28) for i in range(1, len(scenes))]
    pictures = []                    # per scene: the Short's second -> (picture, overlays)
    drawing = {}                     # per 2D scene: the spans in which something is being drawn
    for i, sc in enumerate(scenes):
        t0, t1 = span(i)
        if sc["show"] == "fall":
            lead = sc.get("lead", 0.9)                          # the break, under a second in
            a0 = t_fall - lead
            # words longer than the render slow the fall down: never a held
            # last frame in the seconds that decide whether a viewer stays
            k = min(1.0, (cams["fall"][1] - a0) / max(0.1, t1 - t0))
            sfx.append((t0 + lead / k - 0.05, score.boom(6) * 0.5))
            pictures.append(lambda t, a0=a0, t0=t0, k=k: (renders.frame("fall", a0 + (t - t0) * k), {}))
        elif sc["show"] == "close":
            a, b = cams["close"]
            # the camera's timeline without the stretch it stands parked ("skip"):
            # u, seconds of the shot that move, maps to the canonical second
            sk = sc.get("skip")
            segs = [(a, sk[0]), (sk[1], b)] if sk else [(a, b)]
            hit = _word_at(words, sc.get("cue", "tore"), t0)
            pull = _moving(segs, t_fall + 0.15)
            knots = [(t0, 0.0)]
            if hit:                                             # the pull-through on the word that says it
                knots.append((hit[0], pull))
                sfx.append((hit[0] - 0.05, score.crash() * 0.45))
                knots.append((t1, min(_moving(segs, b), pull + (t1 - hit[0]))))
            else:
                knots.append((t1, _moving(segs, b)))
            xs, us = zip(*knots)
            lab = sc.get("label")
            l_from = _word_at(words, lab["from"], t0) if lab else None
            l_to = _word_at(words, lab["to"], t0) if lab else None

            def close(t, xs=xs, us=us, segs=segs, lab=lab, l_from=l_from, l_to=l_to):
                sec = _canonical(segs, float(np.interp(t, xs, us)))
                extras = {}
                if lab and l_from:
                    a_ = _ramp(t, l_from[0], 0.3) * (1 - _ramp(t, l_to[0], 0.4) if l_to else 1)
                    pos = renders.anchor("close", sec, lab.get("at", "nut"))
                    if a_ > 0 and pos:
                        extras["label"] = (lab["text"], (pos[0], pos[1]), a_)
                return renders.frame("close", sec), extras
            pictures.append(close)
        elif sc["show"] == "stack":
            v_end = voice_end(i)

            def when(anchor, words=words, t0=t0, v_end=v_end):
                """A moment named in the script: "start", "end" (the last word), or a word."""
                if anchor == "start":
                    return t0
                if anchor == "end":
                    return v_end
                hit = _word_at(words, anchor, t0)
                return hit[0] if hit else v_end

            # each side's parts: [anchor, offset, length] builds 0 -> 1 from that moment;
            # {"count": "89,680", "at": [...]} counts up to the number (a tick per step);
            # anything else is passed to the kit as it is
            plans = {}
            for name in ("needed", "built"):
                plan = {}
                for key, v in (sc.get("sides", {}).get(name) or {}).items():
                    if isinstance(v, list):
                        plan[key] = ("ramp", when(v[0]) + v[1], v[2])
                    elif isinstance(v, dict) and "count" in v:
                        a_, off, ln = v["at"]
                        start = when(a_) + off
                        plan[key] = ("count", start, ln, v["count"])
                        prev = ""
                        for n_ in range(int(start * FPS), int((start + ln) * FPS) + 2):
                            now_ = counted(v["count"], _ramp(n_ / FPS, start, ln))
                            if now_ != prev and now_ != "0":
                                sfx.append((n_ / FPS, tick(_ramp(n_ / FPS, start, ln)) * 0.12))
                            prev = now_
                    else:
                        plan[key] = ("value", v)
                plans[name] = plan
            drawing[i] = [(p[1], p[1] + p[2]) for plan in plans.values() for p in plan.values()
                          if p[0] in ("ramp", "count")]
            for moment in sc.get("sounds", []):           # e.g. {"at": ["approved", 0], "sound": "lock"}
                kind = {"lock": score.lock, "crash": score.crash, "boom": score.boom, "ping": score.ping,
                        "groan": score.groan}[moment["sound"]]
                sfx.append((when(moment["at"][0]) + moment["at"][1], kind() * moment.get("level", 0.4)))
            dvb = sheet.get("design_vs_built", {})
            tags = [(dvb.get("designed", {}).get("title", "AS DESIGNED"), (36, STACK_Y[0] + 44), CYAN),
                    (dvb.get("built", {}).get("title", "AS BUILT"), (36, STACK_Y[1] + 44), RED)]

            def args(plan, t):
                out = {}
                for key, p in plan.items():
                    if p[0] == "ramp":
                        out[key] = _ramp(t, p[1], p[2])
                    elif p[0] == "count":
                        out[key] = counted(p[3], _ramp(t, p[1], p[2])) if t >= p[1] else ""
                    else:
                        out[key] = p[1]
                return out

            def stack(t, t0=t0, plans=plans, tags=tags):
                top = kit.side(False, **args(plans["needed"], t))
                bot = kit.side(True, **args(plans["built"], t))
                img = _grid_canvas()
                # in on the joint, the counter and the verdict still in frame, and pushing on
                # (the counter's right edge, 0.93 across, stays in: 0.55 + 0.5 / z >= 0.93)
                z = 1.15 + 0.13 * _ramp(t, t0, 10.0)
                img.paste(_cover(top, SW, PANEL_H, z, 0.55, 0.42), (0, STACK_Y[0]))
                img.paste(_cover(bot, SW, PANEL_H, z, 0.55, 0.42), (0, STACK_Y[1]))
                d = ImageDraw.Draw(img)
                for y in STACK_Y:
                    d.line([(0, y), (SW, y)], fill=(40, 70, 110), width=2)
                    d.line([(0, y + PANEL_H), (SW, y + PANEL_H)], fill=(40, 70, 110), width=2)
                return img, {"tags": tags}
            pictures.append(stack)
        elif sc["show"] == "photo":
            pic = Image.open(photo or sc["photo"]).convert("RGB")
            hit = _word_at(words, sc.get("toll", ""), t0) if sc.get("toll") else None
            count_to = hit[1] if hit else t0 + 2.5
            cta_at = voice_end(i) + 0.15
            # a tick for each number the count goes up by (one per frame at most), a stop when it lands,
            # and the hit under the full story's card
            prev = "0"
            for n_ in range(int(t0 * FPS), int(count_to * FPS) + 2):
                c = _ramp(n_ / FPS, t0, max(0.3, count_to - t0))
                now_ = counted(str(toll.get("value", "")), c)
                if now_ != prev:
                    sfx.append((n_ / FPS, tick(c) * 0.16))
                    prev = now_
            sfx.append((count_to, score.lock() * 0.3))
            if not loop:
                sfx.append((cta_at, score.boom() * 0.6))

            def photo_(t, t0=t0, t1=t1, pic=pic, count_to=count_to, cta_at=cta_at):
                k = (t - t0) / max(0.1, t1 - t0)
                img = Image.new("RGB", (SW, SH), (4, 10, 20))
                # looping: once the count lands, the camera pushes in hard until the cut back to frame one
                z = 1.0 + 0.1 * k + (0.35 * _ramp(t, count_to, max(0.5, t1 - count_to)) ** 1.6 if loop else 0.0)
                shot = _cover(pic, SW, SH - HOOK_H, z)
                shade = Image.new("RGBA", shot.size, (4, 10, 20, 80))
                shot.paste(shade, (0, 0), shade)
                img.paste(shot, (0, HOOK_H))
                count = _ramp(t, t0, max(0.3, count_to - t0))         # counting from the first frame
                return img, {"tags": [("PHOTO", (36, HOOK_H + 60), (170, 206, 255))],
                             "toll": (str(toll.get("value", "")), toll.get("label", ""), count,
                                      0.0 if loop else _ramp(t, cta_at, 0.35)),
                             "cta": _ramp(t, cta_at - 0.6, 0.3) if loop else 0.0}
            pictures.append(photo_)

    # the sound: the voice over the episode's own score (ducked), the sounds on their moments
    people = next((starts[i] for i, sc in enumerate(scenes) if sc["show"] == "photo"), total)
    mixed = os.path.join(out_dir, "mix.wav")
    credits = score.mix(vwav, [(0.0, people, MUSIC[0], MUSIC_LEVEL, 0.05),
                               (people, total, MUSIC[1], MUSIC_LEVEL, 0.6)], total, mixed)
    score.add_sfx(mixed, sfx, mixed)
    even = score.even_loudness(mixed, os.path.join(out_dir, "short_even.wav"), target=-14.0)

    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-i", even,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest",
                            os.path.join(out_dir, "short.mp4")], stdin=subprocess.PIPE)
    groups = chunks(words)
    prev_last = None
    import stillness
    # the picture's own motion, the spoken words left out: a 2D scene by what is
    # being drawn (one thin line growing is motion a phone shows but few pixels
    # measure); 3D and photos against the frame half a second before
    changes, recent = [], []
    for i, sc in enumerate(scenes):
        t0, t1 = span(i)
        f0, f1 = int(round(t0 * FPS)), (int(round(t1 * FPS)) if i + 1 < len(scenes) else n_total)
        cap_y = CAP_Y.get(sc["show"], CAP_DEFAULT)
        hook = sc.get("hook") or script.get("hook", "")
        last = prev_last
        for n in range(f0, f1):
            t = n / FPS
            base, extras = pictures[i](t)
            toll_on = extras.get("toll") and extras["toll"][3] > 0
            g = next((g for g in groups if g[0][1] - 0.05 <= t < g[-1][2] + 0.15), None)
            img = _overlay(base.copy(), hook, (g, t) if g and not toll_on else None, cap_y,
                           extras.get("tags", ()), extras.get("toll"), extras.get("label"))
            if extras.get("cta"):                                # a looping Short's pointer to the full story
                d = ImageDraw.Draw(img, "RGBA")
                _text(d, "FULL STORY ON THE CHANNEL", SW / 2, 1560, 44,
                      (200, 215, 235, int(255 * extras["cta"])), "Inter-Bold.otf")
            clean = img if not g or toll_on else _overlay(
                base.copy(), hook, None, cap_y, extras.get("tags", ()), extras.get("toll"), extras.get("label"))
            k = (n - f0) / (DISSOLVE * FPS)
            if prev_last is not None and k < 1:                  # one scene dissolves into the next
                img = Image.blend(prev_last, img, k)
                clean = Image.blend(prev_last, clean, k)
            if i in drawing:
                changes.append(100.0 if any(a_ <= t <= b_ for a_, b_ in drawing[i]) else 0.0)
            else:
                small = np.asarray(clean.convert("L").resize((stillness.W, stillness.H)))
                back = int(stillness.STEP * FPS)
                changes.append(100.0 if n - f0 < back else stillness.changed_pct(recent[-back], small))
                recent = (recent + [small])[-back:]
            enc.stdin.write(img.tobytes())
            last = img
            if n % 150 == 0:
                print(f"  {n}/{n_total} frames", flush=True)
        prev_last = last
    enc.stdin.close()
    enc.wait()
    series = stillness.per_step(changes, FPS)
    still = stillness.still_runs(series)
    for s0, s1 in still:
        print(f"  STILL {s0:.1f}-{s1:.1f} s: nothing moves for {s1 - s0:.1f} s")
    info = {"seconds": round(total, 2), "top": script.get("hook", ""), "script": script,
            "music_credits": credits, "parts": [],
            "stillness": {"step": stillness.STEP, "motion": [round(v, 2) for v in series], "still": still},
            "scenes": [{"show": sc["show"], "from": round(span(i)[0], 2), "to": round(span(i)[1], 2)}
                       for i, sc in enumerate(scenes)]}
    json.dump(info, open(os.path.join(out_dir, "short.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{out_dir}/short.mp4: {total:.1f} s")
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("frames3d")
    ap.add_argument("script")
    ap.add_argument("out")
    ap.add_argument("--photo", default=None, help="the real photo (else the script's)")
    a = ap.parse_args()
    build(json.load(open(a.sheet)), a.frames3d, json.load(open(a.script)), a.out, a.photo)
