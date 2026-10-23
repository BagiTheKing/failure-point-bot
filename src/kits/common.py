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

import re

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GRID_MAJOR,
                            ease, prog, lerp, Frame, font, fit)

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


def ken_burns(path, t, drift=1, focus=None):
    """A slow push-in on a photo, drifting right (drift 1) or left (-1).
    focus 0/1/2: a closer look at the left, right or middle of it."""
    img = _cover(path)
    z = 1.0 + 0.12 * t + (0.35 if focus is not None else 0.0)
    cw, ch = img.width / z, img.height / z
    cx = {None: 0.5, 0: 0.33, 1: 0.67, 2: 0.5}[focus]
    x0 = min(max(0.0, img.width * cx - cw / 2 + 0.03 * img.width * t * drift), img.width - cw)
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


_shade_cache = []


def _shade():
    """A dark band up the bottom of the frame, so white text reads over footage."""
    if not _shade_cache:
        m = Image.new("L", (1, H * SS))
        for y in range(H * SS):
            m.putpixel((0, y), int(170 * max(0.0, (y / (H * SS) - 0.55) / 0.45) ** 1.2))
        _shade_cache.append(m.resize((W * SS, H * SS)))
    return _shade_cache[0]


def photo(sheet, path, tint_out=True, toll_at=None, quiet=False):
    """The opening shot over real pictures. The place and date are typed in
    under a line drawn across (no box popping in); the death toll is not
    shown here unless toll_at says when the narrator speaks it."""
    d = sheet["disaster"]
    nums = sheet.get("numbers", [])

    def clip(t, T):
        # path: a photo, or a clip function drawing the background (footage)
        if callable(path):
            img = path(t, T).convert("RGB").resize((W * SS, H * SS))
            img = Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, _shade())
        else:
            img = ken_burns(path, t / T) if path else placeholder(t / T)
        if tint_out:
            img = blueprint_tint(img, ease(prog(t, T - 1.0, T)))
        f = Frame()
        f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
        out = 1 - prog(t, T - 1.1, T - 0.5) if tint_out else 1
        if not quiet:                            # after a cold open, these only repeat it
            dateline(f, d["place_date"], d.get("place", ""), t, 0.6, out)
            f.caption(d.get("caption", ""), prog(t, 0.3, 1.0) * out * (1 - prog(t, 6.0, 6.6)))
        if nums and toll_at is not None:
            toll(f, nums[0]["value"], nums[0]["label"], t - toll_at)
        return f.done()
    return clip


def dateline(f, line1, line2, t, t0=0.6, out=1.0, x=60, y=540):
    """A thin line drawn left to right, the place and date typed in above
    it, the place's name fading in under it."""
    a = out
    w = 360 * ease(prog(t, t0, t0 + 0.6))
    if w > 1:
        f.d.line([(x * SS, (y + 31) * SS), ((x + w) * SS, (y + 31) * SS)],
                 fill=RED + (int(220 * a),), width=2 * SS)
    n = int(len(line1) * prog(t, t0 + 0.3, t0 + 1.3))
    f.text(line1[:n], x, y, 22, LINE, "Inter-Bold.otf", screen=True, alpha=a)
    f.text(line2, x, y + 40, 20, DIM, "Inter-Medium.otf", screen=True, alpha=prog(t, t0 + 1.2, t0 + 1.8) * a)


