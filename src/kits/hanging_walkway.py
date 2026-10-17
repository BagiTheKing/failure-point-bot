"""
Structure kit, variant "hanging walkways": decks hung from a roof on steel
rods, one connection overloaded (Hyatt Regency, 1981, is the reference).

The kit owns the drawing, so the structure is always right; the animation
sheet (kits/sheets/*.json) supplies the words and numbers, and the director
only picks clips and timing. Clips, each a function (t, T) -> Image that
starts where the previous one ended (same camera), so no hard cuts:

    build     the structure draws itself, labels, push-in on the failed connection
    physics   loads on the connection, the multiplier, stress, cracks, pull-through
    fall      pull back out; the upper deck drops onto the lower, both fall, dust
    compare   as designed (holds) vs as built (fails), split screen
"""

import math
import random

from PIL import Image, ImageDraw

from kits.blueprint import (W, H, SS, BG, LINE, DIM, RED, AMBER, CYAN, GREEN,
                            ease, prog, lerp, mix, Frame)

# side elevation, world units = screen px at zoom 1
ROOF_Y, UP_Y, LO_Y, GROUND_Y = 120, 330, 540, 650
WALK_X0, WALK_X1 = 300, 980
BEAM_H, DECK_H = 16, 10
B_ZOOM_END = 7.6


