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
in its first seconds): the full 9:16 screen, the 3D model on top and the 2D
drawing of the same moment below it. The failure is on screen from the first
frame; frames where nothing moves are dropped and camera moves run faster;
the collapse plays again in slow motion; the hook changes with each span
(stages split by ||); the words sit on the seam as they are said; and the
last frames run back into the first, so the Short loops instead of ending.

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
MAX_SPEED = 2.5                     # camera moves run up to this fast
LOOP = 0.4                          # the last frames dissolve into the first
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


def schedule(span, n_out, episode_mp4, starts, sheet, kit):
    """Per output frame: what the 3D panel shows (episode second, zoom,
    focus) and what the 2D panel shows (kit clip, its second, zoom, focus)."""
    from kits import timemap
    order = [s["clip"] for s in sheet["shots"]]
    first = span.split("-")[0]
    clip = KIT_CLIP.get(first, "physics")
    top, bot = [], []
    if clip == "fall" and "fall" in starts and not sheet.get("timing", {}).get("ai"):
        # the failure first: both panels a beat before the break, at full
        # speed. The 3D fall is the canonical 20-28 s (kits/timemap.py), the
        # episode's fall shot starting on its 20th second
        tm = timemap.of(sheet)
        fs = starts["fall"]
        drop, settle = fs + tm.real(22.0) - tm.real(20.0), fs + tm.real(28.0) - tm.real(20.0)
        _, diff, path = motion(episode_mp4, drop - 0.6, settle, track=True)
        at = lambda t: path[min(len(path) - 1, max(0, int(round((t - drop + 0.6) * FPS))))]
        # the fall is over once the picture has been still for half a second
        quiet = diff < 0.1 * diff.max() if len(diff) else np.zeros(0, bool)
        peak = int(np.argmax(diff)) if len(diff) else 0
        for k in range(peak, len(quiet) - 15):
            if quiet[k: k + 15].all():
                settle = drop - 0.6 + (k + 15) / FPS
                break
        b = kit.FALL
        kd = b.start(_beats_drop(b))
        kfocus = (_kit_focus(kit, "fall", kd - 0.3, kd + 1.5)[0], 0.72)    # low, where it lands
        run = int((settle - drop + 0.6) * FPS)
        top = [(drop - 0.6 + i / FPS, 1.3, at(drop - 0.6 + i / FPS), "3D MODEL") for i in range(min(run, n_out))]
        bot = [(min(b.total - 1 / FPS, kd - 0.6 + i / FPS), 1.5) for i in range(len(top))]
        # then again, at half speed and closer
        again = int(min(3.0 * 2 * FPS, max(0, n_out - len(top))))
        for i in range(again):
            k = i / max(1, again - 1)
            t = drop - 0.3 + i / (2 * FPS)
            top.append((t, 1.3 + 0.3 * k, at(t), "3D MODEL · SLOW MOTION"))
            bot.append((kd - 0.3 + i / (2 * FPS), 1.5 + 0.2 * k))
        hold_top, hold_bot = settle - 1 / FPS, b.total - 1 / FPS
        # and the real wreckage: the episode's aftermath pictures, moving as they did there
        nxt = order[order.index("aftermath") + 1] if "aftermath" in order[:-1] else None
        if "aftermath" in starts and nxt in starts and len(top) < n_out:
            a, e = starts["aftermath"] + DISSOLVE, starts[nxt]
            frames = [a + i / FPS for i in range(int((e - a) * FPS))]
            for t in _fit(frames, n_out - len(top), speed_max=1.5, keep="head"):
                top.append((t, 1.0, (0.5, 0.45), "PHOTO"))
                bot.append((hold_bot, bot[-1][1] if bot else 1.5))
            hold_top = top[-1][0]
    else:
        times, diff, focus = [], np.zeros(0), (0.5, 0.5)
        for a, b in _windows(span, starts, order):
            t, d, focus = motion(episode_mp4, a, b)
            times += list(t)
            diff = np.concatenate([diff, d])
        still = max(0.25, 0.03 * (diff.max() if len(diff) else 0))
        moving = [t for t, d in zip(times, diff) if d > still]       # held frames are dropped
        focus = tuple(min(0.7, max(0.3, v)) for v in focus)
        top = [(t, 1.0, focus, "3D MODEL") for t in _fit(moving, n_out)]
        clip_b = getattr(kit, kit.CLIPS[clip])
        lead = clip_b.end("lead") if "lead" in clip_b.at else 0.0
        length = clip_b.total - lead
        first_t = lead + max(0.0, length - n_out / FPS)                   # the clip's end: where it fails
        bot = [(min(clip_b.total - 1 / FPS, first_t + i / FPS), 0.99) for i in range(n_out)]
        kfocus = _kit_focus(kit, clip, first_t, clip_b.total - 1 / FPS)
        hold_top, hold_bot = (top[-1][0] if top else (times[-1] if times else 0.0)), clip_b.total - 1 / FPS
    # what is left: hold the last picture, drifting slowly in
    held, z0, kz0 = n_out - len(top), (top[-1][1] if top else 1.0), (bot[-1][1] if bot else 1.0)
    f0, tag0 = (top[-1][2], top[-1][3]) if top else ((0.5, 0.5), "3D MODEL")
    for i in range(max(0, held)):
        top.append((hold_top, z0 + 0.15 * i / max(1, held), f0, tag0))
    for i in range(max(0, n_out - len(bot))):
        bot.append((hold_bot, kz0 + 0.1 * i / max(1, held) if kz0 >= 1 else kz0))
    kfocus = (min(0.75, max(0.25, kfocus[0])), min(0.9, max(0.25, kfocus[1])))
    return [((t, z, f, tag), (clip, kt, kz, kfocus)) for (t, z, f, tag), (kt, kz) in zip(top[:n_out], bot[:n_out])]


