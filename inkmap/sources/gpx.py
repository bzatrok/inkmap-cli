"""Track points out of a GPX file: every <trkpt> and <rtept>, in file order."""

import xml.etree.ElementTree as ET
from pathlib import Path


def points(path: Path) -> list[tuple[float, float]]:
    return [(float(el.get("lat")), float(el.get("lon")))
            for _, el in ET.iterparse(path)
            if el.tag.rsplit("}", 1)[-1] in ("trkpt", "rtept")]
