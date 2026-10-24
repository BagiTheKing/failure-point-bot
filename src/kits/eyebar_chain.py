"""
Bridge kit, variant "eyebar_chain": a suspension bridge hung from chains of
steel eyebars, two bars to a link, pinned together at the joints; hangers
drop from the chain joints to a stiffening truss carrying the deck, and the
towers stand on rocker bearings. A crack grows unseen where an eyebar's eye
bears on its pin; the eye breaks, its sister bar slides off the pin, the
chain parts, and with it the whole bridge goes (the Silver Bridge, Point
Pleasant, West Virginia, 1967, NTSB HAR-71-1, is the reference).

The kit owns the drawing, so the bridge is always right; the sheet supplies
the words and numbers. Clips, each (t, T) -> Image, continuous with the one
before:

    build     the river and its banks, the piers and towers, the chains
              swinging from anchorage to tower to tower, the hangers, the
              stiffening truss and the deck draw themselves; push-in on the
              first chain joint west of the Ohio tower (C13N)
    physics   that joint up close: the pin, the two eyebars of each link,
              the hanger strap; water sits in the gap between pin and hole
              at the point of highest stress; a crack grows there over the
              decades, hidden inside the joint; the eye breaks, the bar
              pulls away, its sister slides off the pin
    fall      pull back to the bridge: the chain parts at the joint, the
              Ohio side span drops, the towers go, the collapse runs east
              across the river
    compare   what it needed (more bars per link: one can break and the
              others carry the chain) against what it had (two bars: one
              breaks, the chain parts)
"""

import math
import random

from PIL import Image

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            prog, lerp, mix, Frame, Beats, KitTiming, fit)

WATER = (60, 150, 230)
RUST = (186, 98, 52)

# the elevation, looking north: Ohio (west) on the left, West Virginia on the right.
# 380 ft side spans and a 700 ft main span (NTSB synopsis) at the same scale.
XA0, XA1 = 60, 1220                          # the anchorages
FT = (XA1 - XA0) / 1460.0                    # px per foot
XT0, XT1 = XA0 + 380 * FT, XA0 + 1080 * FT   # Ohio tower, West Virginia tower
TOP_Y = 236                                  # tower tops (the chain saddles)
U_Y, L_Y = 446, 470                          # stiffening truss: upper chord, lower chord (the deck)
RIVER_Y = 560                                # the water
BANK_L, BANK_R = XT0 - 70, XT1 + 70          # where the banks meet the river
SIDE_LINKS, MAIN_LINKS = 8, 14
JOINT = (0, SIDE_LINKS - 1)                  # C13N: the Ohio side span, the joint before the tower

# the joint, up close (world units; the camera frames it)
JX, JY = 640, 330                            # the pin
R_PIN, R_EYE = 34, 84                        # pin radius, eye radius
BAR_W = 46                                   # eyebar width (the shank)
DEPTH, DX, DY = 1.0, 16, -22                 # each bar's step back along the pin, on screen


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


