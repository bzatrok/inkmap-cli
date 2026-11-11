# inkmap

Read `PROJECT_CONTEXT.md` before acting. It holds this project's purpose, invariants and what is out of scope.

## Layout

- `inkmap/domain/`: pure logic (the frame projection, region definitions). Imports stdlib only.
- `inkmap/render/`: the engraving renderer (numpy, Pillow): fills, relief, stamps, lines, labels. `fonts/` holds the OFL TTFs.
- `inkmap/sources/`: IO adapters: OSM PBF extracts via osmium, DEM tiles over HTTP.
- `inkmap/tiles.py`: slices a rendered scale into a `{z}/{x}/{y}.png` pyramid and writes `meta.json` (size, zooms, bbox, windows, where each name was drawn).
- `regions/<name>.toml`: a region's bbox, scales and titles; `[boxes]` limits a scale (only the finest) to its own box, cut into the pyramid as a window. `tracks` lists GPX files (next to the TOML) whose lines the names keep clear of.
- `site/`: the Leaflet page that shows a tile folder, and the embed snippet for gorica.hu.
- `data/`: downloaded OSM extracts and DEM tiles (ignored). `tiles/`: build output (ignored).

## Commands

- Setup: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`; `brew install osmium-tool`.
- Fetch region data: `.venv/bin/python -m inkmap fetch regions/arnhem.toml`.
- Render and tile: `.venv/bin/python -m inkmap render regions/arnhem.toml`.
- View: `python3 -m http.server -d site 8000` and open `http://localhost:8000`.

## Checks

- `.venv/bin/pytest` and `.venv/bin/ruff check .`. Both must pass.
- Which check binds which design principle:
  - Domain depends on nothing: `tests/test_boundaries.py` (domain imports stdlib only).
  - No layer skipping: `tests/test_boundaries.py` (`render/` never imports `sources/`).
  - No cycles between modules: not checked. Unenforced.
  - Size and complexity ceilings: ruff `C901`, max complexity 10 (`pyproject.toml`).
  - Config read in one place: the region TOML is read only by `inkmap/__main__.py`. Unenforced.
