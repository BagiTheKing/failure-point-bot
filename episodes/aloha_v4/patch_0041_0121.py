"""Aloha v3: new pictures for the history shot (frames 1240-2453, 0:41-1:21)
and an 'up next' note, spliced into the cut episode; the sound is untouched."""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, "/home/user/failure-point-bot/src")
from kits.assemble import reel  # noqa: E402
from kits.blueprint import FPS, W, H  # noqa: E402
from kits.brand import watermark, RED  # noqa: E402

D = "/tmp/claude-0/-home-user/5273b1c1-74a4-5256-b426-61784603815a/scratchpad"
P = D + "/aloha_photos/"
SRC = D + "/al3/episode.mp4"
OUT = D + "/al3/episode_patched.mp4"
S, N = 1240, 1214                 # the shot's first frame and its length
T = N / FPS
FADE = 24                         # the dissolves either side, as cut

# shot time where each picture's words start (the pauses in the voice)
PICS = [
    (0.0, "c_nara_aloha_553959.jpg", "Photo: Charles O'Rear, 1973, U.S. National Archives (public domain)"),
    (4.6, "c_aloha_7372_1985_groves.jpg", "Photo: Clint Groves, 1985 (GFDL 1.2)"),
    (10.8, "c_n73711_schmid_1988.jpg", "Photo: Juerg Schmid, Feb. 1988 (CC BY-SA 4.0)"),
    (17.9, "c_aloha_737297_N726AL_1988.jpg", "Photo: Perry Hoppe, 1988 (GFDL 1.2)"),
    (22.9, "c_hilo_aerial.jpg", "Photo: Forest and Kim Starr (CC BY 3.0 US)"),
    (27.8, "c_route_nasa.jpg", "Map: NASA (public domain)"),
    (30.8, "c_haer_737_inspection_crop.jpg", "Photo: Historic American Engineering Record, Library of Congress (public domain)"),
    (35.7, "faa_Aloha737_skindetail.jpg", "Photo: FAA (public domain)"),
]

NOTE = "UP NEXT: THE HIDDEN FLAW, IN 3D"
NEXT_AT = T - FADE / FPS          # the 3D starts here, shot time


def items():
    out = []
    for i, (a, f, credit) in enumerate(PICS):
        b = PICS[i + 1][0] if i + 1 < len(PICS) else T
        # the dissolve into the next picture is centred on the pause
        out.append({"path": os.path.normpath(P + f), "credit": credit, "seconds": b - a})
    return out


def _font(name, px):
    from PIL import ImageFont
    from kits.blueprint import _FONT_DIRS
    return ImageFont.truetype(next(os.path.join(d, name) for d in _FONT_DIRS
                                   if os.path.exists(os.path.join(d, name))), px)


def note(img, t):
    """A small pill, top left: what comes next, and how soon."""
    a = min(1.0, max(0.0, (t - 1.2) / 0.5)) * min(1.0, max(0.0, (NEXT_AT - t) / 0.4))
    if a <= 0:
        return img
    d = ImageDraw.Draw(img, "RGBA")
    f = _font("Inter-Bold.otf", 17)
    fc = _font("Inter-Medium.otf", 17)
    left = max(0, int(NEXT_AT - t + 0.999))
    clock = f"{left // 60}:{left % 60:02d}"
    tw, cw = f.getlength(NOTE), fc.getlength(clock)
    x, y = 40, 34
    d.rounded_rectangle([x, y, x + 30 + tw + 16 + cw + 14, y + 34], radius=8, fill=(0, 0, 0, int(165 * a)))
    on = 0.55 + 0.45 * (0.5 + 0.5 * np.cos(t * 2 * np.pi / 1.6))     # the dot breathes
    d.ellipse([x + 12, y + 12, x + 22, y + 22], fill=RED + (int(255 * a * on),))
    d.text((x + 30, y + 17), NOTE, font=f, fill=(255, 255, 255, int(255 * a)), anchor="lm")
    d.text((x + 30 + tw + 16, y + 17), clock, font=fc, fill=(190, 198, 210, int(255 * a)), anchor="lm")
    return img


def frame_at(n):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"select=eq(n\\,{n})", "-vsync", "0",
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (W, H), raw)


def main():
    wm = Image.open(watermark(D + "/al3/wm.png")).convert("RGBA")
    before, after = frame_at(S - 1), frame_at(S + N)     # last of the cold open, first of the 3D
    fn = reel(items(), T)
    seg = D + "/al3/seg.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", seg], stdin=subprocess.PIPE)
    for k in range(N):
        t = k / FPS
        img = fn(t, T).convert("RGB")
        img = note(img, t)
        img.paste(wm, (W - wm.width - 22, 18), wm)
        if k < FADE:
            img = Image.blend(before, img, (k + 1) / (FADE + 1))
        elif k >= N - FADE:
            img = Image.blend(img, after, (k - (N - FADE) + 1) / (FADE + 1))
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    # the cut with the shot swapped: before it, the new shot, after it; the sound as it was
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-i", seg, "-filter_complex",
                    f"[0:v]trim=end_frame={S},setpts=PTS-STARTPTS[a];"
                    f"[1:v]setpts=PTS-STARTPTS[b];"
                    f"[0:v]trim=start_frame={S + N},setpts=PTS-STARTPTS[c];"
                    f"[a][b][c]concat=n=3:v=1:a=0[v]",
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", OUT], check=True)
    print(OUT)


if __name__ == "__main__":
    main()
