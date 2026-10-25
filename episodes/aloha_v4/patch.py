"""Aloha v4: three stretches of v3 get new pictures, spliced into the cut
episode with the sound untouched.
  1. 0:41-1:21  the history shot (frames 1240-2453), with an 'up next' note
  2. 4:47-5:29  after the cabin opens: the held 3D and the aftermath stills
  3. 7:37-7:56  the memorial shot of the last chapter
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, "/home/user/failure-point-bot/src")
from kits.assemble import reel  # noqa: E402
from kits.blueprint import FPS, W, H, _FONT_DIRS  # noqa: E402
from kits.brand import watermark, RED  # noqa: E402

D = "/tmp/claude-0/-home-user/5273b1c1-74a4-5256-b426-61784603815a/scratchpad"
P = D + "/aloha_photos/"
SRC = D + "/al3/episode.mp4"
OUT = D + "/al3/episode_v4.mp4"
TOTAL = 14983
FADE = 24

NARA = "Photo: Charles O'Rear, 1973, U.S. National Archives (public domain)"
NTSB = "Photo: NTSB (public domain)"
FAA = "Photo: FAA (public domain)"
BLOCKS = [
    {"name": "history", "start": 1240, "n": 1214, "in": "freeze", "out": "freeze",
     "note": "UP NEXT: THE HIDDEN FLAW, IN 3D", "pics": [
         (0.0, "c_nara_aloha_553959.jpg", NARA, None),
         (4.6, "c_aloha_7372_1985_groves.jpg", "Photo: Clint Groves, 1985 (GFDL 1.2)", None),
         (10.8, "c_n73711_schmid_1988.jpg", "Photo: Juerg Schmid, Feb. 1988 (CC BY-SA 4.0)", None),
         (17.9, "c_aloha_737297_N726AL_1988.jpg", "Photo: Perry Hoppe, 1988 (GFDL 1.2)", None),
         (22.9, "c_hilo_aerial.jpg", "Photo: Forest and Kim Starr (CC BY 3.0 US)", None),
         (27.8, "c_route_nasa.jpg", "Map: NASA (public domain)", None),
         (30.8, "c_haer_737_inspection_crop.jpg",
          "Photo: Historic American Engineering Record, Library of Congress (public domain)", None),
         (35.7, "faa_Aloha737_skindetail.jpg", FAA, None)]},
    # the 3D keeps the fall and the cabin opening; from the first officer's
    # papers on, pictures carry the words
    {"name": "aftermath", "start": 8625, "n": 1250, "in": "live", "out": "freeze", "pics": [
        (0.0, "c_7372_cabin.jpg", "Photo: CambridgeBayWeather, 2013 (CC BY-SA 3.0)", "A BOEING 737-200 CABIN"),
        (3.0, "ntsb_left_open.jpg", NTSB, None),
        (8.1, "c_kahului_aerial.jpg", "Photo: Forest and Kim Starr, 2009 (CC BY 2.0)", "KAHULUI AIRPORT, MAUI"),
        (15.5, "c_fuselage_ntsb.png", NTSB, None),
        (25.5, "c_after_accident_faa.jpg", FAA, None),
        (35.2, "faa_aftermath_card.jpg", FAA, None)]},
    {"name": "memorial", "start": 13701, "n": 582, "in": "freeze", "out": "freeze", "pics": [
        (0.0, "c_hnl_hawaiian_garden.jpg", "Photo: Daniel K. Inouye Airport gardens, 2025 (CC BY-SA 4.0)",
         "HONOLULU AIRPORT'S GARDENS TODAY"),
        (6.3, "faa_Aloha737_initialFinding.jpg", "Drawing: FAA (public domain)", None),
        (12.8, "c_usaf_eddy_current.jpg", "Photo: U.S. Air Force (public domain)", "EDDY-CURRENT CRACK TESTING")]},
]


def _font(name, px):
    from PIL import ImageFont
    return ImageFont.truetype(next(os.path.join(d, name) for d in _FONT_DIRS
                                   if os.path.exists(os.path.join(d, name))), px)


def card(src, out, scale=2.0):
    """A small photo shown as a framed print over its own blurred enlargement."""
    ph = Image.open(src).convert("RGB")
    bg = ph.resize((W, int(W * ph.height / ph.width)), Image.LANCZOS)
    bg = bg.crop((0, (bg.height - H) // 2, W, (bg.height - H) // 2 + H)) if bg.height >= H else bg.resize((W, H))
    bg = Image.blend(bg.filter(ImageFilter.GaussianBlur(28)), Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
    fg = ph.resize((int(ph.width * scale), int(ph.height * scale)), Image.LANCZOS)
    x, y = (W - fg.width) // 2, (H - fg.height) // 2
    ImageDraw.Draw(bg).rectangle([x - 6, y - 6, x + fg.width + 6, y + fg.height + 6], fill=(235, 235, 235))
    bg.paste(fg, (x, y))
    bg.save(out, quality=95)


def crop(src, out, box):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))).save(out, quality=95)


def items(b, T):
    out = []
    for i, (a, f, credit, tag) in enumerate(b["pics"]):
        nxt = b["pics"][i + 1][0] if i + 1 < len(b["pics"]) else T
        it = {"path": os.path.normpath(P + f), "credit": credit or "", "seconds": nxt - a}
        if tag:
            it["tag"] = tag
        out.append(it)
    return out


def note(img, t, text, next_at):
    """A small pill, top left: what comes next, and how soon."""
    a = min(1.0, max(0.0, (t - 1.2) / 0.5)) * min(1.0, max(0.0, (next_at - t) / 0.4))
    if a <= 0:
        return img
    d = ImageDraw.Draw(img, "RGBA")
    f, fc = _font("Inter-Bold.otf", 17), _font("Inter-Medium.otf", 17)
    left = max(0, int(next_at - t + 0.999))
    clock = f"{left // 60}:{left % 60:02d}"
    tw, cw = f.getlength(text), fc.getlength(clock)
    x, y = 40, 34
    d.rounded_rectangle([x, y, x + 30 + tw + 16 + cw + 14, y + 34], radius=8, fill=(0, 0, 0, int(165 * a)))
    on = 0.55 + 0.45 * (0.5 + 0.5 * np.cos(t * 2 * np.pi / 1.6))
    d.ellipse([x + 12, y + 12, x + 22, y + 22], fill=RED + (int(255 * a * on),))
    d.text((x + 30, y + 17), text, font=f, fill=(255, 255, 255, int(255 * a)), anchor="lm")
    d.text((x + 30 + tw + 16, y + 17), clock, font=fc, fill=(190, 198, 210, int(255 * a)), anchor="lm")
    return img


def frames(a, n):
    """n frames of the source from frame a, as images."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-vf",
                          f"select=between(n\\,{a}\\,{a + n - 1})", "-vsync", "0",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    sz = W * H * 3
    return [Image.frombytes("RGB", (W, H), raw[i * sz:(i + 1) * sz]) for i in range(len(raw) // sz)]


def render(b, wm):
    n, s = b["n"], b["start"]
    T = n / FPS
    fn = reel(items(b, T), T)
    before = frames(s, FADE) if b["in"] == "live" else frames(s - 1, 1) * FADE
    after = frames(s + n, 1) * FADE
    seg = f"{D}/al3/seg_{b['name']}.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", seg], stdin=subprocess.PIPE)
    for k in range(n):
        t = k / FPS
        img = fn(t, T).convert("RGB")
        if b.get("note"):
            img = note(img, t, b["note"], T - FADE / FPS)
        img.paste(wm, (W - wm.width - 22, 18), wm)
        if k < FADE:
            img = Image.blend(before[k], img, (k + 1) / (FADE + 1))
        elif k >= n - FADE:
            img = Image.blend(img, after[k - (n - FADE)], (k - (n - FADE) + 1) / (FADE + 1))
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    return seg


