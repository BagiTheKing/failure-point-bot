"""
The highlight Short of a long episode (owner, 2026-10-17: one Short per long
video, 48 hours after it), cut from the finished episode itself: the same
voice and music, no new 3D render.

    python tools/highlight_short.py PREP EPISODE_MP4 OUT \
        --spans fall-dramatization,connection \
        --top "ONE ROD CHANGED.|114 PEOPLE DIED.||THE CHANGE|THAT DOUBLED THE LOAD"

A span runs from the start of its first shot's voice to the end of its last
one's ("fall-dramatization" is the two shots back to back). Where each take
sits in the episode is found in the episode's own sound (the take is
correlated against it), so nothing about the cut needs to be stored.

The picture (owner, 2026-10-22, after the I-35W Short lost 43% to the swipe
in its first seconds): the full 9:16 screen, the failure from the first
frame. Both collapses at once, the 3D over the 2D; then one view at a time,
a tall 4:5 picture: the 3D again at half speed, the 2D falling on the words
that say it; for the cause the 3D says the first sentences and the 2D the
rest (its end, where it fails). Frames where nothing moves are dropped and
camera moves run faster. The hook changes with each span (stages split by
||) and the words sit on one line as they are said. Last, the real photo
with the toll counting up and where the full story is, kept short: YouTube
replays a Short straight into its first frame.

Writes OUT/short.mp4 and OUT/short.json (length, spans, music parts).
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

SW, SH, FPS = 1080, 1920, 30
HOOK_H = 290                        # the hook's band at the top
SEAM = (SH + HOOK_H) // 2           # the 3D panel above it, the 2D panel below
PW, PH = SW, SEAM - HOOK_H
EW, EH = 1280, 720                  # the episode's frame
EP_ROWS = (44, EH)                  # its rows under the watermark
DISSOLVE = 0.8                      # the episode's shots dissolve in over this
LEAD, TAIL = 0.1, 0.5               # sound kept before and after the voice
SOLO_H = 1350                       # one view alone: a tall 4:5 picture under the hook
MAX_SPEED = 2.5                     # camera moves run up to this fast
END = 2.4                           # the photo and the toll, last
# which 3D shots and which 2D clip show a span, by the span's first shot
TOP_SHOTS = {"fall": ("fall", "dramatization"), "dramatization": ("fall", "dramatization"),
             "load_path": ("load_path", "connection"), "connection": ("load_path", "connection"),
             "physics": ("load_path", "connection"), "compare": ("load_path", "connection"),
             "establish": ("establish",), "build": ("establish",)}
KIT_CLIP = {"fall": "fall", "dramatization": "fall", "load_path": "physics", "connection": "physics",
            "physics": "physics", "compare": "compare", "establish": "build", "build": "build"}
FONTS = os.path.join(HERE, "..", "fonts")
WHITE, RED, DIM = (255, 255, 255), (255, 75, 58), (170, 190, 220)
SR = 48000


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _audio(path, sr, start=None, length=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    cmd += ["-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)


def locate(episode_audio, take, sr):
    """Seconds into the episode where the take starts: the peak of their
    cross-correlation (the take is laid at unity gain under ducked music)."""
    n = 1 << int(np.ceil(np.log2(len(episode_audio) + len(take))))
    corr = np.fft.irfft(np.fft.rfft(episode_audio, n) * np.conj(np.fft.rfft(take, n)), n)
    return int(np.argmax(corr[: len(episode_audio)])) / sr


def _wav(prep, voiced, clip):
    p = voiced[clip]["wav"]
    return p if os.path.exists(p) else os.path.join(prep, os.path.basename(p))


def plan(prep, episode_mp4, spans):
    """[(span name, start, end, shot start, [(word, t0, t1)])], times in
    the episode's seconds."""
    import narration
    sheet = json.load(open(os.path.join(prep, "timed_sheet.json")))
    voiced = json.load(open(os.path.join(prep, "voiced.json")))
    text = {s["clip"]: s["narration"] for s in sheet["shots"]}
    low = 8000
    ep = _audio(episode_mp4, low)
    out = []
    for span in spans:
        clips = span.split("-")
        placed = []
        for c in clips:
            wav = _wav(prep, voiced, c)
            at = locate(ep, _audio(wav, low), low)
            secs = voiced[c]["seconds"]
            words = [(w["word"], at + w["start"], at + w.get("end", w["start"] + 0.3))
                     for w in narration.words_of(text[c], wav)]
            placed.append((c, at, secs, words))
            print(f"  {c}: voice at {at:.2f} s for {secs:.1f} s")
        first, last = placed[0], placed[-1]
        out.append({"span": span, "start": first[1] - LEAD, "end": last[1] + last[2] + TAIL,
                    "shot_start": first[1] - narration.PAD_IN,
                    "words": [w for p in placed for w in p[3]]})
    return out, sheet


