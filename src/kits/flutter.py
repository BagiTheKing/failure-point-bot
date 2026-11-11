"""
Bridge kit, variant "flutter": a long, narrow suspension bridge stiffened by
shallow solid plate girders instead of a deep open truss. The wind cannot
pass through the girders; the deck heaves in waves, then twists about its
centre line, and the wind feeds each twist so it grows until the hangers
fail and the main span falls (the Tacoma Narrows Bridge, 7 November 1940,
is the reference: 2,800 ft main span, 39 ft wide, 8 ft girders where the
state's engineers had planned 25 ft trusses; a steady 42 mph wind; a twist
of 12 cycles a minute).

The kit owns the drawing; the sheet supplies the words. Clips, each
(t, T) -> Image, continuous with the one before:

    build     the Narrows and its banks, the piers and towers, the cables,
              the hangers and the deck draw themselves; in on the deck; a
              cut through it: two solid girders 8 ft deep, and drawn over
              them in dashes the 25 ft open truss first planned
    physics   the cut through the deck in the wind: the wind cannot pass
              the solid girder and swirls above and below it; the deck
              heaves in waves along the span (Galloping Gertie); then it
              twists about its centre line, the two halves of the span
              turning opposite ways; each twist lets the wind push harder
              and the swing grows; the hangers fail
    fall      the elevation: the middle of the main span tears away and
              falls, then the rest, the side spans sag
    compare   what it needed (an open, deep truss: the wind passes
              through, the deck stays put) against what it had (a solid,
              shallow girder: the wind catches it, each swing grows)

Every step has its own framing, and the camera never stops moving (owner,
2026-11-05: shots of 4 to 8 s, nothing standing still).
"""

import math

from PIL import Image

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            prog, lerp, mix, Frame, Beats, KitTiming, fit)

WATER = (60, 150, 230)
WIND = (150, 220, 255)

# the elevation, looking north: Gig Harbor (west) on the left, Tacoma on the right.
# 1,100 ft side spans and a 2,800 ft main span at one scale.
XA0, XA1 = 40, 1240                          # the anchorages
FT = (XA1 - XA0) / 5000.0                    # px per foot
XT0, XT1 = XA0 + 1100 * FT, XA0 + 3900 * FT  # west tower, east tower
TOP_Y = 236                                  # the tower tops (cable saddles)
DECK_Y = 470                                 # the deck
RIVER_Y = 560                                # the water
BANK_L, BANK_R = XT0 - 120, XT1 + 120

# the cut through the deck (world units; the camera frames it)
CX, CY = 640, 380                            # the deck's centre
HALF_W = 195                                 # half of 39 ft, at 10 px a foot
G_D = 80                                     # an 8 ft girder
T_D = 250                                    # the 25 ft truss first planned


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _rot(px, py, cx, cy, a):
    s, c = math.sin(a), math.cos(a)
    return (cx + (px - cx) * c - (py - cy) * s, cy + (px - cx) * s + (py - cy) * c)


