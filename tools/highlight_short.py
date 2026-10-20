"""
The highlight Short of a long episode (owner, 2026-10-17: one Short per long
video, 48 hours after it), cut from the finished episode itself: no new
render, the same voice, music and animation.

    python tools/highlight_short.py PREP EPISODE_MP4 OUT \
        --spans fall-dramatization,connection --top "HALF AN INCH OF STEEL|BROUGHT THIS BRIDGE DOWN"

A span runs from the start of its first shot's voice to the end of its last
one's ("fall-dramatization" is the two shots back to back). Where each take
sits in the episode is found in the episode's own sound (the take is
correlated against it), so nothing about the cut needs to be stored. The
picture is set 9:16: the episode's frame large in the middle over a blurred
copy of itself, the hook in two lines at the top, the words big at the
bottom as they are said, and an end card pointing to the full video.

Writes OUT/short.mp4 and OUT/short.json (length, spans, music parts).
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

SW, SH, FPS = 1080, 1920, 30
MAIN_Y, MAIN_H = 470, 1000          # the episode's frame, cropped to the width
DISSOLVE = 0.8                      # the episode's shots dissolve in over this
LEAD, TAIL = 0.1, 0.5               # sound kept before and after the voice
END_CARD = 2.6
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


def _cover(img, w, h):
    ar = w / h
    if img.width / img.height > ar:
        nw = int(img.height * ar)
        img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
    else:
        nh = int(img.width / ar)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
    return img.resize((w, h), Image.LANCZOS)


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


def compose(src, top, caption, t_short, end_card=0.0):
    """One 9:16 frame from the episode's frame `src` (PIL, 16:9)."""
    bg = _cover(src, SW // 12, SH // 12).filter(ImageFilter.GaussianBlur(3)).resize((SW, SH))
    bg = Image.blend(bg, Image.new("RGB", bg.size, (0, 0, 0)), 0.55)
    scale = MAIN_H / src.height
    big = src.resize((int(src.width * scale), MAIN_H), Image.LANCZOS)
    x0 = (big.width - SW) // 2
    bg.paste(big.crop((x0, 0, x0 + SW, MAIN_H)), (0, MAIN_Y))
    d = ImageDraw.Draw(bg, "RGBA")
    d.rectangle([0, MAIN_Y - 4, SW, MAIN_Y], fill=RED + (255,))
    _brand(d)
    lines = [x.strip() for x in top.split("|") if x.strip()]
    for i, line in enumerate(lines[:2]):
        _text(d, line, SW / 2, 210 + i * 110, 84, WHITE if i == 0 else RED)
    if caption and not end_card:
        words, now = caption
        f_size = 92
        line = " ".join(w for w, _, _ in words).upper()
        while _font("InterDisplay-Black.otf", f_size).getlength(line) > SW - 100 and f_size > 40:
            f_size -= 4
        fnt = _font("InterDisplay-Black.otf", f_size)
        x = (SW - fnt.getlength(line)) / 2
        y = MAIN_Y + MAIN_H + 150
        starts = [a for _, a, _ in words]
        lit = max((i for i, a in enumerate(starts) if a <= now), default=None)
        for i, (w, a, b) in enumerate(words):
            s = w.upper()
            col = (255, 214, 64) if i == lit else WHITE
            d.text((x, y), s, font=fnt, fill=col, anchor="lm", stroke_width=6, stroke_fill=(0, 0, 0))
            x += fnt.getlength(s + " ")
    if end_card:
        k = min(1.0, end_card / 0.35)
        shade = Image.new("RGBA", bg.size, (4, 10, 20, int(200 * k)))
        bg.paste(shade, (0, 0), shade)
        d = ImageDraw.Draw(bg, "RGBA")
        a = int(255 * k)
        _text(d, "THE FULL STORY", SW / 2, 820, 96, (255, 255, 255, a))
        _text(d, "HOW IT FAILED, STEP BY STEP", SW / 2, 930, 52, RED + (a,), "InterDisplay-Bold.otf")
        _text(d, "full video on the channel", SW / 2, 1060, 44, DIM + (a,), "Inter-Bold.otf")
        _brand(d)
    return bg


def build(prep, episode_mp4, out_dir, spans, top):
    from score import boom
    os.makedirs(out_dir, exist_ok=True)
    cuts, sheet = plan(prep, episode_mp4, spans)
    # the sound: each span from the episode's own mix, a short crossfade
    # between spans, then a hit under the end card
    xf = int(0.12 * SR)
    sound = np.zeros(0, np.float32)
    for c in cuts:
        a = _audio(episode_mp4, SR, c["start"], c["end"] - c["start"])
        if len(sound):
            a = a.copy()
            a[:xf] *= np.linspace(0, 1, xf, dtype=np.float32)
            sound[-xf:] *= np.linspace(1, 0, xf, dtype=np.float32)
        sound = np.concatenate([sound, a])
    hit = boom()[:, 0] * 0.6
    tail = np.zeros(int(END_CARD * SR), np.float32)
    tail[: min(len(tail), len(hit))] += hit[: len(tail)]
    tail *= np.linspace(1, 0, len(tail), dtype=np.float32) ** 0.5
    sound = np.concatenate([sound, tail])
    sound[: int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR), dtype=np.float32)
    wav = os.path.join(out_dir, "short.wav")
    import soundfile as sf
    sf.write(wav, np.clip(sound, -1, 1), SR)
    from score import even_loudness
    wav = even_loudness(wav, os.path.join(out_dir, "short_even.wav"), target=-14.0)

    total = len(sound) / SR
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-i", wav,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k",
                            "-shortest", os.path.join(out_dir, "short.mp4")], stdin=subprocess.PIPE)
    t_short, last = 0.0, None
    for c in cuts:
        length = c["end"] - c["start"]
        # the first frames of a shot still carry the dissolve from the one
        # before it: they hold on the first clean frame instead
        clean = max(c["start"], c["shot_start"] + DISSOLVE)
        w, h = 1280, 720
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{clean:.3f}", "-t",
                                f"{c['end'] - clean:.3f}", "-i", episode_mp4, "-f", "rawvideo",
                                "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-"],
                               stdout=subprocess.PIPE)
        groups = chunks(c["words"])
        n_frames = int(round(length * FPS))
        frame = None
        for k in range(n_frames):
            t_ep = c["start"] + k / FPS
            if t_ep >= clean or frame is None:
                raw = dec.stdout.read(w * h * 3)
                if len(raw) == w * h * 3:
                    frame = Image.frombytes("RGB", (w, h), raw)
                elif frame is None:
                    frame = Image.new("RGB", (w, h))
            cap = next((g for g in groups if g[0][1] - 0.05 <= t_ep < g[-1][2] + 0.15), None)
            img = compose(frame, top, (cap, t_ep) if cap else None, t_short + k / FPS)
            enc.stdin.write(img.tobytes())
        dec.stdout.close()
        dec.wait()
        last = frame
        t_short += n_frames / FPS
    for k in range(int(round((total - t_short) * FPS))):
        enc.stdin.write(compose(last, top, None, t_short, end_card=(k + 1) / FPS).tobytes())
    enc.stdin.close()
    enc.wait()
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
    ap.add_argument("--top", required=True, help="the hook, two lines split by |")
    a = ap.parse_args()
    build(a.prep, a.episode, a.out, [s.strip() for s in a.spans.split(",") if s.strip()], a.top)
