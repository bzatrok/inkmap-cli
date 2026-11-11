"""Hills drawn the engraver's way: a soft brown shade on the slopes facing away from the light,
and short pen strokes (hachures) running downhill, denser and darker where it is steep.

Elevation is a float32 array of metres, one value per canvas pixel.
"""

import math

import numpy as np
from PIL import Image, ImageDraw

from inkmap.render.inks import RELIEF

LIGHT_AZIMUTH = 315.0  # degrees, light from the north-west as on engraved maps
LIGHT_ALTITUDE = 40.0
SHADE_STRENGTH = 0.35  # how dark the full shadow side gets
EXAGGERATION = 2.5  # vertical exaggeration before slopes are measured
HACHURE_STEP_PX = 7
HACHURE_MIN_SLOPE = 0.06  # rise over run (after exaggeration) under which no stroke is drawn
SMOOTH_M = 45  # the DEM is smoothed over this many ground metres before slopes are measured
HACHURE_LEN_PX = (4, 14)


def slope_aspect(elevation: np.ndarray, metres_per_px: float) -> tuple[np.ndarray, np.ndarray]:
    """Slope as rise over run and aspect in radians (direction the ground faces, downhill)."""
    radius = max(1, round(SMOOTH_M / metres_per_px))
    z = _smooth(elevation.astype(np.float32), radius) * EXAGGERATION
    dy, dx = np.gradient(z, metres_per_px)
    slope = np.hypot(dx, dy)
    aspect = np.arctan2(-dx, dy)  # downhill direction, y down on the image
    return slope, aspect


def _smooth(z: np.ndarray, radius: int) -> np.ndarray:
    """Three box blurs, close to a Gaussian; Pillow's blur does not take float images."""
    for _ in range(3):
        for axis in (0, 1):
            z = _box(z, radius, axis)
    return z


def _box(z: np.ndarray, radius: int, axis: int) -> np.ndarray:
    pad = [(0, 0), (0, 0)]
    pad[axis] = (radius, radius)
    padded = np.pad(z, pad, mode="edge")
    csum = np.cumsum(padded, axis=axis, dtype=np.float64)
    csum = np.concatenate([np.zeros_like(np.take(csum, [0], axis=axis)), csum], axis=axis)
    width = 2 * radius + 1
    n = z.shape[axis]
    hi = np.take(csum, np.arange(width, width + n), axis=axis)
    lo = np.take(csum, np.arange(0, n), axis=axis)
    return ((hi - lo) / width).astype(np.float32)


def hillshade(slope: np.ndarray, aspect: np.ndarray) -> np.ndarray:
    """0 (full shadow) to 1 (fully lit)."""
    zenith = math.radians(90 - LIGHT_ALTITUDE)
    azimuth = math.radians(LIGHT_AZIMUTH)
    # Aspect here is image space (y down); convert to compass bearing of the downhill direction.
    bearing = (np.pi / 2 - aspect) % (2 * np.pi)
    tilt = np.arctan(slope)
    lit = (math.cos(zenith) * np.cos(tilt)
           + math.sin(zenith) * np.sin(tilt) * np.cos(azimuth - bearing))
    return np.clip(lit, 0, 1)


def shade(canvas: Image.Image, slope: np.ndarray, aspect: np.ndarray) -> Image.Image:
    """Darken the canvas towards RELIEF where the ground turns away from the light."""
    lit = hillshade(slope, aspect)
    flat = math.cos(math.radians(90 - LIGHT_ALTITUDE))
    amount = np.clip((flat - lit) / flat, 0, 1) * SHADE_STRENGTH
    pixels = np.asarray(canvas, dtype=np.float32)
    tint = np.array(RELIEF, dtype=np.float32)
    out = pixels * (1 - amount[..., None]) + tint * amount[..., None]
    return Image.fromarray(out.round().clip(0, 255).astype(np.uint8))


def hachure_step(metres_per_px: float) -> int:
    """Strokes stay a pen's width apart on paper: sparser on the fine scales."""
    return round(HACHURE_STEP_PX * max(1.0, (4 / metres_per_px) ** 0.5))


def hachures(canvas: Image.Image, slope: np.ndarray, aspect: np.ndarray,
             step_px: int = HACHURE_STEP_PX, seed: int = 3) -> None:
    """Pen strokes downhill on a jittered grid; longer with slope, darker on the shadow side."""
    h, w = slope.shape
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h:step_px, 0:w:step_px]
    ys = ys + rng.uniform(-3, 3, ys.shape)
    xs = xs + rng.uniform(-3, 3, xs.shape)
    iy = np.clip(ys.round().astype(int), 0, h - 1)
    ix = np.clip(xs.round().astype(int), 0, w - 1)
    s, a = slope[iy, ix], aspect[iy, ix]
    lit = hillshade(s, a)
    # Gentle slopes get a few strokes, steep ones all of them.
    keep = rng.uniform(0, 1, s.shape) < np.interp(s, [HACHURE_MIN_SLOPE, HACHURE_MIN_SLOPE * 4],
                                                  [0.0, 1.0])
    length = np.interp(s, [HACHURE_MIN_SLOPE, HACHURE_MIN_SLOPE * 8], HACHURE_LEN_PX)
    alpha = np.interp(lit, [0.3, 0.85], [230, 90])
    mask = Image.new("L", canvas.size, 0)
    pen = ImageDraw.Draw(mask)
    for x, y, ln, ang, al in zip(xs[keep], ys[keep], length[keep], a[keep], alpha[keep],
                                 strict=True):
        dx, dy = math.sin(ang) * ln, -math.cos(ang) * ln
        pen.line([(x - dx / 2, y - dy / 2), (x + dx / 2, y + dy / 2)], fill=int(al), width=1)
    canvas.paste(RELIEF, (0, 0), mask)
