"""
The episode's three thumbnails (src/kits/thumbnail.py) from its prep (sheet,
photos) and its 3D frames:

    python tools/thumbnails.py PREP RAW3D OUT
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))


def main(prep, raw3d, out):
    import episode
    from kits import thumbnail, timemap
    from kits.assemble import find_frame
    sheet = json.load(open(os.path.join(prep, "timed_sheet.json")))
    pj = os.path.join(prep, "photos.json")
    photos = json.load(open(pj)) if os.path.exists(pj) else {}
    pool = (photos.get("aftermath") or []) + (photos.get("photo") or []) + (photos.get("photos_disaster") or [])
    pick = episode.best_picture("collapsed bridge wreckage river span", pool) if pool else None
    tm = timemap.of(sheet)
    close = find_frame(raw3d, tm.frame(17.5))          # the connection close-up, the plate glowing
    fall = find_frame(raw3d, tm.frame(23.0))            # mid-fall
    made = thumbnail.build(sheet, pick and pick["path"], close, fall, out)
    json.dump({"figures": thumbnail.figures(sheet), "made": made,
               "photo": pick and {k: pick.get(k) for k in ("title", "credit")}},
              open(os.path.join(out, "thumbs.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(made, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