def chunks(words, most=3):
    """Caption groups: up to `most` words, broken after punctuation."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= most or re.search(r"[.,;:!?]$", w[0]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _text(d, s, cx, y, size, fill, name="InterDisplay-Black.otf", max_w=SW - 120, stroke=0):
    while size > 30 and _font(name, size).getlength(s) > max_w:
        size -= 2
    d.text((cx, y), s, font=_font(name, size), fill=fill, anchor="mm",
           stroke_width=stroke, stroke_fill=(0, 0, 0))
    return size


def _brand(d):
    f = _font("Inter-Bold.otf", 30)
    name = "THE POINT OF FAILURE"
    tw = f.getlength(name)
    x = (SW - tw - 40) / 2
    d.line([(x, 92), (x + 26, 92)], fill=WHITE, width=5)
    d.line([(x + 12, 68), (x + 17, 82), (x + 10, 90), (x + 15, 104)], fill=RED, width=4)
    d.text((x + 40, 86), name, font=f, fill=(255, 255, 255, 200), anchor="lm")


def shot_starts(prep, episode_mp4, clips):
    """{clip: second its shot starts in the episode}, for the clips given and
    the shot after each (a window ends where the next shot starts)."""
    sheet = json.load(open(os.path.join(prep, "timed_sheet.json")))
    order = [s["clip"] for s in sheet["shots"]]
    want = []
    for c in clips:
        if c in order:
            want += [c] + order[order.index(c) + 1: order.index(c) + 2]
    cuts, _ = plan(prep, episode_mp4, list(dict.fromkeys(want)))
    return {c["span"]: c["shot_start"] for c in cuts}


def _windows(span, starts, order):
    """The episode's 3D picture for a span: [(start, end)] seconds."""
    first = span.split("-")[0]
    shots = TOP_SHOTS.get(first, (first,))
    out = []
    for c in shots:
        if c not in starts or c not in order:
            continue
        nxt = order[order.index(c) + 1] if order.index(c) + 1 < len(order) else None
        end = starts.get(nxt)
        if end is None:
            continue
        a = starts[c] + DISSOLVE
        if out and abs(out[-1][1] - starts[c]) < 0.05:
            out[-1] = (out[-1][0], end)           # shots back to back: one window
        else:
            out.append((a, end))
    return out


def motion(episode_mp4, a, b, track=False):
    """Each frame's time in [a, b), how much it differs from the one before,
    and where across the frame the movement is (0..1); with track, where it
    is in each frame, smoothed (a camera that follows the action)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", episode_mp4,
                          "-f", "rawvideo", "-pix_fmt", "gray", "-s", "160x90", "-r", str(FPS), "-"],
                         capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 90, 160).astype(np.float32)
    d = np.abs(np.diff(f, axis=0))
    diff = np.concatenate([[0.0], d.mean(axis=(1, 2))])
    cols, rows = d.sum(axis=(0, 1)), d.sum(axis=(0, 2))
    cx = float((cols * np.arange(160)).sum() / max(1e-6, cols.sum()) / 160) if len(d) else 0.5
    cy = float((rows * np.arange(90)).sum() / max(1e-6, rows.sum()) / 90) if len(d) else 0.5
    if not track:
        return a + np.arange(len(f)) / FPS, diff, (cx, cy)
    path, cur = [], (cx, cy)
    for k in range(len(f)):
        if k and d[k - 1].sum() > 160 * 90 * 0.6:          # something moved: follow it, gently
            w = d[k - 1]
            x = float((w.sum(0) * np.arange(160)).sum() / w.sum() / 160)
            y = float((w.sum(1) * np.arange(90)).sum() / w.sum() / 90)
            cur = (cur[0] + 0.08 * (x - cur[0]), cur[1] + 0.08 * (y - cur[1]))
        path.append(cur)
    return a + np.arange(len(f)) / FPS, diff, path


class Episode:
    """The episode's frames at any time, read forwards (a jump back reopens)."""

    def __init__(self, path):
        self.path, self.proc, self.n, self.frame = path, None, -1, None

    def at(self, t):
        n = int(round(t * FPS))
        if self.proc is None or n < self.n or n > self.n + 120:
            if self.proc:
                self.proc.stdout.close()
                self.proc.kill()
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{n / FPS:.3f}", "-i", self.path,
                                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{EW}x{EH}",
                                          "-r", str(FPS), "-"], stdout=subprocess.PIPE)
            self.n = n - 1
        while self.n < n:
            raw = self.proc.stdout.read(EW * EH * 3)
            if len(raw) == EW * EH * 3:
                self.frame = Image.frombytes("RGB", (EW, EH), raw)
            self.n += 1
        return self.frame or Image.new("RGB", (EW, EH))


