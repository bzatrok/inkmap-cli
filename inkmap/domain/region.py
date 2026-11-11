"""A region to render: its ground box and the scales it is drawn at."""

import math
from dataclasses import dataclass, field

from inkmap.domain.frame import Frame


@dataclass(frozen=True)
class Region:
    name: str
    title: str
    south: float
    west: float
    north: float
    east: float
    scales: dict[str, float]  # name -> metres per pixel, coarsest first
    # scale -> its own ground box (south, west, north, east): a fine scale drawn only there
    boxes: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    # GPX files (paths relative to the region file) whose lines the names keep clear of
    tracks: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: dict) -> "Region":
        scales = dict(sorted(data["scales"].items(), key=lambda kv: -kv[1]))
        base = next(iter(scales.values()))
        for name, mpp in scales.items():
            if not math.log2(base / mpp).is_integer():
                raise ValueError(f"scale {name}: {base}/{mpp} is not a power of two")
        boxes = {name: tuple(box) for name, box in data.get("boxes", {}).items()}
        if unknown := set(boxes) - set(scales):
            raise ValueError(f"boxes for scales that do not exist: {sorted(unknown)}")
        return cls(data["name"], data["title"], data["south"], data["west"], data["north"],
                   data["east"], scales, boxes, tuple(data.get("tracks", ())))

    @property
    def centre(self) -> tuple[float, float]:
        return (self.south + self.north) / 2, (self.west + self.east) / 2

    def frame(self, metres_per_px: float) -> Frame:
        lat, lon = self.centre
        width_m = (self.east - self.west) * 111320 * math.cos(math.radians(lat))
        height_m = (self.north - self.south) * 110950
        return Frame(lat, lon, metres_per_px, round(width_m / metres_per_px),
                     round(height_m / metres_per_px))

    def zoom(self, scale: str) -> int:
        """The tile zoom level this scale renders: 0 for the coarsest, +1 per halving."""
        base = next(iter(self.scales.values()))
        return round(math.log2(base / self.scales[scale]))
