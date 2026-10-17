"""
Style samples A-F: one short clip of each visual building block, using the
Hyatt Regency walkway collapse (Kansas City, 1981) as the worked example.

    python tools/style_samples.py out_dir [--photo path.jpg]

A  real archive photo, slow push-in, scale caption
B  schematic animation: the atrium draws itself, zoom to the connection
C  force & stress overlay on the connection
D  scale graphic: 1,600 people, 114 killed
E  timeline and clock
F  as designed vs as built, split screen

No narration or music: these show the look only. Facts used are from the
NBS investigation as reported on Wikipedia ("Hyatt Regency walkway
collapse"): 17 July 1981, about 7:05 pm, ~1,600 people in the atrium, 114
killed, 216 injured; hotel opened 1 July 1980; part of the atrium roof
collapsed during construction in October 1979; the hanger-rod detail was
changed from one continuous rod to two rods during the shop-drawing stage,
doubling the load on the fourth-floor connection.
"""

import argparse
import math
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS, SS = 1280, 720, 30, 2

BG = (9, 22, 41)
GRID = (19, 41, 72)
GRID_MAJOR = (27, 56, 96)
LINE = (226, 236, 255)
DIM = (120, 146, 186)
RED = (255, 75, 58)
AMBER = (255, 176, 32)
CYAN = (70, 210, 255)
GREEN = (60, 220, 140)

_FONT_DIRS = [os.path.join(os.path.dirname(__file__), "..", "fonts"),
              "/usr/share/fonts/opentype/inter"]
_fonts = {}


def font(name, size):
    key = (name, size)
    if key not in _fonts:
        for d in _FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                _fonts[key] = ImageFont.truetype(p, size * SS)
                break
        else:
            _fonts[key] = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size * SS)
    return _fonts[key]


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def prog(t, a, b):
    return ease((t - a) / (b - a)) if b > a else float(t >= b)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, max(0, min(1, t)))) for a, b in zip(c1, c2))


