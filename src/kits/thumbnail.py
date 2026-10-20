"""
Thumbnails for a kit episode, in the channel's own look (owner, 2026-10-19:
not the old channel's design; "we need the 3D and 2D work to promote the
video for us"). Three, for YouTube's Test & Compare or the rotation:

  model   our 3D collapse, a red callout ring on the joint that failed (its
          place on screen from the 3D model's own anchors), the toll huge;
  drawing our 2D blueprint of the part tearing, close in, the one figure that
          explains it (1/2 INCH) on a dimension line;
  xray    the 3D close-up of the part beside the 2D drawing of it, joined by
          a callout line: what you see and how it works.

All on the blueprint palette, inside a technical-drawing frame (corner
brackets, a title block "THE POINT OF FAILURE · I-35W · U10"), so every
thumbnail on the channel reads as the same drawing office.

    paths = build(sheet, close3d, fall3d, fall_anchor, out_dir)
"""

import copy
import os
import re

from PIL import Image, ImageDraw, ImageEnhance

from kits.blueprint import font, BG, CYAN, RED

W, H = 1280, 720
S = 2                                     # drawn at 2x, saved at 1x
WHITE = (255, 255, 255)
FRACTIONS = {0.5: "½", 0.25: "¼", 0.75: "¾", 0.125: "⅛"}