class HangingWalkways:
    def __init__(self, sheet):
        self.sheet = sheet
        k = sheet["kit"]
        n = int(k.get("rod_lines", 3))
        step = (WALK_X1 - WALK_X0) / n
        self.rods = [WALK_X0 + step * (i + 0.5) for i in range(n)]
        self.fail_x = self.rods[int(k.get("failed_line", n // 2))]
        self.levels = k.get("levels", ["upper walkway", "lower walkway"])
        self.labels = k.get("labels", {})
        dvb = sheet.get("design_vs_built", {})
        self.dvb = dvb
        self.mult = dvb.get("multiplier", "2×")
        self.mult_label = dvb.get("multiplier_label", "LOAD ON ONE NUT")
        self.captions = {s["clip"]: s.get("caption", "") for s in sheet.get("shots", [])}

    # ------------------------------------------------------------------ drawing
    def people(self, f, y, x0, x1, alpha=1.0, n=26, seed=3, drop=0.0, tumble=0.0):
        rnd = random.Random(seed)
        col = DIM + (int(255 * alpha),)
        for i in range(n):
            x = lerp(x0, x1, (i + rnd.random() * 0.6) / n)
            h = 16 + rnd.random() * 4
            dx = (rnd.random() - 0.5) * 30 * tumble
            yy = y + drop
            px, py = f.P(x + dx, yy - h)
            r = 3 * SS * f.zoom
            f.d.ellipse([px - r, py - r, px + r, py + r], fill=col)
            a, b = f.P(x + dx - 2.5, yy - h + 4), f.P(x + dx + 2.5, yy)
            f.d.rectangle([a, b], fill=col)

    def structure(self, f, t_walls=1, t_roof=1, t_rods=1, t_walks=1, built=True,
                  drop_up=0.0, drop_lo=0.0, tilt=0.0, highlight=0.0, rod_color=LINE,
                  skip_fail=False):
        for x in (200, 1080):
            f.poly([(x, ROOF_Y - 30), (x, GROUND_Y)], DIM, 2, t_walls)
        f.poly([(150, GROUND_Y), (1130, GROUND_Y)], LINE, 3, t_walls)
        for y in (UP_Y, LO_Y):
            f.poly([(150, y), (200, y)], DIM, 3, t_walls)
            f.poly([(1080, y), (1130, y)], DIM, 3, t_walls)
        pts = [(220, ROOF_Y)]
        for i, x in enumerate(range(220, 1061, 60)):
            pts.append((x, ROOF_Y - (34 if i % 2 else 0)))
        f.poly([(220, ROOF_Y), (1060, ROOF_Y)], LINE, 3, t_roof)
        f.poly([(220, ROOF_Y - 34), (1060, ROOF_Y - 34)], LINE, 2, t_roof)
        f.poly(pts, DIM, 2, t_roof)
        # decks: a falling deck tilts about its far end (it lets go at the middle first)
        for y0, drop, tw, is_up in ((UP_Y, drop_up, t_walks, True), (LO_Y, drop_lo, t_walks, False)):
            def Y(x, y, d=drop, up=is_up):
                return y + d + (tilt * (x - WALK_X0) / (WALK_X1 - WALK_X0) * 20 if up else 0)
            deck = [(WALK_X0, Y(WALK_X0, y0 - DECK_H)), (WALK_X1, Y(WALK_X1, y0 - DECK_H)),
                    (WALK_X1, Y(WALK_X1, y0)), (WALK_X0, Y(WALK_X0, y0)),
                    (WALK_X0, Y(WALK_X0, y0 - DECK_H))]
            f.poly(deck, LINE, 2, tw)
            if tw >= 1:
                for x in self.rods:
                    if skip_fail and x == self.fail_x and is_up:
                        continue
                    yb = Y(x, y0)
                    f.rect(x - 22, yb, x + 22, yb + BEAM_H, LINE, (18, 38, 66), 2)
            f.poly([(WALK_X0, Y(WALK_X0, y0 - DECK_H - 26)), (WALK_X1, Y(WALK_X1, y0 - DECK_H - 26))],
                   DIM, 1, tw)
            for x in range(WALK_X0, WALK_X1 + 1, 34):
                f.poly([(x, Y(x, y0 - DECK_H)), (x, Y(x, y0 - DECK_H - 26))], DIM, 1, tw)
        for x in self.rods:
            if skip_fail and x == self.fail_x:
                continue
            if built:
                # upper rods stay on the roof: the beam pulls off over the nut
                f.poly([(x - 4, ROOF_Y), (x - 4, UP_Y + BEAM_H + 3)], rod_color, 2, t_rods)
                # lower rods hang from the upper beams and go down with them
                if drop_up - drop_lo < (LO_Y - UP_Y - BEAM_H - DECK_H) * 0.9:
                    f.poly([(x + 4, UP_Y + BEAM_H + 3 + drop_up), (x + 4, LO_Y + BEAM_H + 3 + drop_lo)],
                           rod_color, 2, t_rods)
            else:
                f.poly([(x, ROOF_Y), (x, LO_Y + BEAM_H + 3)], rod_color, 2, t_rods)
            if t_rods >= 1:
                nuts = [((UP_Y, -4 if built else 0)), ((LO_Y + drop_lo if built else LO_Y), 4 if built else 0)]
                for y, dx in nuts:
                    a, b = f.P(x + dx - 5, y + BEAM_H), f.P(x + dx + 5, y + BEAM_H + 4)
                    f.d.rectangle([a, b], fill=LINE)
        if highlight > 0:
            pulse = 0.55 + 0.45 * math.sin(highlight * 12)
            a, b = f.P(self.fail_x - 30, UP_Y - 8), f.P(self.fail_x + 30, UP_Y + BEAM_H + 14)
            f.d.rounded_rectangle([a, b], radius=6 * SS, outline=RED + (int(200 * pulse),), width=3 * SS)

    def connection(self, f, stress=0.0, crack=0.0, built=True, pulse=0.0, slip=0.0):
        """The failed connection at real proportions (reads at ~6x zoom).
        slip: how far the beam has slid down over the upper nut (pull-through)."""
        x, y = self.fail_x, UP_Y
        up, lo = (x - 4, x + 4) if built else (x, x)
        if stress > 0:
            cx, cy = f.P(up, y + BEAM_H)
            for k in range(6, 0, -1):
                r = (4 + k * 3.2) * f.zoom * SS * (0.5 + stress)
                f.d.ellipse([cx - r, cy - r, cx + r, cy + r],
                            fill=mix(AMBER, RED, stress) + (int(26 * stress * (7 - k) / 2),))
        yb = y + slip
        f.rect(x - 22, yb, x + 22, yb + BEAM_H, mix(LINE, RED, stress), (18, 38, 66), 1.5)
        f.poly([(x - 22, yb + BEAM_H / 2), (x + 22, yb + BEAM_H / 2)], DIM, 1)
        f.poly([(up, y - 40), (up, y + BEAM_H + 3)], LINE, 1.6, world_width=True)
        if built:
            f.poly([(lo, yb + BEAM_H - 4), (lo, yb + 70)], LINE, 1.6, world_width=True)
            a, b = f.P(lo - 4, yb + BEAM_H - 4), f.P(lo + 4, yb + BEAM_H - 1.5)
            f.d.rectangle([a, b], fill=LINE)
        nut_col = mix(LINE, RED, max(stress, 0.5 + 0.5 * math.sin(pulse * 10) if pulse else 0))
        a, b = f.P(up - 4, y + BEAM_H), f.P(up + 4, y + BEAM_H + 3)
        f.d.rectangle([a, b], fill=nut_col)
        if crack > 0:
            for dx, ang in ((-5, -2.2), (5, -0.9), (-3, -1.8), (4, -1.2)):
                sx, sy = up + dx, yb + BEAM_H
                f.poly([(sx, sy), (sx + math.cos(ang) * 9 * crack, sy + math.sin(ang) * 9 * crack)],
                       RED, 2.5)

    def dust(self, f, t_since, x0, x1, y, seed=9, amount=1.0):
        """Blueprint dust: expanding rings and debris flecks after an impact."""
        if t_since <= 0:
            return
        rnd = random.Random(seed)
        fade = max(0.0, 1 - t_since / 2.6)
        for _ in range(int(40 * amount)):
            x = rnd.uniform(x0, x1)
            r = (14 + rnd.random() * 40) * min(1, t_since / 1.0 + 0.3)
            rise = rnd.random() * 70 * min(1, t_since)
            cx, cy = f.P(x, y - rise)
            rr = r * f.zoom * SS
            f.d.ellipse([cx - rr, cy - rr * 0.7, cx + rr, cy + rr * 0.7],
                        fill=DIM + (int(120 * fade * (0.4 + rnd.random() * 0.6)),))
        for _ in range(int(40 * amount)):
            x = rnd.uniform(x0, x1)
            vx, vy = rnd.uniform(-90, 90), rnd.uniform(-160, -40)
            tt = min(t_since, 1.2)
            px, py = x + vx * tt, y + vy * tt + 260 * tt * tt
            if py > GROUND_Y:
                py = GROUND_Y - 2
            ang = rnd.uniform(0, math.pi)
            f.poly([(px, py), (px + 6 * math.cos(ang), py + 6 * math.sin(ang))],
                   LINE + (int(220 * fade),), 2)

    # -------------------------------------------------------------------- clips
    def b_camera(self, t):
        k = prog(t, 5.0, B_ZOOM_END)
        return (lerp(W / 2, self.fail_x, k), lerp(H / 2 - 20, UP_Y + 8, k), lerp(1.0, 5.2, k))

    def b_content(self, f, t, label_alpha=1.0):
        zoomed = f.zoom > 2.2
        self.structure(f, prog(t, 0.3, 1.6), prog(t, 1.4, 2.4), prog(t, 2.3, 3.4),
                       prog(t, 3.2, 4.4), skip_fail=zoomed)
        a = prog(t, 4.0, 4.6)
        self.people(f, GROUND_Y, 230, 1050, a)
        self.people(f, LO_Y - DECK_H, 320, 960, a, n=14, seed=5)
        self.people(f, UP_Y - DECK_H, 320, 960, a, n=12, seed=7)
        if zoomed:
            self.connection(f, pulse=(t - B_ZOOM_END) if t > B_ZOOM_END else 0)
        la = prog(t, 3.6, 4.3) * (1 - prog(t, 4.9, 5.3))
        L = self.labels
        f.label(L.get("roof", "roof"), 700, ROOF_Y - 17, 860, 70, la)
        f.label(L.get("rods", "hanger rods"), self.rods[-1] + 4, 230, 1010, 230, la)
        f.label(self.levels[0], 520, UP_Y - 5, 380, 270, la)
        f.label(self.levels[1], 520, LO_Y - 5, 380, 480, la)
        lb = prog(t, 7.8, 8.4) * label_alpha
        f.label(L.get("beam", "beam"), self.fail_x + 18, UP_Y + 4, 900, 250, lb, size=19)
        f.label(L.get("nut", "the connection"), self.fail_x - 4, UP_Y + BEAM_H + 2, 300, 520,
                lb, RED, size=19)

    def build(self, t, T):
        f = Frame(*self.b_camera(t))
        f.grid(prog(t, 0, 0.8))
        self.b_content(f, t)
        cap = self.captions.get("establish") if t < 5 else self.captions.get("connection")
        f.caption(cap or "", prog(t, 0.8, 1.4) if cap else 0)
        return f.done()

    PHYS_CAM = (None, UP_Y + 14, 6.0)

    def physics(self, t, T, lead=1.2):
        """Starts on build's last frame when lead > 0 (one continuous shot)."""
        k = ease(prog(t, 0, lead)) if lead else 1
        bx, by, bz = self.b_camera(99)
        f = Frame(lerp(bx, self.fail_x, k), lerp(by, UP_Y + 14, k), lerp(bz, 6.0, k))
        f.grid(1)
        tt = t - lead * 0.5
        if k < 1:
            g = Frame(f.cx, f.cy, f.zoom)
            g.grid(1)
            self.b_content(g, 99, label_alpha=1 - prog(t, 0, 0.6))
            self._physics_body(f, tt, T)
            return Image.blend(g.done(), f.done(), k)
        return self._physics_body(f, tt, T).done()

    def _physics_body(self, f, t, T):
        stress = prog(t, 3.5, 7.0)
        crack = prog(t, 6.2, 8.0)
        slip = 14 * prog(t, 8.0, 9.0) ** 2
        x, y = self.fail_x, UP_Y
        f.rect(WALK_X0, y - DECK_H + slip, WALK_X1, y + slip, LINE, None, 1.5)
        self.connection(f, stress, crack, slip=slip)
        a1 = prog(t, 0.6, 1.4)
        f.arrow(x - 16, y - 30, x - 16, y - 2, AMBER, 6, 16, a1)
        f.text(self.levels[0], 520, 140, 22, AMBER, "Inter-Bold.otf", screen=True, alpha=a1, anchor="rs")
        f.text("its own weight", 520, 166, 18, LINE, "Inter-Medium.otf", screen=True, alpha=a1, anchor="rs")
        a2 = prog(t, 1.8, 2.6)
        f.arrow(x + 12, y + 32, x + 12, y + 56, AMBER, 6, 16, a2)
        f.text(self.levels[1], 740, 540, 22, AMBER, "Inter-Bold.otf", screen=True, alpha=a2)
        f.text("hangs from THIS beam", 740, 566, 18, LINE, "Inter-Medium.otf", screen=True, alpha=a2)
        a3 = prog(t, 3.0, 3.8)
        f.arrow(x - 4, y + BEAM_H + 4, x - 4, y + BEAM_H + 22, RED, 10, 22, a3)
        f.text(self.mult, 590, 470, 70, RED, "InterDisplay-Black.otf", screen=True, alpha=a3, anchor="rs")
        f.text(self.mult_label, 590, 504, 22, RED, "Inter-Bold.otf", screen=True, alpha=a3, anchor="rs")
        p = prog(t, 4.0, 4.8)
        d, b = self.dvb.get("designed", {}), self.dvb.get("built", {})
        f.d.rectangle([40 * SS, 250 * SS, 330 * SS, 400 * SS], fill=(0, 0, 0, int(150 * p)))
        f.text(d.get("title", "AS DESIGNED"), 58, 278, 16, CYAN, "Inter-Bold.otf", screen=True, alpha=p)
        f.text(d.get("load", ""), 58, 304, 20, LINE, "Inter-Medium.otf", screen=True, alpha=p)
        f.text(b.get("title", "AS BUILT"), 58, 344, 16, RED, "Inter-Bold.otf", screen=True, alpha=p)
        f.text(b.get("load", ""), 58, 370, 20, LINE, "Inter-Medium.otf", screen=True, alpha=p)
        if crack > 0:
            f.text("the nut pulls through the steel", W - 40, 120, 24, RED, "Inter-Bold.otf",
                   screen=True, alpha=prog(t, 6.4, 7.0), anchor="rs")
        f.caption(self.captions.get("physics", ""), prog(t, 0.2, 0.8))
        return f

    def fall(self, t, T, lead=1.6):
        """Continues from physics: pull back to the whole structure, then the
        failure chain in the kit's order: upper deck onto lower, both down."""
        k = ease(prog(t, 0, lead))
        f = Frame(lerp(self.fail_x, W / 2, k), lerp(UP_Y + 14, H / 2 + 40, k), lerp(6.0, 0.95, k))
        f.grid(1)
        t0 = lead + 0.6                       # the connection lets go
        gap = LO_Y - UP_Y - BEAM_H - DECK_H
        s1 = prog(t, t0, t0 + 0.45) ** 1.6    # upper deck falls the gap
        s2 = prog(t, t0 + 0.45, t0 + 1.0) ** 1.6
        drop_lo = (GROUND_Y - LO_Y - BEAM_H) * s2
        drop_up = gap * s1 + drop_lo
        tilt = 1 - s1 if t > t0 else 0
        shake = 4 * math.sin(t * 70) * max(0, 1 - abs(t - (t0 + 1.0)) * 3) if t > t0 + 0.9 else 0
        f.cx += shake
        self.structure(f, drop_up=drop_up, drop_lo=drop_lo, tilt=tilt * 0.6,
                       highlight=(t - lead) if lead < t < t0 + 0.2 else 0)
        self.people(f, GROUND_Y, 230, 1050, 1)
        self.people(f, LO_Y - DECK_H, 320, 960, 1, n=14, seed=5, drop=drop_lo, tumble=s2)
        self.people(f, UP_Y - DECK_H, 320, 960, 1, n=12, seed=7, drop=drop_up, tumble=s2)
        self.dust(f, t - (t0 + 1.0), WALK_X0, WALK_X1, GROUND_Y - 20)
        nums = self.sheet.get("numbers", [])
        if nums and t > t0 + 2.0:
            a = prog(t, t0 + 2.0, t0 + 2.6)
            f.text(nums[0]["value"], 1180, 300, 96, RED, "InterDisplay-Black.otf", anchor="rs",
                   screen=True, alpha=a)
            f.text(nums[0]["label"], 1180, 336, 24, LINE, "Inter-Bold.otf", anchor="rs",
                   screen=True, alpha=a)
        f.caption(self.captions.get("fall", ""), prog(t, 0.3, 0.9))
        return f.done()

    def compare(self, t, T):
        fall = prog(t, 5.0, 6.2)
        gap = LO_Y - UP_Y - BEAM_H - DECK_H
        drop_lo = (GROUND_Y - LO_Y - BEAM_H) * prog(fall, 0.55, 1.0)
        drop_up = gap * min(1, fall / 0.55) + drop_lo
        left = Frame(W / 2, H / 2 - 10, 0.52)
        left.grid(0.6)
        self.structure(left, built=False, rod_color=CYAN)
        right = Frame(W / 2, H / 2 - 10, 0.52)
        right.grid(0.6)
        self.structure(right, built=True, drop_up=drop_up, drop_lo=drop_lo,
                       highlight=(t - 2.5) if 2.5 < t < 5.0 else 0)
        self.dust(right, t - 6.2, WALK_X0, WALK_X1, GROUND_Y - 20, amount=0.6)
        for fr, labels in ((left, [("1×", CYAN), ("1×", CYAN)]),
                           (right, [(self.mult, RED), ("1×", AMBER)])):
            a = prog(t, 1.4, 2.2) * (1 - fall)
            for (s, col), y in zip(labels, (UP_Y, LO_Y)):
                fr.text(s, self.fail_x + 40, y + 30, 40, col, "InterDisplay-Black.otf", alpha=a)
        out = Image.new("RGB", (W, H), BG)
        out.paste(left.done().crop((W // 4, 0, W // 4 + W // 2, H)), (0, 0))
        out.paste(right.done().crop((W // 4, 0, W // 4 + W // 2, H)), (W // 2, 0))
        f = Frame()
        f.img = out.resize((W * SS, H * SS))
        f.d = ImageDraw.Draw(f.img, "RGBA")
        f.d.line([(W * SS / 2, 0), (W * SS / 2, H * SS)], fill=LINE, width=2 * SS)
        d, b = self.dvb.get("designed", {}), self.dvb.get("built", {})
        f.text(d.get("title", "AS DESIGNED"), W / 4, 92, 24, CYAN, "Inter-Bold.otf", anchor="mm", screen=True)
        f.text(d.get("detail", ""), W / 4, 120, 17, LINE, "Inter-Medium.otf", anchor="mm", screen=True)
        f.text(b.get("title", "AS BUILT"), 3 * W / 4, 92, 24, RED, "Inter-Bold.otf", anchor="mm", screen=True)
        f.text(b.get("detail", ""), 3 * W / 4, 120, 17, LINE, "Inter-Medium.otf", anchor="mm", screen=True)
        if t > 6.4:
            a = prog(t, 6.4, 7.0)
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
