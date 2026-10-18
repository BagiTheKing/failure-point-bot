"""
The channel's watermark (owner, 2026-10-18: "we need a watermark so our work
won't be stolen"): a small crack mark and FAILURE POINT, white at partial
opacity, in the top-right corner of every frame of the episode. Burned into
the picture, so a re-upload carries it.
"""

from PIL import Image, ImageDraw

from kits.blueprint import RED, font

NAME = "FAILURE POINT"
OPACITY = 0.62


def watermark(path, scale=1):
    """Writes the watermark as a transparent PNG (overlaid by ffmpeg)."""
    fnt = font("Inter-Bold.otf", 17)               # font() scales by SS already
    tw = int(fnt.getlength(NAME))
    h = int(30 * scale * 2)
    img = Image.new("RGBA", (tw + 40 * 2, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    a = int(255 * OPACITY)
    # the mark: a beam with a crack through it
    d.line([(4, h * 0.70), (26, h * 0.70)], fill=(255, 255, 255, a), width=5)
    d.line([(14, h * 0.18), (19, h * 0.42), (12, h * 0.55), (17, h * 0.84)],
           fill=RED + (a,), width=4)
    d.text((40, h / 2), NAME, font=fnt, fill=(255, 255, 255, a), anchor="lm")
    img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)   # back from 2x
    img.save(path)
    return path
