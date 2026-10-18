"""
The cold open: the first ~30 seconds, built to hold a viewer until the
analysis starts (owner, 2026-10-18, after the first full episode: "our
challenge is to keep the viewer with us for 1 min").

A fast montage in the style of a news thriller: a new picture every ~2
seconds (real footage first, security cameras before anything, then the
event's photos, then our own 3D collapse), hard cuts punched in with a flash,
a dark grade with grain. The episode's title wipes in over the first
seconds; the hook lines are spoken over it, each shown big on screen while
it is said. Thriller music carries it (src/episode.py mixes the sound).

    fn = cold_open(sheet, items, lines, T)     # fn(t, T) -> Image, like a kit clip
"""

import random

from PIL import Image, ImageDraw, ImageFilter

from kits.blueprint import W, H, SS, LINE, RED, DIM, ease, prog, Frame, font, fit

BEAT = 2.0            # seconds per picture, on average
FLASH = 0.10          # the white punch on each cut


def plan(items, T, seed=7):
    """The cut list: [(start, length, item, offset into a clip)]. items:
    {"frames": [...], "kind": "footage"|"3d"} clips, {"path"} photos. Footage
    and the 3D are cut into ~2 s pieces taken in order; photos once each.
    Real footage leads; the 3D collapse closes the montage."""
    rnd = random.Random(seed)
    footage = [i for i in items if i.get("frames") and i.get("kind") != "3d"]
    model = [i for i in items if i.get("frames") and i.get("kind") == "3d"]
    photos = [i for i in items if not i.get("frames")]

    def pieces(clips):
        out = []
        for c in clips:
            n = len(c["frames"])
            step = int(BEAT * 30)
            for off in range(0, max(1, n - step // 2), step):
                out.append((c, off))
        return out

    real, ours = pieces(footage), pieces(model)
    order = []
    # alternate real footage and photos, our 3D at the end (its last pieces)
    pool = [("f", p) for p in real]
    pi = 0
    mixed = []
    for k in range(max(len(pool), len(photos))):
        if k < len(pool):
            mixed.append(pool[k])
        if pi < len(photos):
            mixed.append(("p", (photos[pi], 0)))
            pi += 1
    order = mixed
    # the collapse itself, in motion: the first pieces of the fall, in order
    tail = [("m", p) for p in ours[:3]] if ours else []
    cuts, t = [], 0.0
    budget = T - sum(BEAT for _ in tail)
    seq = order or tail
    k = 0
    while seq and t < budget - 0.5:
        kind, (item, off) = seq[k % len(seq)]
        if k >= len(seq) and kind != "p":       # second pass over footage: a later piece
            off = min(off + 15, max(0, len(item["frames"]) - 1))
        d = min(BEAT * rnd.uniform(0.8, 1.2), budget - t)
        cuts.append([t, d, item, off])
        t += d
        k += 1
    for kind, (item, off) in tail:
        d = max(0.5, min(BEAT, T - t))
        cuts.append([t, d, item, off])
        t += d
    if cuts:
        cuts[-1][1] += max(0.0, T - t)
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
    """Cold, contrasty, a little desaturated: the thriller look."""
    gray = img.convert("L").convert("RGB")
    img = Image.blend(img, gray, 0.35)
    img = Image.blend(img, Image.new("RGB", img.size, (8, 18, 34)), 0.22)
    return img


def _picture(item, local, off, dur):
    if item.get("frames"):
        fr = item["frames"]
        img = Image.open(fr[min(len(fr) - 1, off + int(local * 30))]).convert("RGB")
        img = img.resize((W * SS, H * SS))
        z = 1.0 + 0.05 * local / max(0.1, dur)                # slow push
    else:
        img = Image.open(item["path"]).convert("RGB")
        ar = W / H
        if img.width / img.height > ar:
            nw = int(img.height * ar)
            img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
        else:
            nh = int(img.width / ar)
            img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
        img = img.resize((W * SS, H * SS))
        z = 1.04 + 0.10 * local / max(0.1, dur)               # faster push on stills
    z += 0.06 * (1 - ease(min(1.0, local / 0.25)))            # the punch-in on the cut
    cw, ch = img.width / z, img.height / z
    x0, y0 = (img.width - cw) / 2, (img.height - ch) / 2
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(img.size)


def title_card(f, title, sub, t, t0=0.8, t1=5.2):
    """The episode's title, wiped in from a red line drawn across the
    middle, held, then lifted away: no box, no pop."""
    if t < t0 or t > t1 + 0.6:
        return
    cx, cy = W / 2, H / 2
    grow = ease(prog(t, t0, t0 + 0.7))
    out = 1 - prog(t, t1, t1 + 0.6)
    size = fit(title, 64, "InterDisplay-Black.otf", W - 160)
    tw = font("InterDisplay-Black.otf", size).getlength(title) / SS
    half = (tw / 2 + 30) * grow
    a = int(255 * out)
    f.d.line([((cx - half) * SS, (cy + 6) * SS), ((cx + half) * SS, (cy + 6) * SS)],
             fill=RED + (a,), width=3 * SS)
    # the title rises out of the line: draw it on a layer and reveal upward
    rise = ease(prog(t, t0 + 0.45, t0 + 1.15))
    if rise > 0:
        layer = Image.new("RGBA", f.img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.text((cx * SS, (cy - 4 + 22 * (1 - rise)) * SS), title, font=font("InterDisplay-Black.otf", size),
               fill=(255, 255, 255, a), anchor="md")
        mask = Image.new("L", f.img.size, 0)
        top = cy + 6 - (size + 20) * rise
        ImageDraw.Draw(mask).rectangle([0, top * SS, W * SS, (cy + 6) * SS], fill=255)
        f.img.paste(layer, (0, 0), Image.composite(layer, Image.new("RGBA", layer.size), mask))
    if sub:
        sa = prog(t, t0 + 1.0, t0 + 1.5) * out
        n = int(len(sub) * prog(t, t0 + 1.0, t0 + 1.9))       # typed out
        f.text(sub[:n], cx, cy + 40, 20, LINE, "Inter-Bold.otf", anchor="mm", alpha=sa)


def cold_open(sheet, items, lines, T, title="", sub=""):
    """items: pictures (see plan). lines: [(start, end, text)] when each hook
    line is spoken, shown big while it is said."""
    cuts = plan(items, T)

    def clip(t, T_):
        k = next((j for j, (a, d, _, _) in enumerate(cuts) if t < a + d), len(cuts) - 1)
        a, d, item, off = cuts[k] if cuts else (0, T, {"path": None}, 0)
        if item.get("path") is None and not item.get("frames"):
            img = Image.new("RGB", (W * SS, H * SS), (4, 10, 20))
        else:
            img = _grade(_picture(item, t - a, off, d))
        # vignette, grain
        img = Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), _vignette())
        img = Image.blend(img, Image.merge("RGB", [_grain_tile(int(t * 24))] * 3), 0.06)
        flash = 1 - prog(t - a, 0.0, FLASH) if k > 0 else 0
        if flash > 0:
            img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.45 * flash)
        # fade in from black at the very start, out to black at the end
        img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img,
                          prog(t, 0.0, 0.6) * (1 - prog(t, T_ - 0.35, T_)))
        f = Frame()
        f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
        title_card(f, title, sub, t)
        for s, e, text in lines:
            if s - 0.15 <= t <= e + 0.35:
                al = prog(t, s - 0.15, s + 0.1) * (1 - prog(t, e + 0.1, e + 0.35))
                size = fit(text, 34, "InterDisplay-Bold.otf", W - 200)
                f.text(text, W / 2, H - 120, size, LINE, "InterDisplay-Bold.otf", anchor="mm", alpha=al)
        if item.get("tag") and item.get("frames"):
            from kits import common
            common.pill(f, item["tag"], 40, 36, LINE, 15, "la", 0.85)
        if item.get("credit"):
            c = item["credit"]
            f.text(c, W - 24, H - 16, fit(c, 12, "Inter-Medium.otf", 560), DIM,
                   "Inter-Medium.otf", screen=True, anchor="rs", alpha=0.8)
        return f.done()
    return clip


_vig = []


def _vignette():
    if not _vig:
        m = Image.new("L", (W * SS, H * SS), 0)
        ImageDraw.Draw(m).ellipse([-W * SS * 0.15, -H * SS * 0.25, W * SS * 1.15, H * SS * 1.25], fill=255)
        _vig.append(m.filter(ImageFilter.GaussianBlur(W * SS // 7)))
    return _vig[0]