def _fit(frames, n_out, speed_max=MAX_SPEED, keep="tail"):
    """Source times for n_out output frames: the frames played as fast as
    needed to fit (camera moves speed up), never faster than speed_max;
    too many even so: the end kept (or the start)."""
    if not frames:
        return []
    speed = min(speed_max, max(1.0, len(frames) / n_out))
    use = int(n_out * speed)
    if len(frames) > use:
        frames = frames[-use:] if keep == "tail" else frames[:use]
    return [frames[min(len(frames) - 1, int(i * speed))] for i in range(min(n_out, int(len(frames) / speed)))]


def _beats_drop(b):
    """The first beat of a fall that is the failure itself (after the
    handover and the pull back)."""
    return next(n for n in b.at if n not in ("handover", "pull"))


def _kit_focus(kit, clip, a, b):
    """Where the 2D clip changes between seconds a and b (0..1 across, down)."""
    fn = (lambda t: kit.physics(t, None, lead=False)) if clip == "physics" else getattr(kit, clip)
    d = np.abs(np.asarray(fn(b).convert("L").resize((160, 90)), np.float32)
               - np.asarray(fn(a).convert("L").resize((160, 90)), np.float32))
    if d.sum() < 1:
        return 0.5, 0.5
    return (float((d.sum(0) * np.arange(160)).sum() / d.sum() / 160),
            float((d.sum(1) * np.arange(90)).sum() / d.sum() / 90))


def _uncaption(img):
    """The episode's frame without its caption bar (kits/blueprint.py
    Frame.caption: a dark box at rows H-78..H-34, as wide as its words):
    the rows above and below it blended across, so the 3D under it (the
    Hyatt walkways land there) can be shown. Found by being darker than the
    rows around it, or by its white words, so a bar fading in or out is
    found too."""
    a = np.asarray(img).astype(np.float32)
    y0, y1 = EH - 80, EH - 32
    lum = a.mean(2)
    ref = (lum[y0 - 4] + lum[y1 + 4]) / 2
    box = np.median(lum[y0 + 2: y1 - 2], axis=0)
    text = lum[y0 + 12: y1 - 12].max(0) > ref + 70           # its words outlast the box as it fades
    cols = np.where(((box < 0.85 * ref) | text) & (ref > 40))[0]
    if len(cols) < 120:
        return img
    x0, x1 = max(3, cols[0] - 24), min(EW - 4, cols[-1] + 24)      # the box runs past its words
    if x1 - x0 > EW * 0.9:
        return img
    k = np.linspace(0, 1, y1 - y0 + 1)[:, None, None]
    a[y0:y1 + 1, x0 - 3:x1 + 4] = (1 - k) * a[y0 - 1, x0 - 3:x1 + 4] + k * a[y1 + 1, x0 - 3:x1 + 4]
    return Image.fromarray(a.astype(np.uint8))


def _sentence_split(words, a, b):
    """The second (episode time) between a and b where a sentence ends
    nearest the middle: the 3D says the first half, the 2D the second."""
    mid = (a + b) / 2
    ends = [w[2] for w in words if re.search(r"[.!?]$", w[0]) and a + 2 < w[2] < b - 2]
    return min(ends, key=lambda t: abs(t - mid)) if ends else mid


