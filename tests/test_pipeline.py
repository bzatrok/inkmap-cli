from inkmap import tiles
from inkmap.domain.region import Region
from inkmap.sources.pbf import element

ARNHEM = {"name": "a", "title": "A", "south": 51.78, "west": 5.76, "north": 52.12, "east": 6.14,
          "scales": {"street": 1.5, "region": 24, "town": 6}}


def test_region_scales_sort_coarsest_first_and_zoom_from_ratio():
    region = Region.from_mapping(ARNHEM)
    assert list(region.scales) == ["region", "town", "street"]
    assert [region.zoom(s) for s in region.scales] == [0, 2, 4]
    frame = region.frame(24)
    assert 1070 < frame.width < 1090 and 1570 < frame.height < 1580


def test_tile_plan_uses_next_finer_render_shrunk():
    assert tiles.plan({"region": 0, "town": 2, "street": 4}) == {
        0: ("region", 1), 1: ("town", 2), 2: ("town", 1), 3: ("street", 2), 4: ("street", 1)}


def test_polygon_with_hole_becomes_relation():
    outer = [[5.0, 52.0], [5.1, 52.0], [5.1, 52.1], [5.0, 52.0]]
    inner = [[5.02, 52.02], [5.05, 52.02], [5.05, 52.05], [5.02, 52.02]]
    el = element({"properties": {"natural": "wood"},
                  "geometry": {"type": "Polygon", "coordinates": [outer, inner]}})
    assert el["type"] == "relation"
    assert [m["role"] for m in el["members"]] == ["outer", "inner"]
    assert el["members"][0]["geometry"][0] == {"lon": 5.0, "lat": 52.0}


def test_along_spaces_points_and_headings():
    import numpy as np

    from inkmap.render.stamps import along
    pts = along([(0, 0), (100, 0), (100, 50)], 20, np.random.default_rng(0))
    assert 6 <= len(pts) <= 8
    assert abs(pts[0][2]) < 1e-9 and abs(pts[-1][2] - np.pi / 2) < 1e-9


def test_dashes_alternate_on_and_off_along_the_line():
    from inkmap.render.village import dashes
    pieces = dashes([(0, 0), (10, 0), (10, 10)], on=4, off=2)
    assert [(round(p[0][0]), round(p[0][1]), round(p[-1][0]), round(p[-1][1])) for p in pieces] == [
        (0, 0, 4, 0), (6, 0, 10, 0), (10, 2, 10, 6), (10, 8, 10, 10)]


def test_window_snaps_a_box_to_whole_tiles_of_its_zoom():
    from inkmap.domain.frame import Frame, unproject
    base = Frame(46.0, 18.0, 8, 1000, 1000)
    south, west = unproject(base, 300, 700)
    north, east = unproject(base, 700, 300)
    frame, origin = tiles.window(base, 2, (south, west, north, east))
    assert origin == (4, 4)  # zoom-2 pixels 1200..2800 -> tiles 4..10
    assert (frame.width, frame.height, frame.metres_per_px) == (1792, 1792, 2)
    cx, cy = base.project(frame.lat, frame.lon, 4)
    assert (round(cx), round(cy)) == (1920, 1920)


def test_a_name_on_a_kept_clear_line_moves_aside_instead_of_vanishing():
    from PIL import Image

    from inkmap.render.labels import Labels
    from inkmap.render.text import label_font

    labels = Labels(Image.new("RGB", (400, 400), "white"), edge_px=5, gap_px=2)
    labels.avoid([(0, 200), (400, 200)], 12)
    assert labels.put("Nagymáté", 200, 200, label_font(20), (0, 0, 0), 2)
    box = labels.taken[-1]
    assert box[3] < 194 or box[1] > 206  # wholly above or wholly below the line
    assert not labels.put("Nagymáté", 100, 100, label_font(20), (0, 0, 0), 2)  # once per map
    labels.avoid([(200, 0), (200, 400)], 12)  # a second line crossing the first: go beside
    assert labels.put("Kán", 200, 200, label_font(20), (0, 0, 0), 2)
    box = labels.taken[-1]
    assert box[2] < 194 or box[0] > 206
