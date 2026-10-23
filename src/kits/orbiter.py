"""
Spaceflight kit, variant "orbiter": a winged orbiter whose wing leading edge
is a row of heat-shield panels (reinforced carbon-carbon); debris strikes
one panel at launch and breaches it; on re-entry the hot gas around the
wing gets in through the hole, the aluminium structure behind it melts, and
the wing, then the vehicle, break up (Columbia, STS-107, 2003, is the
reference).

The kit owns the drawing, so the vehicle is always right; the sheet supplies
the words and numbers. Clips, each (t, T) -> Image, continuous with the one
before:

    build     the orbiter draws itself from above, its leading-edge panels
              counted out, labels, push-in on the breached panel
    physics   the leading edge in section: the heat shield and the spar
              behind it; the debris strike opens a hole; days pass; re-entry
              heat wraps the wing, gets in, and the structure melts
    fall      pull back to the sky: the wing gives, the vehicle breaks apart
              into streaks
    compare   as designed (the panel whole: the heat flows round it, the wing
              holds) vs as it was (the breach: fails)
"""

import math
import random

from PIL import Image

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            prog, lerp, mix, Frame, Beats, KitTiming, fit)

# the plan view, nose left, port wing below the centre line; world = screen px at zoom 1
CY = 360
X_NOSE, X_BODY, X_TAIL = 140, 262, 1000
HW = 52                                            # the fuselage's half width
# one wing's outline as (x, offset from the centre line): glove, main leading edge, tip, trailing edge
WING = [(400, HW), (560, 94), (865, 262), (910, 268), (968, 246), (975, HW)]
N_PANELS = 22

# the leading edge in section (physics, compare): the heat shield's C, the spar behind it
LX, LY, LR = 430, 380, 118                         # the C's centre and radius
C0, C1, HOLE_A = 70, 290, 135                      # the C runs round the front (180 deg); the hole on its lower face
SPAR_X = 500
HOT = (255, 120, 40)


def _arc(cx, cy, r, a0, a1, n=40):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


