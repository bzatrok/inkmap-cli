"""Tree cover for a frame from ESA WorldCover 2021 (10 m land cover, CC BY 4.0), read as
windows straight from the public tiles on AWS and resampled into the frame's pixels.

Tiles are 3x3 degrees, named by their south-west corner. Class 10 is tree cover.
"""

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

from inkmap.domain.frame import Frame, unproject

URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
       "ESA_WorldCover_10m_2021_v200_{name}_Map.tif")
TREES = 10
TILE_DEG = 3


def tile_names(bbox: tuple[float, float, float, float]) -> list[tuple[str, int, int]]:
    """(name, south, west) of every tile the bbox touches.
    shortcut: N/E hemispheres only; add S/W naming when a region needs them."""
    south, west, north, east = bbox
    out = []
    for lat0 in range(math.floor(south / TILE_DEG) * TILE_DEG, math.ceil(north), TILE_DEG):
        for lon0 in range(math.floor(west / TILE_DEG) * TILE_DEG, math.ceil(east), TILE_DEG):
            out.append((f"N{lat0:02d}E{lon0:03d}", lat0, lon0))
    return out


def tree_cover(frame: Frame, cache_dir: Path) -> np.ndarray:
    """True where WorldCover sees trees, one value per frame pixel. Cached per frame."""
    cache = cache_dir / (f"{frame.lat:.5f}_{frame.lon:.5f}_{frame.metres_per_px}"
                         f"_{frame.width}x{frame.height}.npy")
    if cache.exists():
        return np.load(cache)
    south, west, north, east = frame.bbox()
    xs = np.arange(frame.width, dtype=np.float64) + 0.5
    ys = np.arange(frame.height, dtype=np.float64) + 0.5
    lat, lon = unproject(frame, xs[None, :], ys[:, None])
    lat, lon = np.broadcast_arrays(lat, lon)
    trees = np.zeros(lat.shape, dtype=bool)
    for name, lat0, lon0 in tile_names((south, west, north, east)):
        inside = (lat >= lat0) & (lat < lat0 + TILE_DEG) & (lon >= lon0) & (lon < lon0 + TILE_DEG)
        if not inside.any():
            continue
        with rasterio.open(URL.format(name=name)) as src:
            window = from_bounds(max(west, lon0), max(south, lat0), min(east, lon0 + TILE_DEG),
                                 min(north, lat0 + TILE_DEG), src.transform)
            data = src.read(1, window=window)
            transform = src.window_transform(window)
        col = ((lon - transform.c) / transform.a).astype(np.int64)
        row = ((lat - transform.f) / transform.e).astype(np.int64)
        valid = inside & (row >= 0) & (row < data.shape[0]) & (col >= 0) & (col < data.shape[1])
        trees[valid] = data[row[valid], col[valid]] == TREES
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, trees)
    return trees
