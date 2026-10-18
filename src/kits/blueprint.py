"""
Blueprint drawing primitives shared by every kit: the channel palette, fonts,
easing, a 2D camera (Frame) that draws at 2x and downsamples, and the
encoder. World units are screen pixels at zoom 1 (1280x720).
"""

import math
import os
import shutil
import subprocess

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

_FONT_DIRS = [os.path.join(os.path.dirname(__file__), "..", "..", "fonts"),
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



def encode(frames_dir, mp4, fps=FPS):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", os.path.join(frames_dir, "%05d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)


def render_clip(fn, seconds, mp4, *args):
    """Renders fn(t, T, *args) -> Image for every frame of a clip."""
    frames = mp4 + "_frames"
    os.makedirs(frames, exist_ok=True)
    for i in range(int(round(seconds * FPS))):
        fn(i / FPS, seconds, *args).save(os.path.join(frames, f"{i:05d}.png"))
    encode(frames, mp4)
    shutil.rmtree(frames)
    return mp4


class Beats:
    """A clip's timeline as named beats. Each beat animates in, then HOLDS so
    the viewer can take it in before the next one starts (owner, 2026-10-17:
    pausing at each step is the product). Later the narration sets the holds:
    a beat lasts as long as the sentence that explains it.

        b = Beats(("arrows", 0.8, 1.8), ("panel", 0.8, 2.6))
        b.p(t, "arrows")          # 0..1, eased, during the beat's animation
        b.total                   # the clip's length
    """

    def __init__(self, *beats, start=0.0, pace=1.0):
        self.spec, self.start0, self.pace = beats, start, pace
        self.at = {}
        t = start
        for name, anim, hold in beats:
            self.at[name] = (t, t + anim)
            t += anim + hold * pace
        self.total = t

    def p(self, t, name):
        a, b = self.at[name]
        return prog(t, a, b)

    def start(self, name):
        return self.at[name][0]

    def end(self, name):
        return self.at[name][1]

    def until(self, t, name, fade=0.4):
        """1 until the named beat starts, then fades out: for things that
        give way to that beat."""
        a = self.at[name][0]
        return 1 - prog(t, a - fade, a)

    def fitted(self, seconds, min_pace=0.6):
        """The same beats lasting `seconds`: the animations keep their speed,
        only the holds stretch or shrink (never below min_pace of their
        designed length, so nothing flashes past)."""
        anim = sum(a for _, a, _ in self.spec) + self.start0
        hold = sum(h for _, _, h in self.spec)
        pace = max(min_pace, (seconds - anim) / hold) if hold else 1.0
        return Beats(*self.spec, start=self.start0, pace=pace)


class KitTiming:
    """For kits whose clips are Beats timelines (BUILD, PHYS, FALL, COMP):
    fit them to the narration (step 5b)."""
    CLIPS = {"build": "BUILD", "physics": "PHYS", "fall": "FALL", "compare": "COMP"}

    def durations(self):
        return {clip: getattr(self, attr).total for clip, attr in self.CLIPS.items()}

    def fit(self, seconds):
        """seconds: {clip: how long its narration needs}. Clips not named keep
        their designed timing."""
        for clip, attr in self.CLIPS.items():
            if seconds.get(clip):
                setattr(self, attr, getattr(type(self), attr).fitted(seconds[clip]))
        self._phys_last = None
        return self.durations()