class FlutterBridge(KitTiming):
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        self.labels = k.get("labels", {})
        self.bridge = k.get("bridge", "")
        self.dvb = sheet.get("design_vs_built", {})
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}

    # -------------------------------------------------------------- the bridge
    @staticmethod
    def cable_y(x):
        if XT0 <= x <= XT1:
            u = (x - XT0) / (XT1 - XT0)
            return TOP_Y + (DECK_Y - 12 - TOP_Y) * 4 * u * (1 - u)
        if x < XT0:
            u = (x - XA0) / (XT0 - XA0)
            return lerp(DECK_Y - 4, TOP_Y, u) + 28 * 4 * u * (1 - u)
        u = (x - XT1) / (XA1 - XT1)
        return lerp(TOP_Y, DECK_Y - 4, u) + 28 * 4 * u * (1 - u)

    def deck_y(self, x, wave=0.0, twist=0.0, phase=0.0, fall=0.0):
        """The deck's edge at x: vertical waves (wave, px), the near edge of a
        twist (twist, px at the quarter points), and how far it has fallen."""
        y = DECK_Y
        if XT0 < x < XT1:
            u = (x - XT0) / (XT1 - XT0)
            y += wave * math.sin(3 * math.pi * u) * math.sin(phase)
            y += twist * math.sin(2 * math.pi * u) * math.sin(phase)
            y += self.drop(x, fall)
        else:
            y += 22 * ease(fall * 1.6 - 0.6) * math.sin(math.pi * (x - (XA0 if x < XT0 else XT1)) /
                                                        (XT0 - XA0))
        return y

    def drop(self, x, tf):
        """How far the main span at x has fallen at fall progress tf: the middle
        first, then the rest outward to the towers."""
        if not (XT0 < x < XT1) or tf <= 0:
            return 0.0
        mid = (XT0 + XT1) / 2
        d = abs(x - mid) / ((XT1 - XT0) / 2)
        t0 = 0.0 if d < 0.22 else 0.35 + 0.4 * (d - 0.22)
        k = ease((tf - t0) / 0.25)
        return k * (RIVER_Y + 6 - DECK_Y)

    def scenery(self, f, alpha=1.0, t=0.0):
        a = alpha
        f.poly([(0, RIVER_Y - 70), (BANK_L - 60, RIVER_Y - 60), (BANK_L, RIVER_Y + 6)], DIM, 2, a)
        f.poly([(W, RIVER_Y - 70), (BANK_R + 60, RIVER_Y - 60), (BANK_R, RIVER_Y + 6)], DIM, 2, a)
        if a > 0:
            for k in range(9):
                x = lerp(BANK_L + 30, BANK_R - 70, k / 8) + 14 * math.sin(t * 0.8 + k)
                f.poly([(x, RIVER_Y + 14 + (k % 3) * 9), (x + 40, RIVER_Y + 14 + (k % 3) * 9)],
                       mix(BG, WATER, 0.6 * a), 2)
        L = self.labels
        f.text(L.get("west", "GIG HARBOR"), 40, RIVER_Y + 60, 20, mix(BG, DIM, a), "Inter-Bold.otf", screen=True)
        f.text(L.get("east", "TACOMA"), W - 40, RIVER_Y + 60, 20, mix(BG, DIM, a), "Inter-Bold.otf",
               screen=True, anchor="ra")

    def towers(self, f, frac=1.0, color=LINE):
        for x in (XT0, XT1):
            f.rect(x - 14, RIVER_Y - 20, x + 14, RIVER_Y + 6, DIM, None, 2, frac)        # the pier
            for dx in (-6, 6):
                f.poly([(x + dx, RIVER_Y - 20), (x + dx, TOP_Y - 6)], color, 3, frac)
            for y in (TOP_Y + 4, TOP_Y + 80, DECK_Y + 22):                                # the portal struts
                f.poly([(x - 6, y), (x + 6, y)], color, 3, frac)

    def cable(self, f, frac=1.0, color=LINE):
        xs = [lerp(XA0, XA1, k / 160) for k in range(161)]
        f.poly([(x, self.cable_y(x)) for x in xs], color, 3, frac)

    def deck(self, f, frac=1.0, wave=0.0, twist=0.0, phase=0.0, fall=0.0, color=LINE, hangers=True):
        xs = [lerp(XA0, XA1, k / 200) for k in range(201)]
        near = [(x, self.deck_y(x, wave, twist, phase, fall)) for x in xs]
        far = [(x, self.deck_y(x, wave, -twist, phase, fall) - 6) for x in xs]
        torn = lambda x: XT0 < x < XT1 and self.drop(x, fall) > 1
        for line, col, w in ((far, DIM, 1.6), (near, color, 2.8)):
            run = []
            for x, y in line:
                if torn(x):
                    if len(run) > 1:
                        f.poly(run, col, w, frac)
                    run = []
                else:
                    run.append((x, y))
            if len(run) > 1:
                f.poly(run, col, w, frac)
        if not hangers:
            return
        n = int(len(xs) * frac)
        for x, y in near[:n:4]:
            cy = self.cable_y(x)
            if cy < y - 6 and not torn(x):
                f.poly([(x, cy), (x, y)], DIM, 1.0)
            elif torn(x) and cy < DECK_Y - 6:                    # a snapped hanger, hanging
                f.poly([(x, cy), (x + 3, cy + 26)], DIM, 1.0)

    # -------------------------------------------------------------- the cut through the deck
    def section(self, f, angle=0.0, lift=0.0, girder=True, truss=False, truss_ghost=0.0, alpha=1.0,
                cx=CX, cy=CY, scale=1.0, road=True, color=LINE):
        """The deck in cross-section, looking along the bridge: the road slab
        between two girders (solid plate, G_D deep) or two trusses (open,
        T_D deep), turned by `angle` about the centre line and lifted."""
        cy = cy - lift
        hw, gd, td = HALF_W * scale, G_D * scale, T_D * scale
        R = lambda px, py: _rot(px, py, cx, cy, angle)
        if road:
            f.poly([R(cx - hw, cy), R(cx + hw, cy)], color, 4 * scale, alpha)           # the slab
            for sx in (-1, 1):                                                          # the sidewalks
                f.poly([R(cx + sx * hw * 0.67, cy - 4 * scale), R(cx + sx * hw, cy - 4 * scale)], DIM, 2, alpha)
        if girder:
            for sx in (-1, 1):
                x = cx + sx * hw
                pts = [R(x - 10 * scale, cy - gd * 0.3), R(x + 10 * scale, cy - gd * 0.3),
                       R(x + 10 * scale, cy + gd * 0.7), R(x - 10 * scale, cy + gd * 0.7),
                       R(x - 10 * scale, cy - gd * 0.3)]
                f.poly(pts, color, 3, alpha)
                f.poly([R(x, cy - gd * 0.3), R(x, cy + gd * 0.7)], color, 6 * scale, alpha)   # the solid web
        if truss or truss_ghost > 0:
            a = alpha if truss else truss_ghost
            col = color if truss else mix(BG, CYAN, 0.9)
            for sx in (-1, 1):
                x = cx + sx * hw
                top, bot = cy - 10 * scale, cy + td - 10 * scale
                f.poly([R(x, top), R(x, bot)], col, 2.4, a)
                for j in range(5):                                      # the open web: the wind goes through
                    y0, y1 = lerp(top, bot, j / 5), lerp(top, bot, (j + 1) / 5)
                    f.poly([R(x - 12 * scale, y0), R(x + 12 * scale, y1)], col, 1.6, a)
                    f.poly([R(x + 12 * scale, y0), R(x - 12 * scale, y1)], col, 1.6, a)
            f.poly([R(cx - hw, cy + td - 10 * scale), R(cx + hw, cy + td - 10 * scale)], col, 2, a)  # bottom chord
        return R

    def wind(self, f, t, through=False, alpha=1.0, y0=CY - 160, y1=CY + 200, x0=60, x1=None, strength=1.0):
        """Wind from the left as streaks moving right. Through an open truss
        they pass straight; against the solid girder they bend over and under
        it and curl into eddies behind (above and below the deck)."""
        if alpha <= 0:
            return
        x1 = x1 or W - 60
        for j in range(9):
            y = lerp(y0, y1, j / 8)
            for k in range(3):
                s = ((t * 0.55 * strength + k / 3 + j * 0.13) % 1.0)
                xa = lerp(x0, x1, s)
                xb = xa + 90
                if through or abs(y - CY) > G_D * 1.4 or xb < CX - HALF_W - 40:
                    f.arrow(xa, y, xb, y, mix(BG, WIND, 0.85), 2, 8, alpha)
                elif xa < CX + HALF_W + 40:
                    # deflected: over the deck above it, under it below
                    sgn = -1 if y < CY + G_D * 0.2 else 1
                    pts = [(xa, y), (xa + 45, y + sgn * 40), (xb, y + sgn * 70)]
                    f.poly(pts, mix(BG, WIND, 0.85), 2, alpha)
                else:
                    # eddies behind the girder
                    r = 20 + 12 * ((t * 2 + j) % 1)
                    cxe, cye = xa + 30, CY + (-1 if j % 2 else 1) * (G_D * 0.9)
                    pts = [(cxe + r * math.cos(a), cye + r * math.sin(a)) for a in
                           [i * 0.35 + t * 3 for i in range(16)]]
                    f.poly(pts, mix(BG, WIND, 0.7), 2, alpha)

    # -------------------------------------------------------------- the clips
    BUILD = Beats(("banks", 1.0, 0.2), ("towers", 1.4, 0.4), ("cable", 1.8, 0.4), ("deck", 1.6, 0.6),
                  ("labels", 0.7, 2.4), ("zoom", 1.8, 0.4), ("cut", 1.2, 2.2), ("planned", 1.2, 2.6),
                  ("ratio", 0.8, 2.6))
    PHYS = Beats(("lead", 1.0, 0.3), ("wind", 1.2, 2.4), ("eddies", 1.0, 2.4), ("waves", 1.6, 3.0),
                 ("twist", 1.6, 3.0), ("halves", 1.2, 2.6), ("grows", 3.6, 1.6), ("loop", 1.0, 2.6),
                 ("snap", 1.2, 2.0))
    FALL = Beats(("pull", 1.2, 0.3), ("middle", 2.0, 0.6), ("rest", 3.0, 0.8), ("sag", 1.2, 2.4))
    COMP = Beats(("show", 1.0, 0.6), ("wind", 1.2, 1.6), ("swing", 3.0, 1.2), ("verdict", 0.6, 2.8))

    def b_camera(self, t):
        """Wide while the bridge draws itself; halfway through the hold on its
        labels, in toward the west quarter of the main span; then into the
        cut through the deck. A slow push all through."""
        b = self.BUILD
        mid = (b.end("labels") + b.start("zoom")) / 2 - 1.0
        e = ease(prog(t, mid, mid + 1.0))
        cx, cy, z = lerp(W / 2, (XT0 + W / 2) / 2, e), lerp(H / 2 + 30, DECK_Y - 60, e), lerp(1.0, 1.5, e)
        k = b.p(t, "zoom")
        creep = 1 + 0.004 * min(max(t, 0.0), b.total)
        # through the long hold on the cut: a slow push in toward the girder and a
        # drift across (the Tacoma review copy held this frame for ~20 s)
        h = ease(prog(t, b.end("zoom"), b.total))
        dx = 70 * h + 30 * math.sin(0.5 * t)
        return lerp(cx, CX + dx, k), lerp(cy, CY + 40 - 30 * h, k), lerp(z, 1.0 + 0.45 * h, k) * creep

    def b_content(self, f, t, label_alpha=1.0):
        b = self.BUILD
        out = b.p(t, "zoom")
        if out < 1:
            g = 1 - out
            self.scenery(f, b.p(t, "banks") * g, t)
            self.towers(f, b.p(t, "towers"), mix(BG, LINE, g))
            self.cable(f, b.p(t, "cable"), mix(BG, LINE, g))
            self.deck(f, b.p(t, "deck"), wave=2.0, phase=t * 1.3, color=mix(BG, LINE, g))
            la = b.p(t, "labels") * b.until(t, "zoom") * label_alpha
            L = self.labels
            f.label(L.get("span", "main span: 2,800 ft"), (XT0 + XT1) / 2, DECK_Y, 760, 640, la)
            f.label(L.get("tower", "steel towers on concrete piers"), XT1, TOP_Y + 40, 1060, 170, la, AMBER)
            f.label(L.get("width", "only 39 ft wide: two lanes"), XT0 + 120, DECK_Y, 260, 650, la, DIM)
        if out > 0:
            # the cut fades in as the elevation fades out: never an empty frame
            ca = max(b.p(t, "cut"), ease(out))
            # it rocks a little in the wind already, the way the summer's waves moved it
            self.section(f, angle=math.radians(1.5) * math.sin(2 * math.pi * 0.2 * t), alpha=ca)
            L = self.labels
            ga = ca * label_alpha
            f.label(L.get("girder", "solid plate girder: 8 ft deep"), CX + HALF_W, CY + G_D * 0.2, 1000, 230, ga, AMBER)
            pa = b.p(t, "planned")
            self.section(f, girder=False, road=False, truss_ghost=pa * 0.9)
            f.label(L.get("planned", "first planned: an open truss 25 ft deep"), CX - HALF_W, CY + T_D * 0.6,
                    260, 650, pa * label_alpha, CYAN)
            ra = b.p(t, "ratio")
            f.text(L.get("ratio", "depth to span: 1 to 350"), W / 2, 110, 30, RED, "InterDisplay-Black.otf",
                   anchor="mm", screen=True, alpha=ra * label_alpha)

    def build(self, t, T=None):
        b = self.BUILD
        f = Frame(*self.b_camera(t))
        f.grid(prog(t, 0, 0.8))
        self.b_content(f, t)
        f.caption(self.captions.get("build", ""), prog(t, 0.8, 1.4) * b.until(t, "zoom", 0.3)
                  + prog(t, b.end("cut"), b.end("cut") + 0.5))
        return f.done()

    def p_camera(self, t):
        """A framing per step: the cut in the wind, the eddies behind it, out
        to the span for the waves and the twist, in on one quarter point as
        the swings grow, the loop, the hangers."""
        b = self.PHYS
        cam = (CX, CY + 40, 1.0)
        for beat, to in (("eddies", (CX + 120, CY + 30, 1.25)), ("waves", (W / 2, DECK_Y - 70, 1.0)),
                         ("twist", (W / 2, DECK_Y - 70, 1.05)), ("halves", ((XT0 + W / 2) / 2, DECK_Y - 40, 1.6)),
                         ("grows", (CX, CY + 40, 1.0)), ("loop", (CX, CY + 20, 1.15)),
                         ("snap", (W / 2, DECK_Y - 90, 1.1))):
            e = b.p(t, beat)
            cam = tuple(lerp(a_, b_, e) for a_, b_ in zip(cam, to))
        creep = 1 + 0.004 * min(max(t, 0.0), b.total)
        return cam[0], cam[1], cam[2] * creep

    def physics(self, t, T=None, lead=True):
        b = self.PHYS
        f = Frame(*self.p_camera(t))
        f.grid(1)
        L = self.labels
        # the cut and the span cross-fade (never an empty frame between them)
        xf = lambda name: prog(t, b.start(name) - 0.5, b.start(name) + 0.3)
        sec_a = (1 - xf("waves")) + xf("grows") * (1 - xf("snap"))
        span_a = xf("waves") * (1 - xf("grows")) + xf("snap")
        # 1. the cut in the wind
        if sec_a > 0:
            grow = b.p(t, "grows")
            amp = math.radians(4 + 26 * grow ** 1.5)
            ang = amp * math.sin(2 * math.pi * 0.35 * t) * prog(t, b.start("grows"), b.start("grows") + 0.4)
            self.section(f, angle=ang, alpha=sec_a)
            self.wind(f, t, through=False, alpha=sec_a * b.p(t, "wind"))
            wa = b.p(t, "wind") * b.until(t, "eddies")
            f.text(L.get("wind", "a steady wind: it cannot pass through the girder"), 60, 110, 24, WIND,
                   "Inter-Bold.otf", screen=True, alpha=wa)
            ea = b.p(t, "eddies") * b.until(t, "waves")
            f.text(L.get("eddies", "it swirls over and under the deck"), 60, 110, 24, WIND, "Inter-Bold.otf",
                   screen=True, alpha=ea)
            ga = grow * b.until(t, "loop")
            f.text(L.get("grows", "each twist lets the wind push harder"), 60, 110, 24, RED, "Inter-Bold.otf",
                   screen=True, alpha=ga)
            if grow > 0:                                            # the swings, growing, drawn as a trace
                pts = []
                for i in range(120):
                    tt = t - (119 - i) * 0.05
                    gg = prog(tt, b.start("grows"), b.end("grows"))
                    pts.append((900 + i * 2.6, 620 - 60 * (0.15 + 0.85 * gg ** 1.5) *
                                math.sin(2 * math.pi * 0.35 * tt)))
                f.poly([(x, y) for x, y in pts], RED, 2, sec_a)
            la = b.p(t, "loop") * b.until(t, "snap")
            if la > 0:                                              # the loop: twist -> more push -> more twist
                for k in range(3):
                    a0, a1 = k * 2.1 + t, k * 2.1 + 1.7 + t
                    f.poly([(CX + 260 * math.cos(a0 + (a1 - a0) * i / 12), CY + 40 + 150 * math.sin(a0 + (a1 - a0) * i / 12))
                            for i in range(13)], AMBER, 3, la)
                f.text(L.get("loop", "flutter: the motion feeds itself"), 60, 110, 24, AMBER, "Inter-Bold.otf",
                       screen=True, alpha=la)
        # 2. the span: waves, then the twist
        if span_a > 0:
            ph = 2 * math.pi * 0.25 * t
            wave = 26 * b.p(t, "waves") * b.until(t, "twist")
            tw = 30 * b.p(t, "twist") + 30 * b.p(t, "snap")
            snap = b.p(t, "snap")
            self.towers(f, span_a, mix(BG, LINE, span_a))
            self.cable(f, span_a, mix(BG, LINE, span_a))
            self.deck(f, span_a, wave=wave, twist=tw, phase=ph, fall=0.18 * snap, color=mix(BG, LINE, span_a))
            va = b.p(t, "waves") * b.until(t, "twist")
            f.text(L.get("waves", "the deck rose and fell in waves: \"Galloping Gertie\""), 60, 110, 24, LINE,
                   "Inter-Bold.otf", screen=True, alpha=va * span_a)
            ta = b.p(t, "twist") * b.until(t, "grows")
            f.text(L.get("twist", "7 November 1940: it began to twist"), 60, 110, 24, AMBER, "Inter-Bold.otf",
                   screen=True, alpha=ta)
            ha = b.p(t, "halves") * b.until(t, "grows")
            if ha > 0:
                mid = (XT0 + XT1) / 2
                f.label(L.get("node", "the centre line stays still"), mid, DECK_Y, 640, 230, ha, CYAN)
                for u, sgn in ((0.25, 1), (0.75, -1)):
                    x = lerp(XT0, XT1, u)
                    s = math.sin(ph) * sgn
                    f.arrow(x, DECK_Y - 40, x, DECK_Y - 40 - 50 * s, AMBER, 3, 10, ha)
                f.text(L.get("halves", "one half turns one way, the other half the other"), 60, 150, 20, LINE,
                       "Inter-Medium.otf", screen=True, alpha=ha)
            sa = snap
            f.text(L.get("snap", "the hangers fail: the deck falls"), 60, 110, 24, RED, "Inter-Bold.otf",
                   screen=True, alpha=sa)
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8) * b.until(t, "eddies"))
        img = f.done()
        if lead and b.p(t, "lead") < 1:
            g = Frame(*self.b_camera(999))
            g.grid(1)
            self.b_content(g, 999, label_alpha=1 - prog(t, 0, 0.6))
            img = Image.blend(g.done(), img, b.p(t, "lead"))
        return img

    def fall(self, t, T=None):
        b = self.FALL
        k = b.p(t, "pull")
        f = Frame(lerp(W / 2, W / 2, k), lerp(DECK_Y - 70, H / 2 + 30, k), lerp(1.1, 1.0, k))
        f.grid(1)
        tf = 0.5 * b.p(t, "middle") + 0.5 * b.p(t, "rest")
        self.scenery(f, 1, t)
        self.towers(f, 1)
        self.cable(f, 1)
        self.deck(f, 1, twist=30 * (1 - b.p(t, "middle")), phase=2 * math.pi * 0.25 * t, fall=tf + 0.6 * b.p(t, "sag"))
        if tf > 0:                                               # splashes where the deck meets the water
            for x in range(int(XT0) + 10, int(XT1) - 10, 30):
                d = self.drop(x, tf)
                if d > (RIVER_Y - DECK_Y) * 0.9:
                    s = min(1.0, (d - (RIVER_Y - DECK_Y) * 0.9) / 10)
                    for j in range(3):
                        f.arrow(x, RIVER_Y, x + (j - 1) * 12, RIVER_Y - 30 * s, mix(BG, WATER, 0.8), 2, 6, s)
        f.caption(self.captions.get("fall", ""), prog(t, b.end("pull"), b.end("pull") + 0.5))
        return f.done()

    def side(self, built, deck=1.0, wind=0.0, swing=0.0, verdict=0.0, stamp=0.0, stamp_text="",
             mark=0.0, clock=0.0):
        """One side of the comparison on its own, for a Short (what it needed
        above, what it had below): the cut through the deck, close, in the
        wind. The open truss lets the wind through and barely moves; the
        solid girder turns the wind into eddies and twists further each
        swing. clock: seconds into the scene (the twist keeps going)."""
        f = Frame(CX + 20, CY + 50, 1.25)
        f.grid(1)
        rock = math.sin(2 * math.pi * 0.45 * clock)
        if built:
            ang = math.radians(2 + 26 * swing ** 1.4) * rock * max(0.15, swing)
            R = self.section(f, angle=ang, alpha=deck)
        else:
            ang = math.radians(1.5) * rock * swing
            R = self.section(f, angle=ang, girder=False, truss=True, alpha=deck)
        self.wind(f, clock, through=not built, alpha=wind, x0=CX - 560, x1=CX + 520, strength=1.4)
        if mark > 0 and built:                     # a ring closing in on the solid web
            r = 70 + 90 * (1 - min(1.0, mark))
            x, y = R(CX + HALF_W, CY + G_D * 0.2)
            pts = [(x + r * math.cos(a / 24 * 2 * math.pi), y + r * math.sin(a / 24 * 2 * math.pi))
                   for a in range(25)]
            f.poly(pts, RED, 4, min(1.0, mark * 2))
        if stamp > 0 and stamp_text and verdict < 1:
            k = min(1.0, stamp)
            f.text(stamp_text, W / 2, 80, int(52 * (1.6 - 0.6 * k)), RED, "InterDisplay-Black.otf",
                   anchor="mm", screen=True, alpha=k)
        if verdict > 0:
            word, col = ("FAILS", RED) if built else ("HOLDS", GREEN)
            f.text(word, W / 2, 80, 96, col, "InterDisplay-Black.otf", anchor="mm", screen=True, alpha=verdict)
        return f.done()

    def compare(self, t, T=None):
        b = self.COMP
        wind, swing = b.p(t, "wind"), b.p(t, "swing")
        halves = []
        for built in (False, True):
            g = Frame(CX + 40, CY + 60, 0.62)
            g.grid(0.6)
            if built:
                amp = math.radians(3 + 27 * swing ** 1.5)
                ang = amp * math.sin(2 * math.pi * 0.35 * t) * swing
                self.section(g, angle=ang)
            else:
                ang = math.radians(1.2) * math.sin(2 * math.pi * 0.35 * t) * swing
                self.section(g, angle=ang, girder=False, truss=True)
            self.wind(g, t, through=not built, alpha=wind, x0=CX - 600, x1=CX + 560)
            halves.append(g.done().crop((W // 4, 0, W // 4 + W // 2, H)))
        out = Image.new("RGB", (W, H), BG)
        out.paste(halves[0], (0, 0))
        out.paste(halves[1], (W // 2, 0))
        f = Frame()
        from PIL import ImageDraw
        f.img = out.resize((W * SS, H * SS))
        f.d = ImageDraw.Draw(f.img, "RGBA")
        f.d.line([(W * SS / 2, 0), (W * SS / 2, H * SS)], fill=LINE, width=2 * SS)
        d, bb = self.dvb.get("designed", {}), self.dvb.get("built", {})
        for x, side, col in ((W / 4, d, CYAN), (3 * W / 4, bb, RED)):
            f.text(side.get("title", ""), x, 92, 24, col, "Inter-Bold.otf", anchor="mm", screen=True)
            f.text(side.get("detail", ""), x, 120, fit(side.get("detail", ""), 17, "Inter-Medium.otf", 560), LINE,
                   "Inter-Medium.otf", anchor="mm", screen=True)
            if side.get("load"):
                f.text(side["load"], x, 560, fit(side["load"], 18, "Inter-Bold.otf", 560), col, "Inter-Bold.otf",
                       anchor="mm", screen=True, alpha=wind)
        a = b.p(t, "verdict")
        if a > 0:
            f.text("HOLDS", W / 4, 620, 34, GREEN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
            f.text("FAILS", 3 * W / 4, 620, 34, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.caption(self.captions.get("compare", ""), prog(t, 0.4, 1.0))
        return f.done()
