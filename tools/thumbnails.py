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
    from kits import thumbnail, timemap
    from kits.assemble import find_frame
    sheet = json.load(open(os.path.join(prep, "timed_sheet.json")))
    tm = timemap.of(sheet)
    anchors = {}
    for p in sorted(os.listdir(raw3d)):
        if p.startswith("anchors_"):
            anchors.update(json.load(open(os.path.join(raw3d, p))))
    at = lambda n: (anchors.get(str(n)) or {}).get("node")
    c, fl = tm.frame(17.5), tm.frame(23.4)             # the plate glowing; the span going down
    made = thumbnail.build(sheet, find_frame(raw3d, c), find_frame(raw3d, fl), at(fl), out, at(c))
    json.dump({"figures": thumbnail.figures(sheet), "made": made},
              open(os.path.join(out, "thumbs.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(made, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
