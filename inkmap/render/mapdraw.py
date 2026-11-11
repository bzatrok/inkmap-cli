"""The map box: land fills, burnt edges, roads and rails, then the names.

Memory: a 40x50 print's map is about 4100x4200 px. Each layer is drawn on its own 2x `L` mask,
scaled down, and one flat colour is pasted through it onto a uint8 RGB canvas. No RGB float
canvas is ever held. The burn is computed once at 1x in float32, in bands of rows.
"""

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from inkmap.domain import poi
from inkmap.domain.frame import Frame
from inkmap.render.geometry import area_rings, centre, classify
from inkmap.render.inks import (
    BURN,
    MINOR_ROAD,
    PARCHMENT,
    PARK,
    RIVER_INK,
    SEPIA,
    URBAN,
    WATER,
    WOOD,
)
from inkmap.render.labels import Labels, annotate
from inkmap.render.noise import value_noise
from inkmap.render.pois import NAMED, NAMED_COARSE, draw_pois
from inkmap.render.relief import hachure_step, hachures, shade, slope_aspect
from inkmap.render.stamps import buildings, church, houses, trees
from inkmap.render.text import label_font
from inkmap.render.village import dashes, fences, fields, planted
from inkmap.render.wobble import wobble

SS = 2  # layer masks are drawn this much larger, so lines and edges come out smooth
FILLS = (("urban", URBAN, 1.0), ("park", PARK, 0.85), ("wood", WOOD, 0.95), ("water", WATER, 1.0))
WATERWAY_MM = {"river": 2.2, "canal": 1.2}  # streams and the rest: 0.5
WATERWAY_M = {"river": 30, "canal": 10}  # 3 for the rest; a line is never thinner than the ground
MAJOR_MM = {"motorway": 0.9, "trunk": 0.9, "primary": 0.75, "secondary": 0.6, "tertiary": 0.5}
MINOR = {"residential", "unclassified", "pedestrian", "living_street", "track", "path", "footway"}
DASHED = {"track": (14, 6), "path": (5, 5), "footway": (5, 5)}  # on, off in SS px, street scale
PATHS = {"track", "path", "footway"}
MINOR_MM = 0.22
GROUND_M = {"motorway": 25, "trunk": 18, "primary": 12, "secondary": 9, "tertiary": 7}
MINOR_M = 5
TRACK_M = 2.5
RAIL_M = 4
CASING_MM = 0.7  # added to a major road's width, in parchment, under it
RAIL_MM = 0.3
RAIL_SKIP = {"yard", "siding", "spur"}  # they printed as black bars on the mock-up
BURN_MM = 9
TREE_M = 54  # a stamped tree's canopy, in ground metres; stamps need at least 4 px
HOUSE_M = 60
TRACK_MM = 3.5  # a drawn hike's width, with the air round it, that names keep clear of
TREE_MAX_PX = 16
TREE_MIN_PX = 4.5  # coarse scales draw oversized trees rather than none
BUILDING_GROWTH = 1.7
BUILDING_GROWTH_COARSE = 1.3  # at 2 m/px grown houses would merge into a ribbon
COVER_M = 10  # the satellite tree cover's pixel, in ground metres
CLEARING_M = 30
ROAD_CLEARING_M = 14  # either side of a road, no tree stamps
CLUMP_M = 220  # the forest thins and thickens over about this distance
COVER_CLUMP_M = 400
COVER_THIN = 0.42  # share of the slow noise under which satellite cover is dropped
COVER_PATCH_M = 40  # satellite patches thinner than this vanish
HOUSE_SPACING = 3.4  # in house widths
CHURCH_PX = 11
FOOTPRINT_MAX_MPP = 2.5  # finer than this, buildings are their footprints; coarser, stamps
WOBBLE_PX = (2.5, 70)  # amplitude and wavelength of a drawn line's unsteadiness, in SS pixels
GRAIN = 0.05
_rng = np.random.default_rng(5)
ROW_BAND = 512


