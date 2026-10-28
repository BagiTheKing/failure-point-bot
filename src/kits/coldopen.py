"""
The cold open: the first seconds that keep a viewer (owner, 2026-10-18).

Clear and simple, well under a minute:

  0.0-1.0 s  four photos of the disaster flash in, a quarter second each,
             each with a camera shutter (src/score.py) and a white flash,
             like press shots.
  1.0-4.4 s  the title rises out of a red line drawn across the screen.
  then       one picture per hook line, each held while its line is said,
             with a slow, steady push-in and a straight cut to the next (the
             punch-in-and-out between pictures looked badly edited). Real
             footage first if there is any, then photos; the line that says
             what happened gets the 3D collapse, the last line the 3D close-up
             of the part that failed: the question the episode answers.

    plan = layout(sheet, pictures, fall3d, close3d, footage, lines, T)
    fn = cold_open(plan, lines, T, title, sub)      # fn(t, T) -> Image
"""

import random

from PIL import Image, ImageDraw, ImageFilter

from kits.blueprint import W, H, SS, LINE, RED, DIM, ease, prog, Frame, font, fit

BURST = 4               # photos in the opening flash
BURST_EACH = 0.25       # seconds each
TITLE_AT = 1.0          # the title starts when the burst ends
TITLE_END = 4.4
FLASH = 0.08


def shutter_times():
    """When the burst's photos land: the score puts a shutter on each."""
    return [k * BURST_EACH for k in range(BURST)]


def layout(burst, line_items, lines, T):
    """The cut list [(start, length, item)]: the burst, the title (over a
    dark blur of the last burst photo), then one item per hook line from
    the moment its line starts, the first line's item from the title's end."""
    cuts = []
    for k, item in enumerate(burst[:BURST]):
        cuts.append((k * BURST_EACH, BURST_EACH, item))
    t0 = BURST_EACH * len(cuts)
    title_bg = {**(burst[-1] if burst else {"path": None}), "blur": True}
    first = lines[0][0] if lines else TITLE_END
    cuts.append((t0, max(0.3, min(TITLE_END, first) - t0), title_bg))
    t = cuts[-1][0] + cuts[-1][1]
    for i, (s, e, _) in enumerate(lines):
        nxt = lines[i + 1][0] if i + 1 < len(lines) else T
        start = max(t, s - 0.25)                 # cut just before the line is said
        item = line_items[i] if i < len(line_items) else (line_items[-1] if line_items else title_bg)
        cuts.append((start, max(0.3, nxt - 0.25 - start if i + 1 < len(lines) else T - start), item))
        t = start + cuts[-1][1]
    return cuts


_grain = []