def _font(px, name="InterDisplay-Black.otf"):
    return font(name, max(1, px // 2))    # font() scales by its own SS of 2


def _cover(img, w=W * S, h=H * S, cx=0.5, cy=0.5, zoom=1.0):
    img = img.convert("RGB")
    ar = w / h
    cw = min(img.width, img.height * ar) / zoom
    ch = cw / ar
    x0 = min(max(0, img.width * cx - cw / 2), img.width - cw)
    y0 = min(max(0, img.height * cy - ch / 2), img.height - ch)
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.LANCZOS)


def _grade(img, contrast=1.2, bright=0.95):
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Brightness(img).enhance(bright)
    return Image.blend(img, Image.new("RGB", img.size, BG), 0.12)


def _grid(img, alpha=26, step=80):
    """The blueprint grid, faint, over everything."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, img.width, step * S // 2):
        d.line([(x, 0), (x, img.height)], fill=CYAN + (alpha,), width=1)
    for y in range(0, img.height, step * S // 2):
        d.line([(0, y), (img.width, y)], fill=CYAN + (alpha,), width=1)
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def _scrim(img, top=0.0, left=0.0, strength=200):
    m = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(m)
    if left:
        w = int(img.width * left)
        for x in range(w):
            d.line([(x, 0), (x, img.height)], fill=int(strength * (1 - x / w) ** 1.3))
    if top:
        h = int(img.height * top)
        for y in range(h):
            v = int(strength * (1 - y / h) ** 1.3)
            d.line([(0, y), (img.width, y)], fill=v)
    return Image.composite(Image.new("RGB", img.size, BG), img, m)


def _frame(d, label):
    """A technical drawing's border: corner brackets and a title block."""
    m, L, t = 26 * S, 70 * S, 4 * S
    for (x, y, sx, sy) in ((m, m, 1, 1), (W * S - m, m, -1, 1), (m, H * S - m, 1, -1),
                           (W * S - m, H * S - m, -1, -1)):
        d.line([(x, y), (x + sx * L, y)], fill=CYAN, width=t)
        d.line([(x, y), (x, y + sy * L)], fill=CYAN, width=t)
    f = _font(17 * S, "Inter-Bold.otf")
    tw = d.textlength(label, font=f)
    x1, y1 = W * S - m - 14 * S, H * S - m - 12 * S
    d.rectangle([x1 - tw - 28 * S, y1 - 34 * S, x1, y1], fill=BG + (230,), outline=CYAN, width=2 * S)
    d.text((x1 - 14 * S, y1 - 17 * S), label, font=f, fill=CYAN, anchor="rm")


def _headline(d, text, x, y, px, fill=WHITE, max_w=None, anchor="la"):
    if max_w:
        while px > 50 * S and d.textlength(text, font=_font(px)) > max_w:
            px -= 4 * S
    d.text((x, y), text, font=_font(px), fill=fill, anchor=anchor,
           stroke_width=max(2, px // 26), stroke_fill=BG)
    return px


def _ring(d, x, y, r):
    """The callout: a red ring with a tick, like a marked-up drawing."""
    d.ellipse([x - r, y - r, x + r, y + r], outline=RED, width=7 * S)
    d.ellipse([x - r - 14 * S, y - r - 14 * S, x + r + 14 * S, y + r + 14 * S], outline=RED + (120,), width=2 * S)


def _dimension(d, x0, x1, y, text):
    """A dimension line with arrowheads and its figure above it."""
    d.line([(x0, y), (x1, y)], fill=RED, width=5 * S)
    for x, s in ((x0, 1), (x1, -1)):
        d.polygon([(x, y), (x + s * 26 * S, y - 12 * S), (x + s * 26 * S, y + 12 * S)], fill=RED)
        d.line([(x, y - 34 * S), (x, y + 34 * S)], fill=RED, width=3 * S)
    d.text(((x0 + x1) / 2, y - 22 * S), text, font=_font(120 * S), fill=RED, anchor="md",
           stroke_width=5 * S, stroke_fill=BG)


def _tag(d, text, x, y, color=CYAN):
    f = _font(20 * S, "Inter-Bold.otf")
    tw = d.textlength(text, font=f)
    d.rectangle([x, y, x + tw + 24 * S, y + 36 * S], fill=BG, outline=color, width=2 * S)
    d.text((x + 12 * S, y + 18 * S), text, font=f, fill=color, anchor="lm")


def _save(img, path):
    img.resize((W, H), Image.LANCZOS).save(path, "JPEG", quality=93)
    return path


# --------------------------------------------------------------------------

def figures(sheet):
    """The words: the plate thickness or the multiplier, the toll, the part,
    the drawing's title block."""
    dvb = sheet.get("design_vs_built") or {}
    big = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(inch|in\b|mm)", str(dvb.get("plate_built", "")), re.I)
    if m:
        v = float(m.group(1))
        big = f"{FRACTIONS.get(v, m.group(1))} {'INCH' if m.group(2).lower().startswith('in') else 'MM'}"
    big = big or str(dvb.get("multiplier") or "").strip() or None
    nums = sheet.get("numbers") or []
    dead = None
    if nums and re.search(r"KILL|DEAD|DIED|DEATH", nums[0].get("label", "").upper()):
        dead = re.sub(r"[^0-9,]", "", str(nums[0]["value"]))
    kit = sheet.get("kit", {})
    # what failed, and the cause in two words: the hanger rods held at the
    # Hyatt; the nut pulled through the box beam after one design change
    part = {"truss_bridge": "STEEL PLATE", "hanging_walkways": "CONNECTION"}.get(kit.get("variant"), "PART")
    cause = {"truss_bridge": "ONE STEEL PLATE", "hanging_walkways": "ONE DESIGN CHANGE"}.get(
        kit.get("variant"), f"ONE {part}")
    name = (sheet["disaster"].get("photo_article") or "").replace("Mississippi River bridge", "").strip().upper()
    node = kit.get("failed_node_label", "")
    block = " · ".join(x for x in ("THE POINT OF FAILURE", name, node and f"JOINT {node}") if x)
    # a thickness "wasn't enough"; a load factor is what the change did
    why = (f"ONE CHANGE. {big} THE LOAD." if big and "×" in big
           else f"WHY {big} WASN'T ENOUGH" if big else "HOW IT FAILED")
    return {"big": big, "dead": dead, "part": part, "cause": cause, "why": why, "block": block}


def drawing_frame(sheet, which="tear"):
    """Our own 2D kit frame, without captions: the physics clip at the tear
    (the plate glowing, bowing), or the build clip's whole structure."""
    from episode import kit_class
    quiet = copy.deepcopy(sheet)
    for sh in quiet.get("shots", []):
        sh["caption"] = ""
    kit = kit_class(quiet["kit"]["variant"])(quiet)
    if (quiet.get("timing") or {}).get("kit"):
        kit.fit(quiet["timing"]["kit"])
    D = kit.durations()
    # the drawing alone: its words (labels, panels, captions) would be cut in
    # half by the thumbnail's close crop, so they are switched off
    from kits.blueprint import Frame
    saved = {n: getattr(Frame, n) for n in ("text", "label", "caption", "tag")}
    for n in saved:
        setattr(Frame, n, lambda self, *a, **k: None)
    try:
        if which == "tear":
            return kit.physics(D["physics"] - 0.4, D["physics"], lead=False)
        return kit.build(D["build"] - 0.4, D["build"])
    finally:
        for n, fn in saved.items():
            setattr(Frame, n, fn)


def _follow_down(img, ax, ay):
    """The joint's anchor is where it stood before the fall; mid-collapse the
    span is lower. Walk down the picture from there to the first bright steel
    or deck (the water and sky are dark) and put the ring on it."""
    g = img.convert("L")
    x = int(ax * g.width)
    for y in range(int(ay * g.height), int(g.height * 0.95), 2):
        box = g.crop((max(0, x - 6), y, min(g.width, x + 6), y + 4))
        if sum(box.getdata()) / max(1, box.width * box.height) > 140:
            return (y + 6) / g.height
    return ay


def model(fall3d, anchor, f, out, zoom=1.45):
    """Close in on the failing span and set it low in the frame, under the
    words; the ring follows the joint through the crop."""
    src = Image.open(fall3d)
    ax, ay = (anchor[0], anchor[1]) if anchor else (0.5, 0.5)
    if anchor:
        ay = _follow_down(src, ax, ay)
    cx, cy = ax, ay - 0.16 / zoom                      # the joint lands about two thirds down
    img = _grid(_grade(_cover(src, cx=cx, cy=cy, zoom=zoom), 1.3, 1.0), 18)
    img = _scrim(img, top=0.5, left=0.5, strength=225)
    d = ImageDraw.Draw(img, "RGBA")
    if anchor:
        # where the joint went in the crop (same arithmetic as _cover)
        ar = W / H
        cw = min(src.width, src.height * ar) / zoom
        ch = cw / ar
        x0 = min(max(0, src.width * cx - cw / 2), src.width - cw)
        y0 = min(max(0, src.height * cy - ch / 2), src.height - ch)
        x = (ax * src.width - x0) / cw * W * S
        y = (ay * src.height - y0) / ch * H * S
        _ring(d, x, y, 70 * S)
        _tag(d, f"{f['big'] or f['part']} · FAILED HERE", int(x - 150 * S), int(y + 95 * S), RED)
    big = f"{f['dead']} DEAD" if f["dead"] else (f["big"] or "")
    px = _headline(d, big, 70 * S, 60 * S, 190 * S, WHITE, max_w=W * S * 0.62)
    _headline(d, f["cause"], 74 * S, 60 * S + px * 0.92, 92 * S, RED)
    _frame(d, f["block"])
    return _save(img, out)


def drawing(frame2d, f, out):
    # close in on the joint: the plate sits around the middle of the physics frame
    img = _grid(_cover(frame2d, cx=0.5, cy=0.43, zoom=2.25), 14)   # the plate, the panels outside
    img = _scrim(img, top=0.32, strength=220)
    d = ImageDraw.Draw(img, "RGBA")
    if f["big"]:
        _dimension(d, int(W * S * 0.33), int(W * S * 0.67), int(H * S * 0.88), f["big"])
    _headline(d, f"THE {f['part']} THAT FAILED", W * S / 2, 54 * S, 104 * S, WHITE,
              max_w=W * S * 0.9, anchor="ma")
    _frame(d, f["block"])
    return _save(img, out)


def xray(close3d, frame2d, f, out, close_anchor=None):
    ax, ay = close_anchor[:2] if close_anchor else (0.5, 0.5)
    zoom = 1.15
    left = _grade(_cover(Image.open(close3d), W * S // 2, H * S, cx=ax, cy=ay, zoom=zoom), 1.3, 1.0)
    right = _cover(frame2d, W * S // 2, H * S, cx=0.5, cy=0.42, zoom=1.7)
    img = Image.new("RGB", (W * S, H * S), BG)
    img.paste(left, (0, 0))
    img.paste(right, (W * S // 2, 0))
    img = _grid(img, 16)
    img = _scrim(img, top=0.3, strength=210)
    d = ImageDraw.Draw(img, "RGBA")
    d.line([(W * S // 2, 0), (W * S // 2, H * S)], fill=CYAN, width=3 * S)
    # the callout joining the real-looking plate to its drawing
    # where the plate lands in the left half after the crop centred on it
    a, b = (int(W * S * 0.25), int(H * S * 0.5)), (int(W * S * 0.75), int(H * S * 0.5))
    _ring(d, a[0], a[1], 66 * S)
    _ring(d, b[0], b[1], 66 * S)
    d.line([(a[0] + 80 * S, a[1] - 10 * S), (b[0] - 80 * S, b[1] - 6 * S)], fill=RED, width=5 * S)
    _tag(d, "3D MODEL", 60 * S, H * S - 120 * S)
    _tag(d, "THE PHYSICS", W * S // 2 + 34 * S, H * S - 120 * S)
    _headline(d, f["why"], W * S / 2, 50 * S, 100 * S, WHITE, max_w=W * S * 0.92, anchor="ma")
    _frame(d, f["block"])
    return _save(img, out)


def build(sheet, close3d, fall3d, fall_anchor, out_dir, close_anchor=None):
    os.makedirs(out_dir, exist_ok=True)
    f = figures(sheet)
    made = {}
    try:
        tear = drawing_frame(sheet, "tear")
    except Exception as e:
        print(f"no 2D frame ({type(e).__name__}: {e})")
        tear = None
    if fall3d:
        made["model"] = model(fall3d, fall_anchor, f, os.path.join(out_dir, "thumb_model.jpg"))
    if tear is not None:
        made["drawing"] = drawing(tear, f, os.path.join(out_dir, "thumb_drawing.jpg"))
    if close3d and tear is not None:
        made["xray"] = xray(close3d, tear, f, os.path.join(out_dir, "thumb_xray.jpg"), close_anchor)
    return made
