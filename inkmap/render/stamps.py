"""Little pictures stamped on the map: trees over the woods, houses over the built-up land.
Drawn procedurally so every one differs a little, and in rows from the top so the lower ones
overlap the upper ones, the way an engraver stacks a forest.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from inkmap.render.inks import PARCHMENT, SEPIA, WOOD
from inkmap.render.noise import value_noise

CANOPY = (166, 164, 112)
CANOPY_SHADE = (104, 102, 62)
ROOF = (128, 92, 58)
WALL = (228, 214, 176)
ROOF_SHADE = (186, 162, 120)  # the slope away from the light, on a street-scale footprint


def spots(mask: Image.Image, spacing: float, rng: np.random.Generator,
          jitter: float = 0.45) -> np.ndarray:
    """(x, y) grid points, jittered, that land inside the mask. Sorted top to bottom."""
    on = np.asarray(mask) > 128
    h, w = on.shape
    ys, xs = np.mgrid[spacing / 2:h:spacing, spacing / 2:w:spacing]
    xs = xs + (np.indices(xs.shape)[0] % 2) * spacing / 2  # hex offset on odd rows
    xs = xs + rng.uniform(-jitter, jitter, xs.shape) * spacing
    ys = ys + rng.uniform(-jitter, jitter, ys.shape) * spacing
    pts = np.column_stack([xs.ravel(), ys.ravel()])
    ix = np.clip(pts[:, 0].round().astype(int), 0, w - 1)
    iy = np.clip(pts[:, 1].round().astype(int), 0, h - 1)
    pts = pts[on[iy, ix]]
    return pts[np.argsort(pts[:, 1])]


def trees(canvas: Image.Image, mask: Image.Image, size_px: float, clump_px: float,
          seed: int = 11) -> None:
    """A forest of three kinds of tree in two sizes, thinned by a slow noise so it clumps."""
    rng = np.random.default_rng(seed)
    pen = ImageDraw.Draw(canvas)
    pts = spots(mask, size_px * 0.95, rng)
    density = value_noise(canvas.width, canvas.height, clump_px, rng)
    at = density[np.clip(pts[:, 1].astype(int), 0, canvas.height - 1),
                 np.clip(pts[:, 0].astype(int), 0, canvas.width - 1)]
    keep = rng.uniform(0, 1, len(pts)) < np.interp(at, [0.25, 0.7], [0.35, 1.0])
    pts = pts[keep]
    sizes = rng.uniform(0.8, 1.3, len(pts)) * size_px
    # Spruces need about 9 px to read as spruces; below that the wood is all broadleaf.
    mix = (0.5, 0.25, 0.25) if size_px >= 9 else (0.7, 0.3, 0.0)
    kinds = rng.choice(3, len(pts), p=mix)
    tints = rng.integers(-7, 8, len(pts))
    for (x, y), d, kind, tint in zip(pts, sizes, kinds, tints, strict=True):
        canopy = (CANOPY[0] + int(tint), CANOPY[1] + int(tint), CANOPY[2] + int(tint) // 2)
        (tree, lumpy_tree, conifer)[kind](pen, x, y, d, canopy)


def tree(pen: ImageDraw.ImageDraw, x: float, y: float, d: float, canopy=CANOPY) -> None:
    r = d / 2
    trunk = max(1, round(d / 6))
    pen.line([(x, y + r * 0.6), (x, y + r + trunk)], fill=SEPIA, width=max(1, round(d / 9)))
    pen.ellipse([x - r + d * 0.12, y - r + d * 0.12, x + r + d * 0.12, y + r * 0.9 + d * 0.12],
                fill=CANOPY_SHADE)
    pen.ellipse([x - r, y - r, x + r, y + r * 0.9], fill=canopy, outline=SEPIA, width=1)
    pen.chord([x - r, y - r, x + r, y + r * 0.9], 20, 120, fill=WOOD)


def lumpy_tree(pen: ImageDraw.ImageDraw, x: float, y: float, d: float, canopy=CANOPY) -> None:
    """Two canopies grown together, the broad old tree of a wood's edge."""
    r = d / 2
    pen.line([(x, y + r * 0.5), (x, y + r + max(1, round(d / 6)))], fill=SEPIA,
             width=max(1, round(d / 8)))
    lumps = ((-r * 0.35, r * 0.1, r * 0.75), (r * 0.35, 0, r * 0.8), (0, -r * 0.3, r * 0.7))
    for ox, oy, rr in lumps:
        pen.ellipse([x + ox - rr + d * 0.1, y + oy - rr + d * 0.1, x + ox + rr + d * 0.1,
                     y + oy + rr + d * 0.1], fill=CANOPY_SHADE)
    for ox, oy, rr in lumps:
        pen.ellipse([x + ox - rr, y + oy - rr, x + ox + rr, y + oy + rr], fill=canopy,
                    outline=SEPIA, width=1)
    pen.chord([x - r * 0.35 - r * 0.75, y + r * 0.1 - r * 0.75, x - r * 0.35 + r * 0.75,
               y + r * 0.1 + r * 0.75], 30, 130, fill=WOOD)


