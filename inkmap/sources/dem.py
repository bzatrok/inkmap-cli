"""Elevation for a frame from Terrarium tiles (Mapzen/AWS `elevation-tiles-prod`, public, no key),
resampled from Web Mercator into the frame's pixels. Tiles are cached under `cache_dir`.

Terrarium encodes metres as R*256 + G + B/256 - 32768.
"""

import math
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from inkmap.domain.frame import Frame, unproject

URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
MAX_ZOOM = 15
TILE = 256
EARTH = 40075016.686


def zoom_for(frame: Frame) -> int:
    ground = EARTH * math.cos(math.radians(frame.lat)) / TILE
    return min(MAX_ZOOM, max(0, round(math.log2(ground / frame.metres_per_px))))


def _tile_xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180) / 360 * n
    rad = math.radians(lat)
    y = (1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * n
    return x, y


def fetch_tile(z: int, x: int, y: int, cache_dir: Path) -> Path:
    path = cache_dir / str(z) / str(x) / f"{y}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        reply = httpx.get(URL.format(z=z, x=x, y=y), timeout=60)
        reply.raise_for_status()
        path.write_bytes(reply.content)
    return path


def elevation(frame: Frame, cache_dir: Path) -> np.ndarray:
    """Metres above sea level per frame pixel, float32 (height, width)."""
    z = zoom_for(frame)
    south, west, north, east = frame.bbox()
    x0, y0 = (math.floor(v) for v in _tile_xy(north, west, z))
    x1, y1 = (math.floor(v) for v in _tile_xy(south, east, z))
    mosaic = np.empty(((y1 - y0 + 1) * TILE, (x1 - x0 + 1) * TILE), dtype=np.float32)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            rgb = np.asarray(Image.open(fetch_tile(z, tx, ty, cache_dir)).convert("RGB"),
                             dtype=np.float32)
            mosaic[(ty - y0) * TILE:(ty - y0 + 1) * TILE, (tx - x0) * TILE:(tx - x0 + 1) * TILE] = (
                rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768)
    return _resample(frame, mosaic, z, x0, y0)


def _resample(frame: Frame, mosaic: np.ndarray, z: int, x0: int, y0: int) -> np.ndarray:
    xs = np.arange(frame.width, dtype=np.float64) + 0.5
    ys = np.arange(frame.height, dtype=np.float64) + 0.5
    lat, lon = unproject(frame, xs[None, :], ys[:, None])
    n = 2 ** z
    px = ((lon + 180) / 360 * n - x0) * TILE
    rad = np.radians(lat)
    py = ((1 - np.log(np.tan(rad) + 1 / np.cos(rad)) / np.pi) / 2 * n - y0) * TILE
    px = np.clip(px.astype(np.int64), 0, mosaic.shape[1] - 1)
    py = np.clip(py.astype(np.int64), 0, mosaic.shape[0] - 1)
    return mosaic[np.broadcast_to(py, (frame.height, frame.width)),
                  np.broadcast_to(px, (frame.height, frame.width))]