def _uncaption(img):
    """The episode's frame without its caption bar (the dark box low in the
    frame): the rows above and below it blended across, so the 3D under it
    (the Hyatt walkways land there) can be shown."""
    a = np.asarray(img).astype(np.float32)
    y0b, y1b = EH - 100, EH - 20
    dark = a[y0b:y1b].mean(2) < 60
    cols = np.where(dark.mean(0) > 0.35)[0]
    if len(cols) < 150 or cols[-1] - cols[0] > EW * 0.9:
        return img
    x0, x1 = cols[0], cols[-1]
    rows = np.where(dark[:, x0:x1 + 1].mean(1) > 0.6)[0]
    if len(rows) < 20:
        return img
    y0, y1 = y0b + rows[0] - 3, min(EH - 1, y0b + rows[-1] + 3)
    k = np.linspace(0, 1, y1 - y0 + 1)[:, None, None]
    a[y0:y1 + 1, x0 - 3:x1 + 4] = (1 - k) * a[y0 - 1, x0 - 3:x1 + 4] + k * a[min(EH - 1, y1 + 1), x0 - 3:x1 + 4]
    return Image.fromarray(a.astype(np.uint8))


def _panel(img, zoom=1.0, cx=0.5, cy=0.5, rows=(0, EH), pad=0):
    """A 16:9 frame cropped to fill one panel of the 9:16 screen, inside
    `rows` (the episode's frame: clear of its watermark and caption bar).
    A zoom under 1 shows the whole width instead, on the frame's own ground
    (a 2D drawing, labels and all)."""
    if zoom < 1.0:
        h = int(img.height * PW / img.width)
        out = Image.new("RGB", (PW, PH), img.getpixel((4, 4)))
        out.paste(img.resize((PW, h), Image.LANCZOS), (0, (PH - h) // 2))
        return out
    if pad:
        grown = Image.new("RGB", (img.width, img.height + pad), img.getpixel((4, img.height - 4)))
        grown.paste(img, (0, 0))
        img, rows = grown, (0, grown.height)
    top, bottom = rows
    ch = min(bottom - top, img.height / zoom)
    cw = ch * PW / PH
    x = min(img.width - cw, max(0.0, cx * img.width - cw / 2))
    y = min(bottom - ch, max(top, cy * (img.height - pad) - ch / 2))
    return img.resize((PW, PH), Image.LANCZOS, box=(x, y, x + cw, y + ch))


def _pill(d, text, x, y):
    f = _font("Inter-Bold.otf", 30)
    w = f.getlength(text)
    d.rounded_rectangle([x, y - 26, x + w + 36, y + 26], 26, fill=(4, 10, 20, 170))
    d.text((x + 18, y), text, font=f, fill=(170, 206, 255), anchor="lm")


def compose(top_img, bot_img, hook, caption, flash=0.0, tag="3D MODEL"):
    """One 9:16 frame: the 3D panel over the 2D one, the hook over the top
    of the screen, the words on the seam."""
    im = Image.new("RGB", (SW, SH))
    im.paste(top_img, (0, HOOK_H))
    im.paste(bot_img, (0, SEAM))
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, SW, HOOK_H], fill=(4, 10, 20, 255))
    d.rectangle([0, HOOK_H - 4, SW, HOOK_H], fill=RED + (255,))
    d.rectangle([0, SEAM - 3, SW, SEAM + 3], fill=RED + (255,))
    _brand(d)
    for i, line in enumerate([x.strip() for x in hook.split("|") if x.strip()][:2]):
        _text(d, line, SW / 2, 160 + i * 84, 76, WHITE if i == 0 else RED)
    _pill(d, tag, 36, SEAM - 64)
    _pill(d, "2D DRAWING", 36, SEAM + 138)
    if caption:
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
            d.text((x, SEAM + 44), w.upper(), font=fnt, fill=col, anchor="lm", stroke_width=8,
                   stroke_fill=(0, 0, 0))
            x += fnt.getlength(w.upper() + " ")
    if flash > 0:
        im = Image.blend(im, Image.new("RGB", im.size, WHITE), flash)
    return im