def _grain_tile(k):
    if not _grain:
        r = random.Random(3)
        for _ in range(4):
            g = Image.new("L", (W // 2, H // 2))
            g.putdata([r.randint(0, 255) for _ in range(g.width * g.height)])
            _grain.append(g.resize((W * SS, H * SS)).filter(ImageFilter.GaussianBlur(1)))
    return _grain[k % 4]


def _grade(img):
    """Cold, contrasty, a little desaturated."""
    gray = img.convert("L").convert("RGB")
    img = Image.blend(img, gray, 0.3)
    return Image.blend(img, Image.new("RGB", img.size, (8, 18, 34)), 0.18)


def _cover(img):
    ar = W / H
    if img.width / img.height > ar:
        nw = int(img.height * ar)
        img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
    else:
        nh = int(img.width / ar)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
    return img.resize((W * SS, H * SS))


def _picture(item, local, dur, still=False):
    """One picture at `local` seconds into its cut: footage or 3D frames play,
    photos hold; everything pushes in slowly and steadily (never back out)."""
    if item.get("frames"):
        fr = item["frames"]
        step = item.get("speed", 1.0)
        img = Image.open(fr[min(len(fr) - 1, item.get("offset", 0) + int(local * 30 * step))]).convert("RGB")
        img = _cover(img)
    elif item.get("path"):
        img = _cover(Image.open(item["path"]).convert("RGB"))
    else:
        return Image.new("RGB", (W * SS, H * SS), (4, 10, 20))
    if item.get("blur"):
        img = img.filter(ImageFilter.GaussianBlur(18 * SS))
        img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.55)
    if not still:
        z = 1.0 + 0.06 * min(1.0, local / max(0.5, dur))
        cw, ch = img.width / z, img.height / z
        x0, y0 = (img.width - cw) / 2, (img.height - ch) / 2
        img = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(img.size)
    return img


def title_card(f, title, sub, t, t0=TITLE_AT, t1=TITLE_END):
    """The episode's title rising out of a red line drawn across the middle,
    held, then faded: no box, no pop."""
    if t < t0 or t > t1 + 0.5:
        return
    cx, cy = W / 2, H / 2
    grow = ease(prog(t, t0, t0 + 0.6))
    out = 1 - prog(t, t1, t1 + 0.5)
    size = fit(title, 64, "InterDisplay-Black.otf", W - 160)
    tw = font("InterDisplay-Black.otf", size).getlength(title) / SS
    half = (tw / 2 + 30) * grow
    a = int(255 * out)
    f.d.line([((cx - half) * SS, (cy + 6) * SS), ((cx + half) * SS, (cy + 6) * SS)],
             fill=RED + (a,), width=3 * SS)
    rise = ease(prog(t, t0 + 0.35, t0 + 1.05))
    if rise > 0:
        layer = Image.new("RGBA", f.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((cx * SS, (cy - 4 + 22 * (1 - rise)) * SS), title,
                                   font=font("InterDisplay-Black.otf", size),
                                   fill=(255, 255, 255, a), anchor="md")
        mask = Image.new("L", f.img.size, 0)
        top = cy + 6 - (size + 20) * rise
        ImageDraw.Draw(mask).rectangle([0, top * SS, W * SS, (cy + 6) * SS], fill=255)
        f.img.paste(layer, (0, 0), Image.composite(layer, Image.new("RGBA", layer.size), mask))
    if sub:
        n = int(len(sub) * prog(t, t0 + 0.9, t0 + 1.8))       # typed out
        f.text(sub[:n], cx, cy + 40, 20, LINE, "Inter-Bold.otf", anchor="mm",
               alpha=prog(t, t0 + 0.9, t0 + 1.2) * out)


_vig = []


def _vignette():
    if not _vig:
        m = Image.new("L", (W * SS, H * SS), 0)
        ImageDraw.Draw(m).ellipse([-W * SS * 0.15, -H * SS * 0.25, W * SS * 1.15, H * SS * 1.25], fill=255)
        _vig.append(m.filter(ImageFilter.GaussianBlur(W * SS // 7)))
    return _vig[0]


def events(cuts, line_items):
    """When the effects land, from the cut list: the shake on the title's
    impact and on the last line's hit, the glitch and whoosh on each cut
    between hook pictures, the rumble while the 3D collapse plays."""
    line_cuts = [a for a, _, _ in cuts[BURST + 1:]]
    last = line_cuts[-1] if line_cuts else None
    fall = next(((a, a + d) for a, d, it in cuts[BURST + 1:] if it.get("fall")), None)
    return {"title": TITLE_AT, "cuts": line_cuts, "first": line_cuts[0] if line_cuts else None,
            "last": last, "fall": fall, "shake": [TITLE_AT] + ([last] if last else [])}


def _shake(img, since, amp=10):
    """A camera knock: a few pixels of jolt, dying away in a third of a second."""
    k = max(0.0, 1 - since / 0.35)
    if k <= 0:
        return img
    r = random.Random(int(since * 1000))
    dx, dy = (int(r.uniform(-1, 1) * amp * SS * k) for _ in range(2))
    z = 1.03
    cw, ch = img.width / z, img.height / z
    x0, y0 = (img.width - cw) / 2 + dx, (img.height - ch) / 2 + dy
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(img.size)


def _glitch(img, k):
    """Colour fringes on a cut: red and blue pulled apart for two frames."""
    r, g, b = img.split()
    off = int(10 * SS * k)
    from PIL import ImageChops
    return Image.merge("RGB", (ImageChops.offset(r, off, 0), g, ImageChops.offset(b, -off, 0)))


def cold_open(cuts, lines, T, title="", sub="", fx=None, fade_out=True, opening=True):
    """cuts: layout(). lines: [(start, end, text)] when each hook line is
    spoken, shown on screen while it is said. fx: events(). opening=False:
    the hook lines alone, later in the episode (no burst, no title)."""
    fx = fx or {}

    def clip(t, T_):
        k = next((j for j, (a, d, _) in enumerate(cuts) if t < a + d), len(cuts) - 1)
        a, d, item = cuts[k]
        burst = opening and k < BURST and t < BURST * BURST_EACH
        img = _grade(_picture(item, t - a, d, still=burst))
        for at in fx.get("shake", []):
            if at is not None and 0 <= t - at < 0.35:
                img = _shake(img, t - at)
        for at in fx.get("cuts", []):
            if 0 <= t - at < 2 / 30:
                img = _glitch(img, 1 - (t - at) * 15)
        img = Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), _vignette())
        img = Image.blend(img, Image.merge("RGB", [_grain_tile(int(t * 24))] * 3), 0.05)
        if burst:                                # a camera flash on each press shot
            flash = 1 - prog(t - a, 0.0, FLASH)
            img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.7 * flash)
        if fade_out:                             # alone; in the episode it dissolves on
            img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, 1 - prog(t, T_ - 0.4, T_))
        f = Frame()
        f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
        if opening:
            title_card(f, title, sub, t)
        for s, e, text in lines:
            if s - 0.15 <= t <= e + 0.4:
                al = prog(t, s - 0.15, s + 0.1) * (1 - prog(t, e + 0.15, e + 0.4))
                size = fit(text, 34, "InterDisplay-Bold.otf", W - 200)
                f.text(text, W / 2, H - 120, size, LINE, "InterDisplay-Bold.otf", anchor="mm", alpha=al)
        if item.get("tag") and not burst:
            from kits import common
            common.pill(f, item["tag"], 40, 36, LINE, 15, "la", 0.85)
        if item.get("credit") and not burst and not item.get("blur"):
            c = item["credit"]
            f.text(c, W - 24, H - 16, fit(c, 12, "Inter-Medium.otf", 560), DIM,
                   "Inter-Medium.otf", screen=True, anchor="rs", alpha=0.8)
        return f.done()
    return clip
