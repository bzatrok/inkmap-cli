"""OpenStreetMap elements (Overpass JSON, `out geom`) to the shapes the map draws."""

WOODS = {"wood", "forest"}
PARKS = {"grass", "meadow", "recreation_ground", "cemetery", "farmland", "park", "garden", "pitch",
         "golf_course", "scrub", "heath", "grassland"}
URBAN_USES = {"residential", "industrial", "commercial", "retail"}

Ring = list[tuple[float, float]]  # (lat, lon) points, first == last


def stitch(ways: list[Ring]) -> list[Ring]:
    """Join open ways end to end into rings; rings that never close are dropped."""
    pending = [list(w) for w in ways if len(w) > 1]
    rings = []
    while pending:
        ring = pending.pop()
        while ring[0] != ring[-1] and _extend(ring, pending):
            pass
        if ring[0] == ring[-1] and len(ring) > 3:
            rings.append(ring)
    return rings


def _extend(ring: Ring, pending: list[Ring]) -> bool:
    """Attach the first pending way that shares an end with the ring, in place."""
    for i, other in enumerate(pending):
        if other[0] == ring[-1]:
            ring += other[1:]
        elif other[-1] == ring[-1]:
            ring += other[::-1][1:]
        elif other[-1] == ring[0]:
            ring[:0] = other[:-1]
        elif other[0] == ring[0]:
            ring[:0] = other[::-1][:-1]
        else:
            continue
        pending.pop(i)
        return True
    return False


def members(element: dict, role: str) -> list[Ring]:
    ways = [[(p["lat"], p["lon"]) for p in m["geometry"]] for m in element.get("members", [])
            if m["type"] == "way" and m.get("role") == role and "geometry" in m]
    return stitch(ways)


def area_rings(element: dict) -> tuple[list[Ring], list[Ring]]:
    """(outer rings, inner rings) for a closed way or a multipolygon relation."""
    if element["type"] == "way":
        ring = [(p["lat"], p["lon"]) for p in element.get("geometry", [])]
        return ([ring], []) if len(ring) > 3 and ring[0] == ring[-1] else ([], [])
    return members(element, "outer"), members(element, "inner")


def classify(tags: dict) -> str | None:
    """The land class an area is painted as: water, wood, park, urban, or None."""
    if tags.get("natural") == "water" or tags.get("water"):
        return "water"
    kinds = {tags.get("landuse"), tags.get("natural"), tags.get("leisure")}
    if kinds & WOODS:
        return "wood"
    if kinds & PARKS:
        return "park"
    if kinds & URBAN_USES:
        return "urban"
    return None


def centre(element: dict) -> tuple[float, float]:
    """(lat, lon) of a node, or the mean of a way's points or a relation's first outer ring."""
    if element["type"] == "node":
        return element["lat"], element["lon"]
    pts = element.get("geometry") or next(
        (m["geometry"] for m in element.get("members", []) if m.get("role") == "outer"), [])
    if not pts:
        return float("nan"), float("nan")
    return (sum(p["lat"] for p in pts) / len(pts), sum(p["lon"] for p in pts) / len(pts))