def toll(f, value, label, since, hold=5.5, x=1180, y=470):
    """The death toll rolling up from zero (00 -> 13), each digit sliding in
    like a counter, when the narrator says it; held, then faded. since:
    seconds since the word was spoken (negative before)."""
    if since < -0.2 or since > hold + 0.6:
        return
    digits = re.sub(r"[^0-9]", "", str(value))
    a = prog(since, -0.2, 0.15) * (1 - prog(since, hold, hold + 0.6))
    size = 110
    fnt = font("InterDisplay-Black.otf", size)
    if not digits:
        f.text(str(value), x, y, size, RED, "InterDisplay-Black.otf", anchor="rs", screen=True, alpha=a)
    else:
        N = int(digits)
        width = max(2, len(digits))
        v = N * ease(min(1.0, max(0.0, since) / 1.6))
        cw = fnt.getlength("0") / SS
        layer = Image.new("RGBA", f.img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for k in range(width):                       # k = 0 is the units column
            col_x = x - (k + 0.5) * cw
            place = 10 ** k
            cur = (v / place)
            digit, frac = int(cur) % 10, (cur % 1.0) if k == 0 and v < N else 0.0
            for dd, dy in ((digit, -frac), ((digit + 1) % 10, 1 - frac)):
                if dy >= 1 or (dy > 0 and frac == 0):
                    continue
                d.text((col_x * SS, (y + dy * size * 0.9) * SS), str(dd), font=fnt,
                       fill=RED + (int(255 * a),), anchor="ms")
        # the counter's window: digits slide in and out of a clipped band
        mask = Image.new("L", f.img.size, 0)
        ImageDraw.Draw(mask).rectangle([(x - width * cw - 10) * SS, (y - size * 0.82) * SS,
                                        (x + 10) * SS, (y + 12) * SS], fill=255)
        f.img.paste(layer, (0, 0), Image.composite(layer, Image.new("RGBA", layer.size), mask))
    la = prog(since, 0.8, 1.4) * a
    f.text(label, x, y + 35, 26, LINE, "Inter-Bold.otf", anchor="rs", screen=True, alpha=la)


def clock(sheet):
    c = sheet["clock"]

    def clip(t, T):
        f = Frame()
        f.grid(0.6)
        secs = min(10, int(t / (T - 0.8) * 10))
        s0 = int(c.get("from_seconds", 50))
        s = s0 + secs
        label = (c["label_at"] if secs >= 10
                 else c["label_next"].format(s=s - 60) if s >= 60 and c.get("label_next")
                 else c["label_before"].format(s=s))
        col = RED if secs >= 10 else LINE
        f.text(label, W / 2, H / 2 - 10, 120, col, "InterDisplay-Bold.otf", anchor="mm")
        f.text(c.get("day", ""), W / 2, H / 2 + 80, 22, DIM, "Inter-Bold.otf", anchor="mm")
        if secs >= 10:
            f.text(c.get("event", ""), W / 2, H / 2 - 120, 24, RED, "Inter-Bold.otf", anchor="mm")
        return f.done()
    return clip


def timeline(sheet, reveal=None):
    """reveal: the second each event appears (when the narrator says its
    date); None spreads them evenly over the shot."""
    events = sheet["timeline"]
    cap = next((s.get("caption", "") for s in sheet.get("shots", []) if s.get("clip") == "timeline"), "")
    n = len(events)
    spots = [0.08 + 0.86 * i / max(1, n - 1) for i in range(n)]

    def progress(t, T):
        if not reveal:
            return prog(t, 0.3, T - 1.6)
        # the line runs from dot to dot, arriving at each as its date is said
        knots = [(0.0, 0.0)] + [(max(0.0, r - 0.5), spots[i]) for i, r in enumerate(reveal)]
        knots.sort()
        for (ta, pa), (tb, pb) in zip(knots, knots[1:]):
            if t < tb:
                return pa + (pb - pa) * ease(max(0.0, (t - ta) / max(1e-3, tb - ta))) if t > ta else pa
        last_t, last_p = knots[-1]
        return last_p + (1.0 - last_p) * prog(t, last_t + 0.5, last_t + 2.0)

    def clip(t, T):
        f = Frame()
        f.grid(0.6)
        x0, x1, y = 120, 1160, 360
        p = progress(t, T)
        f.poly([(x0, y), (x1, y)], GRID_MAJOR, 6)
        f.poly([(x0, y), (x1, y)], CYAN, 6, p)
        # neighbours on the same side of the line sit two steps apart
        room = min(360, 2 * 0.86 * (x1 - x0) / max(1, n - 1) - 24)
        for i, e in enumerate(events):
            pos = spots[i]
            x = lerp(x0, x1, pos)
            on = p >= pos - 1e-6
            kind = e.get("kind", "event")
            col = ({"warning": AMBER, "failure": RED}.get(kind, CYAN)) if on else GRID_MAJOR
            a, b = f.P(x - 9, y - 9), f.P(x + 9, y + 9)
            f.d.ellipse([a, b], fill=col)
            if on:
                up = i % 2 == 0
                ty = y - 70 if up else y + 50
                f.text(e["date"], x, ty, 18, col, "Inter-Bold.otf", anchor="mm")
                f.text(e["title"], x, ty + 26, fit(e["title"], 19, "Inter-SemiBold.otf", room),
                       LINE, "Inter-SemiBold.otf", anchor="mm")
                if e.get("sub"):
                    f.text(e["sub"], x, ty + 50, fit(e["sub"], 15, "Inter-Medium.otf", room),
                           DIM, "Inter-Medium.otf", anchor="mm")
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
        # the lines come in one by one across the shot, as the voice reaches them
        step = max(1.6, (T - 2.5) / max(1, len(d["lines"])))
        for i, line in enumerate(d["lines"]):
            a = prog(t, 1.0 + i * step, 1.6 + i * step)
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
    from kits import timemap
    t = timemap.of(sheet).canon(t)      # windows below are on the canonical timeline
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
