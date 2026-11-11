"""OpenStreetMap from a Geofabrik PBF extract, cut and exported with the osmium CLI, then read
as the element dicts the renderer draws (the shape Overpass `out geom` gives).

Map data (c) OpenStreetMap contributors, ODbL.
"""

import json
import subprocess
from pathlib import Path

TAGS = ["w/natural", "w/landuse", "w/leisure", "w/waterway", "w/highway", "w/railway",
        "w/building", "r/natural", "r/landuse", "r/water", "n/place",
        # points of interest: churches, castles, viewpoints, inns
        "n/amenity", "w/amenity", "r/amenity", "n/tourism", "w/tourism", "n/historic",
        "w/historic", "n/natural", "n/man_made", "w/man_made"]


def cut(source: Path, bbox: tuple[float, float, float, float], out: Path) -> Path:
    """Cut south,west,north,east out of the extract into `out` (a .geojsonseq)."""
    south, west, north, east = bbox
    out.parent.mkdir(parents=True, exist_ok=True)
    box_pbf, tagged_pbf = out.with_suffix(".box.pbf"), out.with_suffix(".tagged.pbf")
    run("osmium", "extract", "-b", f"{west},{south},{east},{north}", "-s", "smart",
        str(source), "-o", str(box_pbf), "--overwrite")
    run("osmium", "tags-filter", str(box_pbf), *TAGS, "-o", str(tagged_pbf), "--overwrite")
    run("osmium", "export", str(tagged_pbf), "-f", "geojsonseq", "-o", str(out), "--overwrite",
        "--geometry-types=point,linestring,polygon")
    return out


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def elements(path: Path) -> list[dict]:
    out = []
    with path.open() as lines:
        for line in lines:
            line = line.strip().lstrip("\x1e")
            if line:
                el = element(json.loads(line))
                if el:
                    out.append(el)
    return out


def element(feature: dict) -> dict | None:
    """One GeoJSON feature as an Overpass-style element: node, way, or relation with members."""
    tags = feature.get("properties", {})
    geometry = feature["geometry"]
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "Point":
        return {"type": "node", "tags": tags, "lon": coords[0], "lat": coords[1]}
    if kind == "LineString":
        return {"type": "way", "tags": tags, "geometry": _points(coords)}
    if kind == "Polygon":
        if len(coords) == 1:
            return {"type": "way", "tags": tags, "geometry": _points(coords[0])}
        return {"type": "relation", "tags": tags, "members": _members([coords])}
    if kind == "MultiPolygon":
        return {"type": "relation", "tags": tags, "members": _members(coords)}
    return None


def _points(coords: list) -> list[dict]:
    return [{"lon": lon, "lat": lat} for lon, lat in coords]


def _members(polygons: list) -> list[dict]:
    members = []
    for rings in polygons:
        for i, ring in enumerate(rings):
            members.append({"type": "way", "role": "outer" if i == 0 else "inner",
                            "geometry": _points(ring)})
    return members