class Frame:
    """One frame drawn at SS x resolution through a 2D camera."""

    def __init__(self, cx=W / 2, cy=H / 2, zoom=1.0, bg=BG):
        self.img = Image.new("RGB", (W * SS, H * SS), bg)
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.cx, self.cy, self.zoom = cx, cy, zoom

    # world -> device pixels
    def P(self, x, y):
        return (((x - self.cx) * self.zoom + W / 2) * SS,
                ((y - self.cy) * self.zoom + H / 2) * SS)

    def grid(self, alpha=1.0, step=40):
        z = self.zoom
        x0 = self.cx - W / 2 / z
        x1 = self.cx + W / 2 / z
        y0 = self.cy - H / 2 / z
        y1 = self.cy + H / 2 / z
        s = step if z < 2.5 else step / 4
        k = math.floor(x0 / s)
        while k * s <= x1:
            x = k * s
            col = GRID_MAJOR if round(x / s) % 5 == 0 else GRID
            col = mix(BG, col, alpha)
            self.d.line([self.P(x, y0), self.P(x, y1)], fill=col, width=SS)
            k += 1
        k = math.floor(y0 / s)
        while k * s <= y1:
            y = k * s
            col = GRID_MAJOR if round(y / s) % 5 == 0 else GRID
            col = mix(BG, col, alpha)
            self.d.line([self.P(x0, y), self.P(x1, y)], fill=col, width=SS)
            k += 1

    def poly(self, pts, color=LINE, width=2, frac=1.0, world_width=False):
        """Polyline drawn up to `frac` of its length (the 'drawing itself'
        effect). width in screen px unless world_width."""
        if frac <= 0 or len(pts) < 2:
            return
        w = max(1, int((width * self.zoom if world_width else width) * SS))
        segs = list(zip(pts, pts[1:]))
        lens = [math.dist(a, b) for a, b in segs]
        total = sum(lens) or 1
        left = total * min(1.0, frac)
        out = [self.P(*pts[0])]
        for (a, b), L in zip(segs, lens):
            if left <= 0:
                break
            if L <= left:
                out.append(self.P(*b))
                left -= L
            else:
                f = left / L
                out.append(self.P(lerp(a[0], b[0], f), lerp(a[1], b[1], f)))
                left = 0
        self.d.line(out, fill=color, width=w, joint="curve")

    def rect(self, x0, y0, x1, y1, outline=LINE, fill=None, width=2, frac=1.0):
        if fill is not None and frac >= 1:
            self.d.rectangle([self.P(x0, y0), self.P(x1, y1)], fill=fill)
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
                  outline, width, frac)

    def text(self, s, x, y, size=18, color=LINE, name="Inter-SemiBold.otf",
             anchor="la", screen=False, alpha=1.0):
        if alpha <= 0:
            return
        pos = (x * SS, y * SS) if screen else self.P(x, y)
        col = color + (int(255 * alpha),) if len(color) == 3 else color
        self.d.text(pos, s, font=font(name, size), fill=col, anchor=anchor)

    def label(self, s, ax, ay, tx, ty, alpha=1.0, color=CYAN, size=17):
        """Leader line from a world point to a screen-space text position."""
        if alpha <= 0:
            return
        col = color + (int(255 * alpha),)
        px, py = self.P(ax, ay)
        qx, qy = tx * SS, ty * SS
        self.d.ellipse([px - 4 * SS, py - 4 * SS, px + 4 * SS, py + 4 * SS], fill=col)
        self.d.line([(px, py), (qx, qy)], fill=col, width=SS * 2)
        anchor = "ls" if qx >= px else "rs"
        self.d.line([(qx, qy), (qx + (120 if anchor == "ls" else -120) * SS * 0, qy)],
                    fill=col, width=SS * 2)
        self.d.text((qx + (8 if anchor == "ls" else -8) * SS, qy - 6 * SS), s,
                    font=font("Inter-SemiBold.otf", size), fill=col, anchor=anchor)

    def arrow(self, x0, y0, x1, y1, color=AMBER, width=4, head=12, frac=1.0, world=False):
        if frac <= 0:
            return
        x1, y1 = lerp(x0, x1, frac), lerp(y0, y1, frac)
        a, b = self.P(x0, y0), self.P(x1, y1)
        w = int(width * SS * (self.zoom if world else 1))
        self.d.line([a, b], fill=color, width=w)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        h = head * SS * (self.zoom if world else 1)
        p1 = (b[0] + h * math.cos(ang), b[1] + h * math.sin(ang))
        p2 = (b[0] + h * 0.6 * math.cos(ang + 2.3), b[1] + h * 0.6 * math.sin(ang + 2.3))
        p3 = (b[0] + h * 0.6 * math.cos(ang - 2.3), b[1] + h * 0.6 * math.sin(ang - 2.3))
        self.d.polygon([p1, p2, p3], fill=color)

    def tag(self, letter, title):
        """Top-left sample tag (sample reel only)."""
        f = font("Inter-Bold.otf", 15)
        s = f"{letter} · {title}"
        tw = self.d.textlength(s, font=f)
        self.d.rectangle([24 * SS, 22 * SS, 24 * SS + tw + 28 * SS, 54 * SS],
                         fill=(0, 0, 0, 150))
        self.d.text((38 * SS, 38 * SS), s, font=f, fill=LINE, anchor="lm")

    def caption(self, s, alpha=1.0):
        """Lower caption bar: what the narrator would be saying."""
        if alpha <= 0:
            return
        f = font("Inter-Medium.otf", 22)
        tw = self.d.textlength(s, font=f)
        x0 = (W * SS - tw) / 2 - 22 * SS
        self.d.rectangle([x0, (H - 78) * SS, x0 + tw + 44 * SS, (H - 34) * SS],
                         fill=(0, 0, 0, int(170 * alpha)))
        self.d.text((W * SS / 2, (H - 56) * SS), s, font=f,
                    fill=(255, 255, 255, int(255 * alpha)), anchor="mm")

    def done(self):
        return self.img.resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------------------
# The Hyatt Regency atrium, side elevation (world units ~ screen px at zoom 1)
# ---------------------------------------------------------------------------
ROOF_Y, W4_Y, W2_Y, GROUND_Y = 120, 330, 540, 650
WALK_X0, WALK_X1 = 300, 980
RODS = [380, 640, 900]
BEAM_H = 16          # box beam depth under each deck
DECK_H = 10


def draw_people(f, y, x0, x1, alpha=1.0, color=DIM, n=26, seed=3):
    import random
    rnd = random.Random(seed)
    col = color + (int(255 * alpha),)
    for i in range(n):
        x = lerp(x0, x1, (i + rnd.random() * 0.6) / n)
        h = 16 + rnd.random() * 4
        px, py = f.P(x, y - h)
        r = 3 * SS * f.zoom
        f.d.ellipse([px - r, py - r, px + r, py + r], fill=col)
        a, b = f.P(x - 2.5, y - h + 4), f.P(x + 2.5, y)
        f.d.rectangle([a, b], fill=col)


