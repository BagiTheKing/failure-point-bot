"""
Aircraft kit, variant "fuselage": a pressurised airliner fuselage whose skin
is joined along its length by overlapping lap joints, glued and riveted; the
glue lets go, fatigue cracks grow at every rivet of one row, they join, and
a section of the cabin tears away in flight (Aloha Airlines 243, 1988, is
the reference). The same drawing serves the Comet's windows and other skin
failures: the sheet sets the aircraft, the joint and the section.

The kit owns the drawing, so the aircraft is always right; the sheet
supplies the words and numbers. Clips, each (t, T) -> Image, continuous
with the one before:

    build     the airliner draws itself, labels, push-in on the lap joint
    physics   the seam in section: cabin pressure stretches the skin every
              flight, the bond lets go, the load moves to one rivet row,
              cracks grow at every rivet and join
    fall      pull back; the skin unzips and the section above the floor
              tears away; the cabin is open to the sky
    compare   as designed (a crack reaches a tear strap: a small flap opens,
              the cabin vents, the aircraft holds) vs as it was (fails)
"""

import math
import random

from PIL import Image, ImageDraw

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            ease, prog, lerp, mix, Frame, Beats, KitTiming, fit)

# side elevation, nose left; world units = screen px at zoom 1
X_NOSE, X_TAIL = 120, 1160
CY, R = 330, 62                       # fuselage centre line and half-height
TOP, BOT = CY - R, CY + R
FLOOR_Y = CY + 14                     # cabin floor
WIN_Y = CY - 10                       # window row
SEAM_Y = CY - 30                      # the lap joint, above the windows
SEC_X0, SEC_X1 = 255, 560             # the section that tore away (behind the cockpit to the wing)
SEA_Y = 640