def storyboard(cuts, n_total, episode_mp4, starts, sheet, kit):
    """Per output frame: (layout, picture(s), tag). The owner's order
    (2026-10-22): both collapses at once, top and bottom; then one view at a
    time, the 3D first, then the 2D, each moving the story on; the real
    photo with the toll counting up last."""
    from kits import timemap
    order = [s["clip"] for s in sheet["shots"]]
    frames = []
    for ci, c in enumerate(cuts):
        n = int(round((c["end"] - c["start"]) * FPS))
        t_at = lambda k: c["start"] + k / FPS                       # episode time of output frame k
        first = c["span"].split("-")[0]
        clip = KIT_CLIP.get(first, "physics")
        out = []
        if clip == "fall" and "fall" in starts and not sheet.get("timing", {}).get("ai"):
            tm = timemap.of(sheet)
            fs = starts["fall"]
            drop, settle = fs + tm.real(22.0) - tm.real(20.0), fs + tm.real(28.0) - tm.real(20.0)
            _, diff, path = motion(episode_mp4, drop - 0.6, settle, track=True)
            at = lambda t: path[min(len(path) - 1, max(0, int(round((t - drop + 0.6) * FPS))))]
            quiet = diff < 0.1 * diff.max() if len(diff) else np.zeros(0, bool)
            for k in range(int(np.argmax(diff)) if len(diff) else 0, len(quiet) - 15):
                if quiet[k: k + 15].all():
                    settle = drop - 0.6 + (k + 15) / FPS
                    break
            b = kit.FALL
            kd = b.start(_beats_drop(b))
            kx = _kit_focus(kit, "fall", kd - 0.3, kd + 1.5)[0]
            # 1. both at once, a beat before the break
            run = min(n, int((settle - drop + 0.6) * FPS))
            for k in range(run):
                t = drop - 0.6 + k / FPS
                out.append(("split", ("ep", t, 1.3, at(t)),
                            ("kit", "fall", min(b.total - 1 / FPS, kd - 0.6 + k / FPS), 1.5, (kx, 0.72)), "3D MODEL"))
            # 2. the 3D alone, again at half speed, closing in
            again = min(n - len(out), int(6.0 * FPS))
            for k in range(again):
                t = drop - 0.3 + k / (2 * FPS)
                out.append(("solo", ("ep", t, 1.15 + 0.35 * k / max(1, again), at(t)), None,
                            "3D MODEL · SLOW MOTION"))
            # 3. the 2D alone, its fall from the start, the break on the words
            #    that say it ("crack", "crashed", "collapsed"...)
            k0 = len(out)
            rest = n - k0
            if rest > 0:
                cue = next((w[1] for w in c["words"] if w[1] > t_at(k0) + 1.0
                            and re.search(r"crack|crash|collaps|plung|fell|tore|snap|gave", w[0].lower())), None)
                start = b.end("handover")
                lead = (cue - t_at(k0)) if cue else (kd - start)
                t0 = max(start, kd - lead)                          # the drop lands on the cue
                for k in range(rest):
                    kt = min(b.total - 1 / FPS, t0 + k / FPS)
                    out.append(("solo", ("kit", "fall", kt, 0.99, (kx, 0.5)), None, "2D DRAWING"))
        else:
            # one view at a time: the 3D says the first sentences, the 2D the rest
            split = _sentence_split(c["words"], c["start"], c["end"])
            n3 = int(round((split - c["start"]) * FPS))
            times, diff, focus = [], np.zeros(0), (0.5, 0.5)
            for a, e in _windows(c["span"], starts, order):
                t, d, focus = motion(episode_mp4, a, e)
                times += list(t)
                diff = np.concatenate([diff, d])
            still = max(0.25, 0.03 * (diff.max() if len(diff) else 0))
            moving = [t for t, d in zip(times, diff) if d > still]
            focus = tuple(min(0.7, max(0.3, v)) for v in focus)
            shown = _fit(moving, n3) or ([times[-1]] if times else [0.0])
            for k in range(n3):
                t = shown[min(k, len(shown) - 1)]
                z = 1.0 if k < len(shown) else 1.0 + 0.15 * (k - len(shown)) / max(1, n3)
                out.append(("solo", ("ep", t, z, focus), None, "3D MODEL"))
            clip_b = getattr(kit, kit.CLIPS[clip])
            n2 = n - n3
            lead = clip_b.end("lead") if "lead" in clip_b.at else 0.0
            t0 = max(lead, clip_b.total - n2 / FPS)                 # its end: where it fails
            kf = _kit_focus(kit, clip, t0, clip_b.total - 1 / FPS)
            kf = (min(0.7, max(0.3, kf[0])), min(0.7, max(0.35, kf[1])))
            for k in range(n2):
                out.append(("solo", ("kit", clip, min(clip_b.total - 1 / FPS, t0 + k / FPS), 0.99, kf), None,
                            "2D DRAWING"))
        frames += [(ci, k, f) for k, f in enumerate(out[:n])]
    # last: the real photo, the toll counting up, where the full story is
    photo = starts.get("aftermath")
    for k in range(n_total - len(frames)):
        frames.append((len(cuts), k, ("end", ("ep", (photo or 0.0) + DISSOLVE + 0.6, 1.05 + 0.08 * k / FPS / END,
                                              (0.5, 0.45)), None, "PHOTO")))
    return frames


