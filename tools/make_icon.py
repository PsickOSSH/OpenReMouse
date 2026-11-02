"""Generates assets/icon.ico (+ icon_preview.png): a mouse cursor with a red record dot.

Needs Pillow (build-time only):  python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "assets"
S = 1024                      # draw big, downscale for smooth edges


def vertical_gradient(top, bottom):
    img = Image.new("RGB", (S, S))
    d = ImageDraw.Draw(img)
    for y in range(S):
        t = y / (S - 1)
        d.line([(0, y), (S, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def build() -> Image.Image:
    bg = vertical_gradient((52, 120, 246), (22, 48, 130)).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), radius=220, fill=255)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(bg, (0, 0), mask)

    # soft shadow under the cursor
    pts = [(0.27, 0.15), (0.27, 0.76), (0.43, 0.61), (0.53, 0.84), (0.63, 0.80), (0.53, 0.58), (0.74, 0.58)]
    poly = [(x * S, y * S) for x, y in pts]
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 16, y + 24) for x, y in poly], fill=(0, 0, 0, 120))
    icon = Image.alpha_composite(icon, shadow.filter(ImageFilter.GaussianBlur(18)))

    d = ImageDraw.Draw(icon)
    d.polygon(poly, fill=(255, 255, 255, 255), outline=(14, 28, 70, 255), width=26)
    d.line(poly + [poly[0]], fill=(14, 28, 70, 255), width=26, joint="curve")
    d.polygon(poly, fill=(255, 255, 255, 255))

    # record dot, bottom-right
    cx, cy, r = 0.73 * S, 0.75 * S, 0.17 * S
    d.ellipse((cx - r - 22, cy - r - 22, cx + r + 22, cy + r + 22), fill=(255, 255, 255, 255))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(230, 40, 50, 255))
    d.ellipse((cx - r * 0.55, cy - r * 0.62, cx - r * 0.05, cy - r * 0.12), fill=(255, 120, 125, 200))
    return icon


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    big = build()
    sizes = [256, 128, 64, 48, 32, 24, 16]
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.ico", sizes=[(s, s) for s in sizes])
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon_preview.png")
    print("wrote", OUT / "icon.ico")