def render(episode_mp4, out_dir, cuts, starts, sheet, top):
    """The Short from its spans (plan) and the episode's shot starts."""
    import soundfile as sf
    from episode import kit_class
    from score import even_loudness, whoosh
    os.makedirs(out_dir, exist_ok=True)
    kit = kit_class(sheet["kit"]["variant"])(sheet)
    kit.captions = {}                 # the Short has its own words on screen
    kit.sheet = {**kit.sheet, "numbers": []}   # and the toll in its hook
    hooks = [h for h in top.split("||") if h.strip()] or [""]

    # the sound: each span from the episode's own mix, a short crossfade and a
    # whoosh between spans, faded at both ends so the loop joins softly
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
    for j in joins:
        w = whoosh(31)[:, 0] * 0.35
        i = max(0, int((j - 0.25) * SR))
        sound[i: i + len(w)] += w[: len(sound) - i]
    fade = int(0.25 * SR)
    sound[:int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR), dtype=np.float32)
    sound[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    wav = os.path.join(out_dir, "short.wav")
    sf.write(wav, np.clip(sound, -1, 1), SR)
    wav = even_loudness(wav, os.path.join(out_dir, "short_even.wav"), target=-14.0)
    total = len(sound) / SR

    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-i", wav,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k",
                            "-shortest", os.path.join(out_dir, "short.mp4")], stdin=subprocess.PIPE)
    ep = Episode(episode_mp4)
    cache = {}

    def kit_frame(clip, t):
        key = (clip, round(t * FPS))
        if key not in cache:
            fn = getattr(kit, clip)
            cache.clear() if len(cache) > 8 else None
            cache[key] = fn(t, None, lead=False) if clip == "physics" else fn(t)
        return cache[key]

    n_total = int(round(total * FPS))
    out_n, first = 0, None
    loop_n = int(LOOP * FPS)
    for ci, c in enumerate(cuts):
        n = int(round((c["end"] - c["start"]) * FPS)) if ci < len(cuts) - 1 else n_total - out_n
        plan_ = schedule(c["span"], n, episode_mp4, starts, sheet, kit)
        groups = chunks(c["words"])
        hook = hooks[min(ci, len(hooks) - 1)]
        print(f"  {c['span']}: {n} frames", flush=True)
        for k, ((t, z, (cx, cy), tag), (clip, kt, kz, (kx, ky))) in enumerate(plan_):
            t_ep = c["start"] + k / FPS
            cap = next((g for g in groups if g[0][1] - 0.05 <= t_ep < g[-1][2] + 0.15), None)
            img = compose(_panel(_uncaption(ep.at(t)), z, cx, cy, EP_ROWS), _panel(kit_frame(clip, kt), kz, kx, ky, pad=160),
                          hook, (cap, t_ep) if cap else None,
                          flash=0.6 * max(0.0, 1 - k / 4) if ci > 0 else 0.0, tag=tag)
            if first is None:
                first = img
            left = n_total - out_n
            if left <= loop_n:
                img = Image.blend(img, first, 1 - left / loop_n)
            enc.stdin.write(img.tobytes())
            out_n += 1
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
