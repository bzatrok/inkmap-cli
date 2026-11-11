"""A hand's unsteadiness for every drawn line: the polyline is resampled along its length and
pushed sideways by two slow sine waves with random phases, so nothing is ruler-straight."""

import numpy as np

STEP_SHARE = 1 / 6  # resample spacing as a share of the wavelength


def wobble(points: list[tuple[float, float]], amplitude: float, wavelength: float,
           rng: np.random.Generator) -> list[tuple[float, float]]:
    if len(points) < 2 or amplitude <= 0:
        return points
    pts = np.asarray(points, dtype=np.float64)
    seg = np.diff(pts, axis=0)
    dist = np.concatenate([[0.0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    total = dist[-1]
    if total < wavelength * STEP_SHARE * 2:
        return points
    t = np.linspace(0, total, max(3, int(total / (wavelength * STEP_SHARE)) + 1))
    x, y = np.interp(t, dist, pts[:, 0]), np.interp(t, dist, pts[:, 1])
    dx, dy = np.gradient(x), np.gradient(y)
    norm = np.hypot(dx, dy)
    norm[norm == 0] = 1
    p1, p2 = rng.uniform(0, 2 * np.pi, 2)
    offset = amplitude * (0.65 * np.sin(2 * np.pi * t / wavelength + p1)
                          + 0.35 * np.sin(2 * np.pi * t / (wavelength * 0.41) + p2))
    offset[0] = offset[-1] = 0  # ends stay put, so joined ways still meet
    x, y = x - dy / norm * offset, y + dx / norm * offset
    return list(zip(x.tolist(), y.tolist(), strict=True))
