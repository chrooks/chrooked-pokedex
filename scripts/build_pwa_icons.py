"""Render the PWA icons (#122) from the same pokeball the favicon draws.

Pillow has no SVG rasterizer, so the mark is redrawn here: a tilted ball on the
light paper tone, red band over black band, white button. Output goes to
frontend/public/, which Vite copies into dist/ verbatim.

    .venv/bin/python scripts/build_pwa_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PAPER = (243, 241, 234)
RED = (187, 75, 50)
INK = (23, 21, 18)
TILT_DEGREES = -15
SIZES = {"pwa-192.png": 192, "pwa-512.png": 512, "apple-touch-icon.png": 180}
OUT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public"
# Draw big, then downsample, so the bands and ring stay crisp at 192px.
CANVAS = 1024


def pokeball() -> Image.Image:
    ball = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(ball)
    r = CANVAS * 14 / 32
    c = CANVAS / 2
    d.ellipse((c - r, c - r, c + r, c + r), fill=PAPER)
    # Bands in the favicon's 32-unit grid: red y=11..14, ink y=14..18.
    u = CANVAS / 32
    d.rectangle((0, 11 * u, CANVAS, 14 * u), fill=RED)
    d.rectangle((0, 14 * u, CANVAS, 18 * u), fill=INK)
    # Clip bands to the circle.
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).ellipse((c - r, c - r, c + r, c + r), fill=255)
    ball.putalpha(mask)
    d = ImageDraw.Draw(ball)
    d.ellipse((c - r, c - r, c + r, c + r), outline=INK, width=int(u))
    br = 4 * u
    d.ellipse((c - br, c - br, c + br, c + br), fill=PAPER, outline=INK, width=int(2 * u))
    return ball.rotate(TILT_DEGREES, resample=Image.BICUBIC)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ball = pokeball()
    for name, size in SIZES.items():
        # Android launchers mask icons; the ball sits on an opaque ink plate so a
        # circular mask never shows a hard transparent corner.
        plate = Image.new("RGBA", (CANVAS, CANVAS), INK + (255,))
        plate.alpha_composite(ball)
        plate.resize((size, size), Image.LANCZOS).save(OUT_DIR / name)
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