def draw_atrium(f, t_walls=1, t_roof=1, t_rods=1, t_walks=1, built=True,
                drop4=0.0, drop2=0.0, highlight=0.0, rod_color=LINE, skip_mid=False):
    # walls and floor slabs
    for x in (200, 1080):
        f.poly([(x, ROOF_Y - 30), (x, GROUND_Y)], DIM, 2, t_walls)
    f.poly([(150, GROUND_Y), (1130, GROUND_Y)], LINE, 3, t_walls)
    for y in (W4_Y, W2_Y):
        f.poly([(150, y), (200, y)], DIM, 3, t_walls)
        f.poly([(1080, y), (1130, y)], DIM, 3, t_walls)
    # roof truss
    pts = [(220, ROOF_Y)]
    for i, x in enumerate(range(220, 1061, 60)):
        pts.append((x, ROOF_Y - (34 if i % 2 else 0)))
    f.poly([(220, ROOF_Y), (1060, ROOF_Y)], LINE, 3, t_roof)
    f.poly([(220, ROOF_Y - 34), (1060, ROOF_Y - 34)], LINE, 2, t_roof)
    f.poly(pts, DIM, 2, t_roof)
    # walkways (deck + box beams), possibly dropping
    w4y = W4_Y + drop4
    w2y = W2_Y + drop2
    for y, tw in ((w4y, t_walks), (w2y, t_walks)):
        f.rect(WALK_X0, y - DECK_H, WALK_X1, y, LINE, None, 2, tw)
        for x in RODS:
            if tw >= 1 and not (skip_mid and x == RODS[1] and y == w4y):
                f.rect(x - 22, y, x + 22, y + BEAM_H, LINE, (18, 38, 66), 2)
        # railing
        f.poly([(WALK_X0, y - DECK_H - 26), (WALK_X1, y - DECK_H - 26)], DIM, 1, tw)
        for x in range(WALK_X0, WALK_X1 + 1, 34):
            f.poly([(x, y - DECK_H), (x, y - DECK_H - 26)], DIM, 1, tw)
    # hanger rods
    for x in RODS:
        if skip_mid and x == RODS[1]:
            continue
        if built:
            # upper rod: roof -> 4th-floor box beam (nut under the beam)
            f.poly([(x - 4, ROOF_Y), (x - 4, W4_Y + BEAM_H + 3)], rod_color, 2,
                   t_rods, world_width=False)
            # lower rod: hangs from the 4th-floor beam -> 2nd floor
            if drop4 < 1:
                f.poly([(x + 4, w4y + BEAM_H + 3), (x + 4, w2y + BEAM_H + 3)],
                       rod_color, 2, t_rods)
        else:
            f.poly([(x, ROOF_Y), (x, W2_Y + BEAM_H + 3)], rod_color, 2, t_rods)
        if t_rods >= 1:
            for y, dx in (((w4y if built else W4_Y), -4 if built else 0),
                          ((w2y if built else W2_Y), 4 if built else 0)):
                a, b = f.P(x + dx - 5, y + BEAM_H), f.P(x + dx + 5, y + BEAM_H + 4)
                f.d.rectangle([a, b], fill=LINE)
    if highlight > 0:
        x = RODS[1]
        pulse = 0.55 + 0.45 * math.sin(highlight * 12)
        col = RED + (int(200 * pulse),)
        a, b = f.P(x - 30, W4_Y - 8), f.P(x + 30, W4_Y + BEAM_H + 14)
        f.d.rounded_rectangle([a, b], radius=6 * SS, outline=col, width=3 * SS)


def draw_connection_detail(f, t, stress=0.0, crack=0.0, built=True, pulse=0.0):
    """Close-up of the 4th-floor connection at the middle rod, drawn at real
    proportions so it reads when the camera is zoomed in ~6x. As built: the
    upper rod's nut bears under the box beam's bottom flange; the lower rod
    hangs from a nut resting on that same flange inside the box."""
    x, y = RODS[1], W4_Y
    rx_up, rx_lo = (x - 4, x + 4) if built else (x, x)
    # stress glow around the upper nut
    if stress > 0:
        cx, cy = f.P(rx_up, y + BEAM_H)
        for k in range(6, 0, -1):
            r = (4 + k * 3.2) * f.zoom * SS * (0.5 + stress)
            f.d.ellipse([cx - r, cy - r, cx + r, cy + r],
                        fill=mix(AMBER, RED, stress) + (int(26 * stress * (7 - k) / 2),))
    edge = mix(LINE, RED, stress)
    f.rect(x - 22, y, x + 22, y + BEAM_H, edge, (18, 38, 66), 1.5)
    f.poly([(x - 22, y + BEAM_H / 2), (x + 22, y + BEAM_H / 2)], DIM, 1)   # weld seam
    # rods
    f.poly([(rx_up, y - 40), (rx_up, y + BEAM_H + 3)], LINE, 1.6, world_width=True)
    if built:
        f.poly([(rx_lo, y + BEAM_H - 4), (rx_lo, y + 70)], LINE, 1.6, world_width=True)
        a, b = f.P(rx_lo - 4, y + BEAM_H - 4), f.P(rx_lo + 4, y + BEAM_H - 1.5)
        f.d.rectangle([a, b], fill=LINE)
    nut_col = mix(LINE, RED, max(stress, 0.5 + 0.5 * math.sin(pulse * 10) if pulse else 0))
    a, b = f.P(rx_up - 4, y + BEAM_H), f.P(rx_up + 4, y + BEAM_H + 3)
    f.d.rectangle([a, b], fill=nut_col)
    # cracks through the bottom flange around the nut
    if crack > 0:
        for dx, ang in ((-5, -2.2), (5, -0.9), (-3, -1.8), (4, -1.2)):
            sx, sy = rx_up + dx, y + BEAM_H
            f.poly([(sx, sy), (sx + math.cos(ang) * 9 * crack, sy + math.sin(ang) * 9 * crack)],
                   RED, 2.5)


