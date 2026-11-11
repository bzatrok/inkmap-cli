"""The small things a street-scale map is made of: fences dotted round yards, orchards in rows,
hedgerows and single trees, furrows across the fields, tufts on the meadows. All of it comes
from OpenStreetMap tags; nothing is invented where the data says nothing.
"""

import math

import numpy as np
from PIL import Image, ImageDraw

from inkmap.domain.frame import Frame
from inkmap.render.geometry import area_rings
from inkmap.render.inks import SEPIA
from inkmap.render.stamps import along, spots, tree

SS = 2
FENCED_USES = {"residential", "farmyard", "allotments", "orchard", "garden", "cemetery"}
BARRIERS = {"fence", "wall", "hedge", "retaining_wall"}
FENCE_STEP_M = 2.5
ORCHARD_M = 7  # tree spacing
TREE_ROW_M = 6
FURROW_M = 5
TUFT_M = 18
FURROW_INK = (150, 130, 96)
TUFT_INK = (110, 96, 66)
_rng = np.random.default_rng(23)


def dashes(points: list[tuple[float, float]], on: float, off: float) -> list[list]:
    """Pieces of the polyline, `on` long with `off` between them."""
    out: list[list] = []
    cur, drawing, want = [points[0]], True, on
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        seg, t = math.hypot(x1 - x0, y1 - y0), 0.0
        while seg - t > 1e-9:
            take = min(want, seg - t)
            t, want = t + take, want - take
            p = (x0 + (x1 - x0) * t / seg, y0 + (y1 - y0) * t / seg)
            if drawing:
                cur.append(p)
            if want <= 1e-9:
                if drawing and len(cur) > 1:
                    out.append(cur)
                drawing, want, cur = not drawing, (off if drawing else on), [p]
    if drawing and len(cur) > 1:
        out.append(cur)
    return out


def axis(ring: list[tuple[float, float]]) -> float:
    """The direction of the ring's longest edge, in radians."""
    (x0, y0), (x1, y1) = max(zip(ring, ring[1:] + ring[:1], strict=True),
                             key=lambda e: math.dist(*e))
    return math.atan2(y1 - y0, x1 - x0)


def fences(canvas: Image.Image, frame: Frame, elements: list[dict]) -> None:
    """Dotted ink along fences, walls and hedges, and round yards, gardens and orchards."""
    mask = Image.new("L", (canvas.width * SS, canvas.height * SS), 0)
    pen = ImageDraw.Draw(mask)
    step, r = FENCE_STEP_M / frame.metres_per_px * SS, 0.6 * SS
    for el in elements:
        tags = el.get("tags", {})
        lines = []
        if tags.get("barrier") in BARRIERS and el["type"] == "way":
            lines = [[frame.project(p["lat"], p["lon"], SS) for p in el.get("geometry", [])]]
        elif tags.get("landuse") in FENCED_USES:
            outers, _ = area_rings(el)
            lines = [[frame.project(a, b, SS) for a, b in ring] for ring in outers]
        for line in lines:
            for x, y, _ in along(line, step, _rng):
                pen.ellipse([x - r, y - r, x + r, y + r], fill=255)
    canvas.paste(SEPIA, (0, 0), mask.resize(canvas.size, Image.BOX).point(lambda v: v * 0.85))


def planted(canvas: Image.Image, frame: Frame, elements: list[dict]) -> None:
    """Orchards as rows of small trees, hedgerows as a line of them, and every mapped tree."""
    pen = ImageDraw.Draw(canvas)
    mpp = frame.metres_per_px
    for el in elements:
        tags = el.get("tags", {})
        if tags.get("landuse") == "orchard":
            for ring in area_rings(el)[0]:
                _orchard(pen, [frame.project(a, b) for a, b in ring], ORCHARD_M / mpp)
        elif tags.get("natural") == "tree_row" and el["type"] == "way":
            pts = [frame.project(p["lat"], p["lon"]) for p in el.get("geometry", [])]
            for x, y, _ in along(pts, TREE_ROW_M / mpp, _rng):
                tree(pen, x, y, 7 / mpp)
        elif tags.get("natural") == "tree" and el["type"] == "node":
            tree(pen, *frame.project(el["lat"], el["lon"]), 10 / mpp)


