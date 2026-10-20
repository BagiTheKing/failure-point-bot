"""
The episode's signature preview (owner, 2026-10-20: "we just need to survive
that first one minute"): right after the cold open, about ten seconds that
show what the viewer is about to get, then a beat of silence, then the
episode. The same four words every time, so they become the channel's own:

    The flaw. The forces. The failure. And the fix.
    Stay to the end, and you'll understand this disaster better than the
    people who signed off on it.

Each word lands on a cut to the episode's own picture of it: the failing
part in 3D, the 2D physics as it tears, the 3D collapse, the as-designed
against as-built verdict; a slow 3D shot under the last sentence. Shots are
found in the finished episode by their sound (tools/highlight_short.py), so
nothing is rendered again.

    python tools/preview.py PREP EPISODE_DIR OUT [--splice]

Writes OUT/preview.mp4; with --splice also OUT/episode.mp4 (the preview set
in after the cold open) and OUT/episode.json (its chapters moved).
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

WORDS = ["The flaw.", "The forces.", "The failure.", "And the fix."]
CLOSE = "Stay to the end, and you'll understand this disaster better than the people who signed off on it."
CAPTIONS = ["THE FLAW", "THE FORCES", "THE FAILURE", "THE FIX"]
KEYS = ["flaw", "forces", "failure", "fix", "stay"]
W, H, FPS, SR = 1280, 720, 30, 48000
LEAD = 0.25                  # the voice starts this long into the preview
PAUSE = 0.8                  # the beat of silence before the episode
FONTS = os.path.join(HERE, "..", "fonts")
RED, WHITE = (255, 75, 58), (255, 255, 255)
BED = "Volatile Reaction - Kevin MacLeod.mp3"


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def sources(prep, episode_mp4):
    """Where each cut's picture is in the episode: {key: start seconds}, and
    where the cold open ends (the preview goes in there)."""
    from highlight_short import plan
    cuts, _ = plan(prep, episode_mp4, ["connection", "physics", "dramatization", "compare", "load_path", "photo"])
    at = {c["span"]: c for c in cuts}
    return {"flaw": at["connection"]["end"] - 2.8,           # the part red-hot, close up
            "forces": at["physics"]["end"] - 3.6,            # the tear
            "failure": at["dramatization"]["shot_start"] - 0.3,   # the drop
            "fix": at["compare"]["end"] - 2.8,               # HOLDS / FAILS
            "stay": at["load_path"]["shot_start"] + 1.5}, at["photo"]["shot_start"]


def voice(out_dir):
    """The signature, voiced, with its word timings."""
    import narration
    text = " ".join(WORDS + [CLOSE])
    took = narration.record({"shots": [{"clip": "preview", "narration": text}]}, out_dir)["preview"]
    words = narration.words_of(text, took["wav"])
    times = {}
    for key in KEYS:
        t = narration.find_word(words, key)
        times[key] = LEAD + (t if t is not None else 0.0)
    return took, times, words


def _cut_list(times, total_voice):
    """[(key, start, end)] in preview seconds: each picture from just before
    its word to just before the next."""
    marks = [0.0] + [max(0.0, times[k] - 0.08) for k in KEYS[1:]]
    end = LEAD + total_voice + 0.35
    spans = []
    for i, k in enumerate(KEYS):
        a = marks[i]
        b = marks[i + 1] if i + 1 < len(KEYS) else end
        spans.append((k, a, max(a + 0.4, b)))
    return spans, end


def _frames(episode_mp4, start, n):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", episode_mp4, "-frames:v", str(n),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-"],
                         capture_output=True, check=True).stdout
    size = W * H * 3
    out = [Image.frombytes("RGB", (W, H), raw[i:i + size]) for i in range(0, len(raw) - size + 1, size)]
    while len(out) < n:
        out.append(out[-1] if out else Image.new("RGB", (W, H)))
    return out


def _push(img, k):
    z = 1.0 + 0.06 * k
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)


def _glitch(img, k):
    r, g, b = img.split()
    off = int(14 * k)
    return Image.merge("RGB", (ImageChops.offset(r, off, 0), g, ImageChops.offset(b, -off, 0)))


def _caption(img, text, k, words_left=None):
    d = ImageDraw.Draw(img, "RGBA")
    f = _font("InterDisplay-Black.otf", 74)
    tw = f.getlength(text)
    x, y = (W - tw) / 2, H - 170
    a = int(255 * min(1, k * 4))
    d.text((x + 3, y + 3), text, font=f, fill=(0, 0, 0, int(a * 0.6)))
    d.text((x, y), text, font=f, fill=WHITE + (a,))
    sweep = tw * min(1, k * 2.5)
    d.rectangle([x, y + 92, x + sweep, y + 99], fill=RED + (a,))


def _pill(img, text, alpha):
    d = ImageDraw.Draw(img, "RGBA")
    f = _font("Inter-Bold.otf", 18)
    tw = f.getlength(text)
    d.rounded_rectangle([40, 34, 40 + tw + 30, 70], radius=8, fill=(0, 0, 0, int(160 * alpha)))
    d.ellipse([52, 47, 62, 57], fill=RED + (int(255 * alpha),))
    d.text((70, 52), text, font=f, fill=WHITE + (int(255 * alpha),), anchor="lm")


def _close_lines(img, t_since, words, t0):
    """The last sentence on screen, its second half in red: the promise."""
    d = ImageDraw.Draw(img, "RGBA")
    first, second = "STAY TO THE END", "AND YOU'LL UNDERSTAND IT BETTER THAN THE PEOPLE WHO SIGNED OFF ON IT"
    a1 = min(1, t_since * 3)
    f1, f2 = _font("InterDisplay-Black.otf", 60), _font("InterDisplay-Black.otf", 34)
    d.text((W / 2, H - 196), first, font=f1, fill=WHITE + (int(255 * a1),), anchor="mm")
    k2 = min(1, max(0, t_since - 0.9) * 2)
    while f2.getlength(second) > W - 120:
        f2 = _font("InterDisplay-Black.otf", f2.size - 2)
    d.text((W / 2, H - 132), second, font=f2, fill=RED + (int(255 * k2),), anchor="mm")


def build(prep, episode_dir, out_dir):
    import soundfile as sf
    from score import add_sfx, boom, even_loudness, mix, riser, whoosh
    os.makedirs(out_dir, exist_ok=True)
    episode_mp4 = os.path.join(episode_dir, "episode.mp4")
    src, hook_end = sources(prep, episode_mp4)
    took, times, words = voice(os.path.join(out_dir, "voice"))
    spans, end = _cut_list(times, took["seconds"])
    total = end + PAUSE

    # sound first: the voice over a tense bed, a whoosh into every cut, a
    # riser under the promise into a soft hit, then the beat of silence
    print(f"  cuts: {[(k, round(a, 2), round(b, 2)) for k, a, b in spans]}", flush=True)
    voice_track = np.zeros(int(total * SR), np.float32)
    v, vsr = sf.read(took["wav"], dtype="float32")
    if vsr != SR:
        v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR * vsr, np.arange(len(v)), v).astype(np.float32)
    a0 = int(LEAD * SR)
    voice_track[a0:a0 + len(v)] += v[: len(voice_track) - a0]
    vwav = os.path.join(out_dir, "voice_track.wav")
    sf.write(vwav, voice_track, SR)
    mixed = os.path.join(out_dir, "mix.wav")
    credits = mix(vwav, [(0.0, end, BED, 0.22, 0.2)], total, mixed)
    sfx = [(max(0.0, a - 0.25), whoosh(20 + i) * 0.35) for i, (_, a, _) in enumerate(spans) if a > 0]
    stay = spans[-1][1]
    sfx.append((stay, riser(max(1.0, end - stay), 7) * 0.22))
    sfx.append((end - 0.05, boom(6) * 0.3))
    add_sfx(mixed, sfx, mixed)
    data, _ = sf.read(mixed, dtype="float32", always_2d=True)
    data[int((end + 0.5) * SR):] *= 0.0                                   # the beat of silence
    sf.write(mixed, data, SR)
    even = even_loudness(mixed, os.path.join(out_dir, "mix_even.wav"))
    print("  sound mixed", flush=True)

    # picture, streamed into the encoder a frame at a time
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", even, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                            os.path.join(out_dir, "preview.mp4")], stdin=subprocess.PIPE)
    count = 0
    for i, (key, a, b) in enumerate(spans):
        n = int(round((b - a) * FPS))
        for j, img in enumerate(_frames(episode_mp4, src[key], n)):
            k = j / max(1, n - 1)
            img = _push(img, k)
            t_local = j / FPS
            if t_local < 2 / FPS and i > 0:
                img = _glitch(img, 1 - t_local * 15)
            if t_local < 3 / FPS:
                img = Image.blend(img, Image.new("RGB", img.size, WHITE), 0.55 * (1 - t_local * 10))
            _pill(img, "COMING UP", 1.0)
            if key == "stay":
                _close_lines(img, t_local, words, a)
            else:
                _caption(img, CAPTIONS[i], t_local)
            enc.stdin.write(img.tobytes())
            count += 1
        print(f"  {key}: {n} frames from {src[key]:.2f} s", flush=True)
    brand = Image.new("RGB", (W, H), (4, 10, 20))
    d = ImageDraw.Draw(brand)
    d.text((W / 2, H / 2), "THE POINT OF FAILURE", font=_font("Inter-Bold.otf", 30), fill=(170, 186, 210), anchor="mm")
    for j in range(int(round(PAUSE * FPS))):
        k = min(1, j / (PAUSE * FPS * 0.4))
        img = Image.blend(Image.new("RGB", (W, H)), brand, k * (1 - max(0, j / (PAUSE * FPS) - 0.7) / 0.3))
        enc.stdin.write(img.tobytes())
        count += 1
    enc.stdin.close()
    enc.wait()
    info = {"seconds": round(count / FPS, 2), "hook_end": round(hook_end, 3), "sources": src,
            "spans": spans, "music_credits": credits}
    json.dump(info, open(os.path.join(out_dir, "preview.json"), "w"), indent=1)
    print(f"preview: {info['seconds']} s, set in at {hook_end:.2f} s")
    return info


def splice(episode_dir, out_dir, info):
    """The episode with the preview after its cold open; chapters moved."""
    from score import even_loudness
    ep = os.path.join(episode_dir, "episode.mp4")
    pv = os.path.join(out_dir, "preview.mp4")
    at = info["hook_end"]
    raw = os.path.join(out_dir, "spliced_raw.mp4")
    fc = (f"[0:v]trim=0:{at},setpts=PTS-STARTPTS[v0];[0:a]atrim=0:{at},asetpts=PTS-STARTPTS,afade=t=out:st={at - 0.25}:d=0.25[a0];"
          f"[1:v]setpts=PTS-STARTPTS[v1];[1:a]asetpts=PTS-STARTPTS[a1];"
          f"[0:v]trim=start={at},setpts=PTS-STARTPTS[v2];[0:a]atrim=start={at},asetpts=PTS-STARTPTS,afade=t=in:d=0.3[a2];"
          "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ep, "-i", pv, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "pcm_s16le", raw.replace(".mp4", ".mkv")], check=True)
    wav = os.path.join(out_dir, "spliced.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw.replace(".mp4", ".mkv"), "-vn", "-ac", "2", "-ar", "48000", wav],
                   check=True)
    even = even_loudness(wav, os.path.join(out_dir, "spliced_even.wav"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw.replace(".mp4", ".mkv"), "-i", even, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    os.path.join(out_dir, "episode.mp4")], check=True)
    e = json.load(open(os.path.join(episode_dir, "episode.json")))
    shift = info["seconds"]
    moved = []
    for i, ch in enumerate(e.get("chapters", [])):
        m = re.match(r"^(\d+):(\d\d) (.*)$", ch)
        if not m or i == 0:
            moved.append(ch)
            continue
        t = int(m.group(1)) * 60 + int(m.group(2)) + int(round(shift))
        moved.append(f"{t // 60}:{t % 60:02d} {m.group(3)}")
    e["chapters"] = moved
    e["seconds"] = e.get("seconds", 0) + shift
    e["preview"] = info
    json.dump(e, open(os.path.join(out_dir, "episode.json"), "w"), indent=1, ensure_ascii=False)
    print("chapters:", " | ".join(moved))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("prep")
    ap.add_argument("episode_dir")
    ap.add_argument("out")
    ap.add_argument("--splice", action="store_true")
    a = ap.parse_args()
    info = build(a.prep, a.episode_dir, a.out)
    if a.splice:
        splice(a.episode_dir, a.out, info)