def _panel(img, zoom=1.0, cx=0.5, cy=0.5, rows=(0, EH), pad=0, size=(PW, PH)):
    """A 16:9 frame cropped to fill a panel of the 9:16 screen (`size`),
    inside `rows` (the episode's frame: clear of its watermark). A zoom
    under 1 shows the whole width instead, on the frame's own ground."""
    pw, ph = size
    if zoom < 1.0:
        # the whole drawing, near the top of a tall picture: the words go under it
        cw = min(img.width, img.height * 1.4)        # a little of the sides goes: 7:5
        x = min(img.width - cw, max(0.0, cx * img.width - cw / 2))
        h = int(img.height * pw / cw)
        out = Image.new("RGB", (pw, ph), img.getpixel((4, 4)))
        out.paste(img.resize((pw, h), Image.LANCZOS, box=(x, 0, x + cw, img.height)),
                  (0, 40 if ph > 1.6 * h else (ph - h) // 2))
        return out
    if pad:
        grown = Image.new("RGB", (img.width, img.height + pad), img.getpixel((4, img.height - 4)))
        grown.paste(img, (0, 0))
        img, rows = grown, (0, grown.height)
    top, bottom = rows
    ch = min(bottom - top, img.height / zoom)
    cw = min(img.width, ch * pw / ph)
    x = min(img.width - cw, max(0.0, cx * img.width - cw / 2))
    y = min(bottom - ch, max(top, cy * (img.height - pad) - ch / 2))
    return img.resize((pw, ph), Image.LANCZOS, box=(x, y, x + cw, y + ch))


def _pill(d, text, x, y):
    f = _font("Inter-Bold.otf", 30)
    w = f.getlength(text)
    d.rounded_rectangle([x, y - 26, x + w + 36, y + 26], 26, fill=(4, 10, 20, 170))
    d.text((x + 18, y), text, font=f, fill=(170, 206, 255), anchor="lm")


def _words(d, caption):
    """The words as they are said, three at a time, on the seam's line."""
    words, now = caption
    size = 96
    line = " ".join(w for w, _, _ in words).upper()
    while _font("InterDisplay-Black.otf", size).getlength(line) > SW - 90 and size > 44:
        size -= 4
    fnt = _font("InterDisplay-Black.otf", size)
    x = (SW - fnt.getlength(line)) / 2
    lit = max((i for i, (_, a, _) in enumerate(words) if a <= now), default=None)
    for i, (w, a, b) in enumerate(words):
        col = (255, 214, 64) if i == lit else WHITE
        d.text((x, SEAM + 44), w.upper(), font=fnt, fill=col, anchor="lm", stroke_width=8, stroke_fill=(0, 0, 0))
        x += fnt.getlength(w.upper() + " ")


def compose(layout, top_img, bot_img, hook, caption, flash=0.0, tag="3D MODEL", toll=None):
    """One 9:16 frame. split: the 3D panel over the 2D one; solo and end: one
    tall 4:5 picture. The hook on its band at the top, the words on the
    seam's line; at the end the toll counting up and where the full story is."""
    im = Image.new("RGB", (SW, SH), (4, 10, 20))
    if layout == "split":
        im.paste(top_img, (0, HOOK_H))
        im.paste(bot_img, (0, SEAM))
    else:
        im.paste(top_img, (0, HOOK_H))
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, SW, HOOK_H], fill=(4, 10, 20, 255))
    d.rectangle([0, HOOK_H - 4, SW, HOOK_H], fill=RED + (255,))
    if layout == "split":
        d.rectangle([0, SEAM - 3, SW, SEAM + 3], fill=RED + (255,))
        _pill(d, tag, 36, SEAM - 64)
        _pill(d, "2D DRAWING", 36, SEAM + 138)
    else:
        d.rectangle([0, HOOK_H + SOLO_H, SW, HOOK_H + SOLO_H + 4], fill=RED + (255,))
        _pill(d, tag, 36, HOOK_H + 60)
    _brand(d)
    for i, line in enumerate([x.strip() for x in hook.split("|") if x.strip()][:2]):
        _text(d, line, SW / 2, 160 + i * 84, 76, WHITE if i == 0 else RED)
    if caption:
        _words(d, caption)
    if toll:
        value, label, k = toll
        shade = Image.new("RGBA", (SW, SOLO_H), (4, 10, 20, int(120 * min(1, k * 3))))
        im.paste(shade, (0, HOOK_H), shade)
        d = ImageDraw.Draw(im, "RGBA")
        digits = re.sub(r"\D", "", value)
        shown = str(int(round(int(digits) * (1 - (1 - min(1.0, k / 0.55)) ** 3)))) if digits else value
        _text(d, shown, SW / 2, 860, 300, RED, stroke=6)
        _text(d, label.upper(), SW / 2, 1060, 64, WHITE, "InterDisplay-Bold.otf", stroke=4)
        a = int(255 * min(1.0, max(0.0, (k - 0.45) / 0.2)))
        if a:
            _text(d, "FULL STORY ON THE CHANNEL", SW / 2, 1240, 58, (255, 214, 64, a), stroke=4)
    if flash > 0:
        im = Image.blend(im, Image.new("RGB", im.size, WHITE), flash)
    return im


