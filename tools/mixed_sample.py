"""
A full mixed sample from one animation sheet: real photo, 3D analysis, 2D
kit diagrams, then the collapse itself as ONE AI clip that starts from the
last 3D frame (owner, 2026-10-17: one fall per video, the AI's, and the
scene runs on without a cut). Without a fresh AI clip the accurate 3D fall
stands in. Cut together with the channel's transition rules.

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
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from kits import common  # noqa: E402
from kits.blueprint import FPS, render_clip  # noqa: E402
from kits.hanging_walkway import HangingWalkways  # noqa: E402
from kits.truss_bridge import TrussBridge  # noqa: E402
from kits import timemap  # noqa: E402
from kits.assemble import frames_of, render_3d_part, dramatization, join  # noqa: E402

from kits.fuselage import Fuselage  # noqa: E402
from kits.orbiter import Orbiter  # noqa: E402

KITS = {"hanging_walkways": HangingWalkways, "truss_bridge": TrussBridge, "fuselage": Fuselage,
        "orbiter": Orbiter}

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
    tm = timemap.of(sheet)
    a3d = render_3d_part(sheet, a.raw3d, anchors, 0, tm.window("connection")[1], os.path.join(work, "3d_a"))
    physics = clip2d("physics", phys, D["physics"])
    clock = clip2d("clock", common.clock(sheet), seconds["clock"])
    caps = {sh["clip"]: sh.get("caption", "") for sh in sheet["shots"]}
    ai_start = timemap.ai_start_frame(sheet)
    use_ai = bool(a.ai and os.path.exists(a.ai))
    # with the AI clip, the 3D shot stops on the very frame the clip was made
    # from; without it, the accurate 3D fall plays instead
    f0, f1 = tm.window("fall")
    last = ai_start / FPS if use_ai else f1
    b3d = render_3d_part(sheet, a.raw3d, anchors, f0, last, os.path.join(work, "3d_b"))
    ai = dramatization(a.ai, os.path.join(work, "ai"), caps.get("fall", "")) if use_ai else []
    tl = clip2d("timeline", common.timeline(sheet), seconds["timeline"])
    comp = clip2d("compare", kit.compare, D["compare"])
    today = clip2d("today", common.today(sheet), seconds["today"])

    # transition rules: photo -> model dissolves; the 3D close-up dissolves into
    # the blueprint of the same part; the 3D wide shot runs on into the AI
    # collapse (a few frames of dissolve smooth the render change, no cut)
    segs = [(photo, "dissolve"), (a3d, "dissolve"), (physics, "dissolve"), (clock, "cut"),
            (b3d, ("dissolve", 0.27) if ai else "dissolve")]
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
