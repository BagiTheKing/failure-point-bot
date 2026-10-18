"""
A full episode from an animation sheet, in two halves around the 3D render
(.github/workflows/episode_sample.yml):

    python tools/episode_sample.py prepare SHEET OUT [--ai]   # voice, timing, photos
    python tools/episode_sample.py assemble OUT RAW3D [--ai CLIP]

prepare writes OUT/timed_sheet.json (render the 3D model from it), the voice
takes, OUT/photos.json and OUT/shards.json (the render matrix). assemble
writes OUT/episode.mp4 and OUT/episode.json (length, chapters, credits).
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

FRAMES_PER_SHARD = 80


def prepare(sheet_path, out, ai=False):
    import episode
    from kits import timemap
    from kits.blueprint import FPS
    os.makedirs(out, exist_ok=True)
    sheet = json.load(open(sheet_path))
    sheet, _ = episode.prepare(sheet, out, ai=ai)
    frames = int(math.ceil(timemap.of(sheet).total * FPS)) + 1
    shards = list(range(int(math.ceil(frames / FRAMES_PER_SHARD))))
    json.dump({"frames": frames, "per": FRAMES_PER_SHARD, "shards": shards},
              open(os.path.join(out, "shards.json"), "w"))
    try:
        episode.gather_footage(sheet, out)
    except Exception as e:                 # footage is a bonus: photos carry part 1
        print(f"no footage ({type(e).__name__}: {e})")
        json.dump([], open(os.path.join(out, "footage.json"), "w"))
    try:
        episode.gather_photos(sheet, out)
    except Exception as e:                 # photos are a bonus: 3D stills stand in
        print(f"no photos ({type(e).__name__}: {e})")
        json.dump({}, open(os.path.join(out, "photos.json"), "w"))


def assemble(out, raw3d, ai):
    import episode
    sheet = json.load(open(os.path.join(out, "timed_sheet.json")))
    voiced = json.load(open(os.path.join(out, "voiced.json")))
    photos = json.load(open(os.path.join(out, "photos.json"))) if os.path.exists(
        os.path.join(out, "photos.json")) else {}
    fp = os.path.join(out, "footage.json")
    footage = json.load(open(fp)) if os.path.exists(fp) else []
    info = episode.build(sheet, raw3d, photos, voiced, os.path.join(out, "episode.mp4"),
                         os.path.join(out, "_work"), ai, footage)
    info["credits"] = sorted({p["credit"] for v in photos.values() for p in v if p.get("credit")} |
                             {c["credit"] for c in footage if c.get("credit")})
    info["ai_clip"] = bool(ai and os.path.exists(ai))
    json.dump(info, open(os.path.join(out, "episode.json"), "w"), indent=1, ensure_ascii=False)
    print("\n".join(info["chapters"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("sheet")
    p.add_argument("out")
    p.add_argument("--ai", action="store_true", help="time the fall for an AI clip")
    a = sub.add_parser("assemble")
    a.add_argument("out")
    a.add_argument("raw3d")
    a.add_argument("--ai", default="")
    args = ap.parse_args()
    if args.cmd == "prepare":
        prepare(args.sheet, args.out, args.ai)
    else:
        assemble(args.out, args.raw3d, args.ai)