class Orbiter(KitTiming):
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        self.labels = k.get("labels", {})
        self.vehicle = k.get("vehicle", "")
        self.panel = int(k.get("panel", 8) or 8)
        self.days = str(k.get("days", "") or "")
        self.heat = k.get("heat", "")                  # e.g. "about 3,000 °F"
        dvb = sheet.get("design_vs_built", {})
        self.dvb = dvb
        self.mult = dvb.get("multiplier", "")
        self.mult_label = dvb.get("multiplier_label", "")
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}

    # ------------------------------------------------------------------ drawing
    @staticmethod
    def _wing_pts(side):
        return [(x, CY + side * v) for x, v in WING]

    def body(self, f, frac=1.0, color=LINE, width=2.4):
        """The fuselage from above, nose to engines."""
        nose = []
        for i in range(17):                            # the rounded nose, port to starboard
            a = math.pi * (0.5 + i / 16)
            nose.append((X_BODY + (X_BODY - X_NOSE) * math.cos(a) * 0.95, CY + HW * math.sin(a) * -1))
        pts = [(X_TAIL, CY + HW)] + [(X_BODY, CY + HW)] + nose + [(X_BODY, CY - HW), (X_TAIL, CY - HW),
                                                                   (X_TAIL, CY + HW)]
        f.poly(pts, color, width, frac)

    def wings(self, f, frac=1.0, color=LINE):
        for side in (1, -1):
            f.poly(self._wing_pts(side), color, 2.2, frac)

    def details(self, f, frac=1.0):
        """Payload bay doors, the tail, the engine pods, the nose cap."""
        if frac <= 0:
            return
        f.rect(330, CY - HW + 10, 900, CY + HW - 10, DIM, None, 1.4, frac)
        f.poly([(615, CY - HW + 10), (615, CY + HW - 10)], DIM, 1.2, frac)
        f.poly([(880, CY), (1030, CY)], LINE, 3, frac)                         # the fin, edge on
        for side in (1, -1):
            f.rect(905, CY + side * 30 - 14, 1018, CY + side * 30 + 14, DIM, None, 1.4, frac)
        for dy in (-20, 0, 20):                                               # main engines
            f.poly([(1000, CY + dy - 7), (1030, CY + dy - 10), (1030, CY + dy + 10), (1000, CY + dy + 7)], DIM, 1.4, frac)

    def le_points(self, side=1):
        """The wing's main leading edge, root to tip: where the 22 panels sit
        (the glove ahead of it is drawn plain)."""
        return self._wing_pts(side)[1:3]

    def panel_span(self, i, side=1):
        """The leading edge between panel i's two ends (1-based, root to tip)."""
        pts = self.le_points(side)
        segs = list(zip(pts, pts[1:]))
        lens = [math.dist(a, b) for a, b in segs]
        total = sum(lens)

        def at(d):
            for (a, b), L in zip(segs, lens):
                if d <= L:
                    return lerp(a[0], b[0], d / L), lerp(a[1], b[1], d / L)
                d -= L
            return pts[-1]
        return at(total * (i - 1) / N_PANELS), at(total * i / N_PANELS)

    def panels(self, f, frac=1.0, focus=0.0, breach=0.0, side=1):
        """The leading edge's heat-shield panels counted out root to tip;
        the sheet's panel ringed (focus) and breached (breach)."""
        n = int(round(N_PANELS * frac))
        for i in range(1, n + 1):
            (ax, ay), (bx, by) = self.panel_span(i, side)
            col = (88, 96, 112) if i % 2 else (120, 128, 144)
            if i == self.panel and breach > 0:
                col = mix(col, RED, breach)
            f.poly([(ax, ay), (bx, by)], col, 7)
        if focus > 0 and n >= self.panel:
            (ax, ay), (bx, by) = self.panel_span(self.panel, side)
            cx, cy = f.P((ax + bx) / 2, (ay + by) / 2)
            r = 16 * SS * max(1.0, f.zoom * 0.6)
            pulse = 0.6 + 0.4 * math.sin(focus * 9)
            f.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RED + (int(255 * focus * pulse),), width=3 * SS)

    def vehicle_full(self, f, frac=(1, 1, 1, 1), focus=0.0, breach=0.0, color=LINE):
        t_body, t_wing, t_det, t_pan = frac
        self.body(f, t_body, color)
        self.wings(f, t_wing, color)
        self.details(f, t_det)
        self.panels(f, t_pan, focus, breach)

    # the leading edge in section --------------------------------------------
    @staticmethod
    def _skin(x, side):
        """The wing skin's y at x behind the heat shield (side -1 upper, 1 lower)."""
        x0 = LX + LR * math.cos(math.radians(C0))
        k = (x - x0) / (1200 - x0)
        return LY + side * LR * lerp(math.sin(math.radians(C0)), 0.6, k)

    @staticmethod
    def hole_xy():
        return LX + LR * math.cos(math.radians(HOLE_A)), LY + LR * math.sin(math.radians(HOLE_A))

    def section(self, f, shell=1.0, wing=1.0, hole=0.0, heat=0.0, breach=0.0, melt=0.0, flow=0.0, t=0.0):
        """The heat shield's C round the wing's front (the air comes from the
        left), the spar and skins behind it; a hole in its lower face; the
        heat outside, getting in."""
        d = f.d
        hot = mix(LINE, HOT, heat)
        # the air around the edge: streams split by the edge, red-hot on re-entry
        if flow > 0:
            for k, y in enumerate((210, 260, 310, 450, 500, 550)):
                ph = (t * 1.3 + k * 0.17) % 1.0
                side = -1 if y < LY else 1
                y_edge = LY + side * (LR + 16 + 10 * (k % 3))
                pts = [(40, y), (LX - LR * 1.2, lerp(y, y_edge, 0.5)), (LX, y_edge),
                       (1200, self._skin(1200, side) + side * (16 + 10 * (k % 3)))]
                f.poly(pts, mix(DIM, HOT, heat) + (int(200 * flow),), 2)
                px = lerp(60, 1100, ph)
                py = lerp(y, y_edge, min(1.0, max(0.0, (px - 40) / (LX - 40))))
                f.arrow(px - 30, py, px, py, mix(AMBER, HOT, heat), 3, 9, flow)
        if heat > 0:                                     # the shock layer's glow ahead of the edge
            for k in range(7, 0, -1):
                r = (LR + 14 * k) * SS * f.zoom
                cx, cy = f.P(LX - 30, LY)
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=HOT + (int(9 * heat * (8 - k) / 2),))
        # the wing box behind: spar, upper and lower skins, ribs; the spar melts from below
        if wing > 0:
            x0 = LX + LR * math.cos(math.radians(C0))
            for side in (-1, 1):
                f.poly([(x0, self._skin(x0, side)), (1200, self._skin(1200, side))], LINE, 2.4, wing)
            top, bot = self._skin(SPAR_X, -1), self._skin(SPAR_X, 1)
            gone = melt * (bot - top)
            spar_col = mix(LINE, RED, min(1.0, breach * 1.4))
            f.poly([(SPAR_X, top), (SPAR_X, bot - gone)], spar_col, 5, wing)
            for x in (700, 860, 1020):                   # the ribs behind it go too, less the further back
                g = gone * max(0.0, 1 - (x - SPAR_X) / 700)
                f.poly([(x, self._skin(x, -1)), (x, self._skin(x, 1) - g)], mix(DIM, RED, melt * 0.8), 2, wing)
            if melt > 0:                                 # what melted, dripping
                rnd = random.Random(4)
                for _ in range(int(18 * melt)):
                    x = SPAR_X + rnd.uniform(-6, 40)
                    y = bot - gone * rnd.random() + 26 * melt * rnd.random()
                    rr = rnd.uniform(2, 5) * SS * f.zoom
                    px, py = f.P(x, y)
                    d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=RED + (int(220 * melt),))
        # the heat shield: a thick C, with the hole in its lower face
        if shell > 0:
            if hole > 0:
                gap = 14 * hole
                f.poly(_arc(LX, LY, LR, C0, HOLE_A - gap), hot, 12, shell)
                f.poly(_arc(LX, LY, LR, HOLE_A + gap, C1), hot, 12, shell)
            else:
                f.poly(_arc(LX, LY, LR, C0, C1), hot, 12, shell)
        # the hot gas getting in through the hole, filling the edge, reaching the spar
        if breach > 0 and hole > 0:
            hx, hy = self.hole_xy()
            for k in range(5):
                ang = math.radians(-75 + k * 15)
                ln = 40 + 120 * breach
                f.arrow(hx - 34, hy + 34, hx + ln * math.cos(ang), hy + ln * math.sin(ang), RED, 4, 12, breach)
            for k in range(6, 0, -1):
                r = (16 + 16 * k) * breach * SS * f.zoom
                cx, cy = f.P(LX + 20, LY + 10)
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED + (int(14 * (7 - k)),))

    def foam(self, f, k):
        """The debris on its way to the panel (k 0..1) and the flash as it hits (k > 1)."""
        if k <= 0:
            return
        hx, hy = self.hole_xy()
        if k < 1:
            x, y = lerp(-80, hx - 14, k), lerp(LY + 230, hy + 8, k)
            ang = k * 7
            pts = []
            for dx, dy in ((-26, -12), (26, -16), (22, 14), (-24, 12), (-26, -12)):
                c, s_ = math.cos(ang), math.sin(ang)
                pts.append((x + dx * c - dy * s_, y + dx * s_ + dy * c))
            f.poly(pts, AMBER, 3)
        else:
            fl = max(0.0, 1 - (k - 1) * 4)
            if fl > 0:
                cx, cy = f.P(hx, hy)
                for r in (60, 40, 22):
                    rr = r * SS * f.zoom * (1.4 - fl * 0.4)
                    f.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 230, 180, int(90 * fl)))

    # -------------------------------------------------------------------- clips
    BUILD = Beats(("body", 1.8, 0.2), ("wings", 1.2, 0.2), ("details", 1.0, 0.4),
                  ("panels", 1.4, 0.6), ("labels", 0.7, 2.4), ("zoom", 2.4, 0.4), ("node", 0.6, 2.8))
    PHYS = Beats(("lead", 1.2, 0.3), ("section", 1.2, 1.8), ("foam", 1.1, 0.0), ("hole", 0.5, 2.2),
                 ("days", 2.2, 0.8), ("heat", 1.4, 2.0), ("breach", 1.6, 2.2), ("melt", 2.4, 2.0))
    FALL = Beats(("handover", 0.8, 0.0), ("pull", 1.8, 0.9), ("wing", 0.6, 0.2),
                 ("breakup", 1.4, 0.0), ("settle", 0.1, 2.0), ("toll", 0.6, 2.8))
    COMP = Beats(("show", 1.0, 0.6), ("heat", 1.2, 2.2), ("breach", 1.4, 2.0),
                 ("melt", 1.2, 0.6), ("verdict", 0.6, 2.8))

    def b_camera(self, t):
        k = self.BUILD.p(t, "zoom")
        (ax, ay), (bx, by) = self.panel_span(self.panel)
        return (lerp(W / 2 + 20, (ax + bx) / 2, k), lerp(H / 2, (ay + by) / 2, k), lerp(1.0, 4.0, k))

    def b_content(self, f, t, label_alpha=1.0):
        b = self.BUILD
        self.vehicle_full(f, (b.p(t, "body"), b.p(t, "wings"), b.p(t, "details"), b.p(t, "panels")),
                          focus=(t - b.start("node")) if t > b.start("node") else 0)
        la = b.p(t, "labels") * b.until(t, "zoom")
        L = self.labels
        f.label(L.get("vehicle", self.vehicle or "orbiter"), 600, CY - HW + 4, 640, 120, la)
        f.label(L.get("wing", "left wing"), 860, CY + 150, 980, 600, la)
        (ax, ay), (bx, by) = self.panel_span(14)
        f.label(L.get("leading_edge", "leading edge: 22 heat-shield panels"), (ax + bx) / 2, (ay + by) / 2,
                760, 560, la, AMBER)
        lb = b.p(t, "node") * label_alpha
        (ax, ay), (bx, by) = self.panel_span(self.panel)
        f.label(L.get("panel", f"panel {self.panel}"), (ax + bx) / 2, (ay + by) / 2, 300, 520, lb, RED, size=19)

    def build(self, t, T=None):
        b = self.BUILD
        f = Frame(*self.b_camera(t))
        f.grid(prog(t, 0, 0.8))
        self.b_content(f, t)
        zoom_at = b.start("zoom")
        cap = self.captions.get("establish") if t < zoom_at else self.captions.get("connection")
        f.caption(cap or "", (prog(t, 0.8, 1.4) * b.until(t, "zoom", 0.3)) if t < zoom_at
                  else prog(t, zoom_at + 0.3, zoom_at + 0.8))
        return f.done()

    def _days(self, a):
        digits = "".join(ch for ch in self.days if ch.isdigit())
        if not digits:
            return ""
        return str(max(1, int(round(int(digits) * min(1.0, a / 0.9)))))

    def physics(self, t, T=None, lead=True):
        k = self.PHYS.p(t, "lead") if lead else 1
        f = Frame()
        f.grid(1)
        self._physics_body(f, t)
        if k < 1:
            g = Frame(*self.b_camera(999))
            g.grid(1)
            self.b_content(g, 999, label_alpha=1 - prog(t, 0, 0.6))
            return Image.blend(g.done(), f.done(), k)
        return f.done()

    def _physics_body(self, f, t):
        b = self.PHYS
        L = self.labels
        foam_k = b.p(t, "foam") + (max(0.0, t - b.end("foam")) if t > b.end("foam") else 0)
        self.section(f, b.p(t, "section"), b.p(t, "section"), hole=b.p(t, "hole"),
                     heat=b.p(t, "heat"), breach=b.p(t, "breach"), melt=b.p(t, "melt"),
                     flow=max(b.p(t, "section") * b.until(t, "foam"), b.p(t, "heat")), t=t)
        self.foam(f, foam_k if t < b.end("hole") + 0.6 else 0)
        a = b.p(t, "section") * b.until(t, "foam")
        f.text(L.get("shield", "the heat shield (carbon-carbon)"), 60, 120, 22, LINE, "Inter-Bold.otf",
               screen=True, alpha=a)
        f.text(L.get("spar", "the wing's aluminium spar"), SPAR_X + 20, self._skin(SPAR_X, -1) - 36, 20, LINE,
               "Inter-Bold.otf", screen=True, alpha=a)
        fo = b.p(t, "foam") * b.until(t, "days")
        f.text(L.get("foam", "foam from the tank, at launch"), 60, 120, 22, AMBER, "Inter-Bold.otf", screen=True,
               alpha=fo)
        ho = b.p(t, "hole") * b.until(t, "days")
        f.text(L.get("hole", "a hole in the panel"), LX - 60, LY + LR + 64, 24, RED, "Inter-Bold.otf",
               screen=True, alpha=ho, anchor="ma")
        dy = b.p(t, "days") * b.until(t, "heat")
        n = self._days(b.p(t, "days"))
        if n:
            f.text(n, W - 60, 190, 96, LINE, "InterDisplay-Black.otf", screen=True, alpha=dy, anchor="rs")
            f.text("DAYS IN ORBIT", W - 60, 224, 22, DIM, "Inter-Bold.otf", screen=True, alpha=dy, anchor="rs")
        he = b.p(t, "heat") * b.until(t, "melt")
        f.text(L.get("heat", "re-entry: the air around the wing glows white-hot"),
               60, 120, 22, HOT, "Inter-Bold.otf", screen=True, alpha=he)
        br = b.p(t, "breach") * b.until(t, "melt")
        f.text(L.get("breach", "superheated air gets in through the hole"), W - 60, 640, 24, RED, "Inter-Bold.otf",
               screen=True, alpha=br, anchor="rs")
        me = b.p(t, "melt")
        f.text(L.get("melt", "the aluminium behind it melts"), W - 60, 640, 26, RED, "Inter-Bold.otf",
               screen=True, alpha=me, anchor="rs")
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8) * b.until(t, "foam"))
        return f

    _phys_last = None

    def _pieces(self, f, k, x0, y0, seed=5):
        """The vehicle coming apart (k from 0): pieces carried on along the
        flight path at their own speeds, each a bright head with its trail
        behind it, spreading as they fall."""
        if k <= 0:
            return
        rnd = random.Random(seed)
        for i in range(22):
            ang = rnd.uniform(-0.25, 0.35)
            sp = rnd.uniform(60, 420)
            dx, dy = -k * sp * math.cos(ang), k * sp * math.sin(ang) + 40 * k * k
            x, y = x0 + rnd.uniform(-220, 220) + dx, y0 + rnd.uniform(-50, 50) + dy
            trail = min(1.0, k * 2) * rnd.uniform(140, 320)
            col = mix(HOT, (255, 245, 220), rnd.random())
            f.poly([(x + trail, y - trail * math.tan(ang) * 0.4), (x, y)], col + (int(160 * min(1.0, k * 3)),), 3)
            s = rnd.uniform(3, 9)
            cx, cy = f.P(x, y)
            r = s * SS * f.zoom
            f.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 245, 225, 230))

    def fall(self, t, T=None):
        b = self.FALL
        k = b.p(t, "pull")
        f = Frame(lerp(W / 2, W / 2 + 40, k), lerp(H / 2, H / 2, k), lerp(1.0, 0.7, k))
        f.grid(1)
        wing = b.p(t, "wing")
        brk = b.p(t, "breakup")
        heat = min(1.0, 0.3 + k)
        # the glow along the edges as it flies through the upper air
        if brk < 1:
            a = 1 - brk
            for k2 in range(6, 0, -1):
                cx, cy = f.P(X_NOSE + 20, CY)
                r = (40 + 26 * k2) * SS * f.zoom
                f.d.ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], fill=HOT + (int(10 * heat * a * (7 - k2) / 2),))
            self.body(f, 1, LINE + (int(255 * a),))
            f.poly(self._wing_pts(-1), LINE + (int(255 * a),), 2.2)
            if wing < 1:
                f.poly(self._wing_pts(1), mix(LINE, RED, wing) + (int(255 * a),), 2.2)
            else:                                        # the left wing's leading edge has gone
                f.poly(self._wing_pts(1)[2:], RED + (int(255 * a),), 2.2)
            self.panels(f, 1, breach=1)
        self._pieces(f, brk + max(0.0, t - b.end("breakup")) * 0.2, 620, CY)
        nums = self.sheet.get("numbers", [])
        if nums:
            a = b.p(t, "toll")
            f.text(nums[0]["value"], 1180, 560, 96, RED, "InterDisplay-Black.otf", anchor="rs", screen=True, alpha=a)
            f.text(nums[0]["label"], 1180, 596, fit(nums[0]["label"], 24, "Inter-Bold.otf", 520), LINE,
                   "Inter-Bold.otf", anchor="rs", screen=True, alpha=a)
        f.caption(self.captions.get("fall", ""), prog(t, b.end("pull"), b.end("pull") + 0.5))
        img = f.done()
        h = b.p(t, "handover")
        if h < 1:
            if self._phys_last is None:
                self._phys_last = self.physics(self.PHYS.total - 1 / 30)
            img = Image.blend(self._phys_last, img, h)
        return img

    def side(self, built, shell=1.0, wing=1.0, flow=0.0, foam=0.0, hole=0.0, heat=0.0, breach=0.0,
             melt=0.0, verdict=0.0, stamp=0.0, stamp_text="", counter=""):
        """One side of the comparison on its own, for a Short (owner,
        2026-10-22: "what it needed" above "as built", both drawn from
        nothing at the same time): the leading edge in section, whole (the
        heat flows round it) or struck and breached (it gets in, the spar
        melts). Each argument a 0..1 progress; `counter` (days in orbit)
        sits top right."""
        f = Frame(W / 2 + 40, LY, 1.0)
        f.grid(1)
        if not built:
            foam = hole = breach = melt = 0.0
        self.section(f, shell, wing, hole=hole, heat=heat, breach=breach, melt=melt, flow=flow, t=heat * 3)
        if built:
            self.foam(f, foam if foam < 1 else 1 + hole * 0.3)
            if counter:
                f.text(counter, 1180, 150, 64, LINE, "InterDisplay-Black.otf", anchor="rs", screen=True)
                f.text("DAYS IN ORBIT", 1180, 182, 22, DIM, "Inter-Bold.otf", anchor="rs", screen=True)
        if stamp > 0 and stamp_text and verdict < 1:
            k = min(1.0, stamp)
            f.text(stamp_text, W / 2 + 120, 90, int(56 * (1.6 - 0.6 * k)), RED, "InterDisplay-Black.otf",
                   anchor="mm", screen=True, alpha=k * (1 - min(1.0, melt * 4)))
        if verdict > 0:
            word, col = ("FAILS", RED) if built else ("HOLDS", GREEN)
            f.text(word, W / 2 + 120, 90, 96, col, "InterDisplay-Black.otf", anchor="mm", screen=True, alpha=verdict)
        return f.done()

    def compare(self, t, T=None):
        b = self.COMP
        heat, breach, melt = b.p(t, "heat"), b.p(t, "breach"), b.p(t, "melt")
        left = Frame(W / 2 + 40, LY, 0.52)
        left.grid(0.6)
        self.section(left, 1, 1, heat=heat, flow=1, t=t)
        right = Frame(W / 2 + 40, LY, 0.52)
        right.grid(0.6)
        self.section(right, 1, 1, hole=1, heat=heat, breach=breach, melt=melt, flow=1, t=t)
        out = Image.new("RGB", (W, H), BG)
        out.paste(left.done().crop((W // 4, 0, W // 4 + W // 2, H)), (0, 0))
        out.paste(right.done().crop((W // 4, 0, W // 4 + W // 2, H)), (W // 2, 0))
        f = Frame()
        f.img = out.resize((W * SS, H * SS))
        from PIL import ImageDraw
        f.d = ImageDraw.Draw(f.img, "RGBA")
        f.d.line([(W * SS / 2, 0), (W * SS / 2, H * SS)], fill=LINE, width=2 * SS)
        d, bb = self.dvb.get("designed", {}), self.dvb.get("built", {})
        f.text(d.get("title", "AS DESIGNED"), W / 4, 92, 24, CYAN, "Inter-Bold.otf", anchor="mm", screen=True)
        f.text(d.get("detail", ""), W / 4, 120, fit(d.get("detail", ""), 17, "Inter-Medium.otf", 560), LINE,
               "Inter-Medium.otf", anchor="mm", screen=True)
        f.text(bb.get("title", "AS IT WAS"), 3 * W / 4, 92, 24, RED, "Inter-Bold.otf", anchor="mm", screen=True)
        f.text(bb.get("detail", ""), 3 * W / 4, 120, fit(bb.get("detail", ""), 17, "Inter-Medium.otf", 560), LINE,
               "Inter-Medium.otf", anchor="mm", screen=True)
        for x, s, col in ((W / 4, d.get("load", ""), CYAN), (3 * W / 4, bb.get("load", ""), RED)):
            if s:
                f.text(s, x, 560, fit(s, 18, "Inter-Bold.otf", 560), col, "Inter-Bold.otf", anchor="mm",
                       screen=True, alpha=b.p(t, "heat"))
        a = b.p(t, "verdict")
        if a > 0:
            f.text("HOLDS", W / 4 + 22, 620, 34, GREEN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
            f.text("FAILS", 3 * W / 4 + 22, 620, 34, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.caption(self.captions.get("compare", ""), prog(t, 0.4, 1.0))
        return f.done()
