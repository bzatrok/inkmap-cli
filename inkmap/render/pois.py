"""Points of interest as small ink pictures: a castle, a ruin, a peak, a viewpoint, a tower,
a monument, an inn. Each is drawn as a mask at 3x and shrunk, then placed with a parchment
halo where it covers no name and no other picture."""

from PIL import Image, ImageDraw

from inkmap.domain import poi
from inkmap.domain.frame import Frame
from inkmap.render.geometry import centre
from inkmap.render.inks import SEPIA
from inkmap.render.labels import Labels

GLYPH_PX = 14
SS = 3


NAMED = {"castle", "viewpoint", "ruins", "tower", "inn", "peak"}
NAMED_COARSE = {"castle", "viewpoint", "peak"}


def draw_pois(labels: Labels, frame: Frame, elements: list[dict], name_font,
              names_for: set[str]) -> int:
    """Draws every point of interest that finds room, and the names of the kinds in
    `names_for` beside their glyph; returns how many glyphs were drawn."""
    drawn = 0
    for el in elements:
        tags = el.get("tags", {})
        kind = poi.kind(tags)
        if kind in (None, "church"):  # churches are stamped with the houses
            continue
        x, y = frame.project(*centre(el))
        if not labels.put_mask(glyph(kind), x, y, SEPIA, halo_px=2):
            continue
        drawn += 1
        if kind in names_for and tags.get("name"):
            width = name_font.getlength(tags["name"])
            # past the glyph's halo and the label gap, or the name is refused as a collision
            labels.put(tags["name"], x + GLYPH_PX / 2 + labels.gap + 6 + width / 2, y, name_font,
                       SEPIA, 2)
    return drawn


def glyph(kind: str) -> Image.Image:
    s = GLYPH_PX * SS
    mask = Image.new("L", (s, s), 0)
    pen = ImageDraw.Draw(mask)
    DRAW[kind](pen, s)
    return mask.resize((GLYPH_PX, GLYPH_PX), Image.BOX)