def kb_photo(path, t):
    """Real photo with a slow push-in, darkened, with a vignette."""
    img = Image.open(path).convert("RGB")
    ar = W / H
    if img.width / img.height > ar:
        nw = int(img.height * ar)
        img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
    else:
        nh = int(img.width / ar)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
    z = 1.0 + 0.12 * t
    cw, ch = img.width / z, img.height / z
    x0 = (img.width - cw) / 2 + 0.03 * img.width * t
    y0 = (img.height - ch) / 2
    img = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(
        (W * SS, H * SS), Image.LANCZOS)
    img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.28)
    vig = Image.new("L", img.size, 0)
    ImageDraw.Draw(vig).ellipse([-W * SS * 0.2, -H * SS * 0.3, W * SS * 1.2, H * SS * 1.3], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W * SS // 8))
    return Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), vig)


def placeholder_photo(t):
    img = Image.new("RGB", (W * SS, H * SS), (30, 30, 32))
    d = ImageDraw.Draw(img)
    for i in range(0, W * SS, 6 * SS):
        d.line([(i, 0), (i - H * SS, H * SS)], fill=(38, 38, 40), width=2 * SS)
    d.text((W * SS / 2, H * SS / 2 - 40 * SS), "REAL ARCHIVE PHOTO GOES HERE",
           font=font("Inter-Bold.otf", 30), fill=(150, 150, 150), anchor="mm")
    d.text((W * SS / 2, H * SS / 2), "(the GitHub version uses the real NBS photo of the collapse)",
           font=font("Inter-Medium.otf", 18), fill=(120, 120, 120), anchor="mm")
    return img


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------

def blueprint_tint(img, k):
    """The photo drained to the blueprint palette, k=0 untouched, k=1 fully."""
    if k <= 0:
        return img
    tinted = ImageOps.colorize(ImageOps.grayscale(img), BG, (150, 182, 232))
    return Image.blend(img, tinted, k)


_last_photo = {}


def a_last_frame(photo):
    """Sample A's final photo frame, fully tinted: where sample B starts."""
    if photo not in _last_photo:
        img = kb_photo(photo, 1.0) if photo else placeholder_photo(1.0)
        _last_photo[photo] = blueprint_tint(img, 1.0)
    return _last_photo[photo]


def clip_a(t, T, photo):
    img = kb_photo(photo, t / T) if photo else placeholder_photo(t / T)
    # transition out: the last second drains the photo into blueprint colours
    img = blueprint_tint(img, ease(prog(t, T - 1.0, T)))
    f = Frame()
    f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
    out = 1 - prog(t, T - 1.1, T - 0.5)
    a = prog(t, 0.8, 1.6) * out
    # lower third
    f.d.rectangle([60 * SS, 520 * SS, 66 * SS, 600 * SS], fill=RED + (int(255 * a),))
    f.text("KANSAS CITY · 17 JULY 1981 · 7:05 PM", 82, 540, 22, LINE,
           "Inter-Bold.otf", screen=True, alpha=a)
    f.text("Hyatt Regency hotel atrium", 82, 570, 20, DIM, "Inter-Medium.otf",
           screen=True, alpha=a)
    b = prog(t, 2.6, 3.4) * out
    f.text("114", 1180, 470, 110, RED, "InterDisplay-Black.otf", anchor="rs",
           screen=True, alpha=b)
    f.text("PEOPLE KILLED", 1180, 505, 26, LINE, "Inter-Bold.otf", anchor="rs",
           screen=True, alpha=b)
    f.tag("A", "REAL ARCHIVE PHOTO + SCALE")
    f.caption("Two walkways fell into a crowded hotel lobby.", prog(t, 0.3, 1.0) * out)
    return f.done()


