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
    joint = lambda n: next((v for k, v in (anchors.get(str(n)) or {}).items() if k in ("node", "nut", "joint", "panel", "hole")),
                           None)
    at = joint
    # the part glowing; the structure going down (the walkways drop at 22.0
    # and are out of the shot a second later, the bridge's span falls slower)
    fall = {"hanging_walkways": 22.35, "fuselage": 22.9, "orbiter": 22.6, "earth_dam": 23.0}.get(sheet["kit"]["variant"], 23.4)
    c, fl = tm.frame(17.5), tm.frame(fall)
    made = thumbnail.build(sheet, find_frame(raw3d, c), find_frame(raw3d, fl), at(fl), out, at(c))
    json.dump({"figures": thumbnail.figures(sheet), "made": made},
              open(os.path.join(out, "thumbs.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(made, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