def draw_map(frame: Frame, elements: list[dict], dpi: int, scale: float,
             elevation: np.ndarray | None = None, tree_cover: np.ndarray | None = None,
             regions: list[tuple[str, float, float, float]] = (),
             tracks: list[list[tuple[float, float]]] = ()) -> tuple[Image.Image, dict]:
    px_per_mm = dpi / 25.4
    canvas = Image.new("RGB", (frame.width, frame.height), PARCHMENT)
    footprints = [el for el in elements if "building" in el.get("tags", {})]
    extra_wood = None
    if tree_cover is not None:
        extra_wood = _cover_mask(tree_cover, frame.metres_per_px)
        _clear_around(extra_wood, frame, footprints)
    masks = draw_fills(canvas, frame, elements, px_per_mm, extra_wood)
    if elevation is not None:
        slope, aspect = slope_aspect(elevation, frame.metres_per_px)
        slope = slope * (np.asarray(masks["water"]) < 128)  # water lies flat
        canvas = shade(canvas, slope, aspect)
        hachures(canvas, slope, aspect, step_px=hachure_step(frame.metres_per_px))
    fine = frame.metres_per_px <= FOOTPRINT_MAX_MPP  # the street scales: every house, every fence
    if fine:
        fields(canvas, frame, elements)
    tree_px = min(TREE_MAX_PX, max(TREE_MIN_PX, TREE_M / frame.metres_per_px))
    roads = _roads(frame, elements, px_per_mm)
    if tree_px:
        clearing = _road_keepout(frame, roads, ROAD_CLEARING_M / frame.metres_per_px)
        trees(canvas, ImageChops.multiply(masks["wood"], clearing), tree_px,
              CLUMP_M / frame.metres_per_px)
    if fine:
        planted(canvas, frame, elements)
        buildings(canvas, [_rings(frame, el) for el in footprints], frame.metres_per_px,
                  roofed=True)
        fences(canvas, frame, elements)
    elif (house_px := HOUSE_M / frame.metres_per_px) >= 5:
        plots = ImageChops.multiply(masks["urban"], _road_keepout(frame, roads, house_px * 0.7))
        plots = ImageChops.subtract(plots, masks["water"].filter(ImageFilter.MaxFilter(5)))
        houses(canvas, plots, roads, house_px, house_px * HOUSE_SPACING)
    draw_churches(canvas, frame, elements)
    canvas = burn(canvas, round(BURN_MM * scale * px_per_mm), dpi)
    outline_water(canvas, masks["water"])
    draw_lines(canvas, frame, elements, px_per_mm)
    labels = Labels(canvas, edge_px=10 * scale * px_per_mm, gap_px=0.6 * scale * px_per_mm)
    for track in tracks:  # the site draws a hike over the tiles; names stay off its line
        labels.avoid([frame.project(lat, lon) for lat, lon in track], TRACK_MM * scale * px_per_mm)
    annotate(labels, frame, elements, px_per_mm, scale, regions)
    draw_pois(labels, frame, elements, label_font(round(3.0 * scale * px_per_mm)),
              NAMED if fine else NAMED_COARSE)
    return grain(canvas), labels.placed


def _layer(canvas: Image.Image) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    mask = Image.new("L", (canvas.width * SS, canvas.height * SS), 0)
    return mask, ImageDraw.Draw(mask)


def _paste(canvas: Image.Image, mask: Image.Image, colour: tuple, alpha: float = 1.0) -> None:
    small = mask.resize(canvas.size, Image.BOX)
    if alpha < 1:
        small = small.point(lambda v: round(v * alpha))
    canvas.paste(colour, (0, 0), small)


def _points(frame: Frame, geometry: list[dict]) -> list[tuple[float, float]]:
    pts = [frame.project(p["lat"], p["lon"], SS) for p in geometry]
    return wobble(pts, *WOBBLE_PX, _rng)


def outline_water(canvas: Image.Image, water: Image.Image) -> None:
    """A thin ink line along every shore."""
    edge = ImageChops.subtract(water, water.filter(ImageFilter.MinFilter(3)))
    canvas.paste(RIVER_INK, (0, 0), edge.point(lambda v: min(255, v * 2)))


def grain(canvas: Image.Image) -> Image.Image:
    """Paper texture: a slight random lightness per pixel, softened."""
    h, w = canvas.height, canvas.width
    noise = _rng.normal(1.0, GRAIN, (h, w)).astype(np.float32)
    noise = (noise + np.roll(noise, 1, 0) + np.roll(noise, 1, 1)) / 3
    pixels = np.asarray(canvas, dtype=np.float32) * noise[..., None]
    return Image.fromarray(pixels.round().clip(0, 255).astype(np.uint8))


def draw_churches(canvas: Image.Image, frame: Frame, elements: list[dict]) -> None:
    """One church per place of worship, a fixed size on paper, never two on top of each other."""
    pen = ImageDraw.Draw(canvas)
    size = CHURCH_PX
    # Coarse scales keep churches apart, so a city shows a few spires and not a forest of them.
    apart = size * (6 if frame.metres_per_px > FOOTPRINT_MAX_MPP * 4 else 2)
    drawn: list[tuple[float, float]] = []
    for el in elements:
        if poi.kind(el.get("tags", {})) != "church":
            continue
        x, y = frame.project(*centre(el))
        if any(abs(x - px) < apart and abs(y - py) < apart for px, py in drawn):
            continue
        drawn.append((x, y))
        church(pen, x, y, size)