def piece(a, b, out):
    """Source frames a..b-1 re-encoded on their own (one decode, little memory)."""
    vf = f"trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-an", "-vf", vf, "-frames:v", str(b - a),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", out], check=True)
    return out


def main():
    crop(D + "/aloha_short/photo.jpg", P + "ntsb_left_open.jpg", (0.18, 0.12, 0.82, 0.78))
    card(P + "c_aftermath_faa.jpg", P + "faa_aftermath_card.jpg")
    wm = Image.open(watermark(D + "/al3/wm.png")).convert("RGBA")
    parts, at = [], 0
    for b in BLOCKS:
        if b["name"] == "history" and os.path.exists(D + "/al3/seg.mp4"):
            seg = D + "/al3/seg.mp4"                     # rendered already, unchanged
        else:
            seg = render(b, wm)
        parts.append(piece(at, b["start"], f"{D}/al3/piece_{len(parts)}.mp4"))
        parts.append(seg)
        at = b["start"] + b["n"]
    parts.append(piece(at, TOTAL, f"{D}/al3/piece_{len(parts)}.mp4"))
    ins = sum((["-i", p] for p in parts), [])
    chain = "".join(f"[{i}:v]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-i", SRC, "-filter_complex", chain,
                    "-map", "[v]", "-map", f"{len(parts)}:a", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", OUT], check=True)
    print(OUT)


if __name__ == "__main__":
    main()
