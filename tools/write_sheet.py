"""
Step 5a, end to end for one story: research -> verified fact sheet -> the
writer's animation sheet -> the 2D kit reel rendered from it (no 3D, no
voice), so the sheet can be judged on screen.

    python tools/write_sheet.py "I-35W Mississippi River bridge collapse" truss_bridge out/
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)


def main(topic, variant, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    import story_mode as sm
    from llm_provider import get_pool
    from longform_llm import _call
    from sheet_writer import write_sheet
    pool = get_pool()
    article = sm.gather(pool, topic, _call)
    if not article:
        sys.exit("no article")
    facts = sm.fact_sheet(pool, topic, article, _call)
    if not facts:
        sys.exit("no fact sheet")
    json.dump(facts, open(os.path.join(out_dir, "facts.json"), "w"), indent=1, ensure_ascii=False)
    sheet = write_sheet(pool, topic, article, facts, variant, _call)
    if not sheet:
        sys.exit("no animation sheet")
    path = os.path.join(out_dir, "sheet.json")
    json.dump(sheet, open(path, "w"), indent=2, ensure_ascii=False)
    print(json.dumps({s["clip"]: s["narration"] for s in sheet["shots"]}, indent=1, ensure_ascii=False))
    from mixed_sample import KITS, frames_of, join
    from kits.blueprint import render_clip
    from kits import common
    k = KITS[variant](sheet)
    D = k.durations()
    work = os.path.join(out_dir, "_work")
    segs = []
    for name, fn, T, trans in (("build", k.build, D["build"], "cut"),
                               ("physics", k.physics, D["physics"], "cut"),
                               ("fall", k.fall, D["fall"], "dissolve"),
                               ("timeline", common.timeline(sheet), 7.0, "dissolve"),
                               ("compare", k.compare, D["compare"], "dissolve"),
                               ("today", common.today(sheet), 8.0, "cut")):
        mp4 = os.path.join(work, f"{name}.mp4")
        os.makedirs(work, exist_ok=True)
        render_clip(fn, T, mp4)
        segs.append((frames_of(mp4, os.path.join(work, name)), trans))
    join(segs, os.path.join(out_dir, "kit_from_written_sheet.mp4"), work)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