B_ZOOM_END = 7.6


def b_camera(t):
    # wide, then push in on the middle 4th-floor connection
    k = prog(t, 5.0, B_ZOOM_END)
    return (lerp(W / 2, RODS[1], k), lerp(H / 2 - 20, W4_Y + 8, k), lerp(1.0, 5.2, k))


def b_content(f, t, label_alpha=1.0):
    zoomed = f.zoom > 2.2
    draw_atrium(f, t_walls=prog(t, 0.3, 1.6), t_roof=prog(t, 1.4, 2.4),
                t_rods=prog(t, 2.3, 3.4), t_walks=prog(t, 3.2, 4.4),
                skip_mid=zoomed)
    draw_people(f, GROUND_Y, 230, 1050, prog(t, 4.0, 4.6))
    draw_people(f, W2_Y - DECK_H, 320, 960, prog(t, 4.0, 4.6), n=14, seed=5)
    draw_people(f, W4_Y - DECK_H, 320, 960, prog(t, 4.0, 4.6), n=12, seed=7)
    if zoomed:
        draw_connection_detail(f, 1, pulse=(t - B_ZOOM_END) if t > B_ZOOM_END else 0)
    la = prog(t, 3.6, 4.3) * (1 - prog(t, 4.9, 5.3))
    f.label("roof trusses", 700, ROOF_Y - 17, 860, 70, la)
    f.label("steel hanger rods", RODS[2] + 4, 230, 1010, 230, la)
    f.label("4th-floor walkway", 520, W4_Y - 5, 380, 270, la)
    f.label("2nd-floor walkway", 520, W2_Y - 5, 380, 480, la)
    lb = prog(t, 7.8, 8.4) * label_alpha
    f.label("box beam (two steel channels welded)", RODS[1] + 18, W4_Y + 4, 900, 250, lb, size=19)
    f.label("one nut holds everything", RODS[1] - 4, W4_Y + BEAM_H + 2, 300, 520, lb, RED, size=19)


def clip_b(t, T, photo=None):
    cx, cy, z = b_camera(t)
    f = Frame(cx, cy, z)
    # transition in: A's last frame (the photo, already blueprint-tinted)
    # dissolves away while the grid and the first lines draw over it
    under = 1 - ease(prog(t, 0.0, 1.4))
    if under > 0:
        f.img = Image.blend(f.img, a_last_frame(photo), under)
        f.d = ImageDraw.Draw(f.img, "RGBA")
    f.grid(prog(t, 0, 0.8))
    b_content(f, t)
    f.tag("B", "SCHEMATIC ANIMATION")
    f.caption("Each walkway hung from steel rods fixed to the roof."
              if t < 5 else "Look closely at one connection.", prog(t, 0.8, 1.4))
    return f.done()


C_LEAD = 1.2      # seconds C spends taking over B's last frame


def clip_c(t, T):
    """Starts on B's last frame, same camera, so B -> C is one shot: the
    camera keeps pushing in while the rest of the building and B's labels
    fade, and the force overlay draws on the connection already on screen."""
    k = ease(prog(t, 0, C_LEAD))
    bx, by, bz = b_camera(9.5)
    f = Frame(lerp(bx, RODS[1], k), lerp(by, W4_Y + 14, k), lerp(bz, 6.0, k))
    f.grid(1)
    if k < 1:
        g = Frame(f.cx, f.cy, f.zoom)
        g.grid(1)
        b_content(g, 9.5, label_alpha=1 - prog(t, 0, 0.6))
        g.caption("Look closely at one connection.", 1 - prog(t, 0, 0.5))
        f = _clip_c_body(f, t - C_LEAD * 0.5, T)
        return Image.blend(g.done(), f.done(), k)
    return _clip_c_body(f, t - C_LEAD * 0.5, T).done()


