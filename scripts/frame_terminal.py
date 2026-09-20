"""Build the Screen.studio-style chrome the terminal recording is composited into.

Emits two PNGs that ffmpeg then uses:

  backdrop.png  gradient background + drop shadow + window body + title bar
  mask.png      alpha mask rounding the terminal's bottom corners

Run with Pillow available, e.g.:

    uv run --with pillow python scripts/frame_terminal.py --width 1560 --height 782

Nothing here touches the recording itself; the terminal frames stay untouched pixels.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TITLE_BAR = 44
RADIUS = 16
DEFAULT_PADDING = 40

# Diagonal gradient. Chosen to sit behind a near-black terminal without competing with it.
GRADIENT_FROM = (79, 70, 229)  # indigo
GRADIENT_TO = (168, 85, 247)  # violet

TITLE_BAR_FILL = (32, 38, 48)
TRAFFIC_LIGHTS = ((255, 95, 87), (254, 188, 46), (40, 200, 64))

SHADOW_BLUR = 34
SHADOW_OFFSET = 20
SHADOW_ALPHA = 120

FONT_NAMES = ("JetBrainsMono[wght].ttf", "JetBrainsMono-Regular.ttf", "Menlo.ttc", "Monaco.ttf")
FONT_DIRS = (
    Path.home() / "Library/Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path.home() / ".local/share/fonts",
    Path("/usr/share/fonts/truetype"),
)


def diagonal_gradient(size: tuple[int, int]) -> Image.Image:
    """A smooth corner-to-corner gradient, built small and scaled up for free blending."""
    width, height = size
    small = Image.new("RGB", (64, 64))
    pixels = small.load()
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126.0
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(GRADIENT_FROM, GRADIENT_TO))
    return small.resize((width, height), Image.BICUBIC)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """First monospace font we can actually open, or Pillow's bitmap default."""
    for name in FONT_NAMES:
        for directory in FONT_DIRS:
            candidate = directory / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except OSError:
                    continue
    return ImageFont.load_default()


def rounded_mask(size: tuple[int, int], radius: int, corners: tuple[bool, bool, bool, bool]):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255, corners=corners
    )
    return mask


def build(term_width: int, term_height: int, title: str, out_dir: Path, padding: int) -> None:
    window_w, window_h = term_width, term_height + TITLE_BAR

    # Canvas is the window plus padding, rounded up to even dimensions so H.264 accepts it.
    canvas = (
        (window_w + 2 * padding + 1) // 2 * 2,
        (window_h + 2 * padding + 1) // 2 * 2,
    )
    origin_x = (canvas[0] - window_w) // 2
    origin_y = (canvas[1] - window_h) // 2

    backdrop = diagonal_gradient(canvas).convert("RGBA")

    # Drop shadow: the window silhouette, blurred and pushed down.
    shadow = Image.new("RGBA", canvas, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (
            origin_x,
            origin_y + SHADOW_OFFSET,
            origin_x + window_w,
            origin_y + window_h + SHADOW_OFFSET,
        ),
        radius=RADIUS,
        fill=(0, 0, 0, SHADOW_ALPHA),
    )
    backdrop = Image.alpha_composite(backdrop, shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))

    # Window body. The terminal video covers everything below the title bar, so only the
    # bar itself needs painting, but fill the whole shape so no gradient leaks at the edges.
    window = Image.new("RGBA", canvas, (0, 0, 0, 0))
    draw = ImageDraw.Draw(window)
    draw.rounded_rectangle(
        (origin_x, origin_y, origin_x + window_w, origin_y + window_h),
        radius=RADIUS,
        fill=TITLE_BAR_FILL,
    )
    backdrop = Image.alpha_composite(backdrop, window)

    draw = ImageDraw.Draw(backdrop)
    centre_y = origin_y + TITLE_BAR // 2
    for index, color in enumerate(TRAFFIC_LIGHTS):
        cx = origin_x + 26 + index * 22
        draw.ellipse((cx - 6, centre_y - 6, cx + 6, centre_y + 6), fill=color)

    font = load_font(16)
    text_width = draw.textlength(title, font=font)
    draw.text(
        (origin_x + (window_w - text_width) / 2, centre_y - 9),
        title,
        font=font,
        fill=(150, 158, 170),
    )

    backdrop.convert("RGB").save(out_dir / "backdrop.png")

    # Terminal sits flush under the bar, so only its bottom corners are rounded.
    rounded_mask((term_width, term_height), RADIUS, corners=(False, False, True, True)).save(
        out_dir / "mask.png"
    )

    # ffmpeg needs both of these to place the recording; print them rather than duplicate
    # the geometry maths in the shell.
    print(f"canvas={canvas[0]}x{canvas[1]} overlay={origin_x}:{origin_y + TITLE_BAR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, required=True, help="terminal recording width")
    parser.add_argument("--height", type=int, required=True, help="terminal recording height")
    parser.add_argument("--title", default="jevgrep", help="title bar caption")
    parser.add_argument("--out", type=Path, default=Path("."), help="directory for the PNGs")
    parser.add_argument(
        "--padding",
        type=int,
        default=DEFAULT_PADDING,
        help=f"pixels of backdrop around the window (default {DEFAULT_PADDING})",
    )
    args = parser.parse_args()

    if args.padding < 0:
        parser.error("--padding cannot be negative")

    args.out.mkdir(parents=True, exist_ok=True)
    build(args.width, args.height, args.title, args.out, args.padding)


if __name__ == "__main__":
    main()
