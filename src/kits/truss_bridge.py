"""
Structure kit, variant "truss bridge": a steel truss over one or more spans,
one joint (gusset node) overloaded (I-35W, 2007, is the reference). The same
drawing covers deck trusses and through trusses ("deck": "top" or "bottom")
and any number of spans and panels, from the sheet's "kit" block.

Clips, each (t, T) -> Image, continuous with the one before:

    build     the bridge draws itself span by span, labels, push-in on the joint
    physics   forces into the gusset plate, the plate thickness it had vs needed,
              the plate bows (edge view inset), tears
    fall      pull back; the main span drops into the river, the side spans follow
    compare   what it needed (holds) vs as built (fails), split screen
"""

import math
import random

from PIL import Image, ImageDraw

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            ease, prog, lerp, mix, Frame, Beats, KitTiming, fit)

X0, X1 = 100, 1180          # abutments
DECK_Y = 300                # roadway level
WATER_Y, BED_Y = 560, 640
WATER = (16, 44, 78)


def _rot(px, py, cx, cy, a):
    c, s = math.cos(a), math.sin(a)
    return cx + (px - cx) * c - (py - cy) * s, cy + (px - cx) * s + (py - cy) * c


class TrussBridge(KitTiming):
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        spans = k.get("spans", [1, 2, 1])
        scale = (X1 - X0) / sum(spans)
        self.piers, x = [], X0
        for s_ in spans[:-1]:
            x += s_ * scale
            self.piers.append(x)
        self.n = int(k.get("panels", 24))
        self.dx = (X1 - X0) / self.n
        self.fail_i = int(k.get("failed_node", self.n // 3))
        self.fail_x = X0 + self.fail_i * self.dx
        self.node_name = k.get("failed_node_label", f"U{self.fail_i}")
        self.labels = k.get("labels", {})
        self.dvb = sheet.get("design_vs_built", {})
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}
        self.main = (self.piers[0], self.piers[-1]) if len(self.piers) >= 2 else (X0, X1)
        self.with_load = bool(k.get("load_near_node"))

    # ------------------------------------------------------------- geometry
    def depth(self, x):
        """Deeper over the main piers, shallow at mid-span and the ends."""
        d = min(abs(x - p) for p in self.piers) if self.piers else 999
        return 55 + 70 * max(0.0, 1 - d / 160) ** 1.5

    def nodes(self):
        up = [(X0 + i * self.dx, DECK_Y) for i in range(self.n + 1)]
        lo = [(x, DECK_Y + self.depth(x)) for x, _ in up]
        return up, lo

    def members(self):
        """[(p, q, kind)] in rest position."""
        up, lo = self.nodes()
        out = []
        for i in range(self.n):
            out.append((up[i], up[i + 1], "top"))
            out.append((lo[i], lo[i + 1], "bottom"))
            # Warren diagonals, mirrored about mid-length so the truss is symmetric
            left = (i < self.n / 2)
            if (i % 2 == 0) == left:
                out.append((up[i], lo[i + 1], "diag"))
            else:
                out.append((lo[i], up[i + 1], "diag"))
        for i in range(self.n + 1):
            out.append((up[i], lo[i], "vert"))
        return out

    def group_of(self, x):
        if x < self.main[0]:
            return "side_l"
        if x > self.main[1]:
            return "side_r"
        return "main"

    def pose(self, t_fall):
        """Per group (dx, dy, angle, pivot) for the fall, 0 <= t_fall <= 1."""
        a, b = self.main
        f1 = ease(min(1, t_fall / 0.55))           # main span first: near the failed joint leads
        f2 = ease(max(0, (t_fall - 0.25) / 0.75))  # side spans follow
        drop = WATER_Y - DECK_Y + 25         # the deck ends up just under the surface
        lead_left = self.fail_x < (a + b) / 2
        ang = (0.10 if lead_left else -0.10) * (1 - abs(2 * f1 - 1))
        return {
            "main": (0, drop * f1, ang, ((a + b) / 2, DECK_Y)),
            "side_l": (0, 0, 0.30 * f2, (X0, DECK_Y)),
            "side_r": (0, 0, -0.30 * f2, (X1, DECK_Y)),
        }

    def _xf(self, p, g, pose):
        if not pose:
            return p
        dx, dy, a, (cx, cy) = pose[g]
        x, y = _rot(p[0], p[1], cx, cy, a)
        return x + dx, y + dy

    # -------------------------------------------------------------- drawing
    def scenery(self, f, alpha=1.0, t=0.0):
        a = alpha
        # river and banks
        poly = [f.P(X0 - 200, WATER_Y), f.P(X1 + 200, WATER_Y), f.P(X1 + 200, BED_Y + 80),
                f.P(X0 - 200, BED_Y + 80)]
        f.d.polygon(poly, fill=WATER + (int(255 * a),))
        for k in range(8):
            y = WATER_Y + 12 + k * 9
            off = (t * 20 + k * 37) % 60
            for x in range(int(X0 - 160 + off), int(X1 + 160), 60):
                f.poly([(x, y), (x + 22, y)], (40, 90, 140, int(160 * a)), 1)
        f.poly([(X0 - 200, WATER_Y), (X1 + 200, WATER_Y)], (70, 140, 200, int(255 * a)), 2)
        for xa, sgn in ((X0, -1), (X1, 1)):
            bank = [(xa + sgn * 200, DECK_Y + 20), (xa, DECK_Y + 20), (xa, DECK_Y + 60),
                    (xa + sgn * -10, WATER_Y), (xa + sgn * 200, WATER_Y)]
            f.d.polygon([f.P(*p) for p in bank], fill=(18, 38, 66, int(255 * a)))
            f.poly(bank[:-1], DIM + (int(255 * a),), 2)
        for x in self.piers:
            top = DECK_Y + self.depth(x)
            f.rect(x - 12, top, x + 12, BED_Y, DIM, (18, 38, 66), 2)

    def truss(self, f, frac=1.0, t_fall=0.0, highlight=0.0, color=LINE, skip_node=False,
              node_color=None):
        pose = self.pose(t_fall) if t_fall > 0 else None
        ms = self.members()
        for k, (p, q, kind) in enumerate(ms):
            if frac < 1 and (p[0] + q[0]) / 2 > X0 + (X1 - X0) * frac:
                continue
            g = self.group_of((p[0] + q[0]) / 2)
            a, b = self._xf(p, g, pose), self._xf(q, g, pose)
            if skip_node and math.dist(p, (self.fail_x, DECK_Y)) < 2 or \
               skip_node and math.dist(q, (self.fail_x, DECK_Y)) < 2:
                continue
            w = 3 if kind in ("top", "bottom") else 2
            f.poly([a, b], color if kind != "diag" else mix(color, DIM, 0.3), w)
        # the deck on top of the truss
        if frac > 0:
            for g, (xa, xb) in (("side_l", (X0, self.main[0])), ("main", self.main),
                                ("side_r", (self.main[1], X1))):
                xb = min(xb, X0 + (X1 - X0) * frac)
                if xb <= xa:
                    continue
                pts = [(xa, DECK_Y - 10), (xb, DECK_Y - 10), (xb, DECK_Y), (xa, DECK_Y)]
                pts = [self._xf(p, g, pose) for p in pts]
                f.d.polygon([f.P(*p) for p in pts], fill=(18, 38, 66))
                f.poly(pts + [pts[0]], LINE, 2)
        # gusset plates at every top node, the failed one marked
        for i in range(self.n + 1):
            x = X0 + i * self.dx
            if frac < 1 and x > X0 + (X1 - X0) * frac:
                break
            g = self.group_of(x)
            cx, cy = self._xf((x, DECK_Y), g, pose)
            r = 4 * f.zoom * SS
            px, py = f.P(cx, cy + 3)
            col = node_color if (node_color and i == self.fail_i) else DIM
            f.d.rectangle([px - r, py - r, px + r, py + r], fill=col)
        if highlight > 0:
            pulse = 0.55 + 0.45 * math.sin(highlight * 12)
            a, b = f.P(self.fail_x - 18, DECK_Y - 18), f.P(self.fail_x + 18, DECK_Y + 22)
            f.d.rounded_rectangle([a, b], radius=6 * SS, outline=RED + (int(200 * pulse),), width=3 * SS)

    def cars(self, f, t_fall=0.0, alpha=1.0, seed=2):
        rnd = random.Random(seed)
        pose = self.pose(t_fall) if t_fall > 0 else None
        for k in range(22):
            x = X0 + 30 + (X1 - X0 - 60) * (k + rnd.random() * 0.5) / 22
            g = self.group_of(x)
            pts = [(x - 7, DECK_Y - 10), (x + 7, DECK_Y - 10), (x + 7, DECK_Y - 17), (x - 7, DECK_Y - 17)]
            pts = [self._xf(p, g, pose) for p in pts]
            f.d.polygon([f.P(*p) for p in pts], fill=DIM + (int(255 * alpha),))

    def load_pile(self, f, t_fall=0.0, alpha=1.0):
        if not self.with_load:
            return
        pose = self.pose(t_fall) if t_fall > 0 else None
        g = self.group_of(self.fail_x + 30)
        base = self.fail_x + 8
        for k, w in enumerate((26, 18, 30)):
            x = base + k * 26
            pts = [(x, DECK_Y - 10), (x + w, DECK_Y - 10), (x + w * 0.65, DECK_Y - 24), (x + w * 0.3, DECK_Y - 24)]
            pts = [self._xf(p, g, pose) for p in pts]
            f.d.polygon([f.P(*p) for p in pts], fill=AMBER + (int(200 * alpha),))

    def water_front(self, f, t=0.0):
        """Water drawn again over whatever fell into it, a little see-through."""
        poly = [f.P(X0 - 200, WATER_Y), f.P(X1 + 200, WATER_Y), f.P(X1 + 200, BED_Y + 80),
                f.P(X0 - 200, BED_Y + 80)]
        f.d.polygon(poly, fill=WATER + (190,))
        f.poly([(X0 - 200, WATER_Y), (X1 + 200, WATER_Y)], (70, 140, 200), 2)
        for x in self.piers:
            f.rect(x - 12, WATER_Y, x + 12, BED_Y, DIM, None, 2)

    def splash(self, f, t_since, seed=4):
        if t_since <= 0:
            return
        rnd = random.Random(seed)
        fade = max(0.0, 1 - t_since / 2.2)
        a, b = self.main
        for _ in range(60):
            x = rnd.uniform(a, b)
            vx, vy = rnd.uniform(-60, 60), rnd.uniform(-220, -60)
            tt = min(t_since, 1.4)
            px, py = x + vx * tt, WATER_Y + vy * tt + 300 * tt * tt
            if py > WATER_Y:
                continue
            r = (2 + rnd.random() * 3) * f.zoom * SS
            cx, cy = f.P(px, py)
            f.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200, 225, 255, int(200 * fade)))
        for _ in range(16):
            x = rnd.uniform(a, b)
            r = (16 + rnd.random() * 36) * min(1, t_since + 0.3)
            cx, cy = f.P(x, WATER_Y - rnd.random() * 30 * min(1, t_since))
            rr = r * f.zoom * SS
            f.d.ellipse([cx - rr, cy - rr * 0.5, cx + rr, cy + rr * 0.5],
                        fill=(170, 200, 235, int(80 * fade)))

    def gusset(self, f, stress=0.0, bow=0.0, tear=0.0, thickness=1.0):
        """The failed joint at real proportions (reads at ~6x zoom)."""
        x, y = self.fail_x, DECK_Y
        up, lo = self.nodes()
        i = self.fail_i
        # members meeting here, drawn thick (world width)
        meet = [(up[i - 1], "top"), (up[i + 1], "top"), (lo[i], "vert")]
        for p, q, kind in self.members():
            if kind == "diag" and ((abs(p[0] - x) < 1 and abs(p[1] - y) < 1) or
                                   (abs(q[0] - x) < 1 and abs(q[1] - y) < 1)):
                meet.append((q if abs(p[0] - x) < 1 else p, "diag"))
        if stress > 0:
            cx, cy = f.P(x, y + 6)
            for k in range(6, 0, -1):
                r = (4 + k * 3.4) * f.zoom * SS * (0.5 + stress)
                f.d.ellipse([cx - r, cy - r, cx + r, cy + r],
                            fill=mix(AMBER, RED, stress) + (int(26 * stress * (7 - k) / 2),))
        for p, kind in meet:
            ang = math.atan2(p[1] - y, p[0] - x)
            sep = 4 * tear if kind == "diag" else 0
            a = (x + math.cos(ang) * (6 + sep), y + math.sin(ang) * (6 + sep))
            b = (x + math.cos(ang) * 60, y + math.sin(ang) * 60)
            f.poly([a, b], LINE, 5 if kind == "top" else 4, world_width=True)
        # the plate: a pentagon, its outline bending as it bows
        pts = []
        for k in range(5):
            ang = -math.pi / 2 + k * 2 * math.pi / 5 + math.pi / 5
            r = 13 + (2.5 * bow * math.sin(k * 1.7))
            pts.append((x + math.cos(ang) * r, y + 4 + math.sin(ang) * r))
        f.d.polygon([f.P(*p) for p in pts], fill=mix((40, 70, 110), RED, stress * 0.6) + (230,))
        f.poly(pts + [pts[0]], mix(LINE, RED, stress), 1.5)
        for k in range(6):
            ang = k * math.pi / 3
            rx, ry = f.P(x + math.cos(ang) * 8, y + 4 + math.sin(ang) * 8)
            r = 1.2 * f.zoom * SS
            f.d.ellipse([rx - r, ry - r, rx + r, ry + r], fill=DIM)
        if tear > 0:
            f.poly([(x - 12, y - 4), (x - 4 + 3 * tear, y + 4), (x + 3, y + 1), (x + 12 * tear, y + 12)],
                   RED, 2.5)

    # ----------------------------------------------------------------- clips
    # Every clip is a timeline of beats (blueprint.Beats): each step animates,
    # then holds long enough to be understood before the next one starts.
    BUILD = Beats(("draw", 3.6, 1.0), ("traffic", 0.8, 0.6), ("labels", 0.6, 2.6),
                  ("load", 0.5, 2.2), ("zoom", 2.6, 0.4), ("node", 0.6, 2.8))
    PHYS = Beats(("lead", 1.2, 0.3), ("push", 0.8, 2.0), ("up", 0.8, 2.2),
                 ("thick", 0.8, 3.0), ("half", 0.8, 2.4), ("stress", 2.8, 0.8),
                 ("bow", 2.4, 1.4), ("tear", 1.0, 2.0))
    FALL = Beats(("handover", 0.8, 0.0), ("pull", 1.8, 0.9), ("drop", 1.6, 0.0),
                 ("settle", 0.1, 2.0), ("toll", 0.6, 2.8))
    COMP = Beats(("show", 1.0, 0.6), ("titles", 0.6, 2.6), ("mark", 0.6, 2.4),
                 ("drop", 1.6, 0.6), ("verdict", 0.6, 2.8))

    def b_camera(self, t):
        b = self.BUILD
        k = b.p(t, "zoom")
        return (lerp(W / 2, self.fail_x, k), lerp(H / 2 + 60, DECK_Y + 6, k), lerp(1.0, 5.5, k))

    def b_content(self, f, t, label_alpha=1.0):
        b = self.BUILD
        zoomed = f.zoom > 2.4
        self.scenery(f, prog(t, 0.0, 1.0), t)
        self.truss(f, frac=b.p(t, "draw"), skip_node=zoomed)
        self.cars(f, alpha=b.p(t, "traffic"))
        self.load_pile(f, alpha=b.p(t, "traffic"))
        if zoomed:
            self.gusset(f)
        L = self.labels
        la = b.p(t, "labels") * b.until(t, "load")
        f.label(L.get("deck", "deck"), 250, DECK_Y - 10, 230, 150, la)
        f.label(L.get("truss", "truss"), 760, DECK_Y + 40, 860, 190, la)
        if self.piers:
            f.label(L.get("piers", "piers"), self.piers[-1] + 12, 470, 1020, 470, la)
        f.label(L.get("river", "river"), 640, WATER_Y + 30, 760, 650, la)
        if self.with_load:
            lp = b.p(t, "load") * b.until(t, "zoom")
            f.label(L.get("load", "load"), self.fail_x + 40, DECK_Y - 22, 560, 110, lp, AMBER)
        lb = b.p(t, "node") * label_alpha
        f.label(L.get("node", self.node_name), self.fail_x, DECK_Y + 4, 300, 520, lb, RED, size=19)
        f.label(L.get("plate", "gusset plate"), self.fail_x + 10, DECK_Y + 10, 820, 560, lb, size=18)

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
        """Starts on build's last frame (one continuous shot) when lead."""
        b = self.PHYS
        k = b.p(t, "lead") if lead else 1
        bx, by, bz = self.b_camera(999)
        f = Frame(lerp(bx, self.fail_x, k), lerp(by, DECK_Y + 10, k), lerp(bz, 6.5, k))
        f.grid(1)
        if k < 1:
            g = Frame(f.cx, f.cy, f.zoom)
            g.grid(1)
            self.b_content(g, 999, label_alpha=1 - prog(t, 0, 0.6))
            self._physics_body(f, t)
            return Image.blend(g.done(), f.done(), k)
        return self._physics_body(f, t).done()

    def _physics_body(self, f, t):
        b = self.PHYS
        stress = b.p(t, "stress")
        bow = b.p(t, "bow")
        tear = b.p(t, "tear")
        x, y = self.fail_x, DECK_Y
        f.poly([(x - 120, y - 10), (x + 120, y - 10)], LINE, 1.5)
        self.gusset(f, stress, bow, tear)
        a1 = b.p(t, "push")
        f.arrow(x - 40, y - 2, x - 12, y - 2, AMBER, 6, 14, a1)
        f.arrow(x + 40, y - 2, x + 12, y - 2, AMBER, 6, 14, a1)
        f.text("the beams push in", 470, 150, 22, AMBER, "Inter-Bold.otf", screen=True, alpha=a1, anchor="rs")
        a2 = b.p(t, "up")
        f.arrow(x, y + 46, x, y + 18, AMBER, 6, 14, a2)
        f.text("the truss below pushes up", 915, 560, 22, AMBER, "Inter-Bold.otf", screen=True, alpha=a2)
        f.text("all of it through one steel plate", 915, 586, 18, LINE, "Inter-Medium.otf", screen=True, alpha=a2)
        p = b.p(t, "thick")
        d = self.dvb
        f.d.rectangle([40 * SS, 230 * SS, 360 * SS, 420 * SS], fill=(0, 0, 0, int(160 * p)))
        f.text("PLATE THICKNESS", 58, 258, 16, CYAN, "Inter-Bold.otf", screen=True, alpha=p)
        f.d.rectangle([58 * SS, 290 * SS, (58 + 272 * p) * SS, 300 * SS], fill=CYAN + (int(255 * p),))
        need = f"needed: {d.get('plate_needed') or 'thicker than built'}"
        f.text(need, 58, 308, fit(need, 18, "Inter-Medium.otf", 290), LINE, "Inter-Medium.otf", screen=True, alpha=p)
        q = prog(t, b.start("thick") + 0.9, b.start("thick") + 1.6)
        f.d.rectangle([58 * SS, 350 * SS, (58 + 136 * q) * SS, 360 * SS], fill=RED + (int(255 * q),))
        f.text(f"built: {d.get('plate_built', '')}", 58, 368, 18, LINE, "Inter-Medium.otf", screen=True, alpha=q)
        a3 = b.p(t, "half")
        f.text(d.get("multiplier", "½"), 1200, 470, 76, RED, "InterDisplay-Black.otf", screen=True, alpha=a3, anchor="rs")
        ml = d.get("multiplier_label", "")
        f.text(ml, 1200, 504, fit(ml, 20, "Inter-Bold.otf", 300), RED, "Inter-Bold.otf", screen=True, alpha=a3, anchor="rs")
        q = prog(t, b.start("bow") - 0.4, b.start("bow"))
        if q > 0:
            bx, by = 1000, 170
            f.d.rectangle([(bx - 110) * SS, (by - 60) * SS, (bx + 110) * SS, (by + 70) * SS],
                          fill=(0, 0, 0, int(170 * q)))
            f.text("EDGE VIEW", bx - 96, by - 50, 14, CYAN, "Inter-Bold.otf", screen=True, alpha=q)
            pts = [((bx + 26 * bow * math.sin(math.pi * k / 20)) * SS, (by - 30 + k * 4) * SS)
                   for k in range(21)]
            f.d.line(pts, fill=mix(LINE, RED, bow) + (int(255 * q),), width=4 * SS)
            f.text("the plate bows", bx - 96, by + 50, 15, LINE, "Inter-Medium.otf", screen=True, alpha=q)
        if tear > 0:
            f.text("the plates tear", W / 2, 96, 28, RED, "Inter-Bold.otf", screen=True,
                   alpha=prog(t, b.start("tear") + 0.2, b.start("tear") + 0.8), anchor="mm")
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8))
        return f

    _phys_last = None

    def fall(self, t, T=None):
        """Starts on physics' exact last frame, then pulls back, holds a beat
        on the whole bridge, and lets the failure chain play."""
        b = self.FALL
        k = b.p(t, "pull")
        f = Frame(lerp(self.fail_x, W / 2, k), lerp(DECK_Y + 10, H / 2 + 60, k), lerp(6.5, 1.0, k))
        tf = b.p(t, "drop")
        hit = b.start("drop") + 0.9
        shake = 4 * math.sin(t * 70) * max(0, 1 - abs(t - hit) * 3) if t > hit - 0.1 else 0
        f.cx += shake
        f.grid(1)
        self.scenery(f, 1, t)
        self.truss(f, t_fall=tf, skip_node=f.zoom > 2.4, node_color=RED,
                   highlight=(t - b.end("pull")) if b.end("pull") < t < b.start("drop") + 0.2 else 0)
        if f.zoom > 2.4:
            self.gusset(f, 1, 1, 1)
        self.cars(f, t_fall=tf)
        self.load_pile(f, t_fall=tf)
        self.water_front(f, t)
        self.splash(f, t - hit)
        nums = self.sheet.get("numbers", [])
        if nums:
            a = b.p(t, "toll")
            f.text(nums[0]["value"], 1180, 200, 96, RED, "InterDisplay-Black.otf", anchor="rs",
                   screen=True, alpha=a)
            f.text(nums[0]["label"], 1180, 236, 24, LINE, "Inter-Bold.otf", anchor="rs",
                   screen=True, alpha=a)
        f.caption(self.captions.get("fall", ""), prog(t, b.end("pull"), b.end("pull") + 0.5))
        img = f.done()
        h = b.p(t, "handover")
        if h < 1:
            if self._phys_last is None:
                self._phys_last = self.physics(self.PHYS.total - 1 / 30)
            img = Image.blend(self._phys_last, img, h)
        return img

    def compare(self, t, T=None):
        b = self.COMP
        tf = b.p(t, "drop")
        show = b.p(t, "show")
        left = Frame(W / 2, H / 2 + 60, 0.5)
        left.grid(0.6)
        self.scenery(left, show, t)
        self.truss(left, frac=show, node_color=CYAN)
        right = Frame(W / 2, H / 2 + 60, 0.5)
        right.grid(0.6)
        self.scenery(right, show, t)
        mark = b.p(t, "mark")
        self.truss(right, frac=show, t_fall=tf, node_color=RED if mark > 0 else None,
                   highlight=(t - b.start("mark")) if b.start("mark") < t < b.start("drop") else 0)
        self.water_front(right, t)
        self.splash(right, t - (b.start("drop") + 0.9))
        out = Image.new("RGB", (W, H), BG)
        out.paste(left.done().crop((W // 4, 0, W // 4 + W // 2, H)), (0, 0))
        out.paste(right.done().crop((W // 4, 0, W // 4 + W // 2, H)), (W // 2, 0))
        f = Frame()
        f.img = out.resize((W * SS, H * SS))
        f.d = ImageDraw.Draw(f.img, "RGBA")
        f.d.line([(W * SS / 2, 0), (W * SS / 2, H * SS)], fill=LINE + (int(255 * show),), width=2 * SS)
        d, bb = self.dvb.get("designed", {}), self.dvb.get("built", {})
        a = b.p(t, "titles")
        f.text(d.get("title", ""), W / 4, 92, 24, CYAN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.text(d.get("detail", ""), W / 4, 120, 17, LINE, "Inter-Medium.otf", anchor="mm", screen=True, alpha=a)
        f.text(bb.get("title", ""), 3 * W / 4, 92, 24, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.text(bb.get("detail", ""), 3 * W / 4, 120, 17, LINE, "Inter-Medium.otf", anchor="mm", screen=True, alpha=a)
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