def conifer(pen: ImageDraw.ImageDraw, x: float, y: float, d: float, canopy=CANOPY) -> None:
    """A spruce: a tall triangle, dark on the shadow side."""
    h, w = d * 1.3, d * 0.7
    top, base = y - h * 0.6, y + h * 0.4
    pen.line([(x, base), (x, base + max(1, round(d / 6)))], fill=SEPIA, width=max(1, round(d / 9)))
    pen.polygon([(x, top), (x + w / 2, base), (x - w / 2, base)], fill=canopy, outline=SEPIA)
    pen.polygon([(x, top), (x + w / 2, base), (x, base)], fill=CANOPY_SHADE)
    pen.line([(x, top), (x, base)], fill=SEPIA, width=1)


class Plots:
    """Where a house may stand: on built-up land, one per cell of the spacing grid."""

    def __init__(self, mask: Image.Image, spacing: float):
        self.on = np.asarray(mask) > 128
        self.spacing = spacing
        self.taken: set[tuple[int, int]] = set()

    def claim(self, x: float, y: float) -> bool:
        h, w = self.on.shape
        if not (0 <= x < w and 0 <= y < h) or not self.on[int(y), int(x)]:
            return False
        cell = (int(x / self.spacing), int(y / self.spacing))
        if cell in self.taken:
            return False
        self.taken.add(cell)
        return True


def houses(canvas: Image.Image, mask: Image.Image, roads: list[tuple[list, float]],
           size_px: float, spacing: float, seed: int = 23) -> None:
    """Houses line the roads through built-up land, facing them; the land between gets a
    sparse scatter. `mask` is where a house may stand (built-up land, roads already cut out);
    roads are (points, half width in px)."""
    rng = np.random.default_rng(seed)
    plots = Plots(mask, spacing)
    placed = _roadside(roads, plots, size_px, spacing, rng)
    for x, y in spots(mask, spacing * 2.2, rng, jitter=0.4):
        if plots.claim(x, y):
            placed.append((x, y, rng.uniform(-0.25, 0.25)))
    pen = ImageDraw.Draw(canvas)
    for x, y, angle in sorted(placed, key=lambda h: h[1]):
        house(pen, x, y, size_px * rng.uniform(0.8, 1.15), angle)


def _roadside(roads: list, plots: Plots, size_px: float, spacing: float,
              rng: np.random.Generator) -> list[tuple[float, float, float]]:
    placed = []
    for road, half in roads:
        gap = half + size_px * 0.9  # the house's centre sits this far off the road's centre
        for x, y, angle in along(road, spacing * 1.1, rng):
            for side in (-1, 1):
                if rng.random() > 0.8:
                    continue
                hx = x - math.sin(angle) * gap * side
                hy = y + math.cos(angle) * gap * side
                if plots.claim(hx, hy):
                    placed.append((hx, hy, angle))
    return placed