class EyebarChain(KitTiming):
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        self.labels = k.get("labels", {})
        self.bridge = k.get("bridge", "")
        self.dvb = sheet.get("design_vs_built", {})
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}
        rnd = random.Random(5)
        self.cars = [(rnd.uniform(XA0 + 40, XA1 - 40), rnd.choice((0, 1))) for _ in range(22)]

    # -------------------------------------------------------------- the bridge
    def chain_pts(self):
        """The chain joints, west to east: [(span, i, x, y)]; span 0, 1, 2."""
        pts = []
        # Ohio side span: from the truss at the anchorage end up to the tower top, sagging
        for i in range(SIDE_LINKS + 1):
            u = i / SIDE_LINKS
            x = lerp(XA0, XT0, u)
            y = min(U_Y, lerp(U_Y, TOP_Y, u) + 46 * 4 * u * (1 - u))
            pts.append((0, i, x, y))
        for i in range(1, MAIN_LINKS + 1):
            u = i / MAIN_LINKS
            pts.append((1, i, lerp(XT0, XT1, u), TOP_Y + (U_Y - 6 - TOP_Y) * 4 * u * (1 - u)))
        for i in range(1, SIDE_LINKS + 1):
            u = i / SIDE_LINKS
            x = lerp(XT1, XA1, u)
            y = min(U_Y, lerp(TOP_Y, U_Y, u) + 46 * 4 * u * (1 - u))
            pts.append((2, i, x, y))
        return pts

    def joint_xy(self):
        p = next(p for p in self.chain_pts() if (p[0], p[1]) == JOINT)
        return p[2], p[3]

    def drop(self, x, tf):
        """How far a point at x has fallen at fall progress tf (0..1): the
        collapse starts at the joint in the Ohio side span and runs east."""
        jx = self.joint_xy()[0]
        if x <= XT0:
            t0 = 0.04 + 0.10 * abs(x - jx) / (jx - XA0 + 1)
        else:
            t0 = 0.12 + 0.62 * (x - XT0) / (XA1 - XT0)
        k = ease((tf - t0) / 0.22)
        return k * (self.floor(x) - L_Y)

    @staticmethod
    def floor(x):
        return RIVER_Y + 4 if BANK_L < x < BANK_R else RIVER_Y - 18

    def scenery(self, f, alpha=1.0, t=0.0):
        a = alpha
        f.poly([(0, RIVER_Y - 18), (BANK_L, RIVER_Y - 18), (BANK_L + 30, RIVER_Y + 6)], DIM, 2, a)
        f.poly([(W, RIVER_Y - 18), (BANK_R, RIVER_Y - 18), (BANK_R - 30, RIVER_Y + 6)], DIM, 2, a)
        if a > 0:
            for k in range(8):
                x = lerp(BANK_L + 40, BANK_R - 60, k / 7) + 14 * math.sin(t * 0.8 + k)
                f.poly([(x, RIVER_Y + 14 + (k % 3) * 9), (x + 40, RIVER_Y + 14 + (k % 3) * 9)],
                       mix(BG, WATER, 0.6 * a), 2)
        L = self.labels
        f.text(L.get("west", "OHIO"), 70, RIVER_Y + 40, 20, mix(BG, DIM, a), "Inter-Bold.otf", screen=True)
        f.text(L.get("east", "WEST VIRGINIA"), W - 70, RIVER_Y + 40, 20, mix(BG, DIM, a), "Inter-Bold.otf",
               screen=True, anchor="ra")

    def towers(self, f, frac=1.0, tf=0.0, color=LINE):
        for x in (XT0, XT1):
            k = self.drop(x, tf) / (self.floor(x) - L_Y)          # 0..1: how far it has gone
            base_y = RIVER_Y - 6 if BANK_L < x < BANK_R else RIVER_Y - 18
            f.rect(x - 16, base_y - 30, x + 16, base_y, DIM, None, 2, frac)    # the pier
            px, py = x, base_y - 30
            # off its rocker bearing: it leans over and goes down into the river
            lean = math.radians(78) * ease(k) * (1 if x == XT0 else -1)
            hgt = (py - TOP_Y) * (1 - 0.35 * ease(k))
            top = (px + hgt * math.sin(lean), py - hgt * math.cos(lean))
            nx, ny = math.cos(lean) * 10, math.sin(lean) * 10
            for sgn in (-1, 1):
                f.poly([(px + sgn * nx, py + sgn * ny), (top[0] + sgn * nx, top[1] + sgn * ny)], color, 3, frac)
            for j in range(5):                                    # the tower's cross bracing
                u0, u1 = j / 5, (j + 1) / 5
                a = (lerp(px, top[0], u0) - nx, lerp(py, top[1], u0) - ny)
                b = (lerp(px, top[0], u1) + nx, lerp(py, top[1], u1) + ny)
                f.poly([a, b], DIM, 1.4, frac)
            if frac >= 1 and k < 0.05:
                f.d.ellipse([f.P(px - 6, py - 4), f.P(px + 6, py + 8)], outline=AMBER, width=SS * 2)

    def chain(self, f, frac=1.0, tf=0.0, color=LINE, hot=0.0, parted=0.0):
        pts = self.chain_pts()
        pos = []
        for span, i, x, y in pts:
            k = self.drop(x, tf) / (self.floor(x) - L_Y)          # 0..1: how far down this part is
            pos.append((x + (6 if parted and span == 0 and i >= JOINT[1] else 0) * parted,
                        lerp(y, self.floor(x) - 10, k)))
        n = len(pos)
        drawn = int((n - 1) * min(1.0, frac))
        for k in range(drawn):
            a, b = pos[k], pos[k + 1]
            if parted > 0 and (pts[k][0], pts[k][1]) == JOINT:
                continue                               # the link east of the joint: parted from it
            f.poly([a, b], color, 3.2)
            f.poly([(a[0], a[1] + 3), (b[0], b[1] + 3)], mix(BG, color, 0.5), 1.4)   # the second bar
        for k, (span, i, x, y) in enumerate(pts[:drawn + 1]):
            if (span, i) == JOINT and hot > 0:
                px, py = pos[k]
                f.d.ellipse([f.P(px - 9, py - 9), f.P(px + 9, py + 9)], outline=RED + (int(255 * hot),),
                            width=SS * 3)
        return pos

    def hangers_truss(self, f, frac=1.0, tf=0.0, pos=None):
        pos = pos or [(x, y) for _, _, x, y in self.chain_pts()]
        # the stiffening truss and the deck, in panels
        xs = [lerp(XA0, XA1, k / 58) for k in range(59)]
        up = [(x, U_Y + self.drop(x, tf)) for x in xs]
        lo = [(x, L_Y + self.drop(x, tf)) for x in xs]
        f.poly(lo, LINE, 2.6, frac)
        f.poly(up, DIM, 1.6, frac)
        n = int(len(xs) * frac)
        for k in range(n - 1):
            f.poly([lo[k], up[k]], DIM, 1.0)
            f.poly([lo[k], up[k + 1]] if k % 2 else [up[k], lo[k + 1]], DIM, 1.0)
        # the hangers: chain joint down to the truss
        for (x, y), (_, _, x0, y0) in zip(pos, self.chain_pts()):
            if y0 < U_Y - 8 and (x0 - XA0) / (XA1 - XA0) <= frac:
                f.poly([(x, y), (x, U_Y + self.drop(x0, tf))], DIM, 1.2)

    def vehicles(self, f, alpha=1.0, tf=0.0):
        if alpha <= 0:
            return
        for x, lane in self.cars:
            d = self.drop(x, tf)
            y = L_Y - 7 - lane * 3 + d
            f.d.rectangle([f.P(x - 6, y - 5), f.P(x + 6, y + 1)], fill=mix(BG, AMBER, 0.8 * alpha))

    # -------------------------------------------------------------- the joint, up close
    def joint(self, f, bars=2, crack=0.0, fracture=0.0, part=0.0, slip=0.0, water=0.0, years="",
              t=0.0, needed=False):
        """The pin and its eyebars, seen a little from above so the bars of a
        link stand side by side along the pin (as in the NTSB's drawing of
        joint C13N): the link from the west (two bars, or `bars`), the link
        east to the tower, the hanger strap. crack 0..1 grows at the
        pinhole in the lower limb of the front bar's eye; fracture 0..1
        breaks the eye; part 0..1 pulls the broken bar away; slip 0..1
        slides its sister off the pin (as built)."""
        ang_w = math.radians(12)             # the west link rises toward the joint
        ang_e = math.radians(-20)            # the east link rises on to the tower
        n = bars * 2                         # the pin carries both links' eyes, interleaved
        span = (n - 1) * DEPTH
        c = lambda k: (JX + DX * (k * DEPTH - span / 2) / DEPTH, JY + DY * (k * DEPTH - span / 2) / DEPTH)
        back, front = c(n - 1), c(0)
        # the pin: a cylinder through every eye
        f.poly([(back[0], back[1] - R_PIN), (front[0], front[1] - R_PIN)], DIM, 2)
        f.poly([(back[0], back[1] + R_PIN), (front[0], front[1] + R_PIN)], DIM, 2)
        f.d.ellipse([f.P(back[0] - R_PIN, back[1] - R_PIN), f.P(back[0] + R_PIN, back[1] + R_PIN)],
                    fill=(28, 38, 58), outline=DIM, width=SS * 2)
        # the hanger strap, down to the truss, at the middle of the pin
        mx, my = c((n - 1) / 2)
        f.poly([(mx - 12, my), (mx - 12, H + 60)], DIM, 6)
        f.poly([(mx + 12, my), (mx + 12, H + 60)], DIM, 6)
        # back to front: odd slots carry the east link, even slots the west link; slot 0 is eyebar 330's
        for k in reversed(range(n)):
            cx, cy = c(k)
            if k % 2:                                             # the east link, up to the tower
                ex, ey = cx + 520 * math.cos(ang_e), cy + 520 * math.sin(ang_e)
                self._bar(f, (cx, cy), (ex, ey), mix(BG, LINE, 0.62), eye_at_start=True)
                continue
            bar = k // 2                                          # 0: the front bar of the west link
            sx, sy = cx - 560 * math.cos(ang_w), cy + 560 * math.sin(ang_w)
            dx = dy = 0.0
            if bar == 0 and part > 0:
                dx, dy = -150 * ease(part), 44 * ease(part)
            if bar == 1 and slip > 0 and not needed:
                dx, dy = -100 * ease(slip), 30 * ease(slip)
            col = LINE if bar == 0 else mix(BG, LINE, 0.85)
            self._bar(f, (sx + dx, sy + dy), (cx + dx, cy + dy), col, eye_at_start=False,
                      broken=fracture if bar == 0 else 0.0, part=part if bar == 0 else 0.0, pin=(cx, cy))
            if bar == 0 and part <= 0 and not needed:
                self._crack(f, cx, cy, crack, fracture)
        # the pin's front face and its nut
        f.d.ellipse([f.P(front[0] - R_PIN, front[1] - R_PIN), f.P(front[0] + R_PIN, front[1] + R_PIN)],
                    fill=(28, 38, 58), outline=LINE, width=SS * 3)
        f.d.ellipse([f.P(front[0] - 12, front[1] - 12), f.P(front[0] + 12, front[1] + 12)], outline=DIM,
                    width=SS * 2)
        # water in the gap between pin and hole, at the point of high stress (front eye)
        if water > 0:
            for k in range(5):
                ph = (t * 0.6 + k / 5) % 1.0
                a = math.radians(70 + 40 * k / 4)
                x = front[0] + (R_PIN + 4) * math.cos(a)
                y = front[1] + (R_PIN + 4) * math.sin(a) + 6 * ph
                f.d.ellipse([f.P(x - 3, y - 3), f.P(x + 3, y + 3)], fill=WATER + (int(200 * water),))
        if years:
            f.text(years, W - 60, 120, 54, AMBER, "InterDisplay-Black.otf", anchor="rs", screen=True)

    def _crack(self, f, cx, cy, crack, fracture):
        """From the pinhole surface into the lower limb of the eye, square to the bar."""
        if crack <= 0:
            return
        n = math.radians(90 + 12)
        x0, y0 = cx + R_PIN * math.cos(n), cy + R_PIN * math.sin(n)
        ln = (R_EYE - R_PIN) * (0.05 + 0.15 * crack) + (R_EYE - R_PIN) * 0.8 * fracture   # small, then through
        x1, y1 = x0 + ln * math.cos(n), y0 + ln * math.sin(n)
        f.poly([(x0, y0), (x1, y1)], RED, 3 + 2 * crack)
        f.d.ellipse([f.P(x0 - 6, y0 - 6), f.P(x0 + 6, y0 + 6)], outline=RED + (160,), width=SS * 2)

    def _bar(self, f, a, b, color, eye_at_start=True, broken=0.0, part=0.0, pin=(JX, JY)):
        """One eyebar: a flat shank with an eye at the pin end."""
        (x0, y0), (x1, y1) = a, b
        ex, ey = (x0, y0) if eye_at_start else (x1, y1)
        ang = math.atan2(y1 - y0, x1 - x0)
        nx, ny = -math.sin(ang), math.cos(ang)
        h = BAR_W / 2
        f.d.polygon([f.P(x0 + nx * h, y0 + ny * h), f.P(x1 + nx * h, y1 + ny * h),
                     f.P(x1 - nx * h, y1 - ny * h), f.P(x0 - nx * h, y0 - ny * h)], fill=(18, 30, 50))
        f.poly([(x0 + nx * h, y0 + ny * h), (x1 + nx * h, y1 + ny * h)], color, 2.4)
        f.poly([(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h)], color, 2.4)
        # the eye: a ring around the pin; broken, its far half stays behind on the pin
        f.d.ellipse([f.P(ex - R_EYE, ey - R_EYE), f.P(ex + R_EYE, ey + R_EYE)], fill=(18, 30, 50))
        if broken >= 1 and part > 0:
            # the outboard fragment left on the pin, the rest pulled away with the bar
            f.d.arc([f.P(pin[0] - R_EYE, pin[1] - R_EYE), f.P(pin[0] + R_EYE, pin[1] + R_EYE)], -80, 80,
                    fill=mix(color, RED, 0.5), width=SS * 3)
            f.d.arc([f.P(ex - R_EYE, ey - R_EYE), f.P(ex + R_EYE, ey + R_EYE)], 100, 260, fill=color, width=SS * 3)
        else:
            f.d.ellipse([f.P(ex - R_EYE, ey - R_EYE), f.P(ex + R_EYE, ey + R_EYE)], outline=color, width=SS * 3)
        f.d.ellipse([f.P(ex - R_PIN - 3, ey - R_PIN - 3), f.P(ex + R_PIN + 3, ey + R_PIN + 3)], fill=BG,
                    outline=mix(BG, color, 0.6), width=SS)

    # -------------------------------------------------------------- the clips
    BUILD = Beats(("banks", 1.2, 0.2), ("towers", 1.6, 0.4), ("chain", 2.2, 0.4), ("truss", 1.6, 0.4),
                  ("labels", 0.7, 2.2), ("traffic", 0.8, 0.6), ("zoom", 2.2, 0.4), ("node", 0.6, 2.6))
    PHYS = Beats(("lead", 1.2, 0.3), ("joint", 1.6, 1.6), ("pair", 1.0, 2.0), ("water", 1.4, 2.2),
                 ("crack", 3.6, 1.6), ("hidden", 0.8, 2.0), ("fracture", 0.8, 0.6), ("part", 1.2, 0.8),
                 ("slip", 1.2, 1.8))
    FALL = Beats(("handover", 0.8, 0.0), ("pull", 1.6, 0.3), ("part", 0.6, 0.2), ("collapse", 5.0, 1.0),
                 ("toll", 0.6, 2.8))
    COMP = Beats(("show", 1.0, 0.6), ("load", 1.2, 1.4), ("crack", 1.6, 1.2), ("break", 1.0, 1.0),
                 ("verdict", 0.6, 2.8))

    def b_camera(self, t):
        k = self.BUILD.p(t, "zoom")
        jx, jy = self.joint_xy()
        return (lerp(W / 2, jx + 30, k), lerp(H / 2 + 20, jy + 60, k), lerp(1.0, 3.0, k))

    def b_content(self, f, t, label_alpha=1.0):
        b = self.BUILD
        self.scenery(f, b.p(t, "banks"), t)
        self.towers(f, b.p(t, "towers"))
        pos = self.chain(f, b.p(t, "chain"), hot=b.p(t, "node"))
        self.hangers_truss(f, b.p(t, "truss"), pos=pos)
        self.vehicles(f, b.p(t, "traffic"))
        la = b.p(t, "labels") * b.until(t, "zoom")
        L = self.labels
        mid = self.chain_pts()[SIDE_LINKS + MAIN_LINKS // 2]
        f.label(L.get("chain", "eyebar chain: two bars to a link"), mid[2] - 80, mid[3] - 40, 640, 150, la)
        f.label(L.get("tower", "tower on a rocker bearing"), XT1, TOP_Y + 60, 1000, 190, la, AMBER)
        f.label(L.get("truss", "stiffening truss and deck"), 760, L_Y, 860, 640, la, DIM)
        jx, jy = self.joint_xy()
        lb = b.p(t, "node") * label_alpha
        f.label(L.get("node", "joint C13N"), jx, jy, 300, 160, lb, RED, size=19)

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

    def physics(self, t, T=None, lead=True):
        k = self.PHYS.p(t, "lead") if lead else 1
        b = self.PHYS
        z = b.p(t, "crack") * (1 - b.p(t, "part"))          # in on the eye while the crack grows
        fx, fy = JX - 1.5 * DX, JY - 1.5 * DY                 # the front eye (slot 0 of four)
        f = Frame(lerp(JX - 60, fx, z), lerp(JY + 20, fy + 40, z), lerp(1.0, 2.2, z))
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
        cr = b.p(t, "crack")
        yrs = ""
        if b.start("crack") <= t < b.end("hidden") + 1.0:
            yrs = str(int(round(lerp(1928, 1967, cr))))
        self.joint(f, 2, crack=cr, fracture=b.p(t, "fracture"), part=b.p(t, "part"), slip=b.p(t, "slip"),
                   water=b.p(t, "water"), years=yrs, t=t)
        a = b.p(t, "joint") * b.until(t, "water")
        f.text(L.get("pin", "the pin"), JX + 50, JY - 120, 22, LINE, "Inter-Bold.otf", alpha=a)
        pa = b.p(t, "pair") * b.until(t, "water")
        f.text(L.get("eyebar", "eyebar 330 and its sister, eyebar 33: the whole link"), 60, 110, 24, LINE,
               "Inter-Bold.otf", screen=True, alpha=pa)
        wa = b.p(t, "water") * b.until(t, "crack")
        f.text(L.get("water", "water collects at the pin, where the stress is highest"), 60, 110, 24, WATER,
               "Inter-Bold.otf", screen=True, alpha=wa)
        ca = b.p(t, "crack") * b.until(t, "hidden")
        f.text(L.get("crack", "a crack grows at the pinhole: about 1/8 inch"), 60, 110, 24, RED,
               "Inter-Bold.otf", screen=True, alpha=ca)
        ha = b.p(t, "hidden") * b.until(t, "fracture")
        f.text(L.get("hidden", "inside the joint: no inspection could see it"), 60, 110, 24, AMBER,
               "Inter-Bold.otf", screen=True, alpha=ha)
        fa = b.p(t, "part") * b.until(t, "slip")
        f.text(L.get("break", "the eye breaks: the bar pulls away"), 60, 110, 24, RED, "Inter-Bold.otf",
               screen=True, alpha=fa)
        sa = b.p(t, "slip")
        f.text(L.get("slip", "its sister slides off the pin: the chain parts"), 60, 110, 24, RED,
               "Inter-Bold.otf", screen=True, alpha=sa)
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8) * b.until(t, "pair"))
        return f

    _phys_last = None

    def fall(self, t, T=None):
        b = self.FALL
        k = b.p(t, "pull")
        jx, jy = self.joint_xy()
        f = Frame(lerp(jx + 30, W / 2, k), lerp(jy + 60, H / 2 + 20, k), lerp(3.0, 1.0, k))
        f.grid(1)
        tf = b.p(t, "collapse")
        self.scenery(f, 1, t)
        self.towers(f, 1, tf)
        pos = self.chain(f, 1, tf, parted=b.p(t, "part"), hot=1 - b.p(t, "collapse"))
        self.hangers_truss(f, 1, tf, pos=pos)
        self.vehicles(f, 1, tf)
        if tf > 0:                                   # splashes where the spans reach the water
            for x in range(int(BANK_L) + 20, int(BANK_R) - 20, 46):
                d = self.drop(x, tf)
                if d > (RIVER_Y - L_Y) * 0.9:
                    s = min(1.0, (d - (RIVER_Y - L_Y) * 0.9) / 10)
                    for j in range(3):
                        f.arrow(x, RIVER_Y, x + (j - 1) * 14, RIVER_Y - 30 * s, mix(BG, WATER, 0.8), 2, 6, s)
        nums = self.sheet.get("numbers", [])
        if nums:
            a = b.p(t, "toll")
            f.text(nums[0]["value"], 1180, 150, 96, RED, "InterDisplay-Black.otf", anchor="rs", screen=True, alpha=a)
            f.text(nums[0]["label"], 1180, 186, fit(nums[0]["label"], 24, "Inter-Bold.otf", 520), LINE,
                   "Inter-Bold.otf", anchor="rs", screen=True, alpha=a)
        f.caption(self.captions.get("fall", ""), prog(t, b.end("pull"), b.end("pull") + 0.5))
        img = f.done()
        h = b.p(t, "handover")
        if h < 1:
            if self._phys_last is None:
                self._phys_last = self.physics(self.PHYS.total - 1 / 30)
            img = Image.blend(self._phys_last, img, h)
        return img

    def side(self, built, joint=1.0, load=0.0, crack=0.0, fracture=0.0, part=0.0, slip=0.0, water=0.0,
             verdict=0.0, stamp=0.0, stamp_text="", years="", t=0.0):
        """One side of the comparison on its own, for a Short (what it
        needed above, as built below): the joint up close, more bars to the
        link (one breaks, the others carry it) or two (one breaks, its
        sister slides off, the chain parts)."""
        f = Frame(JX - 40, JY + 30, 0.95)
        f.grid(1)
        if joint > 0:
            self.joint(f, 2 if built else 4, crack=crack, fracture=fracture, part=part,
                       slip=slip if built else 0.0, water=water, years=years if built else "", t=t,
                       needed=not built)
        if load > 0:
            col = (RED if built and slip > 0.3 else GREEN) if part > 0 else AMBER
            for k in range(3):
                f.arrow(JX + 130 + k * 70, JY - 60 - k * 24, JX + 230 + k * 70, JY - 96 - k * 24, col, 4, 12, load)
        if stamp > 0 and stamp_text and verdict < 1:
            k = min(1.0, stamp)
            f.text(stamp_text, W / 2, 80, int(52 * (1.6 - 0.6 * k)), RED, "InterDisplay-Black.otf",
                   anchor="mm", screen=True, alpha=k * (1 - min(1.0, slip * 4)))
        if verdict > 0:
            word, col = ("FAILS", RED) if built else ("HOLDS", GREEN)
            f.text(word, W / 2, 80, 96, col, "InterDisplay-Black.otf", anchor="mm", screen=True, alpha=verdict)
        return f.done()

    def compare(self, t, T=None):
        b = self.COMP
        load, crack, brk = b.p(t, "load"), b.p(t, "crack"), b.p(t, "break")
        halves = []
        for built in (False, True):
            g = Frame(JX - 40, JY + 30, 0.55)
            g.grid(0.6)
            self.joint(g, 2 if built else 4, crack=crack, fracture=brk, part=brk,
                       slip=brk if built else 0.0, water=load, t=t, needed=not built)
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
                       anchor="mm", screen=True, alpha=load)
        a = b.p(t, "verdict")
        if a > 0:
            f.text("HOLDS", W / 4, 620, 34, GREEN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
            f.text("FAILS", 3 * W / 4, 620, 34, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.caption(self.captions.get("compare", ""), prog(t, 0.4, 1.0))
        return f.done()
