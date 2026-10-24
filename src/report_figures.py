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

DPI = 220                          # crops about 1,200 px wide: sharp enough for HD
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


def _bilevel(img, mid=0.08):
    """True when a picture is nearly all pure black and pure white: a photo
    scanned to one bit (the Silver Bridge report's), which shows on screen as
    blobs, not as a picture."""
    g = np.asarray(img.convert("L"), np.uint8)
    return float(((g > 40) & (g < 215)).mean()) < mid


def _picture_pages(pdf, out_dir, dpi=40):
    """Pages of a scanned report that hold a picture block, from a quick low-resolution pass."""
    stem = os.path.join(out_dir, "scan")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", pdf, stem], check=True)
    out = []
    for path in sorted(glob.glob(stem + "*.png")):
        if blocks(Image.open(path)):
            out.append(int(re.search(r"(\d+)\.png$", path).group(1)))
        os.remove(path)
    return out


def _ocr(img):
    try:
        r = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "3"], input=_png(img),
                           capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "ignore")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _png(img):
    import io
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _ocr_captions(page):
    """(the page turned upright, its figure captions): a scanned report
    prints some figures sideways, captions and all."""
    for rot in (0, 90, 270):
        img = page.rotate(rot, expand=True) if rot else page
        caps = captions(_ocr(img))
        if caps:
            return img, caps
    return page, []


def figures(url_or_path, out_dir, credit, year=None, limit=40):
    os.makedirs(out_dir, exist_ok=True)
    pdf = url_or_path
    if re.match(r"https?://", url_or_path):
        pdf = os.path.join(out_dir, "report.pdf")
        if not os.path.exists(pdf):
            subprocess.run(["curl", "-sSL", "-m", "600", "-o", pdf, url_or_path], check=True)
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    pages = text.split("\f")
    scanned = len(text.split()) < 20 * max(1, len(pages))       # a scan with no text layer (NTSB, 1970)
    # only the pages that carry a figure caption are rendered
    want = _picture_pages(pdf, out_dir) if scanned else [i + 1 for i, t in enumerate(pages) if captions(t)]
    print(f"  report: {len(pages)} pages{' (a scan: captions read by OCR)' if scanned else ''}, "
          f"{len(want)} with figures")
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
        if scanned:
            page, caps = _ocr_captions(page)
            if not caps:                      # no caption read: a text page with a dark block, not a figure
                os.remove(made[0])
                continue
        else:
            caps = captions(pages[p - 1])
        found = blocks(page)
        for k, (x0, y0, x1, y1) in enumerate(found):
            # pictures and captions both run top to bottom; one caption for
            # several pictures (a, b) covers them all
            cap = caps[min(k, len(caps) - 1)] if caps else f"Report page {p}"
            # third-party material in a government report keeps its owner's
            # rights (the Hyatt report's TV frames are "courtesy of KMBC TV")
            if re.search(r"courtesy|videotape|copyright|©", cap, re.I):
                continue
            # a photo credited to a company, not the government ("(U. S. Steel Photo)"): its owner's too
            who = re.search(r"\(([^()]*?)\s*photo\)", cap, re.I)
            if who and not re.search(r"NBS|NTSB|Bureau|Board|Federal|Administration|Government|Survey|Navy|"
                                     r"Army|Corps|NASA|Department|Commission", who.group(1), re.I):
                continue
            crop = page.crop((x0, y0, x1, y1)).convert("RGB")
            if _bilevel(crop):                # a halftone scanned to pure black and white: unreadable on screen
                continue
            path = os.path.join(out_dir, f"fig_{p:04d}_{k}.jpg")
            crop.save(path, quality=92)
            label = (re.match(r"^\S+\s*[\d.]+\w?", cap) or [f"Page {p}"])[0]
            # "title — author — license", the way Commons credits read
            out.append({"path": path, "title": cap[:120], "about": cap,
                        "credit": f"{label} — {credit} — Public domain",
                        "width": crop.width, "height": crop.height, "year": year, "url": f"{url_or_path}#page={p}"})
        os.remove(made[0])
    print(f"  report: {len(out)} picture(s) cut out")
    return out