def _rings(frame: Frame, element: dict) -> list[list[tuple[float, float]]]:
    """A building's outer rings in canvas pixels, grown about their centre so a hamlet reads
    as one at map scale (holes are not drawn)."""
    outers, _ = area_rings(element)
    rings = []
    growth = BUILDING_GROWTH if frame.metres_per_px <= 1.2 else BUILDING_GROWTH_COARSE
    for ring in outers:
        pts = [frame.project(a, b) for a, b in ring]
        cx, cy = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
        rings.append([(cx + (x - cx) * growth, cy + (y - cy) * growth) for x, y in pts])
    return rings


def _width(mm: float, px_per_mm: float, metres: float = 0, metres_per_px: float = 1) -> int:
    """Paper width, or the ground width when that is wider on this scale's pixels."""
    return max(1, round(max(mm * px_per_mm, metres / metres_per_px) * SS))


def _cover_mask(tree_cover: np.ndarray, metres_per_px: float) -> Image.Image:
    """Satellite tree cover as a wood mask at SS size: small patches and slivers dropped, the
    rest thinned by a slow noise so it reads as woods with gaps, not a blanket."""
    h, w = tree_cover.shape
    noise = value_noise(w, h, COVER_CLUMP_M / metres_per_px, _rng)
    kept = tree_cover & (noise > COVER_THIN)
    mask = Image.fromarray(kept.astype(np.uint8) * 255)
    mask = mask.resize((w * SS, h * SS), Image.BILINEAR)
    radius = COVER_PATCH_M / metres_per_px * SS * 0.5
    return mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: 255 if v > 150 else 0)


def road_px(tags: dict, px_per_mm: float, metres_per_px: float) -> float:
    """A road's drawn width in canvas pixels, casing included."""
    h = tags.get("highway")
    if h in MAJOR_MM:
        mm, metres = MAJOR_MM[h] + CASING_MM, GROUND_M[h]
    else:
        mm, metres = MINOR_MM, TRACK_M if h == "track" else MINOR_M
    return max(1.0, max(mm * px_per_mm, metres / metres_per_px))


def _roads(frame: Frame, elements: list[dict], px_per_mm: float) -> list[tuple[list, float]]:
    """(points in canvas px, half width in px) of every road."""
    return [([frame.project(p["lat"], p["lon"]) for p in el["geometry"]],
             road_px(el["tags"], px_per_mm, frame.metres_per_px) / 2) for el in elements
            if el["type"] == "way" and "highway" in el.get("tags", {}) and el.get("geometry")]


def _road_keepout(frame: Frame, roads: list[tuple[list, float]], margin_px: float) -> Image.Image:
    """White where a stamp may stand: every road, plus margin_px either side, is cut out."""
    mask = Image.new("L", (frame.width, frame.height), 255)
    pen = ImageDraw.Draw(mask)
    for pts, half in roads:
        pen.line(pts, fill=0, width=max(1, round(2 * (half + margin_px))), joint="curve")
    return mask


def _clear_around(cover: Image.Image, frame: Frame, footprints: list[dict]) -> None:
    """Villages are clearings: satellite trees within CLEARING_M of a building are dropped
    (gardens and orchards read as tree cover)."""
    pen = ImageDraw.Draw(cover)
    width = max(1, round(2 * CLEARING_M / frame.metres_per_px * SS))
    for el in footprints:
        for ring in _rings(frame, el):
            pen.polygon([(x * SS, y * SS) for x, y in ring], fill=0, outline=0, width=width)


def draw_fills(canvas: Image.Image, frame: Frame, elements: list[dict], px_per_mm: float,
               extra_wood: Image.Image | None = None) -> dict[str, Image.Image]:
    """Paints the land classes and returns each class's mask at canvas size. Wood is the
    union of OpenStreetMap's woods and the satellite tree cover, when given."""
    by_kind = _by_kind(elements)
    masks = {}
    for kind, colour, alpha in FILLS:
        mask, pen = _layer(canvas)
        _paint_areas(pen, frame, by_kind.get(kind, []))
        if kind == "urban":
            urban = mask
        if kind == "wood" and extra_wood is not None:
            mask = ImageChops.lighter(mask, ImageChops.subtract(extra_wood, urban))
        if kind == "water":
            _paint_waterways(pen, frame, by_kind.get("waterway", []), px_per_mm)
        masks[kind] = mask.resize(canvas.size, Image.BOX)
        _paste(canvas, mask, colour, alpha)
    return masks