def _clip_c_body(f, t, T):
    stress = prog(t, 3.5, 7.0)
    crack = prog(t, 6.2, 8.0)
    x, y = RODS[1], W4_Y
    f.rect(WALK_X0, y - DECK_H, WALK_X1, y, LINE, None, 1.5)      # deck edge
    draw_connection_detail(f, 1, stress, crack)
    # 4th-floor walkway load: down onto the beam from the deck
    a1 = prog(t, 0.6, 1.4)
    f.arrow(x - 16, y - 30, x - 16, y - 2, AMBER, 6, 16, a1)
    f.text("4th-floor walkway", 520, 140, 22, AMBER, "Inter-Bold.otf", screen=True,
           alpha=a1, anchor="rs")
    f.text("its own weight", 520, 166, 18, LINE, "Inter-Medium.otf", screen=True,
           alpha=a1, anchor="rs")
    # 2nd-floor walkway load: pulling down on the lower rod
    a2 = prog(t, 1.8, 2.6)
    f.arrow(x + 12, y + 32, x + 12, y + 56, AMBER, 6, 16, a2)
    f.text("2nd-floor walkway", 740, 540, 22, AMBER, "Inter-Bold.otf", screen=True, alpha=a2)
    f.text("hangs from THIS beam", 740, 566, 18, LINE, "Inter-Medium.otf", screen=True, alpha=a2)
    # both arrive at the one nut
    a3 = prog(t, 3.0, 3.8)
    f.arrow(x - 4, y + BEAM_H + 4, x - 4, y + BEAM_H + 22, RED, 10, 22, a3)
    f.text("2×", 590, 470, 70, RED, "InterDisplay-Black.otf", screen=True, alpha=a3, anchor="rs")
    f.text("LOAD ON ONE NUT", 590, 504, 22, RED, "Inter-Bold.otf", screen=True,
           alpha=a3, anchor="rs")
    # side panel
    p = prog(t, 4.0, 4.8)
    f.d.rectangle([40 * SS, 250 * SS, 330 * SS, 400 * SS], fill=(0, 0, 0, int(150 * p)))
    f.text("AS DESIGNED", 58, 278, 16, CYAN, "Inter-Bold.otf", screen=True, alpha=p)
    f.text("1 walkway per nut", 58, 304, 20, LINE, "Inter-Medium.otf", screen=True, alpha=p)
    f.text("AS BUILT", 58, 344, 16, RED, "Inter-Bold.otf", screen=True, alpha=p)
    f.text("2 walkways on one nut", 58, 370, 20, LINE, "Inter-Medium.otf", screen=True, alpha=p)
    if crack > 0:
        f.text("the nut pulls through the steel", W - 40, 120, 24, RED, "Inter-Bold.otf",
               screen=True, alpha=prog(t, 6.4, 7.0), anchor="rs")
    f.tag("C", "FORCE & STRESS OVERLAY")
    f.caption("A change to the rods doubled the load on this one nut.", prog(t, 0.2, 0.8))
    return f