class Fuselage(KitTiming):
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        self.labels = k.get("labels", {})
        self.joint = k.get("joint_label", "")
        self.aircraft = k.get("aircraft", "")
        self.cycles = str(k.get("cycles", "") or "")
        dvb = sheet.get("design_vs_built", {})
        self.dvb = dvb
        self.mult = dvb.get("multiplier", "")
        self.mult_label = dvb.get("multiplier_label", "")
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}

    # ------------------------------------------------------------------ drawing
    def outline(self, f, frac=1.0, color=LINE, width=2.4):
        """The fuselage's side outline, nose to tail cone."""
        top = [(X_NOSE + 70, TOP + 4), (X_NOSE + 110, TOP), (1000, TOP), (1090, TOP + 12),
               (1150, CY - 30), (X_TAIL, CY - 22)]
        bot = [(X_TAIL, CY - 22), (1120, CY + 10), (1020, BOT - 6), (980, BOT),
               (X_NOSE + 110, BOT), (X_NOSE + 50, BOT - 10)]
        nose = []
        for i in range(13):                      # the rounded nose, bottom to top
            a = math.pi * (0.5 + i / 12)
            nose.append((X_NOSE + 70 + math.cos(a) * 70, CY + math.sin(a) * (R - 3) * 0.95 + 4))
        nose[0] = (X_NOSE + 50, BOT - 10)
        f.poly(top + bot + nose + [top[0]], color, width, frac)

    def wing_tail(self, f, frac=1.0):
        f.poly([(530, BOT - 18), (720, BOT - 4), (760, BOT + 6), (560, BOT + 6), (530, BOT - 18)], LINE, 2, frac)
        f.rect(520, BOT + 14, 640, BOT + 40, LINE, (18, 38, 66), 2, frac)          # engine pod
        f.poly([(600, BOT + 6), (600, BOT + 14)], DIM, 2, frac)
        f.poly([(1020, TOP + 4), (1080, TOP - 130), (1135, TOP - 130), (1140, CY - 32)], LINE, 2.2, frac)
        f.poly([(1060, CY - 6), (1150, CY - 2), (1150, CY + 6), (1080, CY + 6)], DIM, 2, frac)

    def details(self, f, frac=1.0, skip=None):
        """Windows, cockpit, doors, frames: `skip` (x0, x1) leaves out what tore away."""
        if frac <= 0:
            return
        a = int(255 * frac)
        for x in range(262, 990, 22):
            if skip and skip[0] < x < skip[1]:
                continue
            p, q = f.P(x - 5, WIN_Y - 7), f.P(x + 5, WIN_Y + 7)
            f.d.rounded_rectangle([p, q], radius=3 * SS * f.zoom, outline=DIM + (a,), width=max(1, int(1.4 * SS)))
        for x0 in (150, 172, 194):                   # cockpit windows
            f.poly([(x0, CY - 22), (x0 + 18, CY - 26), (x0 + 18, CY - 12), (x0, CY - 10), (x0, CY - 22)], DIM, 1.6, frac)
        for x in (232, 940):                          # doors
            f.rect(x, CY - 34, x + 22, CY + 34, DIM, None, 1.4, frac)
        for x in range(300, 1000, 44):                # frames, faint
            if skip and skip[0] < x < skip[1]:
                f.poly([(x, FLOOR_Y), (x, BOT - 3)], (40, 66, 104), 1, frac)
                continue
            f.poly([(x, TOP + 3), (x, BOT - 3)], (40, 66, 104), 1, frac)

    def seam(self, f, frac=1.0, color=AMBER, width=2.2, x0=SEC_X0 - 20, x1=990):
        f.poly([(x0, SEAM_Y), (x1, SEAM_Y)], color, width, frac)
        if frac >= 1:
            for x in range(int(x0), int(x1), 9):
                px, py = f.P(x, SEAM_Y)
                r = max(1.0, 1.1 * SS * min(f.zoom, 4))
                f.d.ellipse([px - r, py - r - 2.2 * SS * min(f.zoom, 4) * 0.5, px + r, py + r - 2.2 * SS * min(f.zoom, 4) * 0.5],
                            fill=color)

    def cabin(self, f, x0, x1, alpha=1.0):
        """Seats and heads where the cabin lies open."""
        col = DIM + (int(255 * alpha),)
        for x in range(int(x0) + 8, int(x1) - 4, 20):
            f.rect(x, FLOOR_Y - 18, x + 10, FLOOR_Y, col, None, 1.4)
            px, py = f.P(x + 4, FLOOR_Y - 24)
            r = 3.2 * SS * f.zoom
            f.d.ellipse([px - r, py - r, px + r, py + r], fill=col)
        f.poly([(x0, FLOOR_Y), (x1, FLOOR_Y)], LINE + (int(255 * alpha),), 2)

    def sky(self, f, alpha=1.0, t=0.0):
        """The sea far below and air streaming past: the aircraft is flying."""
        f.poly([(-400, SEA_Y), (1700, SEA_Y)], (30, 64, 104), 2, alpha)
        rnd = random.Random(2)
        for _ in range(16):
            y = rnd.uniform(60, 600)
            x = (rnd.uniform(-200, 1500) - t * 420) % 1700 - 200
            ln = rnd.uniform(40, 120)
            if TOP - 20 < y < BOT + 50 and X_NOSE - 30 < x < X_TAIL + 30:
                continue
            f.poly([(x, y), (x + ln, y)], (34, 62, 100), 1, alpha)

    def aircraft_full(self, f, frac=(1, 1, 1, 1), skip=None):
        t_out, t_wing, t_det, t_seam = frac
        self.outline(f, t_out)
        self.wing_tail(f, t_wing)
        self.details(f, t_det, skip)
        self.seam(f, t_seam)

    def dust(self, f, t_since, x0, x1, y, seed=9, amount=1.0):
        """Debris and insulation streaming back from the opening."""
        if t_since <= 0:
            return
        rnd = random.Random(seed)
        fade = max(0.0, 1 - t_since / 2.8)
        for _ in range(int(70 * amount)):
            x = rnd.uniform(x0, x1)
            vx, vy = rnd.uniform(180, 520), rnd.uniform(-120, 40)
            tt = min(t_since, 1.8)
            px, py = x + vx * tt, y + vy * tt + 40 * tt * tt
            ang = rnd.uniform(0, math.pi)
            f.poly([(px, py), (px + 7 * math.cos(ang), py + 7 * math.sin(ang))],
                   LINE + (int(220 * fade),), 2)
        for _ in range(int(14 * amount)):                 # the cabin air rushing out
            cx, cy = f.P(rnd.uniform(x0, x1), TOP - 10 - rnd.random() * 30 * min(1, t_since))
            rr = (16 + rnd.random() * 34) * min(1, t_since * 1.5) * f.zoom * SS
            f.d.ellipse([cx - rr, cy - rr * 0.6, cx + rr, cy + rr * 0.6],
                        fill=DIM + (int(90 * fade * (0.4 + rnd.random() * 0.6)),))

    # -------------------------------------------------------------------- clips
    BUILD = Beats(("outline", 1.8, 0.2), ("wing", 1.0, 0.2), ("details", 1.2, 0.5),
                  ("labels", 0.7, 2.6), ("seam", 1.0, 1.4), ("zoom", 2.4, 0.4), ("node", 0.6, 2.8))
    PHYS = Beats(("lead", 1.2, 0.3), ("pressure", 0.9, 2.2), ("hoop", 0.8, 2.2),
                 ("bond", 0.8, 2.2), ("disbond", 1.6, 2.2), ("rivets", 0.9, 2.4),
                 ("cycles", 3.0, 0.8), ("link", 1.4, 2.0))
    FALL = Beats(("handover", 0.8, 0.0), ("pull", 1.8, 0.9), ("unzip", 0.5, 0.0),
                 ("tear", 0.9, 0.0), ("settle", 0.1, 2.0), ("toll", 0.6, 2.8))
    COMP = Beats(("show", 1.0, 0.6), ("crack", 0.8, 2.4), ("strap", 0.6, 2.4),
                 ("open", 1.2, 0.6), ("verdict", 0.6, 2.8))

    ZX = 420                                           # where the build pushes in on the seam

    def b_camera(self, t):
        k = self.BUILD.p(t, "zoom")
        return (lerp(W / 2, self.ZX, k), lerp(H / 2 - 20, SEAM_Y + 6, k), lerp(1.0, 4.4, k))

    def b_content(self, f, t, label_alpha=1.0):
        b = self.BUILD
        self.sky(f, b.p(t, "outline"), t)
        self.aircraft_full(f, (b.p(t, "outline"), b.p(t, "wing"), b.p(t, "details"), b.p(t, "seam")))
        la = b.p(t, "labels") * b.until(t, "zoom")
        L = self.labels
        f.label(L.get("fuselage", self.aircraft or "fuselage"), 760, TOP + 2, 820, 130, la)
        f.label(L.get("cabin", "pressurised cabin"), 640, CY + 4, 700, 560, la)
        f.label(L.get("skin", "aluminium skin"), 880, TOP + 10, 980, 190, la)
        ls = b.p(t, "seam") * b.until(t, "zoom")
        f.label(L.get("joint", "lap joint"), 300, SEAM_Y, 160, 160, ls, AMBER)
        lb = b.p(t, "node") * label_alpha
        f.label(L.get("rivets", "rows of rivets"), self.ZX + 10, SEAM_Y - 2, 900, 230, lb, size=19)
        f.label(f"{self.joint} · " + L.get("bond", "glued and riveted") if self.joint else L.get("bond", "glued and riveted"),
                self.ZX - 14, SEAM_Y + 1, 260, 480, lb, RED, size=19)

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

    # the seam in section, in screen units: the outer sheet from the left,
    # the inner one from the right, overlapping across three rivet rows
    SX0, SX1, OV0, OV1 = 150, 1130, 470, 850
    SY = 330                                            # outer sheet's lower face
    ROWS = (540, 660, 780)

    def _section(self, f, t):
        b = self.PHYS
        d = f.d
        sk = lambda x0, y0, x1, y1, col, fill: d.rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=fill,
                                                             outline=col, width=2 * SS)
        hoop = b.p(t, "hoop")
        stretch = 6 * hoop * (0.5 + 0.5 * math.sin(t * 2.4)) if hoop else 0
        dis = b.p(t, "disbond")
        rv = b.p(t, "rivets")
        link = b.p(t, "link")
        part = 26 * link
        # outer sheet (left) and inner sheet (right); after the link-up the outer one lifts away
        sk(self.SX0 - stretch, self.SY - 16 - part, self.OV1, self.SY - part, LINE, (30, 56, 92))
        sk(self.OV0, self.SY + 6, self.SX1 + stretch, self.SY + 22, LINE, (30, 56, 92))
        # the bond between them
        bond = b.p(t, "bond")
        if bond > 0:
            rnd = random.Random(5)
            for x in range(self.OV0 + 2, self.OV1 - 2, 6):
                gone = rnd.random() < dis * 0.92
                col = mix(AMBER, (60, 46, 30), dis) if not gone else (9, 22, 41)
                d.rectangle([x * SS, (self.SY + 0.5) * SS, (x + 5) * SS, (self.SY + 5.5) * SS],
                            fill=col + (int(255 * bond),))
            for _ in range(int(40 * dis)):                       # corrosion between the sheets
                x = rnd.uniform(self.OV0, self.OV1)
                r = rnd.uniform(1.5, 3.5) * SS
                d.ellipse([x * SS - r, (self.SY + 3) * SS - r, x * SS + r, (self.SY + 3) * SS + r],
                          fill=(170, 140, 90, int(200 * dis)))
        # rivets: countersunk heads in the outer sheet
        for i, x in enumerate(self.ROWS):
            hot = i == 0 and rv > 0
            col = mix(LINE, RED, rv if i == 0 else 0)
            lift = part if link and i == 0 else 0
            d.polygon([((x - 9) * SS, (self.SY - 16 - lift) * SS), ((x + 9) * SS, (self.SY - 16 - lift) * SS),
                       ((x + 3) * SS, (self.SY - 6 - lift) * SS), ((x - 3) * SS, (self.SY - 6 - lift) * SS)], fill=col)
            if not (link > 0.3 and i == 0):
                d.rectangle([(x - 3) * SS, (self.SY - 6) * SS, (x + 3) * SS, (self.SY + 28) * SS], fill=col)
            if hot:
                for k in range(5, 0, -1):
                    rr = (6 + k * 5) * SS * (0.6 + rv)
                    d.ellipse([x * SS - rr, (self.SY - 8) * SS - rr, x * SS + rr, (self.SY - 8) * SS + rr],
                              fill=RED + (int(20 * rv * (6 - k) / 2),))

    def _rivet_strip(self, f, t):
        """The rivet row seen from outside: a crack grows from every hole and
        they join into one (multiple-site damage)."""
        b = self.PHYS
        d = f.d
        a = b.p(t, "cycles")
        if a <= 0:
            return
        x0, x1, y = 300, 980, 588
        d.rectangle([x0 * SS, (y - 34) * SS, x1 * SS, (y + 34) * SS], fill=(14, 32, 58, int(235 * min(1, a * 3))),
                    outline=DIM + (int(255 * min(1, a * 3)),), width=2 * SS)
        f.text("THE RIVET ROW, SEEN FROM OUTSIDE", x0, y - 44, 15, DIM, "Inter-Bold.otf", screen=True, alpha=min(1, a * 3))
        holes = [x0 + 30 + i * 52 for i in range(13)]
        grow = a ** 1.4
        link = b.p(t, "link")
        for i, hx in enumerate(holes):
            r = 7 * SS
            d.ellipse([hx * SS - r, y * SS - r, hx * SS + r, y * SS + r], outline=LINE, width=2 * SS)
            rnd = random.Random(i)
            ln = (8 + 14 * rnd.random()) * grow + 26 * link
            for sgn in (-1, 1):
                d.line([((hx + sgn * 7) * SS, y * SS), ((hx + sgn * (7 + ln)) * SS, (y + rnd.uniform(-1.5, 1.5)) * SS)],
                       fill=RED, width=2 * SS)
        if link > 0:
            d.line([((x0 + 30) * SS, y * SS), ((x0 + 30 + (holes[-1] - holes[0]) * link) * SS, y * SS)],
                   fill=RED, width=int(3 * SS))
        # the flight counter
        n = self._count(a)
        f.text(n, W - 60, 210, 64, RED, "InterDisplay-Black.otf", screen=True, alpha=min(1, a * 3), anchor="rs")
        f.text(self.mult_label or "FLIGHTS", W - 60, 240, 20, LINE, "Inter-Bold.otf", screen=True,
               alpha=min(1, a * 3), anchor="rs")

    def _count(self, a):
        """The flight counter, rolling up to the sheet's figure."""
        digits = "".join(ch for ch in (self.cycles or self.mult) if ch.isdigit())
        if not digits:
            return self.mult
        v = int(int(digits) * min(1.0, a / 0.9))
        return f"{v:,}"

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
        self._section(f, t)
        a = b.p(t, "pressure")
        for x in range(200, 1100, 70):                    # cabin pressure, pushing the skin out
            f.arrow(x, self.SY + 110, x, self.SY + 34, AMBER, 4, 12, a)
        f.text("INSIDE · CABIN PRESSURE", 150, self.SY + 150, 20, AMBER, "Inter-Bold.otf", screen=True, alpha=a)
        f.text("OUTSIDE · THIN AIR AT ALTITUDE", 150, self.SY - 120, 20, DIM, "Inter-Bold.otf", screen=True,
               alpha=a * b.until(t, "cycles"))
        h = b.p(t, "hoop")
        f.arrow(self.SX0 + 60, self.SY - 46, self.SX0 - 10, self.SY - 46, AMBER, 5, 14, h * b.until(t, "cycles"))
        f.arrow(self.SX1 - 60, self.SY + 52, self.SX1 + 10, self.SY + 52, AMBER, 5, 14, h * b.until(t, "cycles"))
        f.text("every flight stretches the skin, then lets it go", W - 60, self.SY - 60, 19, LINE,
               "Inter-Medium.otf", screen=True, alpha=h * b.until(t, "bond"), anchor="rs")
        mid = (self.OV0 + self.OV1) / 2
        bo = b.p(t, "bond") * b.until(t, "rivets")
        f.text(L.get("bond", "the bond between the sheets"), mid, self.SY - 76, 20, AMBER,
               "Inter-Bold.otf", screen=True, alpha=bo, anchor="ma")
        ds = b.p(t, "disbond") * b.until(t, "rivets")
        f.text("the bond lets go; salt water gets in", mid, self.SY - 50, 19, RED,
               "Inter-Medium.otf", screen=True, alpha=ds, anchor="ma")
        rv = b.p(t, "rivets") * b.until(t, "link")
        f.text("now one rivet row carries the load", self.ROWS[0], self.SY - 64, 21, RED, "Inter-Bold.otf",
               screen=True, alpha=rv, anchor="ma")
        self._rivet_strip(f, t)
        lk = b.p(t, "link")
        if lk > 0:
            f.text("the cracks join into one", 640, 640, 26, RED, "Inter-Bold.otf", screen=True, alpha=lk, anchor="ma")
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8) * (1 - b.p(t, "cycles")))
        return f

    _phys_last = None

    def _torn(self, f, k, alpha=1.0, seed=3):
        """The section above the floor peeling up and back (k 0..1)."""
        if k <= 0:
            return
        rnd = random.Random(seed)
        step = (SEC_X1 - SEC_X0) / 5
        for i in range(5):
            x0 = SEC_X0 + i * step
            lag = i * 0.08
            kk = max(0.0, min(1.0, (k - lag) / (1 - lag)))
            if kk >= 1:
                continue
            ang = -kk * (1.4 + rnd.random())
            dx, dy = kk * (500 + 300 * rnd.random()), -kk * (140 + 120 * rnd.random())
            cx, cy = x0 + step / 2, (TOP + FLOOR_Y) / 2
            pts = [(x0, TOP), (x0 + step, TOP), (x0 + step, FLOOR_Y - 2), (x0, FLOOR_Y - 2)]
            out = []
            for px, py in pts + [pts[0]]:
                c, s = math.cos(ang), math.sin(ang)
                qx, qy = cx + (px - cx) * c - (py - cy) * s + dx, cy + (px - cx) * s + (py - cy) * c + dy
                out.append((qx, qy))
            f.poly(out, mix(LINE, DIM, kk) + (int(255 * alpha * (1 - kk)),), 2)

    def fall(self, t, T=None):
        b = self.FALL
        k = b.p(t, "pull")
        f = Frame(lerp(W / 2, W / 2, k), lerp(H / 2, H / 2 - 20, k), lerp(1.0, 0.95, k))
        f.grid(1)
        unzip = b.p(t, "unzip")
        tear = b.p(t, "tear")
        hit = b.end("tear")
        shake = 3 * math.sin(t * 60) * max(0, 1 - abs(t - b.start("tear")) * 2.5)
        f.cy += shake
        self.sky(f, 1, t)
        gone = tear > 0.05
        self.outline(f, 1, LINE)
        self.wing_tail(f, 1)
        self.details(f, 1, (SEC_X0, SEC_X1) if gone else None)
        # the seam unzips from front to back, red
        self.seam(f, 1, AMBER, 2.2, SEC_X1, 990)
        if unzip > 0 and not gone:
            f.poly([(SEC_X0, SEAM_Y), (lerp(SEC_X0, SEC_X1, unzip), SEAM_Y)], RED, 3)
        if gone:
            # the opening: the outline's top edge is gone over the section
            f.d.rectangle([f.P(SEC_X0, TOP - 3), f.P(SEC_X1, FLOOR_Y - 3)], fill=BG)
            self.cabin(f, SEC_X0, SEC_X1)
            f.poly([(SEC_X0, TOP + 2), (SEC_X0 - 4, TOP + 14), (SEC_X0 + 3, FLOOR_Y - 2)], RED, 2.4)
            f.poly([(SEC_X1, TOP + 2), (SEC_X1 + 5, TOP + 18), (SEC_X1 - 2, FLOOR_Y - 2)], RED, 2.4)
        else:
            self.seam(f, 1, AMBER, 2.2, SEC_X0 - 20, SEC_X1)
        self._torn(f, tear)
        self.dust(f, t - b.start("tear"), SEC_X0, SEC_X1, TOP + 10)
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

    def side(self, built, outline=1.0, details=1.0, seam=1.0, crack=0.0, strap=0.0, open_=0.0,
             verdict=0.0, stamp=0.0, stamp_text="", counter=""):
        """One side of the comparison on its own, for a Short (owner,
        2026-10-22: "what it needed" above "as built", both drawn from
        nothing at the same time). Each argument is a 0..1 progress: the
        outline and wing, the windows and frames, the lap joint, the crack
        running along it, the tear straps (where it needed them), the
        opening (a flap venting the cabin where it held, the roof tearing
        off as built), the verdict, a stamp; `counter` (the flights flown)
        sits over the built side."""
        f = Frame(440, CY + 10, 1.9)                 # the front half, where it fails: big on a phone
        f.grid(1)
        self.outline(f, outline)
        self.wing_tail(f, outline)
        sx = 420
        if not built:
            # as it needed to be: the crack runs to the next tear strap and stops; a flap vents the cabin
            self.details(f, details)
            self.seam(f, seam, CYAN)
            f.poly([(sx - 60, SEAM_Y), (sx - 60 + 60 * crack, SEAM_Y)], RED, 3.5)
            if strap > 0:
                for x in (sx - 66, sx + 4):
                    f.poly([(x, TOP + 2), (x, FLOOR_Y)], CYAN, 3.5, strap)
            if open_ > 0:
                f.poly([(sx - 60, SEAM_Y), (sx - 30, SEAM_Y - 26 * open_), (sx, SEAM_Y)], LINE, 2.4)
                for i in range(4):
                    f.arrow(sx - 30 + i * 4, SEAM_Y - 30, sx - 10 + i * 10, SEAM_Y - 80 - i * 6, DIM, 2, 8, open_)
        else:
            # as it was: every rivet cracked, the cracks pass the straps, the section goes
            self.details(f, details, (SEC_X0, SEC_X1) if open_ > 0.15 else None)
            self.seam(f, seam, AMBER)
            f.poly([(SEC_X0, SEAM_Y), (lerp(SEC_X0, SEC_X1, crack), SEAM_Y)], RED, 3.5)
            if open_ > 0.15:
                f.d.rectangle([f.P(SEC_X0, TOP - 3), f.P(SEC_X1, FLOOR_Y - 3)], fill=BG)
                self.cabin(f, SEC_X0, SEC_X1)
            self._torn(f, open_)
            if counter:
                f.text(counter, 1180, 150, 48, AMBER, "InterDisplay-Black.otf", anchor="rs", screen=True)
                f.text("FLIGHTS", 1180, 178, 22, LINE, "Inter-Bold.otf", anchor="rs", screen=True)
        if stamp > 0 and stamp_text and verdict < 1:
            k = min(1.0, stamp)
            f.text(stamp_text, W / 2 - 120, 120, int(56 * (1.6 - 0.6 * k)), RED, "InterDisplay-Black.otf",
                   anchor="mm", screen=True, alpha=k * (1 - min(1.0, open_ * 4)))
        if verdict > 0:
            word, col = ("FAILS", RED) if built else ("HOLDS", GREEN)
            f.text(word, W / 2 - 120, 120, 96, col, "InterDisplay-Black.otf", anchor="mm", screen=True, alpha=verdict)
        return f.done()

    def compare(self, t, T=None):
        b = self.COMP
        crack = b.p(t, "crack")
        op = b.p(t, "open")
        left = Frame(W / 2, H / 2 - 10, 0.52)
        left.grid(0.6)
        right = Frame(W / 2, H / 2 - 10, 0.52)
        right.grid(0.6)
        for fr in (left, right):
            self.outline(fr, 1)
            self.wing_tail(fr, 1)
        # as designed: the crack runs to the next tear strap and stops; a small flap vents the cabin
        self.details(left, 1)
        self.seam(left, 1, CYAN)
        sx = 420
        left.poly([(sx - 60, SEAM_Y), (sx - 60 + 60 * crack, SEAM_Y)], RED, 3)
        if b.p(t, "strap") > 0:
            for x in (sx - 66, sx + 4):
                left.poly([(x, TOP + 2), (x, FLOOR_Y)], CYAN, 3, b.p(t, "strap"))
        if op > 0:
            left.poly([(sx - 60, SEAM_Y), (sx - 30, SEAM_Y - 26 * op), (sx, SEAM_Y)], LINE, 2)
            for i in range(4):
                left.arrow(sx - 30 + i * 4, SEAM_Y - 30, sx - 10 + i * 10, SEAM_Y - 80 - i * 6, DIM, 2, 8, op)
        # as it was: every rivet cracked, the cracks pass the straps, the section goes
        self.details(right, 1, (SEC_X0, SEC_X1) if op > 0.15 else None)
        self.seam(right, 1, AMBER)
        right.poly([(SEC_X0, SEAM_Y), (lerp(SEC_X0, SEC_X1, crack), SEAM_Y)], RED, 3)
        if op > 0.15:
            right.d.rectangle([right.P(SEC_X0, TOP - 3), right.P(SEC_X1, FLOOR_Y - 3)], fill=BG)
            self.cabin(right, SEC_X0, SEC_X1)
        self._torn(right, op)
        out = Image.new("RGB", (W, H), BG)
        out.paste(left.done().crop((W // 4, 0, W // 4 + W // 2, H)), (0, 0))
        out.paste(right.done().crop((W // 4, 0, W // 4 + W // 2, H)), (W // 2, 0))
        f = Frame()
        f.img = out.resize((W * SS, H * SS))
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
                f.text(s, x, 520, fit(s, 18, "Inter-Bold.otf", 560), col, "Inter-Bold.otf", anchor="mm",
                       screen=True, alpha=b.p(t, "strap"))
        a = b.p(t, "verdict")
        if a > 0:
            f.text("HOLDS", W / 4 + 22, 600, 34, GREEN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
            f.text("FAILS", 3 * W / 4 + 22, 600, 34, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
            cx, cy = (W / 4 - 70) * SS, 600 * SS
            f.d.line([(cx - 12 * SS, cy), (cx - 3 * SS, cy + 10 * SS), (cx + 14 * SS, cy - 12 * SS)],
                     fill=GREEN + (int(255 * a),), width=5 * SS)
            cx = (3 * W / 4 - 64) * SS
            for s1, s2 in (((-11, -11), (11, 11)), ((-11, 11), (11, -11))):
                f.d.line([(cx + s1[0] * SS, cy + s1[1] * SS), (cx + s2[0] * SS, cy + s2[1] * SS)],
                         fill=RED + (int(255 * a),), width=5 * SS)
        f.caption(self.captions.get("compare", ""), prog(t, 0.4, 1.0))
        return f.done()
