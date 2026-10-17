"""
A full mixed sample from one animation sheet: real photo, 3D analysis, 2D
kit diagrams, the accurate 3D fall, then the AI dramatization, cut together
with the channel's transition rules.

    python tools/mixed_sample.py SHEET RAW3D OUT_DIR [--photo P] [--ai CLIP]

RAW3D holds the rendered 3D frames (0001.png ...) and their anchors_*.json
(src/kits/hanging_walkway_3d.py). Writes OUT_DIR/mixed_sample.mp4 and
OUT_DIR/kit_2d_with_fall.mp4 (the 2D kit alone, its own fall included).
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from kits import common  # noqa: E402
from kits.blueprint import W, H, FPS, SS, LINE, ease, prog, render_clip, encode, Frame, font  # noqa: E402
from kits.hanging_walkway import HangingWalkways  # noqa: E402
from kits.truss_bridge import TrussBridge  # noqa: E402

KITS = {"hanging_walkways": HangingWalkways, "truss_bridge": TrussBridge}

SHOT_3D = {"establish": (0, 7), "load_path": (7, 13), "connection": (13, 20), "fall": (20, 28)}
DISSOLVE = 0.8


def frames_of(mp4, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vf",
                    f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x091629,fps={FPS}",
                    os.path.join(out_dir, "%05d.png")], check=True)
    return sorted(glob.glob(os.path.join(out_dir, "*.png")))


def render_3d_part(sheet, raw, anchors, first_sec, last_sec, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for n in range(int(first_sec * FPS) + 1, int(last_sec * FPS) + 1):
        src = os.path.join(raw, f"{n:04d}.png")
        if not os.path.exists(src):
            continue
        img = common.overlay_3d(sheet, Image.open(src), n, anchors, (n - 1) / FPS)
        p = os.path.join(out_dir, f"{len(files):05d}.png")
        img.save(p)
        files.append(p)
    return files


def dramatization(clip, out_dir):
    """The AI clip, tagged as a dramatization so nobody takes it for footage."""
    files = frames_of(clip, out_dir + "_src")
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for i, p in enumerate(files):
        f = Frame()
        f.img = Image.open(p).convert("RGB").resize((W * SS, H * SS))
        f.d = ImageDraw.Draw(f.img, "RGBA")
        common.pill(f, "DRAMATIZATION", W - 40, 36, LINE, 15, "ra", 0.9)
        q = os.path.join(out_dir, f"{i:05d}.png")
        f.done().save(q)
        out.append(q)
    return out


def join(segments, out_mp4, work):
    """segments: [(frame files, transition into the next: 'cut' | 'dissolve')]."""
    reel = os.path.join(work, "_reel")
    os.makedirs(reel, exist_ok=True)
    k = int(DISSOLVE * FPS)
    seq, skip = [], 0
    for i, (files, trans) in enumerate(segments):
        files = files[skip:]
        skip = 0
        nxt = segments[i + 1][0] if i + 1 < len(segments) else None
        if nxt and trans == "dissolve" and len(files) > k and len(nxt) > k:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("raw3d")
    ap.add_argument("out_dir")
    ap.add_argument("--photo", default="")
    ap.add_argument("--ai", default="")
    a = ap.parse_args()
    sheet = json.load(open(a.sheet))
    kit = KITS[sheet["kit"]["variant"]](sheet)
    D = kit.durations()          # the kit's beats set its clips' lengths
    work = os.path.join(a.out_dir, "_work")
    os.makedirs(work, exist_ok=True)
    anchors = {}
    for p in glob.glob(os.path.join(a.raw3d, "anchors_*.json")):
        anchors.update(json.load(open(p)))

    def clip2d(name, fn, seconds):
        mp4 = os.path.join(work, f"{name}.mp4")
        render_clip(fn, seconds, mp4)
        return frames_of(mp4, os.path.join(work, name))

    seconds = {s["clip"]: s.get("seconds") for s in sheet["shots"]}
    phys = lambda t, T: kit.physics(t, T, lead=False)
    photo = clip2d("photo", common.photo(sheet, a.photo or None, tint_out=False), seconds["photo"])
    a3d = render_3d_part(sheet, a.raw3d, anchors, 0, SHOT_3D["connection"][1], os.path.join(work, "3d_a"))
    physics = clip2d("physics", phys, D["physics"])
    clock = clip2d("clock", common.clock(sheet), seconds["clock"])
    b3d = render_3d_part(sheet, a.raw3d, anchors, *SHOT_3D["fall"], os.path.join(work, "3d_b"))
    ai = dramatization(a.ai, os.path.join(work, "ai")) if a.ai and os.path.exists(a.ai) else []
    tl = clip2d("timeline", common.timeline(sheet), seconds["timeline"])
    comp = clip2d("compare", kit.compare, D["compare"])
    today = clip2d("today", common.today(sheet), seconds["today"])

    # transition rules: photo -> model dissolves; 3D close-up dissolves into the
    # blueprint of the same part; the failure itself is the one hard cut
    segs = [(photo, "dissolve"), (a3d, "dissolve"), (physics, "dissolve"), (clock, "cut"),
            (b3d, "cut" if ai else "dissolve")]
    if ai:
        segs.append((ai, "dissolve"))
    segs += [(tl, "dissolve"), (comp, "dissolve"), (today, "cut")]
    join([s for s in segs if s[0]], os.path.join(a.out_dir, "mixed_sample.mp4"), work)

    # the 2D kit on its own: build -> physics -> its own fall, one continuous shot
    b = clip2d("k_build", kit.build, D["build"])
    p = clip2d("k_phys", kit.physics, D["physics"])
    fl = clip2d("k_fall", kit.fall, D["fall"])
    cp = clip2d("k_comp", kit.compare, D["compare"])
    join([(b, "cut"), (p, "cut"), (fl, "dissolve"), (cp, "cut")],
         os.path.join(a.out_dir, "kit_2d_with_fall.mp4"), work)
    shutil.rmtree(work)


if __name__ == "__main__":
    main()
