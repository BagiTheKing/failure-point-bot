"""
Water kit, variant "earth_dam": a zoned earthfill dam across a canyon of
jointed rock. Its seepage control is a core of fine soil carried down into
deep key trenches cut in the abutments, and a grout curtain below; water
under full head finds open rock joints at a trench wall, gets into the
trench fill, carries it away (internal erosion, "piping"), and the pipe
grows until the dam above it collapses (Teton Dam, Idaho, 1976, is the
reference).

The kit owns the drawing, so the dam is always right; the sheet supplies
the words and numbers. Clips, each (t, T) -> Image, continuous with the one
before:

    build     the canyon and its jointed rock draw themselves, looking
              upstream at the dam's downstream face; the dam, the key trench
              in the right abutment (screen left), the grout curtain, the
              reservoir rising behind; push-in on the trench
    physics   the dam in section through that trench: the core, the shells,
              the trench in rock; water under full head finds the open
              joints, gets into the trench fill, a pipe erodes through it
              downstream, muddy water leaves at the face, the pipe grows
    fall      pull back to the face: the leak grows to a hole, the crest
              drops into it, the breach widens and the reservoir goes
    compare   what it needed (the joints sealed, a filter that holds the
              fines: the dam holds) against what it had (open joints, fill
              that washes out, no filter: fails)
"""

import math
import random

from PIL import Image, ImageDraw

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            prog, lerp, mix, Frame, Beats, KitTiming, fit)

WATER = (60, 150, 230)
MUD = (176, 132, 82)
SILT = (196, 170, 120)

# the face, looking upstream (the right abutment on screen left); world = screen px at zoom 1
CREST_Y, BASE_Y = 210, 600
VALLEY = [(80, 120), (150, 170), (230, 250), (330, 420), (430, 560), (520, 600), (760, 600),
          (860, 540), (960, 400), (1060, 250), (1140, 170), (1200, 120)]   # canyon floor and walls
TRENCH_X = (255, 330)                                                        # the right-abutment key trench
RES_Y = 228                                                                  # reservoir at failure, just below the crest

# the section through the right-abutment trench: upstream left
SX0, SX1 = 140, 1140                         # toes of the dam
CX = 600                                     # centre line
SEC_CREST, SEC_BASE = 150, 470              # crest and foundation (top of rock)
TR_TOP_W, TR_BOT_W, TR_D = 260, 90, 170      # key trench: width at rock surface and at the bottom, depth


def _joints(rnd, x0, x1, y0, y1, n, slope=0.25):
    out = []
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        ln = rnd.uniform(30, 90)
        a = rnd.uniform(-slope, slope) + (math.pi / 2 if rnd.random() < 0.5 else 0)
        out.append(((x, y), (x + ln * math.cos(a), y + ln * math.sin(a))))
    return out


