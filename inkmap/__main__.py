"""inkmap fetch|render regions/<name>.toml. The only reader of a region's TOML."""

import argparse
import json
import tomllib
from pathlib import Path

from PIL import Image

from inkmap import tiles
from inkmap.domain.detail import keep
from inkmap.domain.region import Region
from inkmap.render.mapdraw import draw_map
from inkmap.sources import dem, gpx, pbf, worldcover

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT, TILES = ROOT / "data", ROOT / "out", ROOT / "tiles"
DPI = 96


def main() -> None:
    parser = argparse.ArgumentParser(prog="inkmap")
    parser.add_argument("command", choices=["fetch", "render"])
    parser.add_argument("region", type=Path)
    parser.add_argument("--scale", help="render only this scale, no tiles")
    args = parser.parse_args()
    spec = tomllib.loads(args.region.read_text())
    region = Region.from_mapping(spec)
    names = [(r["name"], r["lat"], r["lon"], r.get("angle", 0.0)) for r in spec.get("regions", [])]
    ext = spec.get("tile_format", "png")
    osm_cut = DATA / "osm" / f"{spec.get('osm', region.name)}.geojsonseq"
    extract = DATA / "osm" / spec.get("extract", "gelderland-latest.osm.pbf")
    if args.command == "fetch":
        fetch(region, extract, osm_cut)
    else:
        tracks = [gpx.points(args.region.parent / t) for t in region.tracks]
        render(region, osm_cut, args.scale, names, ext, tracks)


def frames(region: Region) -> tuple[dict, dict]:
    """Each scale's frame, and for a scale with its own box the first tile it covers."""
    out = {name: region.frame(mpp) for name, mpp in region.scales.items()}
    base = next(iter(out.values()))
    origins = {}
    for name, box in region.boxes.items():
        out[name], origins[name] = tiles.window(base, region.zoom(name), box)
    return out, origins


def fetch(region: Region, extract: Path, osm_cut: Path) -> None:
    pbf.cut(extract, (region.south, region.west, region.north, region.east), osm_cut)
    for frame in frames(region)[0].values():
        dem.elevation(frame, DATA / "dem")  # warms the caches
        worldcover.tree_cover(frame, DATA / "worldcover")
    print("fetched")


def render(region: Region, osm_cut: Path, only: str | None, names: list, ext: str,
           tracks: list = ()) -> None:
    Image.MAX_IMAGE_PIXELS = None
    elements = pbf.elements(osm_cut)
    out_dir = OUT / region.name
    out_dir.mkdir(parents=True, exist_ok=True)
    scale_frames, origins = frames(region)
    for name, mpp in region.scales.items():
        if only and name != only:
            continue
        frame = scale_frames[name]
        shown = [el for el in elements if keep(el.get("tags", {}), mpp)]
        print(f"{name}: {frame.width}x{frame.height} px, {len(shown)} features")
        image, placed = draw_map(frame, shown, DPI, 1.0, dem.elevation(frame, DATA / "dem"),
                                 worldcover.tree_cover(frame, DATA / "worldcover"), names, tracks)
        image.save(out_dir / f"{name}.png")
        (out_dir / f"{name}.labels.json").write_text(json.dumps(placed, ensure_ascii=False))
    if only:
        return
    zooms = {name: region.zoom(name) for name in region.scales}
    tile_dir = TILES / region.name
    windows, labels = {}, {}
    for z, (name, shrink) in tiles.plan(zooms).items():
        if name in origins and shrink > 1:
            raise ValueError(f"{name} has its own box, so it can only be the finest scale")
        tiles.slice_scale(Image.open(out_dir / f"{name}.png"), shrink, z, tile_dir, ext,
                          origins.get(name, (0, 0)))
        ox, oy = origins.get(name, (0, 0))
        off = (ox * tiles.TILE, oy * tiles.TILE) * 2
        placed = json.loads((out_dir / f"{name}.labels.json").read_text())
        labels[z] = {text: [round(v / shrink + o) for v, o in zip(box, off, strict=True)]
                     for text, box in placed.items()}
        if name in origins:
            (ox, oy), f = origins[name], scale_frames[name]
            windows[z] = (ox, oy, ox + f.width // tiles.TILE, oy + f.height // tiles.TILE)
    base = next(iter(scale_frames.values()))
    tiles.write_meta(tile_dir, region.title, base.width, base.height, max(zooms.values()),
                     (region.south, region.west, region.north, region.east), ext, windows, labels)
    print(f"tiles in {tile_dir}")


if __name__ == "__main__":
    main()
