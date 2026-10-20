"""
Photographs from an official investigation report (owner, 2026-10-20:
Wikimedia had four Hyatt Regency pictures). Reports by US federal agencies
(the National Bureau of Standards, the NTSB) are public domain and carry the
best pictures of a disaster there are: the structure before, the wreckage,
the failed part up close.

The old reports are page scans, so a photo is found on its page: the page is
rendered, blurred, and the large dark blocks that are not text are cut out,
each with the page's figure caption as what it shows. Diagrams and graphs
come out too; the photo picker (episode.pick_photos) turns away what fits
no shot.

    cands = figures(url, out_dir, credit="National Bureau of Standards, BSS 143 (1982)")
    # [{"path", "title", "about", "credit", "width", "height", "year"}]
"""

import glob
import os
import re
import subprocess

import numpy as np
from PIL import Image, ImageFilter

DPI = 110
MIN_W, MIN_H = 0.38, 0.16          # of the page: smaller blocks are text or logos
DARK = 200                         # a blurred text page stays lighter than this


def blocks(page):
    """(x0, y0, x1, y1) of the picture blocks on a page image (grayscale)."""
    g = np.asarray(page.convert("L").filter(ImageFilter.GaussianBlur(page.width / 120)), np.float32)
    mask = g < DARK
    h, w = mask.shape
    rows = mask.mean(axis=1) > 0.35
    out, y = [], 0
    while y < h:
        if not rows[y]:
            y += 1
            continue
        y0 = y
        while y < h and rows[y]:
            y += 1
        if y - y0 < MIN_H * h:
            continue
        cols = mask[y0:y].mean(axis=0) > 0.5
        xs = np.flatnonzero(cols)
        if len(xs) and xs[-1] - xs[0] >= MIN_W * w:
            out.append((int(xs[0]), y0, int(xs[-1]) + 1, y))
    return out


def captions(text):
    """The figure captions on a page: "Figure 2.3 View of the atrium ..."."""
    lines = [ln.strip() for ln in text.splitlines()]
    found = []
    for i, ln in enumerate(lines):
        if re.match(r"^(fig(ure)?\.?)\s*\d", ln, re.I):
            cap = ln
            for nxt in lines[i + 1:i + 3]:          # captions run onto a second line
                if not nxt or re.match(r"^(fig(ure)?\.?)\s*\d", nxt, re.I):
                    break
                cap += " " + nxt
            found.append(re.sub(r"\s+", " ", cap)[:300])
    return found


def figures(url_or_path, out_dir, credit, year=None, limit=40):
    os.makedirs(out_dir, exist_ok=True)
    pdf = url_or_path
    if re.match(r"https?://", url_or_path):
        pdf = os.path.join(out_dir, "report.pdf")
        if not os.path.exists(pdf):
            subprocess.run(["curl", "-sSL", "-m", "600", "-o", pdf, url_or_path], check=True)
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    pages = text.split("\f")
    # only the pages that carry a figure caption are rendered
    want = [i + 1 for i, t in enumerate(pages) if captions(t)]
    print(f"  report: {len(pages)} pages, {len(want)} with figures")
    out = []
    for p in want:
        if len(out) >= limit:
            break
        stem = os.path.join(out_dir, f"page{p:04d}")
        subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-f", str(p), "-l", str(p), "-png", pdf, stem],
                       check=True)
        made = sorted(glob.glob(stem + "*.png"))
        if not made:
            continue
        page = Image.open(made[0])
        caps = captions(pages[p - 1])
        for k, (x0, y0, x1, y1) in enumerate(blocks(page)):
            crop = page.crop((x0, y0, x1, y1)).convert("RGB")
            path = os.path.join(out_dir, f"fig_{p:04d}_{k}.jpg")
            crop.save(path, quality=92)
            cap = caps[min(k, len(caps) - 1)] if caps else f"Report page {p}"
            out.append({"path": path, "title": cap[:120], "about": cap, "credit": f"{credit} — Public domain",
                        "width": crop.width, "height": crop.height, "year": year, "url": f"{url_or_path}#page={p}"})
        os.remove(made[0])
    print(f"  report: {len(out)} picture(s) cut out")
    return out
