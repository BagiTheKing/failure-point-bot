"""
Blocks every kit shares, filled from the animation sheet:

    photo       the real archive photo, slow push-in, place/date and the toll;
                its last second drains into blueprint colours (the hand-over
                to a drawing)
    clock       the last seconds before the failure
    timeline    the warnings, in order
    today       "could it happen today?" card
    overlay_3d  labels and captions over rendered 3D frames, following the
                parts' screen positions recorded at render time
"""

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GRID_MAJOR,
                            ease, prog, lerp, Frame, font)

_photo_cache = {}


def _cover(path):
    if path not in _photo_cache:
        img = Image.open(path).convert("RGB")
        ar = W / H
        if img.width / img.height > ar:
            nw = int(img.height * ar)
            img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
        else:
            nh = int(img.width / ar)
            img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
        _photo_cache[path] = img
    return _photo_cache[path]


def ken_burns(path, t):
    img = _cover(path)
    z = 1.0 + 0.12 * t
    cw, ch = img.width / z, img.height / z
    x0 = (img.width - cw) / 2 + 0.03 * img.width * t
    y0 = (img.height - ch) / 2
    img = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W * SS, H * SS), Image.LANCZOS)
    img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.28)
    vig = Image.new("L", img.size, 0)
    ImageDraw.Draw(vig).ellipse([-W * SS * 0.2, -H * SS * 0.3, W * SS * 1.2, H * SS * 1.3], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W * SS // 8))
    return Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), vig)


def placeholder(t):
    img = Image.new("RGB", (W * SS, H * SS), (30, 30, 32))
    d = ImageDraw.Draw(img)
    d.text((W * SS / 2, H * SS / 2), "REAL ARCHIVE PHOTO", font=font("Inter-Bold.otf", 30),
           fill=(150, 150, 150), anchor="mm")
    return img


def blueprint_tint(img, k):
    if k <= 0:
        return img
    return Image.blend(img, ImageOps.colorize(ImageOps.grayscale(img), BG, (150, 182, 232)), k)


def photo(sheet, path, tint_out=True):
    d = sheet["disaster"]
    nums = sheet.get("numbers", [])

    def clip(t, T):
        img = ken_burns(path, t / T) if path else placeholder(t / T)
        if tint_out:
            img = blueprint_tint(img, ease(prog(t, T - 1.0, T)))
        f = Frame()
        f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
        out = 1 - prog(t, T - 1.1, T - 0.5) if tint_out else 1
        a = prog(t, 0.8, 1.6) * out
        f.d.rectangle([60 * SS, 520 * SS, 66 * SS, 600 * SS], fill=RED + (int(255 * a),))
        f.text(d["place_date"], 82, 540, 22, LINE, "Inter-Bold.otf", screen=True, alpha=a)
        f.text(d.get("place", ""), 82, 570, 20, DIM, "Inter-Medium.otf", screen=True, alpha=a)
        if nums:
            b = prog(t, 2.6, 3.4) * out
            f.text(nums[0]["value"], 1180, 470, 110, RED, "InterDisplay-Black.otf", anchor="rs",
                   screen=True, alpha=b)
            f.text(nums[0]["label"], 1180, 505, 26, LINE, "Inter-Bold.otf", anchor="rs",
                   screen=True, alpha=b)
        f.caption(d.get("caption", ""), prog(t, 0.3, 1.0) * out)
        return f.done()
    return clip


def clock(sheet):
    c = sheet["clock"]

    def clip(t, T):
        f = Frame()
        f.grid(0.6)
        secs = min(10, int(t / (T - 0.8) * 10))
        s0 = int(c.get("from_seconds", 50))
        label = c["label_before"].format(s=s0 + secs) if secs < 10 else c["label_at"]
        col = RED if secs >= 10 else LINE
        f.text(label, W / 2, H / 2 - 10, 120, col, "InterDisplay-Bold.otf", anchor="mm")
        f.text(c.get("day", ""), W / 2, H / 2 + 80, 22, DIM, "Inter-Bold.otf", anchor="mm")
        if secs >= 10:
            f.text(c.get("event", ""), W / 2, H / 2 - 120, 24, RED, "Inter-Bold.otf", anchor="mm")
        return f.done()
    return clip


def timeline(sheet):
    events = sheet["timeline"]
    cap = next((s.get("caption", "") for s in sheet.get("shots", []) if s.get("clip") == "timeline"), "")
    n = len(events)

    def clip(t, T):
        f = Frame()
        f.grid(0.6)
        x0, x1, y = 120, 1160, 360
        p = prog(t, 0.3, T - 1.6)
        f.poly([(x0, y), (x1, y)], GRID_MAJOR, 6)
        f.poly([(x0, y), (x1, y)], CYAN, 6, p)
        for i, e in enumerate(events):
            pos = 0.08 + 0.86 * i / max(1, n - 1)
            x = lerp(x0, x1, pos)
            on = p >= pos
            kind = e.get("kind", "event")
            col = ({"warning": AMBER, "failure": RED}.get(kind, CYAN)) if on else GRID_MAJOR
            a, b = f.P(x - 9, y - 9), f.P(x + 9, y + 9)
            f.d.ellipse([a, b], fill=col)
            if on:
                up = i % 2 == 0
                ty = y - 70 if up else y + 50
                f.text(e["date"], x, ty, 18, col, "Inter-Bold.otf", anchor="mm")
                f.text(e["title"], x, ty + 26, 19, LINE, "Inter-SemiBold.otf", anchor="mm")
                if e.get("sub"):
                    f.text(e["sub"], x, ty + 50, 15, DIM, "Inter-Medium.otf", anchor="mm")
        f.caption(cap, prog(t, 1.4, 2.0))
        return f.done()
    return clip


