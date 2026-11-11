"""Text on the print: fonts, letter spacing, and labels with a halo drawn on a crop.

Every piece of text becomes a small mask first. The halo grows that mask, never a mask the
size of the print: full-canvas halos made the mock-up take 7 minutes on Arnhem.
"""

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).parent / "fonts"

Box = tuple[float, float, float, float]


@lru_cache(maxsize=64)
def _font(name: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), max(size_px, 1))


def title_font(size_px: int) -> ImageFont.FreeTypeFont:
    return _font("Cinzel-700.ttf", size_px)


def label_font(size_px: int) -> ImageFont.FreeTypeFont:
    return _font("LibreBaskerville-400italic.ttf", size_px)


def text_width(text: str, fnt: ImageFont.FreeTypeFont, spacing_px: float = 0) -> float:
    if not spacing_px:
        return fnt.getlength(text)
    return sum(fnt.getlength(c) for c in text) + spacing_px * (len(text) - 1)


def text_mask(text: str, fnt: ImageFont.FreeTypeFont, spacing_px: float = 0,
              angle: float = 0) -> Image.Image:
    """The text as an L mask, cropped to its line height, turned by angle degrees."""
    ascent, descent = fnt.getmetrics()
    mask = Image.new("L", (math.ceil(text_width(text, fnt, spacing_px)) + 2, ascent + descent))
    pen = ImageDraw.Draw(mask)
    if not spacing_px:
        pen.text((1, 0), text, font=fnt, fill=255)
    else:
        x = 1.0
        for c in text:
            pen.text((x, 0), c, font=fnt, fill=255)
            x += fnt.getlength(c) + spacing_px
    if angle:
        mask = mask.rotate(angle, resample=Image.BICUBIC, expand=True)
    return mask


def placed(mask: Image.Image, x: float, y: float, halo_px: int = 0) -> Box:
    """The box the mask (and its halo) covers, centred on x, y."""
    w, h = mask.width + 2 * halo_px, mask.height + 2 * halo_px
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def stamp(canvas: Image.Image, mask: Image.Image, x: float, y: float, fill: tuple,
          halo_px: int = 0, halo_fill: tuple | None = None) -> None:
    """Paste the text centred on x, y, with a halo of halo_fill around it when halo_px > 0."""
    if halo_px:
        padded = Image.new("L", (mask.width + 2 * halo_px, mask.height + 2 * halo_px))
        padded.paste(mask, (halo_px, halo_px))
        halo = padded.filter(ImageFilter.MaxFilter(2 * halo_px + 1))
        left, top = round(x - padded.width / 2), round(y - padded.height / 2)
        canvas.paste(halo_fill, (left, top, left + padded.width, top + padded.height), halo)
        canvas.paste(fill, (left, top, left + padded.width, top + padded.height), padded)
        return
    left, top = round(x - mask.width / 2), round(y - mask.height / 2)
    canvas.paste(fill, (left, top, left + mask.width, top + mask.height), mask)