class EarthDam(KitTiming):
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        self.labels = k.get("labels", {})
        self.dam = k.get("dam", "")
        self.height = str(k.get("height", "") or "")
        dvb = sheet.get("design_vs_built", {})
        self.dvb = dvb
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}
        rnd = random.Random(7)
        self.face_joints = _joints(rnd, 90, 360, 140, 560, 28) + _joints(rnd, 880, 1190, 140, 540, 22)
        self.sec_joints = _joints(random.Random(3), SX0 - 100, SX1 + 100, SEC_BASE + 20, H - 20, 70, 0.4)

    # -------------------------------------------------------------- the face
    def _y_at(self, x):
        """The canyon's surface height at x (rock below it)."""
        for (xa, ya), (xb, yb) in zip(VALLEY, VALLEY[1:]):
            if xa <= x <= xb:
                return lerp(ya, yb, (x - xa) / (xb - xa))
        return VALLEY[0][1] if x < VALLEY[0][0] else VALLEY[-1][1]

    def canyon(self, f, frac=1.0, joints=0.0):
        f.poly(VALLEY, LINE, 2.4, frac)
        if joints > 0:
            n = int(len(self.face_joints) * joints)
            for a, b in self.face_joints[:n]:
                if a[1] > self._y_at(a[0]) + 8:
                    f.poly([a, b], DIM, 1.4)

    def dam_face(self, f, frac=1.0, hole=0.0, breach=0.0, color=LINE):
        """The downstream face between the canyon walls, from the crest down;
        a hole at the right abutment (hole 0..1) and the breach (0..1)."""
        x0 = next(x for x in range(80, 640) if self._y_at(x) >= CREST_Y)
        x1 = next(x for x in range(1200, 640, -1) if self._y_at(x) >= CREST_Y)
        if breach <= 0:
            f.poly([(x0, CREST_Y), (x1, CREST_Y)], color, 3, frac)
        else:                                   # the breach: a notch eaten down and across from the right abutment
            k = min(1.0, breach * 1.3)
            depth = lerp(CREST_Y, BASE_Y - 30, k)
            wall = lambda y: next(x for x in range(80, 640) if self._y_at(x) >= y) + 4   # the abutment rock
            right = lerp(340, 640, breach)
            ys = [lerp(CREST_Y, depth, i / 8) for i in range(9)]
            notch = [(wall(y), y) for y in ys] + [(right - 50, depth), (right, CREST_Y)]
            f.poly([(x0, CREST_Y), (wall(CREST_Y), CREST_Y)], color, 3)
            f.poly([(right, CREST_Y), (x1, CREST_Y)], color, 3)
            # the reservoir pouring through the notch, torn and muddy
            f.d.polygon([f.P(*q) for q in notch], fill=WATER + (int(170 * k),))
            rnd = random.Random(11)
            for i in range(30):
                ph = (breach * 3 + rnd.random()) % 1.0
                ya = lerp(CREST_Y + 10, depth - 30, ph)
                xa = lerp(wall(ya) + 10, lerp(right, right - 50, (ya - CREST_Y) / max(1, depth - CREST_Y)) - 10,
                          rnd.random())
                f.poly([(xa, ya), (xa + rnd.uniform(-6, 6), min(depth, ya + rnd.uniform(30, 70)))],
                       mix(WATER, MUD, rnd.random() * 0.7) + (int(220 * k),), 3)
            f.poly(notch, RED, 2.4)
        # the face's berm lines, fading downward
        if frac >= 1:
            for k, y in enumerate((300, 390, 480)):
                xa = next(x for x in range(80, 640) if self._y_at(x) >= y)
                xb = next(x for x in range(1200, 640, -1) if self._y_at(x) >= y)
                if breach > 0:
                    xa = max(xa, lerp(300, 560, breach) + 40) if y < BASE_Y - 40 else xa
                f.poly([(xa, y), (xb, y)], DIM, 1.2)
        if hole > 0 and breach <= 0:            # the leak becomes a hole at the right abutment
            cx, cy = 290, lerp(470, 430, hole)
            r = lerp(4, 46, hole ** 1.3)
            px, py = f.P(cx, cy)
            rr = r * SS * f.zoom
            f.d.ellipse([px - rr, py - rr * 0.7, px + rr, py + rr * 0.7], fill=MUD + (230,))
            for k in range(5):                  # the muddy water leaving it
                f.arrow(cx + (k - 2) * r * 0.25, cy + r * 0.5, cx + (k - 2) * r * 0.4, cy + r * 0.5 + 40 + 60 * hole,
                        MUD, 3, 9)

    def trench_face(self, f, frac=1.0, alpha=1.0):
        """The key trench cut down into the right abutment, seen through the dam."""
        x0, x1 = TRENCH_X
        y0 = self._y_at((x0 + x1) / 2)
        pts = [(x0 - 10, self._y_at(x0 - 10)), (x0 + 18, y0 + 130), (x1 - 18, y0 + 130), (x1 + 10, self._y_at(x1 + 10))]
        f.poly(pts, AMBER + (int(255 * alpha),), 2.4, frac)

    def curtain_face(self, f, frac=1.0):
        x0, x1 = TRENCH_X
        for k in range(9):
            x = lerp(x0 - 40, x1 + 160, k / 8)
            y = self._y_at(x) + (130 if x0 < x < x1 else 10)
            f.poly([(x, y), (x, y + 70)], CYAN + (150,), 1.4, frac)

    def reservoir_face(self, f, level=0.0):
        """The reservoir behind the dam, as a dashed level line (0..1 of the way up)."""
        if level <= 0:
            return
        y = lerp(BASE_Y, RES_Y, level)
        xa = next(x for x in range(80, 640) if self._y_at(x) >= y)
        xb = next(x for x in range(1200, 640, -1) if self._y_at(x) >= y)
        x = xa
        while x < xb:
            f.poly([(x, y), (min(xb, x + 22), y)], WATER, 2)
            x += 34

    # ------------------------------------------------------------- the section
    def _trench_pts(self):
        tl, tr = CX - TR_TOP_W / 2, CX + TR_TOP_W / 2
        bl, br = CX - TR_BOT_W / 2, CX + TR_BOT_W / 2
        return [(tl, SEC_BASE), (bl, SEC_BASE + TR_D), (br, SEC_BASE + TR_D), (tr, SEC_BASE)]

    def section(self, f, rock=1.0, dam=1.0, water=0.0, seep=0.0, joints_sealed=False, crack=0.0,
                pipe=0.0, leak=0.0, collapse=0.0, filter_=False, t=0.0):
        d = f.d
        # rock and its joints
        if rock > 0:
            f.poly([(0, SEC_BASE), (W, SEC_BASE)], LINE, 2.2, rock)
            n = int(len(self.sec_joints) * rock)
            for a, b in self.sec_joints[:n]:
                col = DIM if not joints_sealed else (70, 90, 120)
                f.poly([a, b], col, 1.4 if not joints_sealed else 1.0)
            # grout curtain under the trench: a hatched band
            gx = CX
            for k in range(-4, 5):
                f.poly([(gx + k * 7, SEC_BASE + TR_D), (gx + k * 7, H - 10)], CYAN + (int(110 * rock),), 1.2)
        # the dam: shells and the core (fine soil) carried down into the trench
        if dam > 0:
            cr = collapse
            sag = 140 * cr
            outline = [(SX0, SEC_BASE), (CX - 70, SEC_CREST + sag * 0.6), (CX + 70, SEC_CREST + sag),
                       (SX1, SEC_BASE)]
            f.poly(outline, LINE, 2.6, dam)
            core = [(CX - TR_TOP_W / 2, SEC_BASE), (CX - 45, SEC_CREST + 8 + sag * 0.6),
                    (CX + 45, SEC_CREST + 8 + sag), (CX + TR_TOP_W / 2, SEC_BASE)]
            f.poly(core, SILT, 1.8, dam)
            f.poly(self._trench_pts(), SILT, 2.0, dam)
            if dam >= 1:                         # the trench fill: dotted silt
                rnd = random.Random(2)
                for _ in range(140):
                    x = rnd.uniform(CX - TR_TOP_W / 2 + 10, CX + TR_TOP_W / 2 - 10)
                    y = rnd.uniform(SEC_BASE + 6, SEC_BASE + TR_D - 6)
                    k = (y - SEC_BASE) / TR_D
                    half = lerp(TR_TOP_W / 2, TR_BOT_W / 2, k) - 6
                    if abs(x - CX) < half:
                        px, py = f.P(x, y)
                        d.ellipse([px - 2 * SS, py - 2 * SS, px + 2 * SS, py + 2 * SS], fill=SILT + (150,))
            if filter_:                          # a sand filter downstream of the core, down into the trench
                fx = CX + TR_TOP_W / 2 - 18
                f.poly([(fx, SEC_BASE + TR_D - 10), (fx, SEC_BASE), (CX + 55, SEC_CREST + 20)], GREEN, 4, dam)
        # the reservoir against the upstream face
        if water > 0:
            wy = lerp(SEC_BASE, SEC_CREST + 18, water)
            xa = lerp(SX0, CX - 70, (SEC_BASE - wy) / (SEC_BASE - SEC_CREST))
            d.polygon([f.P(0, wy), f.P(xa, wy), f.P(SX0, SEC_BASE), f.P(0, SEC_BASE)], fill=WATER + (70,))
            f.poly([(0, wy), (xa, wy)], WATER, 2.4)
        # seepage: under the head, through the rock joints round the curtain to the trench walls
        if seep > 0:
            for k in range(6):
                ph = (t * 0.5 + k / 6) % 1.0
                y = SEC_BASE + 40 + 18 * k
                path = [(SX0 + 40, y), (CX - TR_TOP_W / 2 - 30, y + 20),
                        (CX - lerp(TR_TOP_W, TR_BOT_W, (y + 20 - SEC_BASE) / TR_D) / 2, y + 20)]
                if joints_sealed:
                    path = path[:2]
                f.poly(path, WATER + (int(200 * seep),), 2)
                q = path[0][0] + (path[-1][0] - path[0][0]) * ph
                f.arrow(q - 24, y + 20 * ph, q, y + 20 * ph, WATER, 3, 8, seep)
        # a crack along the trench where the fill arched between its steep walls
        if crack > 0:
            f.poly([(CX - TR_TOP_W / 2 + 26, SEC_BASE + TR_D * 0.62), (CX, SEC_BASE + TR_D * 0.68),
                    (CX + TR_TOP_W / 2 - 26, SEC_BASE + TR_D * 0.62)], RED, 2.2, crack)
        # the pipe: eroding downstream through the fill, under the core, out at the face
        if pipe > 0:
            y = SEC_BASE + TR_D * 0.66
            x0 = CX - TR_TOP_W / 2 + 20
            xe = lerp(x0, SX1 - 80, pipe)
            r = lerp(5, 26, pipe ** 1.5)
            pts = [(x0, y), (CX + TR_TOP_W / 2 - 10, y - 10), (CX + 200, SEC_BASE - 20), (SX1 - 80, SEC_BASE - 6)]
            # the pipe along its path so far
            segs = []
            total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            left = total * pipe
            out = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                L = math.dist(a, b)
                if left <= 0:
                    break
                if L <= left:
                    out.append(b)
                    left -= L
                else:
                    out.append((lerp(a[0], b[0], left / L), lerp(a[1], b[1], left / L)))
                    left = 0
            f.poly(out, (40, 20, 10), max(3, r), 1.0, world_width=True)
            f.poly(out, MUD, max(2, r * 0.6), 1.0, world_width=True)
        if leak > 0:                              # muddy water leaving at the downstream face
            lx, ly = SX1 - 80, SEC_BASE - 6
            for k in range(6):
                ph = (t * 0.9 + k / 6) % 1.0
                f.arrow(lx + 10, ly, lx + 10 + 90 * ph, ly + 40 * ph * ph, MUD, 3 + 4 * leak, 10, leak)

    # -------------------------------------------------------------- the clips
    BUILD = Beats(("canyon", 1.6, 0.2), ("joints", 1.2, 0.6), ("dam", 1.4, 0.4), ("trench", 1.0, 0.6),
                  ("curtain", 0.8, 0.4), ("fill", 2.4, 0.6), ("labels", 0.7, 2.2), ("zoom", 2.0, 0.4),
                  ("node", 0.6, 2.6))
    PHYS = Beats(("lead", 1.2, 0.3), ("section", 1.4, 1.6), ("water", 1.6, 1.6), ("seep", 1.4, 2.4),
                 ("crack", 0.8, 2.0), ("pipe", 3.0, 1.4), ("leak", 1.0, 2.0), ("grow", 1.8, 1.6))
    FALL = Beats(("handover", 0.8, 0.0), ("pull", 1.6, 0.4), ("hole", 2.2, 0.6), ("breach", 2.6, 0.6),
                 ("settle", 0.1, 1.2), ("toll", 0.6, 2.8))
    COMP = Beats(("show", 1.0, 0.6), ("water", 1.2, 1.4), ("seep", 1.2, 2.0), ("pipe", 2.0, 1.4),
                 ("verdict", 0.6, 2.8))

    def b_camera(self, t):
        k = self.BUILD.p(t, "zoom")
        x0, x1 = TRENCH_X
        return (lerp(W / 2, (x0 + x1) / 2 + 40, k), lerp(H / 2, 420, k), lerp(1.0, 2.4, k))

    def b_content(self, f, t, label_alpha=1.0):
        b = self.BUILD
        self.canyon(f, b.p(t, "canyon"), b.p(t, "joints"))
        self.reservoir_face(f, b.p(t, "fill"))
        self.dam_face(f, b.p(t, "dam"))
        self.trench_face(f, b.p(t, "trench"))
        self.curtain_face(f, b.p(t, "curtain"))
        la = b.p(t, "labels") * b.until(t, "zoom")
        L = self.labels
        f.label(L.get("dam", self.dam or "the dam"), 700, CREST_Y, 760, 130, la)
        f.label(L.get("rock", "jointed rock"), 1020, 330, 1060, 470, la)
        f.label(L.get("reservoir", "the reservoir, filling"), 820, lerp(BASE_Y, RES_Y, b.p(t, "fill")) + 2,
                900, 640, la, CYAN)
        f.label(L.get("trench", "key trench, right abutment"), (TRENCH_X[0] + TRENCH_X[1]) / 2, 330, 330, 640,
                la, AMBER)
        lb = b.p(t, "node") * label_alpha
        f.label(L.get("node", "the trench fill: windblown silt"), (TRENCH_X[0] + TRENCH_X[1]) / 2, 380, 640, 560,
                lb, RED, size=19)

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
        pipe = b.p(t, "pipe") * 0.8 + b.p(t, "grow") * 0.2
        self.section(f, b.p(t, "section"), b.p(t, "section"), water=b.p(t, "water"), seep=b.p(t, "seep"),
                     crack=b.p(t, "crack"), pipe=pipe, leak=b.p(t, "leak"), t=t)
        a = b.p(t, "section") * b.until(t, "pipe")
        f.text(L.get("core", "the core: fine windblown silt"), CX, SEC_CREST + 70, 20, SILT, "Inter-Bold.otf",
               screen=True, alpha=a, anchor="ms")
        f.text(L.get("curtain", "grout curtain"), CX + 40, H - 30, 18, CYAN, "Inter-Bold.otf", screen=True,
               alpha=a, anchor="ls")
        f.text(L.get("upstream", "upstream"), 60, SEC_BASE - 12, 18, DIM, "Inter-Bold.otf", screen=True, alpha=a)
        f.text(L.get("downstream", "downstream"), W - 60, SEC_BASE - 12, 18, DIM, "Inter-Bold.otf", screen=True,
               alpha=a, anchor="rs")
        sp = b.p(t, "seep") * b.until(t, "crack")
        f.text(L.get("seep", "water under full head finds the open joints"), 60, 110, 24, WATER, "Inter-Bold.otf",
               screen=True, alpha=sp)
        cr = b.p(t, "crack") * b.until(t, "pipe")
        f.text(L.get("crack", "the fill cracks between the trench's steep walls"), 60, 110, 24, RED,
               "Inter-Bold.otf", screen=True, alpha=cr)
        pp = b.p(t, "pipe") * b.until(t, "leak")
        f.text(L.get("pipe", "the water carries the silt away: a pipe"), 60, 110, 24, MUD, "Inter-Bold.otf",
               screen=True, alpha=pp)
        lk = b.p(t, "leak")
        f.text(L.get("leak", "muddy water at the downstream face"), W - 60, 110, 24, MUD, "Inter-Bold.otf",
               screen=True, alpha=lk, anchor="rs")
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8) * b.until(t, "water"))
        return f

    _phys_last = None

    def fall(self, t, T=None):
        b = self.FALL
        k = b.p(t, "pull")
        f = Frame(lerp(W / 2 - 200, W / 2, k), lerp(430, H / 2, k), lerp(1.8, 1.0, k))
        f.grid(1)
        self.canyon(f, 1, 1)
        brk = b.p(t, "breach")
        self.reservoir_face(f, 1 - 0.7 * brk)
        self.dam_face(f, 1, hole=b.p(t, "hole"), breach=brk)
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

    def side(self, built, rock=1.0, dam=1.0, water=0.0, seep=0.0, crack=0.0, pipe=0.0, leak=0.0,
             collapse=0.0, verdict=0.0, stamp=0.0, stamp_text="", t=0.0):
        """One side of the comparison on its own, for a Short (what it
        needed above, as built below, both drawn from nothing at once): the
        section through the trench, the joints sealed and a filter in place
        (it holds) or open joints and no filter (the pipe, the leak, the
        collapse)."""
        f = Frame(CX, (SEC_CREST + H) / 2 + 10, 1.15)
        f.grid(1)
        if not built:
            crack = pipe = leak = collapse = 0.0
        self.section(f, rock, dam, water=water, seep=seep, joints_sealed=not built, crack=crack, pipe=pipe,
                     leak=leak, collapse=collapse, filter_=not built, t=t)
        if stamp > 0 and stamp_text and verdict < 1:
            k = min(1.0, stamp)
            f.text(stamp_text, W / 2, 80, int(52 * (1.6 - 0.6 * k)), RED, "InterDisplay-Black.otf",
                   anchor="mm", screen=True, alpha=k * (1 - min(1.0, collapse * 4)))
        if verdict > 0:
            word, col = ("FAILS", RED) if built else ("HOLDS", GREEN)
            f.text(word, W / 2, 80, 96, col, "InterDisplay-Black.otf", anchor="mm", screen=True, alpha=verdict)
        return f.done()

    def compare(self, t, T=None):
        b = self.COMP
        water, seep, pipe = b.p(t, "water"), b.p(t, "seep"), b.p(t, "pipe")
        halves = []
        for built in (False, True):
            g = Frame(CX, (SEC_CREST + H) / 2, 0.55)
            g.grid(0.6)
            self.section(g, 1, 1, water=water, seep=seep, joints_sealed=not built,
                         crack=pipe if built else 0, pipe=pipe if built else 0, leak=pipe if built else 0,
                         filter_=not built, t=t)
            halves.append(g.done().crop((W // 4, 0, W // 4 + W // 2, H)))
        out = Image.new("RGB", (W, H), BG)
        out.paste(halves[0], (0, 0))
        out.paste(halves[1], (W // 2, 0))
        f = Frame()
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
                       anchor="mm", screen=True, alpha=water)
        a = b.p(t, "verdict")
        if a > 0:
            f.text("HOLDS", W / 4, 620, 34, GREEN, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
            f.text("FAILS", 3 * W / 4, 620, 34, RED, "Inter-Bold.otf", anchor="mm", screen=True, alpha=a)
        f.caption(self.captions.get("compare", ""), prog(t, 0.4, 1.0))
        return f.done()
