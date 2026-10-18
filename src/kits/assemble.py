"""
Cutting kit clips, 3D frames, AI clips and photos into one reel: the
channel's transition rules ('cut', 'dissolve', ('dissolve', seconds)) and
the frame-level helpers every assembler shares (tools/mixed_sample.py,
src/episode.py).
"""

import glob
import os
import shutil
import subprocess

from PIL import Image, ImageDraw

from kits import common
from kits.blueprint import W, H, FPS, SS, LINE, ease, prog, encode, Frame

DISSOLVE = 0.8


def frames_of(mp4, out_dir, cover=False):
    """cover: fill the frame (crop the overflow) instead of letterboxing, so
    a clip made from one of our frames keeps that frame's framing."""
    os.makedirs(out_dir, exist_ok=True)
    fit = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}" if cover else
           f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
           f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x091629")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vf", f"{fit},fps={FPS}",
                    os.path.join(out_dir, "%05d.png")], check=True)
    return sorted(glob.glob(os.path.join(out_dir, "*.png")))


def render_3d_part(sheet, raw, anchors, first_sec, last_sec, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for n in range(int(round(first_sec * FPS)) + 1, int(round(last_sec * FPS)) + 1):
        src = find_frame(raw, n)
        if not src:
            continue
        img = common.overlay_3d(sheet, Image.open(src), n, anchors, (n - 1) / FPS)
        p = os.path.join(out_dir, f"{len(files):05d}.png")
        img.save(p)
        files.append(p)
    return files


def dramatization(clip, out_dir, caption="", n_frames=None):
    """The AI clip, tagged as a dramatization so nobody takes it for footage.
    It carries on the 3D shot's caption, so nothing pops at the hand-over.
    n_frames: run on past the clip's end (a slow push-in on its last frame)
    while the narration needs it."""
    files = frames_of(clip, out_dir + "_src", cover=True)
    if n_frames:
        files = held(files, n_frames, out_dir + "_src")
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for i, p in enumerate(files):
        f = Frame()
        f.img = Image.open(p).convert("RGB").resize((W * SS, H * SS))
        f.d = ImageDraw.Draw(f.img, "RGBA")
        common.pill(f, "DRAMATIZATION", W - 40, 36, LINE, 15, "ra", 0.9)
        if caption:
            f.caption(caption, 1 - prog(i / FPS, 2.6, 3.0))
        q = os.path.join(out_dir, f"{i:05d}.png")
        f.done().save(q)
        out.append(q)
    return out


def join(segments, out_mp4, work):
    """segments: [(frame files, transition into the next)], the transition
    'cut', 'dissolve' or ('dissolve', seconds)."""
    reel = os.path.join(work, "_reel")
    os.makedirs(reel, exist_ok=True)
    seq, skip = [], 0
    for i, (files, trans) in enumerate(segments):
        files = files[skip:]
        skip = 0
        nxt = segments[i + 1][0] if i + 1 < len(segments) else None
        secs = trans[1] if isinstance(trans, tuple) else DISSOLVE
        k = max(1, int(secs * FPS))
        if nxt and trans != "cut" and len(files) > k and len(nxt) > k:
            seq += files[:-k]
            seq += [(a, b, (j + 1) / (k + 1)) for j, (a, b) in enumerate(zip(files[-k:], nxt[:k]))]
            skip = k
        else:
            seq += files
    for j, item in enumerate(seq):
        dst = os.path.join(reel, f"{j:05d}.png")
        if isinstance(item, tuple):
            a, b, w = item
            Image.blend(Image.open(a).convert("RGB"), Image.open(b).convert("RGB"), ease(w)).save(dst)
        else:
            shutil.copyfile(item, dst)
    encode(reel, out_mp4)
    shutil.rmtree(reel)
    print(f"{out_mp4}: {len(seq) / FPS:.1f} s")


def find_frame(raw, n):
    """A rendered 3D frame by number: PNG straight from Blender, or the JPEG
    the render shards ship to save space."""
    for ext in ("png", "jpg"):
        p = os.path.join(raw, f"{n:04d}.{ext}")
        if os.path.exists(p):
            return p
    return None


def to_mp4(files, mp4, keep=False):
    """Encodes a list of frame files as one clip; returns (mp4, frames)."""
    tmp = mp4 + "_seq"
    os.makedirs(tmp, exist_ok=True)
    for i, p in enumerate(files):
        dst = os.path.join(tmp, f"{i:05d}.png")
        if p.endswith(".png"):
            shutil.copyfile(p, dst) if keep else shutil.move(p, dst)
        else:
            Image.open(p).convert("RGB").save(dst)
    encode(tmp, mp4)
    shutil.rmtree(tmp)
    return mp4, len(files)


def slideshow(photos, seconds, caption="", credits=None, fade=0.8):
    """A clip of real photographs, each pushed in slowly, cross-fading into
    the next, the shot's caption first and each photo's credit in a corner.
    photos: image paths (ours or archive). Returns fn(t, T)."""
    credits = credits or [""] * len(photos)
    n = max(1, len(photos))
    per = seconds / n

    def frame(i, t):
        return common.ken_burns(photos[i], min(1.0, t / (per + fade)), 1 if i % 2 == 0 else -1)

    def clip(t, T):
        i = min(n - 1, int(t / per))
        local = t - i * per
        img = frame(i, local)
        if i + 1 < n and local > per - fade:
            img = Image.blend(img, frame(i + 1, 0.0), ease((local - (per - fade)) / fade))
        f = Frame()
        f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
        if credits[i]:
            from kits.blueprint import fit, DIM
            c = credits[i]
            f.text(c, W - 24, H - 16, fit(c, 12, "Inter-Medium.otf", 560), DIM,
                   "Inter-Medium.otf", screen=True, anchor="rs", alpha=0.85)
        if caption:
            f.caption(caption, prog(t, 0.3, 1.0) * (1 - prog(t, 4.5, 5.1)))
        return f.done()
    return clip


def held(files, n_frames, out_dir, zoom=0.07):
    """Runs a shot on past its last frame: a slow push-in on that frame
    until the shot has n_frames (for the AI clip, the 3D fall's settle)."""
    if len(files) >= n_frames:
        return files[:n_frames]
    os.makedirs(out_dir, exist_ok=True)
    last = Image.open(files[-1]).convert("RGB")
    extra = n_frames - len(files)
    out = list(files)
    for j in range(extra):
        z = 1.0 + zoom * ease((j + 1) / extra)
        cw, ch = last.width / z, last.height / z
        x0, y0 = (last.width - cw) / 2, (last.height - ch) / 2
        p = os.path.join(out_dir, f"h{j:05d}.png")
        last.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(last.size, Image.LANCZOS).save(p)
        out.append(p)
    return out


def xfade_join(segments, out_mp4):
    """segments: [(mp4, frames, transition into the next)], the transition
    'cut', 'dissolve' or ('dissolve', seconds). Joined by ffmpeg on encoded
    clips, so a 10-minute episode never sits on disk as single frames.
    Returns the frame each segment starts at (where its dissolve begins)."""
    if len(segments) == 1:
        shutil.copyfile(segments[0][0], out_mp4)
        return [0]
    starts, pos, chain, inputs = [0], 0, [], []
    for i, (mp4, n, trans) in enumerate(segments):
        inputs += ["-i", mp4]
        chain.append(f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[s{i}]")
    prev = "s0"
    for i, (mp4, n, trans) in enumerate(segments[:-1]):
        secs = trans[1] if isinstance(trans, tuple) else DISSOLVE
        k = 1 if trans == "cut" else max(1, int(secs * FPS))   # a cut: one shared frame
        k = min(k, n - 1, segments[i + 1][1] - 1)
        pos += n - k
        starts.append(pos)
        out = f"x{i}"
        chain.append(f"[{prev}][s{i + 1}]xfade=transition=fade:duration={k / FPS:.4f}:"
                     f"offset={pos / FPS:.4f}[{out}]")
        prev = out
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chain),
                    "-map", f"[{prev}]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                    out_mp4], check=True)
    return starts
