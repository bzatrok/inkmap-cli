"""What each scale draws. A PBF extract holds everything, so the renderer is handed only the
features that are still visible at the scale's metres per pixel."""

from inkmap.domain import poi

HIGHWAYS = {
    24: {"motorway", "trunk", "primary", "secondary"},
    6: {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified"},
    1.5: {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified",
          "pedestrian", "living_street", "track", "path", "footway"},
}
PLACES = {
    24: {"city", "town", "village"},
    6: {"city", "town", "village", "suburb", "hamlet", "locality"},
    1.5: {"city", "town", "village", "suburb", "quarter", "neighbourhood", "hamlet", "locality",
          "farm"},
}
WATERWAYS = {24: {"river", "canal"}, 6: {"river", "canal"}, 1.5: {"river", "canal", "stream"}}


def _tier(metres_per_px: float) -> float:
    return min(HIGHWAYS, key=lambda t: abs(t - metres_per_px))


def keep(tags: dict, metres_per_px: float) -> bool:
    tier = _tier(metres_per_px)
    if name := poi.kind(tags):
        return poi.shows(name, tier)
    if "highway" in tags:
        return tags["highway"] in HIGHWAYS[tier]
    if "place" in tags:
        return tags["place"] in PLACES[tier]
    if "waterway" in tags and not tags.get("natural") == "water":
        return tags["waterway"] in WATERWAYS[tier] or tags["waterway"] == "riverbank"
    if "building" in tags:
        return tier <= 1.5
    return True
