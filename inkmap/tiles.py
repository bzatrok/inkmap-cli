"""Slice rendered scales into a `{z}/{x}/{y}.png` pyramid for Leaflet's CRS.Simple.

Zoom 0 is the coarsest render. Each finer zoom doubles the pixels; a zoom with no render of its
own is the next finer render scaled down, so it stays crisp.
"""

import json
import math
from pathlib import Path

from PIL import Image

from inkmap.domain.frame import Frame, unproject

TILE = 256
WEBP_QUALITY = 82


def plan(zooms: dict[str, int]) -> dict[int, tuple[str, int]]:
    """zoom level -> (render to cut from, factor to shrink it by)."""
    out = {}
    for z in range(max(zooms.values()) + 1):
        name, rz = min(((n, rz) for n, rz in zooms.items() if rz >= z), key=lambda kv: kv[1])
        out[z] = (name, 2 ** (rz - z))
    return out


Box = tuple[float, float, float, float]


def window(base: Frame, zoom: int, box: Box) -> tuple[Frame, tuple[int, int]]:
    """The frame for a scale drawn only inside `box`: its pixels snapped outward to whole tiles
    of this zoom, so they drop straight into the pyramid. Returns the frame and its first tile."""
    south, west, north, east = box
    k = 2 ** zoom
    (x0, y0), (x1, y1) = base.project(north, west, k), base.project(south, east, k)
    tx0, ty0 = max(0, math.floor(x0 / TILE)), max(0, math.floor(y0 / TILE))
    tx1 = min(math.ceil(base.width * k / TILE), math.ceil(x1 / TILE))
    ty1 = min(math.ceil(base.height * k / TILE), math.ceil(y1 / TILE))
    w, h = (tx1 - tx0) * TILE, (ty1 - ty0) * TILE
    lat, lon = unproject(base, (tx0 * TILE + w / 2) / k, (ty0 * TILE + h / 2) / k)
    return Frame(lat, lon, base.metres_per_px / k, w, h), (tx0, ty0)


def slice_scale(image: Image.Image, shrink: int, z: int, out_dir: Path, ext: str = "png",
                origin: tuple[int, int] = (0, 0)) -> None:
    """Cuts one zoom level. `ext` is png (lossless) or webp (a quarter the size, for the web).
    `origin` is the first tile's index, for a render that covers only a window of the level."""
    if shrink > 1:
        image = image.reduce(shrink)
    for ty in range(-(-image.height // TILE)):
        for tx in range(-(-image.width // TILE)):
            tile = image.crop((tx * TILE, ty * TILE, (tx + 1) * TILE, (ty + 1) * TILE))
            path = out_dir / str(z) / str(tx + origin[0]) / f"{ty + origin[1]}.{ext}"
            path.parent.mkdir(parents=True, exist_ok=True)
            if ext == "webp":
                tile.save(path, quality=WEBP_QUALITY, method=6)
            else:
                tile.save(path, optimize=True)


def write_meta(out_dir: Path, title: str, width: int, height: int, max_zoom: int,
               bbox: tuple[float, float, float, float], ext: str = "png",
               windows: dict[int, tuple[int, int, int, int]] | None = None,
               labels: dict[int, dict[str, list[int]]] | None = None) -> None:
    """What a viewer needs: the zoom-0 size, the zoom range, the tile format and the ground box
    (south, west, north, east), so it can turn lat/lon into pixels. `windows` names the levels
    that exist only in part, as their tile range (x0, y0, x1, y1), x1 and y1 exclusive. `labels`
    gives, per level, the box each name was drawn in, in that level's pixels, so a viewer can
    mark a name on the map."""
    south, west, north, east = bbox
    meta = {"title": title, "width": width, "height": height, "maxZoom": max_zoom, "ext": ext,
            "south": south, "west": west, "north": north, "east": east,
            "attribution": "Map data © OpenStreetMap contributors (ODbL)"}
    if windows:
        meta["windows"] = {str(z): list(w) for z, w in windows.items()}
    if labels:
        meta["labels"] = {str(z): names for z, names in labels.items()}
    (out_dir / "meta.json").write_text(json.dumps(meta))
