"""
Finds where a video's picture stands still (owner, 2026-10-26: "if nothing
is happening for over 3 s, people just leave"; the house rule is no hold
over 1.5 s). Words changing on screen do not count: the rows the captions
and the title band sit in are left out with --ignore, so only the 3D, the
2D and the photos are measured.

    python tools/stillness.py VIDEO [--ignore 0:290 --ignore 1175:1435] [--json OUT]
    python tools/stillness.py --report short/short.json

A Short measures itself as it is made (tools/story_short.py: every frame
with everything but the spoken words), into short.json's "stillness";
--report reads that and exits 1 on a still stretch, before publishing.

Prints the picture's motion per half second (the share of pixels that
changed, at most, within it) and every still stretch; exits 1 if a stretch
of --longest seconds or more has under --floor % of its pixels changing.
"""

import argparse
import json
import subprocess
import sys

import numpy as np

W, H = 180, 320          # measured small: fast, and fine detail is not motion a viewer sees
STEP = 0.5


def motion(video, ignore=(), size=None):
    """Per half second: the most any one frame changed (% of measured pixels)."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                            "stream=width,height,r_frame_rate", "-of", "csv=p=0", video],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    vw, vh = int(probe[0]), int(probe[1])
    num, den = probe[2].split("/")
    fps = float(num) / float(den)
    w, h = size or ((W, H) if vh > vw else (H, W))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    keep = np.ones((h, w), bool)
    for a, b in ignore:                                   # rows in the video's own pixels
        keep[int(a * h / vh):int(np.ceil(b * h / vh))] = False
    changed = (np.abs(np.diff(frames, axis=0)) > 18)[:, keep].mean(axis=1) * 100
    return per_step(list(changed), fps)


def per_step(changed, fps):
    """Per-frame changes (%) to the most within each half second."""
    per = max(1, int(round(fps * STEP)))
    return [float(max(changed[i:i + per])) for i in range(0, len(changed) - per + 1, per)]


def changed_pct(a, b):
    """% of pixels that changed between two small grey frames (uint8 arrays)."""
    return float((np.abs(a.astype(np.int16) - b.astype(np.int16)) > 18).mean() * 100)


def still_runs(series, floor=0.5, longest=1.5):
    """[(from, to)] seconds where the picture stays under floor % for longest or more."""
    runs, start = [], None
    for i, v in enumerate(series + [floor + 1]):
        if v < floor and start is None:
            start = i
        elif v >= floor and start is not None:
            if (i - start) * STEP >= longest:
                runs.append((start * STEP, i * STEP))
            start = None
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--report", default=None, help="a Short's short.json: its own measure")
    ap.add_argument("--ignore", action="append", default=[], help="rows a:b left out (captions, bands)")
    ap.add_argument("--floor", type=float, default=0.5, help="%% of pixels changing below which it is still")
    ap.add_argument("--longest", type=float, default=1.5, help="seconds still allowed")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    if a.report:
        series = json.load(open(a.report))["stillness"]["motion"]
    else:
        ignore = [tuple(int(x) for x in r.split(":")) for r in a.ignore]
        series = motion(a.video, ignore)
    runs = still_runs(series, a.floor, a.longest)
    print(" ".join(f"{i * STEP:.1f}:{v:.1f}" for i, v in enumerate(series)))
    for s, e in runs:
        print(f"STILL {s:.1f}-{e:.1f} s ({e - s:.1f} s)")
    if a.json:
        json.dump({"step": STEP, "motion": [round(v, 2) for v in series], "still": runs,
                   "floor": a.floor, "longest": a.longest}, open(a.json, "w"), indent=1)
    print("no still stretch" if not runs else f"{len(runs)} still stretch(es)")
    sys.exit(1 if runs else 0)


if __name__ == "__main__":
    main()