def _orchard(pen: ImageDraw.ImageDraw, ring: list[tuple[float, float]], step: float) -> None:
    """Trees on a grid turned to the plot's long side, inside the plot."""
    xs, ys = [x for x, _ in ring], [y for _, y in ring]
    x0, y0 = math.floor(min(xs)), math.floor(min(ys))
    x1, y1 = math.ceil(max(xs)), math.ceil(max(ys))
    inside = Image.new("1", (x1 - x0 + 1, y1 - y0 + 1), 0)
    ImageDraw.Draw(inside).polygon([(x - x0, y - y0) for x, y in ring], fill=1)
    a, cx, cy = axis(ring), (x0 + x1) / 2, (y0 + y1) / 2
    u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    n = int(math.hypot(x1 - x0, y1 - y0) / step) + 1
    rows = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = cx + (u[0] * i + v[0] * j) * step, cy + (u[1] * i + v[1] * j) * step
            if 0 <= x - x0 < inside.width and 0 <= y - y0 < inside.height \
                    and inside.getpixel((int(x - x0), int(y - y0))):
                rows.append((x, y))
    for x, y in sorted(rows, key=lambda p: p[1]):
        tree(pen, x, y, step * 0.7)


def fields(canvas: Image.Image, frame: Frame, elements: list[dict]) -> None:
    """Furrows along the farmland's long side; tufts scattered over the meadows."""
    mpp = frame.metres_per_px
    furrows = Image.new("L", (canvas.width * SS, canvas.height * SS), 0)
    meadow = Image.new("L", canvas.size, 0)
    for el in elements:
        use = el.get("tags", {}).get("landuse")
        if use == "farmland":
            for ring in area_rings(el)[0]:
                _furrows(furrows, [frame.project(a, b, SS) for a, b in ring], FURROW_M / mpp * SS)
        elif use in ("meadow", "grassland"):
            for ring in area_rings(el)[0]:
                ImageDraw.Draw(meadow).polygon([frame.project(a, b) for a, b in ring], fill=255)
    canvas.paste(FURROW_INK, (0, 0), furrows.resize(canvas.size, Image.BOX))
    pen = ImageDraw.Draw(canvas)
    for x, y in spots(meadow, TUFT_M / mpp, _rng):
        _tuft(pen, x, y, max(2.0, 2.5 / mpp))


def _furrows(mask: Image.Image, ring: list[tuple[float, float]], spacing: float) -> None:
    """Parallel lines across one plot, clipped to it, drawn onto the shared mask."""
    xs, ys = [x for x, _ in ring], [y for _, y in ring]
    x0, y0 = math.floor(min(xs)), math.floor(min(ys))
    w, h = math.ceil(max(xs)) - x0 + 1, math.ceil(max(ys)) - y0 + 1
    plot = Image.new("L", (w, h), 0)
    ImageDraw.Draw(plot).polygon([(x - x0, y - y0) for x, y in ring], fill=255)
    lines = Image.new("L", (w, h), 0)
    pen = ImageDraw.Draw(lines)
    a, reach = axis(ring), math.hypot(w, h)
    u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    cx, cy = w / 2, h / 2
    k = -int(reach / spacing) - 1
    while k * spacing < reach:
        ox, oy = cx + v[0] * k * spacing, cy + v[1] * k * spacing
        pen.line([(ox - u[0] * reach, oy - u[1] * reach), (ox + u[0] * reach, oy + u[1] * reach)],
                 fill=255, width=1)
        k += 1
    mask.paste(255, (x0, y0), _both(plot, lines))


def _both(a: Image.Image, b: Image.Image) -> Image.Image:
    return Image.fromarray(np.minimum(np.asarray(a), np.asarray(b)))


def _tuft(pen: ImageDraw.ImageDraw, x: float, y: float, h: float) -> None:
    """Three short grass strokes."""
    for dx, lean in ((-h * 0.7, -0.4), (0, 0), (h * 0.7, 0.4)):
        pen.line([(x + dx, y), (x + dx + lean * h, y - h)], fill=TUFT_INK, width=1)
