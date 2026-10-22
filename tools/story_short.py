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
       {"show": "stack", "say": "...", "stamp": "APPROVED BY PHONE",
        "cues": {"rods_needed": "rod", "rods_built": "split", "stamp": "approved",
                 "people": "same", "double": "double"}},
       {"show": "photo", "photo": "photo.jpg", "say": "...", "toll": "fourteen"}]}

    python tools/story_short.py SHEET FRAMES3D SCRIPT OUT [--photo P]

FRAMES3D holds fall/ and close/ (frames and anchors_*.json). Writes
OUT/short.mp4 and OUT/short.json (length, script, music credits).
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
END_HOLD = 1.8              # after the last word: the toll and where the full story is
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


def _grid_canvas():
    out = Image.new("RGB", (SW, SH), NAVY)
    d = ImageDraw.Draw(out)
    for gx in range(0, SW, 54):
        d.line([(gx, 0), (gx, SH)], fill=(16, 30, 50))
    for gy in range(0, SH, 54):
        d.line([(0, gy), (SW, gy)], fill=(16, 30, 50))
    return out


def _cover(img, w, h, zoom=1.0, cx=0.5, cy=0.5):
    ch = min(img.height, img.width * h / w) / zoom
    cw = ch * w / h
    x = min(img.width - cw, max(0.0, cx * img.width - cw / 2))
    y = min(img.height - ch, max(0.0, cy * img.height - ch / 2))
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
        value, what, count, cta = toll
        digits = re.sub(r"\D", "", value)
        shown = str(int(round(int(digits) * (1 - (1 - min(1.0, count)) ** 3)))) if digits else value
        _text(d, shown, SW / 2, 820, 300, RED, stroke=6)
        _text(d, what.upper(), SW / 2, 1020, 64, WHITE, "InterDisplay-Bold.otf", stroke=4)
        if cta > 0:
            _text(d, "FULL STORY ON THE CHANNEL", SW / 2, 1200, 58, (255, 214, 64, int(255 * min(1, cta))),
                  stroke=4)
    if caption:
        _words(d, caption, cap_y)
    return img


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
    starts, t = [], 0.0
    for i, (sc, (_, secs, _)) in enumerate(zip(scenes, takes)):
        starts.append(t)
        tail = STACK_TAIL if sc["show"] == "stack" else END_HOLD if i == len(scenes) - 1 else GAP
        t += LEAD + secs + tail
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
    for i, sc in enumerate(scenes):
        t0, t1 = span(i)
        if sc["show"] == "fall":
            a0 = t_fall - 0.9                                   # the break, just under a second in
            sfx.append((t0 + 0.85, score.boom(6) * 0.5))
            pictures.append(lambda t, a0=a0, t0=t0: (renders.frame("fall", a0 + (t - t0)), {}))
        elif sc["show"] == "close":
            a, b = cams["close"]
            hit = _word_at(words, sc.get("cue", "tore"), t0)
            knots = [(t0, a)]
            if hit:                                             # the pull-through on the word that says it
                knots.append((hit[0], t_fall + 0.15))
                sfx.append((hit[0] - 0.05, score.crash() * 0.45))
                knots.append((t1, min(b, t_fall + 0.15 + (t1 - hit[0]))))
            else:
                knots.append((t1, b))
            xs, ys = zip(*knots)
            lab = sc.get("label")
            l_from = _word_at(words, lab["from"], t0) if lab else None
            l_to = _word_at(words, lab["to"], t0) if lab else None

            def close(t, xs=xs, ys=ys, lab=lab, l_from=l_from, l_to=l_to):
                sec = float(np.interp(t, xs, ys))
                extras = {}
                if lab and l_from:
                    a_ = _ramp(t, l_from[0], 0.3) * (1 - _ramp(t, l_to[0], 0.4) if l_to else 1)
                    pos = renders.anchor("close", sec, lab.get("at", "nut"))
                    if a_ > 0 and pos:
                        extras["label"] = (lab["text"], (pos[0], pos[1]), a_)
                return renders.frame("close", sec), extras
            pictures.append(close)
        elif sc["show"] == "stack":
            at = {k: (v[0] if v else None) for k, v in
                  ((k, _word_at(words, w, t0)) for k, w in (sc.get("cues") or {}).items())}
            v_end = voice_end(i)
            if at.get("stamp"):
                sfx.append((at["stamp"], score.lock() * 0.35))
            sfx.append((v_end + 0.3, score.crash() * 0.45))
            dvb = sheet.get("design_vs_built", {})
            tags = [(dvb.get("designed", {}).get("title", "AS DESIGNED"), (36, STACK_Y[0] + 44), CYAN),
                    (dvb.get("built", {}).get("title", "AS BUILT"), (36, STACK_Y[1] + 44), RED)]

            def stack(t, t0=t0, at=at, v_end=v_end, sc=sc, tags=tags):
                def cue(k, length, default):
                    return _ramp(t, at[k] if at.get(k) is not None else default, length)
                common = dict(walls=_ramp(t, t0, 1.0), walks=_ramp(t, t0 + 0.5, 1.0),
                              people=cue("people", 0.6, v_end), loads=cue("people", 0.4, v_end),
                              verdict=_ramp(t, v_end + 1.3, 0.4))
                top = kit.side(False, rods=cue("rods_needed", 0.8, t0 + 1.5), **common)
                bot = kit.side(True, rods=cue("rods_built", 0.8, t0 + 3.0), double=cue("double", 0.5, v_end),
                               fall=_ramp(t, v_end + 0.3, 0.9), stamp=cue("stamp", 0.35, v_end),
                               stamp_text=sc.get("stamp", ""), **common)
                img = _grid_canvas()
                z = 1.0 + 0.06 * _ramp(t, t0, 12.0)                  # a slow push in: nothing stands still
                img.paste(_cover(top, SW, PANEL_H, z), (0, STACK_Y[0]))
                img.paste(_cover(bot, SW, PANEL_H, z), (0, STACK_Y[1]))
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
            sfx.append((count_to - 0.05, score.boom(7) * 0.45))

            def photo_(t, t0=t0, t1=t1, pic=pic, count_to=count_to, cta_at=cta_at):
                k = (t - t0) / max(0.1, t1 - t0)
                img = Image.new("RGB", (SW, SH), (4, 10, 20))
                shot = _cover(pic, SW, SH - HOOK_H, 1.0 + 0.1 * k)
                shade = Image.new("RGBA", shot.size, (4, 10, 20, 80))
                shot.paste(shade, (0, 0), shade)
                img.paste(shot, (0, HOOK_H))
                count = _ramp(t, t0, max(0.3, count_to - t0))         # counting from the first frame
                return img, {"tags": [("PHOTO", (36, HOOK_H + 60), (170, 206, 255))],
                             "toll": (str(toll.get("value", "")), toll.get("label", ""), count,
                                      _ramp(t, cta_at, 0.3))}
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
            k = (n - f0) / (DISSOLVE * FPS)
            if prev_last is not None and k < 1:                  # one scene dissolves into the next
                img = Image.blend(prev_last, img, k)
            enc.stdin.write(img.tobytes())
            last = img
            if n % 150 == 0:
                print(f"  {n}/{n_total} frames", flush=True)
        prev_last = last
    enc.stdin.close()
    enc.wait()
    info = {"seconds": round(total, 2), "top": script.get("hook", ""), "script": script,
            "music_credits": credits, "parts": []}
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