def render(episode_mp4, out_dir, cuts, starts, sheet, top):
    """The Short from its spans (plan) and the episode's shot starts."""
    import soundfile as sf
    from episode import kit_class
    from score import boom, even_loudness, riser, whoosh
    os.makedirs(out_dir, exist_ok=True)
    kit = kit_class(sheet["kit"]["variant"])(sheet)
    kit.captions = {}                 # the Short has its own words on screen
    kit.sheet = {**kit.sheet, "numbers": []}   # and the toll at its end
    hooks = [h for h in top.split("||") if h.strip()] or [""]
    toll = (sheet.get("numbers") or [{}])[0]

    # the sound: each span from the episode's own mix, a short crossfade and
    # a whoosh between spans; then a rising tone under the toll, landing on a hit
    xf = int(0.12 * SR)
    sound, joins = np.zeros(0, np.float32), []
    for c in cuts:
        a = _audio(episode_mp4, SR, c["start"], c["end"] - c["start"])
        if len(sound):
            a = a.copy()
            a[:xf] *= np.linspace(0, 1, xf, dtype=np.float32)
            sound[-xf:] *= np.linspace(1, 0, xf, dtype=np.float32)
            joins.append(len(sound) / SR)
        sound = np.concatenate([sound, a])
    end = np.zeros(int(END * SR), np.float32)
    r = riser(0.55 * END, 7)[:, 0] * 0.3
    end[: len(r)] += r[: len(end)]
    hit = boom(6)[:, 0] * 0.55
    i = int(0.55 * END * SR)
    end[i: i + len(hit)] += hit[: len(end) - i]
    end[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR), dtype=np.float32)
    joins.append(len(sound) / SR)
    sound = np.concatenate([sound, end])
    for j in joins:
        w = whoosh(31)[:, 0] * 0.35
        i = max(0, int((j - 0.25) * SR))
        sound[i: i + len(w)] += w[: len(sound) - i]
    sound[:int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR), dtype=np.float32)
    wav = os.path.join(out_dir, "short.wav")
    sf.write(wav, np.clip(sound, -1, 1), SR)
    wav = even_loudness(wav, os.path.join(out_dir, "short_even.wav"), target=-14.0)
    total = len(sound) / SR
    n_total = int(round(total * FPS))

    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-i", wav,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k",
                            "-shortest", os.path.join(out_dir, "short.mp4")], stdin=subprocess.PIPE)
    ep = Episode(episode_mp4)
    cache = {}

    def picture(src, size, rows=EP_ROWS):
        if src[0] == "ep":
            _, t, z, (cx, cy) = src
            return _panel(_uncaption(ep.at(t)), z, cx, cy, rows, size=size)
        _, clip, t, z, (kx, ky) = src
        key = (clip, round(t * FPS))
        if key not in cache:
            fn = getattr(kit, clip)
            cache.clear() if len(cache) > 8 else None
            cache[key] = fn(t, None, lead=False) if clip == "physics" else fn(t)
        return _panel(cache[key], z, kx, ky, pad=160, size=size)

    groups = [chunks(c["words"]) for c in cuts]
    prev, flash_from = None, -99
    for n, (ci, k, (layout, top_src, bot_src, tag)) in enumerate(storyboard(cuts, n_total, episode_mp4,
                                                                            starts, sheet, kit)):
        hook = hooks[min(ci, len(hooks) - 1)]
        cap, tol = None, None
        if ci < len(cuts):
            t_ep = cuts[ci]["start"] + k / FPS
            g = next((g for g in groups[ci] if g[0][1] - 0.05 <= t_ep < g[-1][2] + 0.15), None)
            cap = (g, t_ep) if g else None
        else:
            tol = (toll.get("value", ""), toll.get("label", ""), k / FPS / END) if toll.get("value") else None
        if layout == "split":
            img = compose(layout, picture(top_src, (PW, PH)), picture(bot_src, (PW, PH)), hook, cap, tag=tag)
        else:
            # the photo is cropped above the episode's own line about it
            rows = (EP_ROWS[0], EH - 92) if layout == "end" else EP_ROWS
            img = compose(layout, picture(top_src, (SW, SOLO_H), rows), None, hook, cap, tag=tag, toll=tol)
        # a cut to a new view: a quick flash
        view = (layout, top_src[0], tag)
        if prev is not None and view != prev:
            flash_from = n
        prev = view
        if n - flash_from < 4:
            img = Image.blend(img, Image.new("RGB", img.size, WHITE), 0.5 * (1 - (n - flash_from) / 4))
        enc.stdin.write(img.tobytes())
        if n % 150 == 0:
            print(f"  {n}/{n_total} frames", flush=True)
    enc.stdin.close()
    enc.wait()
    return total


