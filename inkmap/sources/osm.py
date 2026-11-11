"""OpenStreetMap over the network: Nominatim to find a place, Overpass for a print's features.

Copied from gallery/sources/osm.py and owned here, with a second Overpass server: the main
one was busy while the mock-up was made.

Nominatim's usage policy (operations.osmfoundation.org/policies/nominatim, read 2026-10-09):
at most one request a second, a User-Agent that names the application, and no search as you
type. The page searches only when asked; search() spaces requests a second apart.
Map data (c) OpenStreetMap contributors, ODbL.
"""

import threading
import time

import httpx

USER_AGENT = "AmberglassPrints/1.0 (home wall-print renderer)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter")
RESULTS = 6
# Overpass is shared and often busy: these answers mean "try again", so each server is
# asked again, pausing this many seconds before its second, third and fourth attempt.
BUSY_STATUSES = (429, 502, 503, 504)
RETRY_PAUSES = (5, 10, 20)

_spacing = threading.Lock()
_last_search = 0.0


class OsmError(Exception):
    """OpenStreetMap could not answer: a network error, an error status or a failed query."""


def search(text: str) -> list[dict]:
    """[{name, lat, lon}] for a free-text place or address, best match first."""
    global _last_search
    with _spacing:
        time.sleep(max(0.0, _last_search + 1.0 - time.monotonic()))
        try:
            reply = httpx.get(NOMINATIM, params={"q": text, "format": "jsonv2", "limit": RESULTS},
                              headers={"User-Agent": USER_AGENT}, timeout=15)
        except httpx.HTTPError as error:
            raise OsmError(f"Nominatim: {error}") from error
        finally:
            _last_search = time.monotonic()
    if reply.status_code != 200:
        raise OsmError(f"Nominatim answered {reply.status_code}")
    return [{"name": r["display_name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
            for r in reply.json()]


def features(query: str) -> list[dict]:
    """The elements an Overpass QL query returns (`out geom`): the main server first, then the
    second one if the first fails."""
    failures = []
    for server in OVERPASS:
        try:
            return _ask(server, query)
        except OsmError as error:
            failures.append(str(error))
    raise OsmError("; ".join(failures))


def _ask(server: str, query: str) -> list[dict]:
    for attempt, pause in enumerate((*RETRY_PAUSES, None)):
        try:
            reply = httpx.post(server, data={"data": query}, headers={"User-Agent": USER_AGENT},
                               timeout=240)
        except httpx.TimeoutException as error:  # a query that hangs is not asked again
            raise OsmError(f"Overpass {server}: {error}") from error
        except httpx.HTTPError as error:
            failure = f"Overpass {server}: {error}"
        else:
            if reply.status_code == 200:
                return _elements(reply)
            failure = f"Overpass {server} answered {reply.status_code}"
            if reply.status_code not in BUSY_STATUSES:
                raise OsmError(failure)
        if pause is None:
            raise OsmError(f"{failure} (after {attempt + 1} attempts)")
        time.sleep(pause)


def _elements(reply: httpx.Response) -> list[dict]:
    try:
        body = reply.json()
    except ValueError as error:
        raise OsmError("Overpass sent something that is not JSON") from error
    # A query that runs out of time or memory still answers 200, with a remark.
    remark = body.get("remark", "")
    if "error" in remark.lower():
        raise OsmError(f"Overpass: {remark.strip()}")
    return body["elements"]