def _by_kind(elements: list[dict]) -> dict[str, list[dict]]:
    by_kind: dict[str, list[dict]] = {}
    for el in elements:
        tags = el.get("tags", {})
        if "waterway" in tags and el["type"] == "way":
            by_kind.setdefault("waterway", []).append(el)
        elif kind := classify(tags):
            by_kind.setdefault(kind, []).append(el)
    return by_kind


def _paint_areas(pen: ImageDraw.ImageDraw, frame: Frame, areas: list[dict]) -> None:
    for el in areas:
        outers, inners = area_rings(el)
        for ring in outers:
            pen.polygon([frame.project(a, b, SS) for a, b in ring], fill=255)
        for ring in inners:
            pen.polygon([frame.project(a, b, SS) for a, b in ring], fill=0)


def _paint_waterways(pen: ImageDraw.ImageDraw, frame: Frame, ways: list[dict],
                     px_per_mm: float) -> None:
    for el in ways:
        kind_w = el["tags"]["waterway"]
        pen.line(_points(frame, el.get("geometry", [])), fill=255, joint="curve",
                 width=_width(WATERWAY_MM.get(kind_w, 0.5), px_per_mm,
                              WATERWAY_M.get(kind_w, 3), frame.metres_per_px))


def burn(canvas: Image.Image, width_px: int, dpi: int) -> Image.Image:
    """Old-map darkening towards the border, ragged."""
    w, h = canvas.size
    xs, ys = np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    edge = np.minimum.outer(np.minimum(ys, h - 1 - ys), np.minimum(xs, w - 1 - xs))
    rng = np.random.default_rng(7)
    noise = (rng.standard_normal((h, w), dtype=np.float32) * 40 + 128).clip(0, 255)
    blur = ImageFilter.GaussianBlur(max(0.5, 3 * dpi / 600))
    ragged = np.asarray(Image.fromarray(noise.astype(np.uint8)).filter(blur), dtype=np.float32)
    del noise
    edge += (ragged - 128) / 20 * width_px * 0.12
    del ragged
    amount = np.clip(1 - edge / max(width_px, 1), 0, 1) ** 1.8 * 0.45
    del edge
    pixels = np.asarray(canvas)
    out = np.empty_like(pixels)
    tint = np.array(BURN, dtype=np.float32)
    for top in range(0, h, ROW_BAND):
        a = amount[top:top + ROW_BAND, :, None]
        band = pixels[top:top + ROW_BAND] * (1 - a) + tint * a
        out[top:top + ROW_BAND] = band.round().clip(0, 255).astype(np.uint8)
    return Image.fromarray(out)


def draw_lines(canvas: Image.Image, frame: Frame, elements: list[dict], px_per_mm: float) -> None:
    """Minor roads, then the parchment casings, the major roads, and the rails on top."""
    ways = [el for el in elements if el["type"] == "way" and el.get("geometry")]
    minor = [(el, MINOR_MM, TRACK_M if h in PATHS else MINOR_M) for el in ways
             if (h := el["tags"].get("highway")) in MINOR]
    major = [(el, MAJOR_MM[h], GROUND_M[h]) for el in ways
             if (h := el["tags"].get("highway")) in MAJOR_MM]
    rails = [(el, RAIL_MM, RAIL_M) for el in ways if el["tags"].get("railway") == "rail"
             and el["tags"].get("service") not in RAIL_SKIP]
    for lines, colour, extra in ((minor, MINOR_ROAD, 0), (major, PARCHMENT, CASING_MM),
                                 (major, SEPIA, 0), (rails, SEPIA, 0)):
        if not lines:
            continue
        mask, pen = _layer(canvas)
        for el, mm, metres in lines:
            width = _width(mm, px_per_mm, metres, frame.metres_per_px) + _width(extra, px_per_mm)
            for piece in _strokes(frame, el):
                pen.line(piece, fill=255, width=width, joint="curve")
        _paste(canvas, mask, colour)


def _strokes(frame: Frame, el: dict) -> list[list[tuple[float, float]]]:
    """A way's line, or at street scale a track's dashes and a path's dots."""
    pts = _points(frame, el["geometry"])
    pattern = DASHED.get(el["tags"].get("highway"))
    if pattern and frame.metres_per_px <= FOOTPRINT_MAX_MPP and len(pts) > 1:
        return dashes(pts, *pattern)
    return [pts]
