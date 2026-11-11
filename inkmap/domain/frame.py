"""The print's map box laid over the ground, and the OpenStreetMap features to draw in it.

Copied from gallery/domain/maps.py and owned here. Frame takes its size from the map box at
the print's resolution and its scale from the ground width. The Overpass detail levels are
the gallery's, picked by the scale the same ground would have on the 800 px wide panel.
"""

import math
from dataclasses import dataclass

PANEL_W = 800
MARGIN = 1 / 80  # data is fetched this far past the frame (a share of its width)


@dataclass(frozen=True)
class Frame:
    """A local equirectangular projection around the centre, width x height pixels."""
    lat: float
    lon: float
    metres_per_px: float
    width: int
    height: int

    @classmethod
    def for_box(cls, lat: float, lon: float, ground_width_m: float, width: int,
                height: int) -> "Frame":
        return cls(lat, lon, ground_width_m / width, width, height)

    @property
    def panel_metres_per_px(self) -> float:
        """The scale the same ground would have across the E1002 panel."""
        return self.metres_per_px * self.width / PANEL_W

    def project(self, lat: float, lon: float, scale: float = 1) -> tuple[float, float]:
        x = (lon - self.lon) * 111320 * math.cos(math.radians(self.lat)) / self.metres_per_px
        y = -(lat - self.lat) * 110950 / self.metres_per_px
        return (self.width / 2 + x) * scale, (self.height / 2 + y) * scale

    def bbox(self) -> tuple[float, float, float, float]:
        """south, west, north, east in degrees."""
        margin = self.width * MARGIN
        half_lat = (self.height / 2 + margin) * self.metres_per_px / 110950
        half_lon = ((self.width / 2 + margin) * self.metres_per_px
                    / (111320 * math.cos(math.radians(self.lat))))
        return self.lat - half_lat, self.lon - half_lon, self.lat + half_lat, self.lon + half_lon


def overpass_query(frame: Frame) -> str:
    """The OSM features the print draws. Wider frames leave out the small ones: they would be
    too fine to see, and the download would run to tens of megabytes."""
    south, west, north, east = frame.bbox()
    box = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    body = "\n".join(f" {line.format(box=box)}" for line in detail(frame))
    return f"[out:json][timeout:180];\n(\n{body}\n);\nout geom;\n"


def detail(frame: Frame) -> tuple[str, ...]:
    scale = frame.panel_metres_per_px
    if scale <= 15:
        return DETAILED
    if scale <= 30:
        return REDUCED
    if scale <= 60:
        return REGIONAL
    return WIDE


DETAILED = (
    'way["natural"="water"]({box}); relation["natural"="water"]({box});',
    'way["waterway"~"river|stream|canal"]({box});',
    'way["landuse"~"forest|grass|meadow|recreation_ground|cemetery|farmland|residential|'
    'industrial|commercial"]({box});',
    'way["natural"~"wood|scrub|heath|grassland"]({box}); relation["natural"="wood"]({box}); '
    'relation["landuse"="forest"]({box});',
    'way["leisure"~"park|garden|pitch|golf_course"]({box});',
    'way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|'
    'pedestrian|living_street"]({box});',
    'way["railway"="rail"]({box});',
    'node["place"~"suburb|neighbourhood|quarter|city|town|village"]({box});',
)
REDUCED = (
    'way["natural"="water"]({box}); relation["natural"="water"]({box});',
    'way["waterway"~"river|canal"]({box});',
    'way["landuse"~"forest|residential|industrial|commercial"]({box});',
    'way["natural"~"wood|heath"]({box}); relation["natural"="wood"]({box}); '
    'relation["landuse"="forest"]({box});',
    'way["highway"~"motorway|trunk|primary|secondary"]({box});',
    'way["railway"="rail"]({box});',
    'node["place"~"city|town|village"]({box});',
)
REGIONAL = (
    'way["natural"="water"]({box}); relation["natural"="water"]({box});',
    'way["waterway"~"river|canal"]({box});',
    'way["landuse"~"forest|residential"]({box});',
    'way["natural"="wood"]({box}); relation["natural"="wood"]({box}); '
    'relation["landuse"="forest"]({box});',
    'way["highway"~"motorway|trunk|primary"]({box});',
    'way["railway"="rail"]({box});',
    'node["place"~"city|town|village"]({box});',
)
WIDE = (  # 80 to 320 km across: only what is still visible at 100+ m per panel pixel
    'relation["natural"="water"]({box}); way["natural"="water"]["name"]({box});',
    'way["waterway"="river"]({box});',
    'way["highway"~"motorway|trunk"]({box});',
    'node["place"~"city|town"]({box});',
)


def unproject(frame: Frame, x, y):
    """Pixel coordinates (arrays or floats) back to (lat, lon)."""
    lon = frame.lon + (x - frame.width / 2) * frame.metres_per_px / (
        111320 * math.cos(math.radians(frame.lat)))
    lat = frame.lat - (y - frame.height / 2) * frame.metres_per_px / 110950
    return lat, lon