def along(points: list[tuple[float, float]], step: float,
          rng: np.random.Generator) -> list[tuple[float, float, float]]:
    """(x, y, heading) every `step` pixels along a polyline, a little unevenly."""
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 2:
        return []
    seg = np.diff(pts, axis=0)
    dist = np.concatenate([[0.0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    if dist[-1] < step:
        return []
    t = np.arange(step / 2, dist[-1], step)
    t = t + rng.uniform(-0.3, 0.3, len(t)) * step
    t = np.clip(t, 0, dist[-1])
    x, y = np.interp(t, dist, pts[:, 0]), np.interp(t, dist, pts[:, 1])
    i = np.clip(np.searchsorted(dist, t, side="right") - 1, 0, len(seg) - 1)
    heading = np.arctan2(seg[i, 1], seg[i, 0])
    return list(zip(x.tolist(), y.tolist(), heading.tolist(), strict=True))


def house(pen: ImageDraw.ImageDraw, x: float, y: float, w: float, tilt: float) -> None:
    """A gabled front: body, roof, drawn around (x, y), turned by tilt radians."""
    h = w * 0.55
    c, s = math.cos(tilt), math.sin(tilt)

    def at(px, py):
        return (x + px * c - py * s, y + px * s + py * c)

    body = [at(-w / 2, 0), at(w / 2, 0), at(w / 2, h), at(-w / 2, h)]
    roof = [at(-w / 2 - w * 0.08, 0), at(0, -h * 0.9), at(w / 2 + w * 0.08, 0)]
    pen.polygon([at(-w / 2 + 1, h * 0.3 + 1), at(w / 2 + 1, h * 0.3 + 1), at(w / 2 + 1, h + 1),
                 at(-w / 2 + 1, h + 1)], fill=CANOPY_SHADE)
    pen.polygon(body, fill=WALL, outline=SEPIA)
    pen.polygon(roof, fill=ROOF, outline=SEPIA)
    pen.line([at(-w / 2, 0), at(w / 2, 0)], fill=SEPIA, width=1)


def church(pen: ImageDraw.ImageDraw, x: float, y: float, h: float) -> None:
    """A nave with a tower and spire on its left, a cross on top; h is the nave's height."""
    w, tw = h * 1.5, h * 0.6
    left, base = x - w / 2, y + h / 2
    pen.polygon([(left + 2, base - h * 0.6 + 2), (left + w + 2, base - h * 0.6 + 2),
                 (left + w + 2, base + 2), (left + 2, base + 2)], fill=CANOPY_SHADE)
    pen.polygon([(left, base - h * 0.8), (left + w, base - h * 0.8), (left + w, base),
                 (left, base)], fill=WALL, outline=SEPIA)
    pen.polygon([(left - w * 0.05, base - h * 0.8), (left + w / 2, base - h * 1.25),
                 (left + w * 1.05, base - h * 0.8)], fill=ROOF, outline=SEPIA)
    pen.polygon([(left, base - h * 1.6), (left + tw, base - h * 1.6), (left + tw, base),
                 (left, base)], fill=WALL, outline=SEPIA)
    pen.polygon([(left - tw * 0.1, base - h * 1.6), (left + tw / 2, base - h * 2.4),
                 (left + tw * 1.1, base - h * 1.6)], fill=ROOF, outline=SEPIA)
    cx, top = left + tw / 2, base - h * 2.4
    pen.line([(cx, top), (cx, top - h * 0.35)], fill=SEPIA, width=max(1, round(h / 10)))
    pen.line([(cx - h * 0.12, top - h * 0.25), (cx + h * 0.12, top - h * 0.25)], fill=SEPIA,
             width=max(1, round(h / 10)))
    _ = PARCHMENT


def buildings(canvas: Image.Image, rings: list[list[list[tuple[float, float]]]],
              metres_per_px: float, roofed: bool = False) -> None:
    """Footprints as they stand: a cast shadow to the south-east, the walls, an ink outline.
    Drawn at 2x and pasted through a mask, so small houses keep their corners. Roofed: a ridge
    along the long side, the south-east slope in shade."""
    ss = 2
    shadow_px = max(1, round(1.5 / metres_per_px)) * ss
    walls = Image.new("L", (canvas.width * ss, canvas.height * ss), 0)
    shade = Image.new("L", walls.size, 0)
    pen_w, pen_s = ImageDraw.Draw(walls), ImageDraw.Draw(shade)
    for footprint in rings:
        for ring in footprint:
            pts = [(x * ss, y * ss) for x, y in ring]
            pen_s.polygon([(x + shadow_px, y + shadow_px) for x, y in pts], fill=255)
            pen_w.polygon(pts, fill=255)
    canvas.paste(CANOPY_SHADE, (0, 0), shade.resize(canvas.size, Image.BOX))
    small = walls.resize(canvas.size, Image.BOX)
    canvas.paste(WALL, (0, 0), small)
    if roofed:
        roofs(canvas, rings)
    edge = ImageChops.subtract(small, small.filter(ImageFilter.MinFilter(3)))
    canvas.paste(SEPIA, (0, 0), edge)


def roofs(canvas: Image.Image, rings: list[list[list[tuple[float, float]]]]) -> None:
    """On each footprint, the half beyond the ridge (towards the south-east) in roof shade,
    and the ridge as an ink line."""
    pen = ImageDraw.Draw(canvas)
    for footprint in rings:
        for ring in footprint:
            if len(ring) < 3:
                continue
            (x0, y0), (x1, y1) = max(zip(ring, ring[1:] + ring[:1], strict=True),
                                     key=lambda e: math.dist(*e))
            a = math.atan2(y1 - y0, x1 - x0)
            u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
            if v[0] + v[1] < 0:  # v points towards the light; shade lies the other way
                v = (-v[0], -v[1])
            cx = sum(x for x, _ in ring) / len(ring)
            cy = sum(y for _, y in ring) / len(ring)
            reach = max(math.dist((cx, cy), q) for q in ring) + 2
            _shade_half(canvas, ring, (cx, cy), u, v, reach)
            ts = [((x - cx) * u[0] + (y - cy) * u[1]) for x, y in ring]
            lo, hi = min(ts) + 1, max(ts) - 1
            pen.line([(cx + u[0] * lo, cy + u[1] * lo), (cx + u[0] * hi, cy + u[1] * hi)],
                     fill=SEPIA, width=1)


def _shade_half(canvas: Image.Image, ring: list, c: tuple, u: tuple, v: tuple,
                reach: float) -> None:
    ss = 2
    xs, ys = [x for x, _ in ring], [y for _, y in ring]
    x0, y0 = math.floor(min(xs)), math.floor(min(ys))
    w, h = math.ceil(max(xs)) - x0 + 1, math.ceil(max(ys)) - y0 + 1
    mask = Image.new("L", (w * ss, h * ss), 0)
    pen = ImageDraw.Draw(mask)
    pen.polygon([((x - x0) * ss, (y - y0) * ss) for x, y in ring], fill=255)
    cx, cy = (c[0] - x0) * ss, (c[1] - y0) * ss
    r = reach * ss
    lit = [(cx - u[0] * r, cy - u[1] * r), (cx + u[0] * r, cy + u[1] * r),
           (cx + u[0] * r - v[0] * r, cy + u[1] * r - v[1] * r),
           (cx - u[0] * r - v[0] * r, cy - u[1] * r - v[1] * r)]
    pen.polygon(lit, fill=0)
    canvas.paste(ROOF_SHADE, (x0, y0), mask.resize((w, h), Image.BOX))
