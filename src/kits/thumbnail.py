"""
Thumbnails for a kit episode: three looks from what the episode itself has
(its real wreckage photos and our own 3D renders), for the owner to pick or
to run in YouTube's Test & Compare:

  wreck  the strongest real photo of the wreckage, full frame, the one
         figure that explains the failure huge, what it did in a red box;
  split  the real wreck on the left, our 3D close-up of the part that failed
         on the right, glowing, the hook across the top;
  fall   our 3D collapse mid-fall, the death toll huge, the cause in a box.

    paths = build(sheet, wreck_photo, close3d_frame, fall3d_frame, out_dir)
"""

import os
import re

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from kits.blueprint import font

W, H = 1280, 720
RED = (230, 40, 30)
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)

FRACTIONS = {0.5: "½", 0.25: "¼", 0.75: "¾", 0.125: "⅛"}


def _f(size, name="InterDisplay-Black.otf"):
    return font(name, size)            # font() renders at 2x: sizes below are for a 2x canvas


def _cover(path, w=W * 2, h=H * 2):
    img = Image.open(path).convert("RGB")
    ar = w / h
    if img.width / img.height > ar:
        nw = int(img.height * ar)
        img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
    else:
        nh = int(img.width / ar)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
    return img.resize((w, h), Image.LANCZOS)


def _punch(img, contrast=1.25, color=1.15, dark=0.82):
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(color)
    return ImageEnhance.Brightness(img).enhance(dark)


def _scrim(img, side="left", reach=0.6, strength=210):
    """A dark gradient under the text so it reads on any picture."""
    m = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(m)
    w = int(img.width * reach)
    for x in range(w):
        a = int(strength * (1 - x / w) ** 1.4)
        xx = x if side == "left" else img.width - 1 - x
        d.line([(xx, 0), (xx, img.height)], fill=a)
    return Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, m)


def _text(d, s, size, xy, fill=WHITE, anchor="la", stroke=10, name="InterDisplay-Black.otf"):
    d.text(xy, s, font=_f(size // 2, name), fill=fill, anchor=anchor,
           stroke_width=stroke, stroke_fill=(0, 0, 0))


def _fit(d, s, size, width, name="InterDisplay-Black.otf"):
    while size > 60 and d.textlength(s, font=_f(size // 2, name)) > width:
        size -= 6
    return size


def _box(d, s, x, y, size=84, max_w=1100):
    size = _fit(d, s, size, max_w - 60, "InterDisplay-Bold.otf")
    tw = d.textlength(s, font=_f(size // 2, "InterDisplay-Bold.otf"))
    d.rectangle([x, y, x + tw + 60, y + size * 0.62 + 52], fill=RED)
    d.text((x + 30, y + 26), s, font=_f(size // 2, "InterDisplay-Bold.otf"), fill=WHITE, anchor="la")


def _glow(img, xy, r, color=RED, strength=150):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], fill=color + (strength,))
    layer = layer.filter(ImageFilter.GaussianBlur(r // 2))
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def _save(img, path):
    img.resize((W, H), Image.LANCZOS).save(path, "JPEG", quality=92)
    return path


def figures(sheet):
    """The thumbnail words from the sheet: the plate thickness or the
    design-vs-built multiplier, the death toll, a short cause."""
    dvb = sheet.get("design_vs_built") or {}
    big = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(inch|in\b|mm)", str(dvb.get("plate_built", "")), re.I)
    if m:
        v = float(m.group(1))
        unit = "INCH" if m.group(2).lower().startswith("in") else "MM"
        big = f"{FRACTIONS.get(v, m.group(1))} {unit}"
    big = big or str(dvb.get("multiplier") or "").strip() or None
    nums = sheet.get("numbers") or []
    dead = None
    if nums and re.search(r"KILL|DEAD|DIED|DEATH", nums[0].get("label", "").upper()):
        dead = re.sub(r"[^0-9,]", "", str(nums[0]["value"]))
    kit = sheet.get("kit", {})
    part = {"truss_bridge": "STEEL PLATE", "hanging_walkways": "STEEL ROD"}.get(kit.get("variant"), "PART")
    return {"big": big, "dead": dead, "part": part}


def wreck(photo, f, out):
    img = _scrim(_punch(_cover(photo)), "left", 0.7)
    d = ImageDraw.Draw(img)
    big = f["big"] or (f"{f['dead']} DEAD" if f["dead"] else "")
    size = _fit(d, big, 360, 1500)
    _text(d, big, size, (80, 70), YELLOW, stroke=14)
    _box(d, f"OF {f['part']} BROUGHT IT DOWN" if f["big"] else f"ONE {f['part']}", 80, 70 + size * 1.02)
    return _save(img, out)


def split(photo, close3d, f, out):
    left = _punch(_cover(photo, W, H * 2), dark=0.75)
    right = _punch(_cover(close3d, W, H * 2), contrast=1.35, dark=0.95)
    right = _glow(right, (W // 2, int(H * 0.9)), 260)
    img = Image.new("RGB", (W * 2, H * 2))
    img.paste(left, (0, 0))
    img.paste(right, (W, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([W - 6, 0, W + 6, H * 2], fill=WHITE)
    hook = f"THE {f['big']} MISTAKE" if f["big"] else f"ONE {f['part']}"
    top = Image.new("L", img.size, 0)
    ImageDraw.Draw(top).rectangle([0, 0, W * 2, 420], fill=170)
    img = Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, top.filter(ImageFilter.GaussianBlur(80)))
    d = ImageDraw.Draw(img)
    size = _fit(d, hook, 230, W * 2 - 160)
    _text(d, hook, size, (W, 60), WHITE, anchor="ma", stroke=14)
    # the arrow onto the part that failed
    ax, ay = int(W * 1.5), int(H * 0.62)
    d.line([(ax - 260, ay - 170), (ax - 40, ay + 60)], fill=RED, width=26)
    d.polygon([(ax - 10, ay + 100), (ax - 110, ay + 50), (ax - 30, ay - 20)], fill=RED)
    _text(d, "REAL", 70, (60, H * 2 - 130), WHITE, stroke=8, name="InterDisplay-Bold.otf")
    _text(d, "3D", 70, (W + 60, H * 2 - 130), WHITE, stroke=8, name="InterDisplay-Bold.otf")
    return _save(img, out)


def fall(fall3d, f, out):
    img = _scrim(_punch(_cover(fall3d), contrast=1.3, dark=0.9), "left", 0.65)
    img = _glow(img, (int(W * 1.3), int(H * 1.0)), 340, strength=110)
    d = ImageDraw.Draw(img)
    big = f"{f['dead']} DEAD" if f["dead"] else (f["big"] or "")
    size = _fit(d, big, 330, 1400)
    _text(d, big, size, (80, 80), WHITE, stroke=14)
    _box(d, f"ONE {f['part']}" + (f" · {f['big']}" if f["big"] else ""), 80, 80 + size * 1.02)
    return _save(img, out)


def build(sheet, wreck_photo, close3d, fall3d, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    f = figures(sheet)
    made = {}
    if wreck_photo:
        made["wreck"] = wreck(wreck_photo, f, os.path.join(out_dir, "thumb_wreck.jpg"))
    if wreck_photo and close3d:
        made["split"] = split(wreck_photo, close3d, f, os.path.join(out_dir, "thumb_split.jpg"))
    if fall3d:
        made["fall"] = fall(fall3d, f, os.path.join(out_dir, "thumb_fall.jpg"))
    return made
