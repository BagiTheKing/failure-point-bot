"""
What an investigation report gives (src/report_figures.py): cuts its
pictures out and lays them on contact sheets with their captions, to judge
before an episode uses them (.github/workflows/report_probe.yml).

    python tools/report_probe.py URL OUT --credit "..."
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--credit", default="Investigation report")
    a = ap.parse_args()
    from report_figures import figures
    got = figures(a.url, os.path.join(a.out, "figures"), a.credit)
    json.dump(got, open(os.path.join(a.out, "figures.json"), "w"), indent=1, ensure_ascii=False)
    fnt = ImageFont.truetype(os.path.join(os.path.dirname(__file__), "..", "fonts", "Inter-Medium.otf"), 13)
    per, cw, ch = 12, 400, 300
    for s in range(0, len(got), per):
        sheet = Image.new("RGB", (cw * 4, (ch + 40) * 3), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for k, c in enumerate(got[s:s + per]):
            im = Image.open(c["path"]).convert("RGB")
            im.thumbnail((cw - 8, ch - 8))
            x, y = (k % 4) * cw, (k // 4) * (ch + 40)
            sheet.paste(im, (x + 4, y + 4))
            d.text((x + 4, y + ch + 2), f"{s + k}: {c['title'][:60]}", fill=(230, 230, 230), font=fnt)
            d.text((x + 4, y + ch + 18), f"{c['width']}x{c['height']}", fill=(150, 150, 150), font=fnt)
        sheet.save(os.path.join(a.out, f"sheet_{s // per:02d}.jpg"), quality=85)
    print(f"{len(got)} pictures")


if __name__ == "__main__":
    main()
