# Project Context — inkmap

<!-- The project map. Outlives every effort in .handovers/. -->
<!-- Write standing conditions, not current status. See ~/.claude/skills/project-context. -->

**Exposure:** published (public repo bzatrok/inkmap-cli since 2026-11-11, MIT; the rendered map is public on gorica.hu)

## Destination
Real places drawn as a hand-engraved medieval map in the style of Kingdom Come: Deliverance 2's
world map (parchment, hachured hills, stamped trees and houses, hand-drawn roads, serif names),
from OpenStreetMap and elevation data. Pre-rendered tile pyramids of bounded regions, panned in a
browser; the same renders as E1002 screens and framed prints.

## Intent, verbatim
> how'd one go about building a converter to generate KCD2 style maps from google maps/OSRM/other data?
> i'd want to be able to pan, like an embedded map.
> i'd want to embed this on gorica.hu as well, that's the panning idea
> other use is eink frame or print
> a slightly larger area than my immediate surroundings. dieren to oosterbeek to south of apeldoorn, down to nijmwegen … want hillier regions too

## Stakeholders
- Ben — owns everything: the renderer, the region list, gorica.hu where it is embedded.
- OpenStreetMap contributors (ODbL) — the map data; attribution travels with every public render.

## Invariants
- Data is OpenStreetMap (Geofabrik extracts, Overpass only for small frames), an open DEM
  (Terrarium) and ESA WorldCover tree cover (CC BY 4.0).
  Never Google Maps data: its terms forbid derived maps. OSRM is a router, not a source.
- Output is static: tile folders and images. No server renders at view time.
- The style is a style-alike, never the game's own assets: fonts OFL, sprites drawn here.
- Public renders carry the OSM attribution (ODbL).
- Python 3.12, numpy and Pillow, as the renderer it was copied from (XteinkX4ProDashboard
  `prints/render/`). Copied and owned here, not imported: this style changes every layer and
  must not bend the print output over there.

## Decisions so far
<!-- index only: gist + rejected alternative, linking the ADR or handover map -->
- 2026-11-10 — Pan by pre-rendering a bounded region at a few scales and slicing it into tiles,
  the way the game's own map is one image zoomed into. Rejected: on-demand tiles of any place
  (needs a database, seamless deterministic stamps, global label placement; about twice the
  renderer's effort); a MapLibre vector style (no hachures, no line wobble: parchment-themed
  OSM, not engraving).
- 2026-11-10 — First region: Dieren–Oosterbeek–south of Apeldoorn–Nijmegen, including the
  Veluwe hills (Posbank), so relief shows. Rejected: Arnhem city only (flat, no relief to test).
- 2026-11-10 — Three scales: region, town, street. Rejected: two (house stamps and road wobble
  only show at street scale).
- 2026-11-10 — Region data from a Geofabrik PBF cut with osmium, not Overpass: the region is
  ~37×26 km and Overpass times out or truncates at that size.

- 2026-11-10 — Woods are OSM woods ∪ WorldCover tree cover, with a clearing around every
  building and built-up area (gardens and orchards read as trees and swallowed Gorica).
  Rejected: Google imagery (terms), raw Sentinel-2 (would need our own classification).
- 2026-11-10 — Buildings at the fine scales are their OSM footprints grown 1.7x about their
  centre, so a hamlet reads as one (Ben: "every house should be the shape it is"). Rejected:
  generic house stamps there (kept for the coarse scales, where footprints are too small).
- 2026-11-10 — Points of interest come from OSM tags (churches, castles, ruins, named peaks,
  viewpoints, towers, monuments, inns), drawn as procedural ink glyphs that yield to place
  names. Rejected: Mapy.cz (Seznam's data is not open).
- 2026-11-10 — Houses at the coarse scales line the roads through built-up land and face them,
  with a sparse scatter between; forests mix three tree shapes, two sizes and a slow noise so
  they clump; tree stamps keep clear of roads. Rejected: grid stamps (confetti towns, carpet
  forests).
- 2026-11-10 — Tiles reach gorica.hu as WebP files in that repo (`public/terkep/gorica/`, 32 MB,
  1,602 files; Workers static assets allow 20,000), shown by a dependency-free viewer written
  there (TileMap.astro: crossfade between scales, flyTo for the scrolling timeline). Rejected:
  Leaflet (new package + CSP change on a site that forbids both; wheel zoom would fight the
  page scroll), PNG tiles (204 MB), an R2 bucket (infra for a static folder).
- 2026-11-11 — Gorica gets 5 km of air round the old box so the map can be moved about on a phone;
  the street scale is drawn only inside the old box and cut into the pyramid as a window (`[boxes]`,
  `windows` in meta.json). Rejected: street detail over the whole wider box (about 4.4 times the
  tiles and a street render too large to hold in memory).
- 2026-11-11 — Names nudge aside (up, down, sideways, diagonally) instead of being dropped, keep off the kék kör's GPX line, and go on the map once per name. Rejected: the site drawing the trail under the tiles (the trail must stay readable), and a keep-out only in the viewer (the viewer cannot move ink that is baked into the tiles).
- 2026-11-11 — meta.json carries, per zoom, the box every name was drawn in (`labels`), so a viewer can ring the name on the map itself when a stop is chosen. Rejected: a name chip next to the pin (Ben: the parchment nameplate is what should light up), and re-drawing ribbons in the viewer (they stay baked ink).

## Not yet specified
<!-- the fog: questions not yet sharp, and work deliberately unfinished with its reason -->
- Which E1002/print sizes get a cut of the region and whether they dither here or in the
  Terminus pipeline — waits on the first approved render.
- Second region (another in Hungary; Prague) — waits on the first one.

## Out of scope
<!-- ruled out for the project, with the reason. Never graduates. -->
- Google Maps as a data source — its terms of service forbid deriving maps from it.
- Rendering tiles on demand for arbitrary places — the panning idea is a bounded world, and
  the static output is what makes hosting free.
- Reproducing the game's actual map art, fonts or place names — style-alike only.

## Efforts
- [.handovers/handover_log.md](.handovers/handover_log.md)
