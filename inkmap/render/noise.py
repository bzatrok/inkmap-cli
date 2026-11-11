"""Slow-varying random fields: a coarse grid of random values, stretched smoothly to size.
Used to let forests clump and thin instead of filling every polygon evenly."""

import numpy as np
from PIL import Image


def value_noise(width: int, height: int, cell_px: float, rng: np.random.Generator) -> np.ndarray:
    """float32 (height, width) in 0..1, varying over about cell_px pixels."""
    cols, rows = max(2, int(width / cell_px) + 2), max(2, int(height / cell_px) + 2)
    coarse = rng.random((rows, cols), dtype=np.float32)
    big = Image.fromarray(coarse, mode="F").resize((cols * 64, rows * 64), Image.BICUBIC)
    arr = np.asarray(big, dtype=np.float32)
    # Bicubic overshoot is clipped; crop the stretched grid to the canvas.
    scale = cell_px / 64
    ys = np.clip((np.arange(height) / scale).astype(int), 0, arr.shape[0] - 1)
    xs = np.clip((np.arange(width) / scale).astype(int), 0, arr.shape[1] - 1)
    return np.clip(arr[ys[:, None], xs[None, :]], 0, 1)