def _castle(pen, s):
    w = max(2, s // 10)
    pen.rectangle([s * 0.15, s * 0.4, s * 0.85, s * 0.95], outline=255, width=w)
    for i in range(3):
        x0 = s * (0.15 + i * 0.25)
        pen.rectangle([x0, s * 0.22, x0 + s * 0.2, s * 0.4], fill=255)
    pen.rectangle([s * 0.42, s * 0.65, s * 0.58, s * 0.95], fill=255)


def _ruins(pen, s):
    w = max(2, s // 10)
    wall = [(0.15, 0.95), (0.15, 0.35), (0.35, 0.35), (0.35, 0.55), (0.55, 0.55), (0.55, 0.7),
            (0.85, 0.7), (0.85, 0.95)]
    pen.line([(s * x, s * y) for x, y in wall], fill=255, width=w, joint="curve")
    pen.line([(s * 0.1, s * 0.95), (s * 0.9, s * 0.95)], fill=255, width=w)


def _peak(pen, s):
    w = max(2, s // 10)
    pen.polygon([(s * 0.5, s * 0.15), (s * 0.92, s * 0.9), (s * 0.08, s * 0.9)], outline=255,
                width=w)
    pen.polygon([(s * 0.5, s * 0.15), (s * 0.66, s * 0.45), (s * 0.34, s * 0.45)], fill=255)


def _viewpoint(pen, s):
    w = max(2, s // 10)
    pen.pieslice([s * 0.2, s * 0.45, s * 0.8, s * 1.05], 180, 360, fill=255)
    for dx in (-0.3, 0, 0.3):
        pen.line([(s * 0.5, s * 0.6), (s * (0.5 + dx), s * 0.1 + abs(dx) * s * 0.4)], fill=255,
                 width=w)


def _tower(pen, s):
    w = max(2, s // 10)
    pen.rectangle([s * 0.35, s * 0.35, s * 0.65, s * 0.95], outline=255, width=w)
    pen.polygon([(s * 0.3, s * 0.35), (s * 0.5, s * 0.08), (s * 0.7, s * 0.35)], fill=255)
    pen.rectangle([s * 0.45, s * 0.5, s * 0.55, s * 0.65], fill=255)


def _monument(pen, s):
    pen.polygon([(s * 0.42, s * 0.12), (s * 0.58, s * 0.12), (s * 0.64, s * 0.75),
                 (s * 0.36, s * 0.75)], fill=255)
    pen.rectangle([s * 0.25, s * 0.78, s * 0.75, s * 0.92], fill=255)


def _inn(pen, s):
    w = max(2, s // 10)
    pen.rectangle([s * 0.2, s * 0.25, s * 0.65, s * 0.9], outline=255, width=w)
    pen.arc([s * 0.55, s * 0.4, s * 0.9, s * 0.75], 270, 90, fill=255, width=w)
    pen.rectangle([s * 0.2, s * 0.25, s * 0.65, s * 0.4], fill=255)


def _spring(pen, s):
    w = max(2, s // 10)
    pen.ellipse([s * 0.3, s * 0.55, s * 0.7, s * 0.9], outline=255, width=w)
    pen.arc([s * 0.25, s * 0.15, s * 0.55, s * 0.55], 200, 340, fill=255, width=w)
    pen.arc([s * 0.45, s * 0.15, s * 0.75, s * 0.55], 200, 340, fill=255, width=w)


def _cross(pen, s):
    w = max(2, s // 9)
    pen.line([(s * 0.5, s * 0.1), (s * 0.5, s * 0.8)], fill=255, width=w)
    pen.line([(s * 0.3, s * 0.32), (s * 0.7, s * 0.32)], fill=255, width=w)
    pen.pieslice([s * 0.2, s * 0.7, s * 0.8, s * 1.0], 180, 360, fill=255)


def _well(pen, s):
    w = max(2, s // 10)
    pen.ellipse([s * 0.2, s * 0.6, s * 0.8, s * 0.95], outline=255, width=w)
    pen.line([(s * 0.25, s * 0.72), (s * 0.25, s * 0.35)], fill=255, width=w)
    pen.line([(s * 0.75, s * 0.72), (s * 0.75, s * 0.35)], fill=255, width=w)
    pen.polygon([(s * 0.15, s * 0.35), (s * 0.5, s * 0.08), (s * 0.85, s * 0.35)], fill=255)


def _hide(pen, s):
    w = max(2, s // 10)
    pen.rectangle([s * 0.25, s * 0.2, s * 0.75, s * 0.55], outline=255, width=w)
    pen.polygon([(s * 0.2, s * 0.2), (s * 0.5, s * 0.05), (s * 0.8, s * 0.2)], fill=255)
    pen.line([(s * 0.3, s * 0.55), (s * 0.2, s * 0.95)], fill=255, width=w)
    pen.line([(s * 0.7, s * 0.55), (s * 0.8, s * 0.95)], fill=255, width=w)
    pen.line([(s * 0.5, s * 0.55), (s * 0.5, s * 0.95)], fill=255, width=w)


def _shelter(pen, s):
    w = max(2, s // 10)
    pen.polygon([(s * 0.08, s * 0.45), (s * 0.5, s * 0.1), (s * 0.92, s * 0.45)], fill=255)
    pen.line([(s * 0.2, s * 0.45), (s * 0.2, s * 0.92)], fill=255, width=w)
    pen.line([(s * 0.8, s * 0.45), (s * 0.8, s * 0.92)], fill=255, width=w)


DRAW = {"castle": _castle, "ruins": _ruins, "peak": _peak, "viewpoint": _viewpoint,
        "tower": _tower, "monument": _monument, "inn": _inn, "spring": _spring, "cross": _cross,
        "well": _well, "hide": _hide, "shelter": _shelter}
