"""Points of interest: what an OpenStreetMap feature is to the map, and from which scale it
shows. Churches anchor villages at every scale; inns only appear in the streets."""

KINDS = (
    ("church", lambda t: t.get("amenity") == "place_of_worship"),
    ("castle", lambda t: t.get("historic") in {"castle", "fort", "manor"}),
    ("ruins", lambda t: t.get("historic") == "ruins"),
    ("peak", lambda t: t.get("natural") == "peak" and "name" in t),
    ("viewpoint", lambda t: t.get("tourism") == "viewpoint"),
    ("tower", lambda t: t.get("man_made") in {"tower", "lighthouse", "windmill", "watermill"}),
    ("cross", lambda t: t.get("historic") in {"wayside_cross", "wayside_shrine"}
     or t.get("man_made") == "cross"),
    ("monument", lambda t: t.get("historic") in {"monument", "memorial"}),
    ("inn", lambda t: t.get("amenity") in {"restaurant", "pub", "cafe", "biergarten"}
     or t.get("tourism") in {"guest_house", "hotel", "chalet"}),
    ("spring", lambda t: t.get("natural") == "spring"),
    ("well", lambda t: t.get("amenity") == "drinking_water" or t.get("man_made") == "water_well"),
    ("hide", lambda t: t.get("amenity") == "hunting_stand"),
    ("shelter", lambda t: t.get("amenity") == "shelter"),
)
FROM_TIER = {"church": 24, "castle": 24, "peak": 6, "viewpoint": 6, "ruins": 6, "tower": 6,
             "cross": 1.5, "monument": 1.5, "inn": 1.5, "spring": 1.5, "well": 1.5, "hide": 1.5,
             "shelter": 1.5}


def kind(tags: dict) -> str | None:
    for name, test in KINDS:
        if test(tags):
            return name
    return None


def shows(name: str, tier: float) -> bool:
    return tier <= FROM_TIER[name]
