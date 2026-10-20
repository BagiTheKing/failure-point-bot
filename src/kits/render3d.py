"""
Renders a sheet's 3D model, whichever kit it belongs to.

    python -m kits.render3d sheet.json out_dir [--first N --last M] [--samples S] [--still F]
"""

import argparse
import importlib
import json

MODELS = {"hanging_walkways": "kits.hanging_walkway_3d", "truss_bridge": "kits.truss_bridge_3d",
          "fuselage": "kits.fuselage_3d"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("out_dir")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--still", type=int, default=0)
    a = ap.parse_args()
    sheet = json.load(open(a.sheet))
    mod = importlib.import_module(MODELS[sheet["kit"]["variant"]])
    mod.render(sheet, a.out_dir, a.first, a.last or None, a.samples, a.still)
