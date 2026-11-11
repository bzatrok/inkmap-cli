"""The map's names: cities and towns, the two biggest rivers along their straightest stretch,
then the other places, biggest kind first. Space goes first come, first served; a name that
would cover another, or run into the edge, is left out.

Ported from gallery/maps/annotate.py (ranked_places, rivers, river_label,
straight_stretches) and the mock-up's sizes.
"""

import math

from PIL import Image, ImageDraw

from inkmap.domain.frame import Frame
from inkmap.render.geometry import centre
from inkmap.render.inks import BURN, PAPER, PARCHMENT, REGION_INK, RIVER_INK, SEPIA
from inkmap.render.text import Box, label_font, placed, stamp, text_mask, title_font

PLACE_RANK = {"city": 0, "town": 1, "village": 2, "suburb": 3, "quarter": 4, "neighbourhood": 5,
              "hamlet": 6, "farm": 7, "locality": 8}
BIG = {"city", "town", "suburb"}  # these get the larger type, as on the mock-up
RIBBON = {"city", "town", "village", "hamlet"}  # settlements: capitals on a parchment ribbon
FIRST = RIBBON  # named before the rivers, so a river cannot push them off
MAX_PLACES = 60


class Labels:
    """Names on the map canvas, with the boxes they already take."""

    def __init__(self, canvas: Image.Image, edge_px: float, gap_px: float):
        self.canvas = canvas
        self.edge = edge_px
        self.gap = gap_px
        self.taken: list[Box] = []
        self.names: set[str] = set()  # a name goes on the map once, whatever else carries it
        self.placed: dict[str, Box] = {}  # name -> the box it got, for a viewer that marks it

    def put(self, text: str, x: float, y: float, fnt, fill: tuple, halo_px: int,
            spacing_px: float = 0, angle: float = 0) -> bool:
        if text in self.names:
            return False
        if self.put_mask(text_mask(text, fnt, spacing_px, angle), x, y, fill, halo_px):
            self.names.add(text)
            self.placed[text] = self.taken[-1]
            return True
        return False

    def put_mask(self, mask: Image.Image, x: float, y: float, fill: tuple, halo_px: int) -> bool:
        """Any picture, text or glyph, centred on x, y, if it covers nothing placed before."""
        if (spot := self._claim(placed(mask, x, y, halo_px))) is None:
            return False
        stamp(self.canvas, mask, *spot, fill, halo_px, PARCHMENT)
        return True

    def avoid(self, line: list[tuple[float, float]], width_px: float) -> None:
        """A drawn line (a hike's track) that names must keep clear of, as boxes along it."""
        half = width_px / 2
        for (x0, y0), (x1, y1) in zip(line, line[1:], strict=False):
            n = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / width_px))
            for i in range(n + 1):
                x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
                self.taken.append((x - half, y - half, x + half, y + half))

    def _claim(self, box: Box) -> tuple[float, float] | None:
        """The box where asked, or nudged to the side that is free; None when none is. The
        nudged centre comes back so the picture is drawn where the box was taken."""
        w, h = box[2] - box[0], box[3] - box[1]
        side = (w + h) / 2  # beside the point, with half a line's height of air
        for dx, dy in ((0, 0), (0, -h), (0, h), (-side, 0), (side, 0), (-side, -h), (side, -h),
                       (-side, h), (side, h), (0, -2 * h), (0, 2 * h)):
            moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
            if self._inside(moved) and self._free(moved):
                self.taken.append(moved)
                return (moved[0] + moved[2]) / 2, (moved[1] + moved[3]) / 2
        return None

    def put_ribbon(self, text: str, x: float, y: float, fnt, fill: tuple, pad_px: int,
                   spacing_px: float = 0) -> bool:
        """The name on a notched parchment ribbon, outlined in ink, with a thin shadow."""
        mask = text_mask(text, fnt, spacing_px)
        w, h = mask.width + 4 * pad_px, mask.height + 2 * pad_px
        if text in self.names:
            return False
        if (spot := self._claim(placed(Image.new("L", (w, h)), x, y))) is None:
            return False
        self.names.add(text)
        self.placed[text] = self.taken[-1]
        x, y = spot
        left, top, n = round(x - w / 2), round(y - h / 2), pad_px
        pts = [(left, top), (left + w, top), (left + w - n, top + h / 2), (left + w, top + h),
               (left, top + h), (left + n, top + h / 2)]
        pen = ImageDraw.Draw(self.canvas)
        off = max(1, pad_px // 3)
        pen.polygon([(px + off, py + off) for px, py in pts], fill=BURN)
        pen.polygon(pts, fill=PAPER)
        pen.line([*pts, pts[0]], fill=SEPIA, width=max(1, pad_px // 4), joint="curve")
        stamp(self.canvas, mask, x, y, fill)
        return True

    def _inside(self, box: Box) -> bool:
        w, h = self.canvas.size
        return (box[0] > self.edge and box[1] > self.edge and box[2] < w - self.edge
                and box[3] < h - self.edge)

    def _free(self, box: Box) -> bool:
        g = self.gap
        return not any(box[0] - g < t[2] and box[2] + g > t[0] and box[1] - g < t[3]
                       and box[3] + g > t[1] for t in self.taken)


def annotate(labels: Labels, frame: Frame, elements: list[dict], px_per_mm: float,
             scale: float, regions: list[tuple[str, float, float, float]] = ()) -> None:
    """Cities and towns first, then the region names (hills and ranges from OSM, plus the
    region file's own), then rivers, then the other places. Type sizes are the mock-up's at
    this print's scale."""
    def size(mm: float) -> int:
        return round(mm * scale * px_per_mm)

    big, small = label_font(size(4.6)), label_font(size(3.4))

    ribbon_big, ribbon_small = title_font(size(4.4)), title_font(size(3.6))

    def put_places(places):
        for name, el in places:
            x, y = frame.project(el["lat"], el["lon"])
            kind = el["tags"]["place"]
            if kind in RIBBON:
                fnt = ribbon_big if kind in BIG or kind == "village" else ribbon_small
                labels.put_ribbon(name.upper(), x, y, fnt, SEPIA, size(0.8), size(0.3))
            else:
                labels.put(name, x, y, big if kind in BIG else small, SEPIA, size(0.6))

    places = ranked_places(frame, elements)
    put_places(p for p in places if p[1]["tags"]["place"] in FIRST)
    region_type = title_font(size(5.2))
    for name, lat, lon, angle in [*regions, *ranges(elements)]:
        x, y = frame.project(lat, lon)
        labels.put(name.upper(), x, y, region_type, REGION_INK, size(1.0), size(2.2), angle)
    river_type = title_font(size(3.4))
    for river, line in rivers(frame, elements, labels.edge):
        river_label(labels, river, line, river_type, size(1.4), size(0.4))
    put_places(p for p in places if p[1]["tags"]["place"] not in FIRST)


def ranked_places(frame: Frame, elements: list[dict]) -> list[tuple[str, dict]]:
    """Named place nodes, biggest kind first, then nearest the centre, names cleaned up:
    "Burgemeesterswijk/Hoogkamp" is "Hoogkamp", and a name is used once."""
    centre = frame.project(frame.lat, frame.lon)
    nodes = [el for el in elements if el["type"] == "node"
             and el.get("tags", {}).get("place") in PLACE_RANK and el["tags"].get("name")]

    def rank(el):
        return PLACE_RANK[el["tags"]["place"]], math.dist(frame.project(el["lat"], el["lon"]),
                                                          centre)

    seen, found = set(), []
    for el in sorted(nodes, key=rank):
        name = el["tags"]["name"].split("/")[-1].replace("-West", "").replace("-Oost", "")
        name = name.strip()
        if name and name not in seen:
            seen.add(name)
            found.append((name, el))
    return found[:MAX_PLACES]


def ranges(elements: list[dict]) -> list[tuple[str, float, float, float]]:
    """Named hill ranges from OSM, at their centre, level."""
    out = []
    for el in elements:
        tags = el.get("tags", {})
        if tags.get("natural") == "mountain_range" and tags.get("name"):
            lat, lon = centre(el)
            out.append((tags["name"], lat, lon, 0.0))
    return out


def rivers(frame: Frame, elements: list[dict], inset: float) -> list[tuple[str, list]]:
    """The two named rivers or canals with the most points inside the frame, with those
    points."""
    lines: dict[str, list] = {}
    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "way" and tags.get("name") and tags.get("waterway") in ("river", "canal"):
            pts = (frame.project(p["lat"], p["lon"]) for p in el.get("geometry", []))
            inside = [q for q in pts if inset < q[0] < frame.width - inset
                      and inset < q[1] < frame.height - inset]
            lines.setdefault(tags["name"], []).extend(inside)
    ranked = sorted(lines.items(), key=lambda kv: -len(kv[1]))[:2]
    return [(name.upper(), line) for name, line in ranked if len(line) >= 8]


def river_label(labels: Labels, text: str, line: list, fnt, spacing_px: float,
                halo_px: int) -> bool:
    """The name along the straightest free stretch of the river, never upside down."""
    for (x0, y0), (x1, y1) in straight_stretches(line, min(6, len(line) - 1)):
        angle = -math.degrees(math.atan2(y1 - y0, x1 - x0))
        angle = angle + 180 if angle < -90 else angle - 180 if angle > 90 else angle
        if labels.put(text, (x0 + x1) / 2, (y0 + y1) / 2, fnt, RIVER_INK, halo_px,
                      spacing_px, angle):
            return True
    return False


def straight_stretches(pts: list, span: int, tries: int = 8) -> list[tuple]:
    """Windows of `span` points, straightest first: their ends lie closest to the path length
    between them."""
    def straightness(i):
        chord = math.dist(pts[i], pts[i + span])
        path = sum(math.dist(a, b) for a, b in zip(pts[i:i + span], pts[i + 1:i + span + 1],
                                                   strict=True))
        return chord / path if path else 0
    order = sorted(range(len(pts) - span), key=straightness, reverse=True)
    return [(pts[i], pts[i + span]) for i in order[:tries]]