def clip_d(t, T):
    f = Frame()
    f.grid(0.6)
    cols, rows = 80, 20          # 1,600 people
    x0, y0, dx, dy = 140, 160, 12.5, 18
    shown = int(cols * rows * prog(t, 0.3, 2.6))
    red_n = int(114 * prog(t, 3.2, 4.4))
    amb_n = int(216 * prog(t, 4.6, 5.6))
    order = [(i % cols, i // cols) for i in range(cols * rows)]
    import random
    rnd = random.Random(11)
    hit = rnd.sample(range(cols * rows), 114 + 216)
    reds, ambs = set(hit[:red_n]), set(hit[114:114 + amb_n])
    for i, (c, r) in enumerate(order[:shown]):
        col = RED if i in reds else AMBER if i in ambs else DIM
        px, py = f.P(x0 + c * dx, y0 + r * dy)
        rr = 2.6 * SS
        f.d.ellipse([px - rr, py - rr - 6 * SS, px + rr, py + rr - 6 * SS], fill=col)
        f.d.rectangle([px - 2.4 * SS, py - 2 * SS, px + 2.4 * SS, py + 6 * SS], fill=col)
    f.text(f"{min(1600, shown):,}", 140, 130, 34, LINE, "InterDisplay-Bold.otf", screen=True)
    f.text("people in the atrium, at a tea dance", 262, 130, 20, DIM, "Inter-Medium.otf", screen=True)
    if red_n:
        f.text(f"{red_n}", 140, 570, 54, RED, "InterDisplay-Black.otf", screen=True)
        f.text("killed", 245, 570, 24, RED, "Inter-Bold.otf", screen=True)
    if amb_n:
        f.text(f"{amb_n}", 420, 570, 54, AMBER, "InterDisplay-Black.otf", screen=True)
        f.text("injured", 525, 570, 24, AMBER, "Inter-Bold.otf", screen=True)
    f.tag("D", "SCALE GRAPHIC")
    f.caption("At the time, the deadliest structural collapse in US history.", prog(t, 4.6, 5.2))
    return f.done()


def clip_e(t, T):
    f = Frame()
    f.grid(0.6)
    events = [
        (0.08, "1979", "Rod design changed", "two rods instead of one"),
        (0.33, "OCT 1979", "Atrium roof collapses", "during construction"),
        (0.62, "1 JUL 1980", "Hotel opens", ""),
        (0.94, "17 JUL 1981", "Walkways fall", "7:05 pm"),
    ]
    split = 5.2
    if t < split:
        x0, x1, y = 120, 1160, 360
        p = prog(t, 0.3, 4.2)
        f.poly([(x0, y), (x1, y)], GRID_MAJOR, 6)
        f.poly([(x0, y), (x1, y)], CYAN, 6, p)
        for i, (pos, date, title, sub) in enumerate(events):
            x = lerp(x0, x1, pos)
            on = p >= pos
            col = (RED if i == 3 else AMBER if i == 1 else CYAN) if on else GRID_MAJOR
            a, b = f.P(x - 9, y - 9), f.P(x + 9, y + 9)
            f.d.ellipse([a, b], fill=col)
            if on:
                up = i % 2 == 0
                ty = y - 70 if up else y + 50
                f.text(date, x, ty, 18, col, "Inter-Bold.otf", anchor="mm")
                f.text(title, x, ty + (26 if up else 26), 19, LINE, "Inter-SemiBold.otf", anchor="mm")
                if sub:
                    f.text(sub, x, ty + 50, 15, DIM, "Inter-Medium.otf", anchor="mm")
        f.caption("There were warnings.", prog(t, 2.2, 2.8))
    else:
        tt = t - split
        secs = min(10, int(tt / (T - split - 0.6) * 10))
        hh = f"7:04:{50 + secs:02d}" if secs < 10 else "7:05:00"
        col = RED if secs >= 10 else LINE
        f.text(hh, W / 2, H / 2 - 10, 120, col, "InterDisplay-Bold.otf", anchor="mm")
        f.text("PM · FRIDAY 17 JULY 1981", W / 2, H / 2 + 80, 22, DIM, "Inter-Bold.otf", anchor="mm")
        if secs >= 10:
            f.text("THE 4TH-FLOOR CONNECTION FAILS", W / 2, H / 2 - 120, 24, RED,
                   "Inter-Bold.otf", anchor="mm")
    f.tag("E", "TIMELINE & CLOCK")
    return f.done()


def clip_f(t, T):
    left = Frame(W / 2, H / 2 - 10, 0.5)
    left.grid(0.6)
    fall = prog(t, 5.0, 6.2)
    # the 4th-floor walkway drops onto the 2nd, then both fall to the floor
    gap = W2_Y - W4_Y - BEAM_H - DECK_H
    drop2 = (GROUND_Y - W2_Y - BEAM_H) * prog(fall, 0.55, 1.0)
    drop4 = gap * min(1, fall / 0.55) + drop2
    # left half: as designed
    imgL = Frame(W / 2, H / 2 - 10, 0.52)
    imgL.grid(0.6)
    draw_atrium(imgL, built=False, rod_color=CYAN)
    imgR = Frame(W / 2, H / 2 - 10, 0.52)
    imgR.grid(0.6)
    draw_atrium(imgR, built=True, drop4=drop4, drop2=drop2,
                highlight=(t - 2.5) if 2.5 < t < 5.0 else 0)
    # load labels
    for fr, labels in ((imgL, [("1×", CYAN), ("1×", CYAN)]), (imgR, [("2×", RED), ("1×", AMBER)])):
        a = prog(t, 1.4, 2.2) * (1 - fall)
        for (s, col), y in zip(labels, (W4_Y, W2_Y)):
            fr.text(s, RODS[1] + 40, y + 30, 40, col, "InterDisplay-Black.otf", alpha=a)
    out = Image.new("RGB", (W, H), BG)
    out.paste(imgL.done().crop((W // 4, 0, W // 4 + W // 2, H)), (0, 0))
    out.paste(imgR.done().crop((W // 4, 0, W // 4 + W // 2, H)), (W // 2, 0))
    f = Frame()
    f.img = out.resize((W * SS, H * SS))
    f.d = ImageDraw.Draw(f.img, "RGBA")
    f.d.line([(W * SS / 2, 0), (W * SS / 2, H * SS)], fill=LINE, width=2 * SS)
    f.text("AS DESIGNED", W / 4, 92, 24, CYAN, "Inter-Bold.otf", anchor="mm", screen=True)
    f.text("one continuous rod", W / 4, 120, 17, LINE, "Inter-Medium.otf", anchor="mm", screen=True)
    f.text("AS BUILT", 3 * W / 4, 92, 24, RED, "Inter-Bold.otf", anchor="mm", screen=True)
    f.text("two rods, one beam carries both", 3 * W / 4, 120, 17, LINE, "Inter-Medium.otf",
           anchor="mm", screen=True)
    if t > 6.4:
        a = prog(t, 6.4, 7.0)
        f.text("HOLDS", W / 4 + 22, 640, 34, GREEN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.text("FAILS", 3 * W / 4 + 22, 640, 34, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        cx, cy = (W / 4 - 70) * SS, 640 * SS
        f.d.line([(cx - 12 * SS, cy), (cx - 3 * SS, cy + 10 * SS), (cx + 14 * SS, cy - 12 * SS)],
                 fill=GREEN + (int(255 * a),), width=5 * SS)
        cx = (3 * W / 4 - 64) * SS
        for s1, s2 in (((-11, -11), (11, 11)), ((-11, 11), (11, -11))):
            f.d.line([(cx + s1[0] * SS, cy + s1[1] * SS), (cx + s2[0] * SS, cy + s2[1] * SS)],
                     fill=RED + (int(255 * a),), width=5 * SS)
    f.tag("F", "AS DESIGNED vs AS BUILT")
    return f.done()


CLIPS = [("a", clip_a, 5.0), ("b", clip_b, 9.5), ("c", clip_c, 9.1),
         ("d", clip_d, 6.5), ("e", clip_e, 8.0), ("f", clip_f, 8.0)]


# How each sample hands over to the next. "continuous": the next sample is
# built to start on this one's last frame (same camera, same drawing), so a
# plain join is already seamless. "dissolve": two different drawings on the
# same blueprint board, cross-faded so only the content changes.
TRANSITIONS = {("a", "b"): "continuous", ("b", "c"): "continuous",
               ("c", "d"): "dissolve", ("d", "e"): "dissolve", ("e", "f"): "dissolve"}
DISSOLVE = 0.6


def _encode(frames_dir, mp4):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                    "-i", os.path.join(frames_dir, "%05d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)


def render(out_dir, photo=None, only=None, stills=False):
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for key, fn, T in CLIPS:
        if only and key not in only:
            continue
        frames = os.path.join(out_dir, f"_frames_{key}")
        os.makedirs(frames, exist_ok=True)
        n = int(T * FPS)
        for i in range(n):
            t = i / FPS
            img = fn(t, T, photo) if key in ("a", "b") else fn(t, T)
            img.save(os.path.join(frames, f"{i:05d}.png"))
            if stills and i == int(n * 0.85):
                img.save(os.path.join(out_dir, f"still_{key}.png"))
        mp4 = os.path.join(out_dir, f"sample_{key}.mp4")
        _encode(frames, mp4)
        made.append((key, frames))
        print(f"rendered {mp4} ({T:.1f}s)")
    if len(made) > 1:
        reel_dir = os.path.join(out_dir, "_frames_reel")
        os.makedirs(reel_dir, exist_ok=True)
        seq, skip = [], 0   # a path, or (path, path to blend in, weight)
        for i, (key, frames) in enumerate(made):
            files = [os.path.join(frames, x) for x in sorted(os.listdir(frames))][skip:]
            skip = 0
            nxt = made[i + 1] if i + 1 < len(made) else None
            if nxt and TRANSITIONS.get((key, nxt[0])) == "dissolve":
                k = int(DISSOLVE * FPS)
                head = [os.path.join(nxt[1], x) for x in sorted(os.listdir(nxt[1]))[:k]]
                seq.extend(files[:-k])
                seq.extend((x, y, (j + 1) / (k + 1))
                           for j, (x, y) in enumerate(zip(files[-k:], head)))
                skip = k
            else:
                seq.extend(files)
        for j, item in enumerate(seq):
            out = os.path.join(reel_dir, f"{j:05d}.png")
            if isinstance(item, tuple):
                a, b, w = item
                Image.blend(Image.open(a).convert("RGB"), Image.open(b).convert("RGB"),
                            ease(w)).save(out)
            else:
                shutil.copyfile(item, out)
        reel = os.path.join(out_dir, "style_samples_A_to_F.mp4")
        _encode(reel_dir, reel)
        print(f"reel: {reel} ({len(seq) / FPS:.1f}s)")
        shutil.rmtree(reel_dir)
    for _, frames in made:
        shutil.rmtree(frames)
    return [os.path.join(out_dir, f"sample_{k}.mp4") for k, _ in made]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--photo")
    ap.add_argument("--only", default="")
    ap.add_argument("--stills", action="store_true")
    a = ap.parse_args()
    render(a.out_dir, a.photo, set(a.only) if a.only else None, a.stills)
    sys.exit(0)