def build(prep, episode_mp4, out_dir, spans, top):
    cuts, sheet = plan(prep, episode_mp4, spans)
    need = [c for span in spans for c in TOP_SHOTS.get(span.split("-")[0], ())]
    need += ["aftermath"] if "fall" in need else []
    starts = shot_starts(prep, episode_mp4, need)
    total = render(episode_mp4, out_dir, cuts, starts, sheet, top)
    from sheet_writer import SHOTS
    part = {clip: p for p, _, clip, _ in SHOTS}
    info = {"seconds": round(total, 2), "top": top,
            "spans": [{k: c[k] for k in ("span", "start", "end")} for c in cuts],
            "parts": sorted({part[x] for c in cuts for x in c["span"].split("-") if x in part})}
    json.dump(info, open(os.path.join(out_dir, "short.json"), "w"), indent=1)
    print(f"{out_dir}/short.mp4: {total:.1f} s")
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("prep")
    ap.add_argument("episode")
    ap.add_argument("out")
    ap.add_argument("--spans", default="fall-dramatization,connection")
    ap.add_argument("--top", required=True, help="the hook, two lines split by |; one per span, split by ||")
    a = ap.parse_args()
    build(a.prep, a.episode, a.out, [s.strip() for s in a.spans.split(",") if s.strip()], a.top)