def today(sheet):
    d = sheet["today"]

    def clip(t, T):
        f = Frame()
        f.grid(0.6)
        f.text(d["title"], W / 2, 200, 40, CYAN, "InterDisplay-Black.otf", anchor="mm",
               alpha=prog(t, 0.2, 0.8))
        for i, line in enumerate(d["lines"]):
            a = prog(t, 1.0 + i * 1.6, 1.6 + i * 1.6)
            f.text(line, W / 2, 300 + i * 64, 26, LINE if i < len(d["lines"]) - 1 else AMBER,
                   "Inter-SemiBold.otf", anchor="mm", alpha=a)
        return f.done()
    return clip


def pill(f, s, x, y, color=CYAN, size=20, anchor="la", alpha=1.0):
    """Text on a dark rounded box: readable over a light 3D render."""
    if alpha <= 0:
        return
    fnt = font("Inter-Bold.otf", size)
    tw = f.d.textlength(s, font=fnt)
    th = size * SS
    px = x * SS - (tw if anchor.startswith("r") else 0)
    py = y * SS
    pad = 10 * SS
    f.d.rounded_rectangle([px - pad, py - pad * 0.7, px + tw + pad, py + th + pad * 0.5],
                          radius=8 * SS, fill=(9, 22, 41, int(215 * alpha)))
    f.d.text((px, py), s, font=fnt, fill=color + (int(255 * alpha),))


COLORS = {"cyan": CYAN, "amber": AMBER, "red": RED, "white": LINE}

# The 3D shot windows (seconds) every 3D model uses: establish, load path,
# connection, then the pull-back where the AI collapse (or the 3D fall) takes over.
SHOTS_3D = {"establish": (0, 7), "load_path": (7, 13), "connection": (13, 20), "fall": (20, 28)}
CAPTION_WINDOWS = {"establish": (0.6, 6.4), "load_path": (8.0, 12.6),
                   "connection": (13.6, 19.6), "fall": (20.4, 26.0)}


def overlay_3d(sheet, frame_img, frame_no, anchors, t):
    """Captions and part labels over one rendered 3D frame (t in seconds).
    What to label, when and where comes from the sheet's model_3d block:

        "labels_3d": [{"anchor": "nut", "text": "...", "color": "cyan",
                       "t": [15.4, 19.4], "at": [760, 150]}, ...]
        "big_3d":    {"anchor": "nut", "text": "2×", "label": "...", "t": [16.6, 19.4]}

    Anchors are the parts' screen positions recorded at render time, so the
    labels follow the 3D model as the camera moves."""
    img = frame_img.convert("RGB").resize((W * SS, H * SS))
    f = Frame()
    f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
    m = sheet.get("model_3d", {})
    caps = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}
    A = anchors.get(str(frame_no)) or anchors.get(frame_no) or {}

    def at(name):
        p = A.get(name)
        if not p or p[2] <= 0 or not (0.02 < p[0] < 0.98 and 0.02 < p[1] < 0.98):
            return None
        return p[0] * W, p[1] * H

    def lead(name, text, tx, ty, color, alpha):
        p = at(name)
        if not p or alpha <= 0:
            return
        f.d.line([(p[0] * SS, p[1] * SS), (tx * SS, (ty + 12) * SS)],
                 fill=color + (int(255 * alpha),), width=2 * SS)
        f.d.ellipse([p[0] * SS - 5 * SS, p[1] * SS - 5 * SS, p[0] * SS + 5 * SS, p[1] * SS + 5 * SS],
                    fill=color + (int(255 * alpha),))
        # text grows away from the screen edge it sits nearest
        pill(f, text, tx, ty, color, 19, "la" if tx < W / 2 or tx > p[0] else "ra", alpha)

    for lab in m.get("labels_3d", []):
        t0, t1 = lab["t"]
        a = prog(t, t0, t0 + 0.6) * (1 - prog(t, t1, t1 + 0.5))
        lead(lab["anchor"], lab["text"], lab["at"][0], lab["at"][1],
             COLORS.get(lab.get("color", "cyan"), CYAN), a)
    big = m.get("big_3d")
    if big:
        t0, t1 = big["t"]
        b = prog(t, t0, t0 + 0.6) * (1 - prog(t, t1, t1 + 0.5))
        p = at(big["anchor"]) if b > 0 else None
        if p:
            f.text(big["text"], p[0] - 60, p[1] + 10, 80, RED, "InterDisplay-Black.otf",
                   screen=True, alpha=b, anchor="rs")
            pill(f, big.get("label", ""), p[0] - 60, p[1] + 26, RED, 20, "ra", b)
    for clip, (c0, c1) in CAPTION_WINDOWS.items():
        if caps.get(clip):
            f.caption(caps[clip], prog(t, c0, c0 + 0.5) * (1 - prog(t, c1 - 0.4, c1)))
    return f.done()
