"""
The cold open alone, once per candidate intro track, from an episode
already voiced and rendered (its prep/ and 3D frames), so the intro can be
judged and tuned without cutting the whole episode.

    python tools/intro_sample.py PREP RAW3D OUT [--hook "a | b"] [--title T] [--tracks "A.mp3,B.mp3"]
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prep")
    ap.add_argument("raw3d")
    ap.add_argument("out")
    ap.add_argument("--hook", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--tracks", default="")
    a = ap.parse_args()
    import episode
    from episode_sample import _hook
    sheet = json.load(open(os.path.join(a.prep, "timed_sheet.json")))
    voiced = json.load(open(os.path.join(a.prep, "voiced.json")))
    if a.hook or a.title:
        voiced = {k: v for k, v in voiced.items() if not k.startswith("hook_")}
        voiced.update(_hook(sheet, a.prep, a.hook, a.title))
    load = lambda f, d: json.load(open(os.path.join(a.prep, f))) if os.path.exists(os.path.join(a.prep, f)) else d
    photos, footage = load("photos.json", {}), load("footage.json", [])
    os.makedirs(a.out, exist_ok=True)
    tracks = [t.strip() for t in a.tracks.split(",") if t.strip()] or [None]
    made = {}
    for t in tracks:
        slug = re.sub(r"[^a-z0-9]+", "_", (t or "default").lower().replace(".mp3", "")).strip("_")[:40]
        out = os.path.join(a.out, f"intro_{slug}.mp4")
        try:
            info = episode.build_intro(sheet, a.raw3d, photos, voiced, out,
                                       os.path.join(a.out, "_work_" + slug), footage, t)
            made[os.path.basename(out)] = {"track": t, **info}
        except Exception as e:
            print(f"intro with {t} failed: {type(e).__name__}: {e}")
    json.dump({"hook": sheet.get("hook"), "intros": made},
              open(os.path.join(a.out, "intros.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(made, indent=1))


if __name__ == "__main__":
    main()
