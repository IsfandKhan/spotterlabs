"""Address -> coordinates (no API key).

Photon (photon.komoot.io) is tried first — it's the same source the frontend
autocomplete uses, so any address the user picked from the dropdown resolves.
Nominatim is the fallback and still does reverse-geocoding for the remarks column.

Nominatim usage policy: <=1 request/second, real User-Agent, cache results.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import requests

_PHOTON = "https://photon.komoot.io/api/"
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
_UA = "spotterlabs-eld-trip-planner/1.0 (assessment project)"
_MIN_INTERVAL_S = 1.1
_TIMEOUT_S = 15

_lock = threading.Lock()
_last_call = 0.0
_cache: dict[str, "Place"] = {}
_reverse_cache: dict[tuple[float, float], str] = {}

_US_STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


class GeocodeError(Exception):
    pass


@dataclass(frozen=True)
class Place:
    query: str
    lat: float
    lon: float
    display_name: str

    def to_dict(self) -> dict:
        return {"query": self.query, "lat": self.lat, "lon": self.lon, "label": self.display_name}


def _get(url: str, params: dict) -> requests.Response:
    """Rate-limited GET honoring Nominatim's <=1 req/s policy."""
    global _last_call
    with _lock:
        wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            return requests.get(url, params=params, headers={"User-Agent": _UA}, timeout=_TIMEOUT_S)
        finally:
            _last_call = time.monotonic()


def geocode(address: str) -> Place:
    key = " ".join(address.split()).lower()
    if not key:
        raise GeocodeError("empty address")
    if key in _cache:
        return _cache[key]

    place = None
    try:
        place = _photon_lookup(address)
    except (requests.RequestException, ValueError, KeyError, IndexError):
        place = None
    if place is None:
        place = _nominatim_lookup(address)  # raises GeocodeError if this misses too

    _cache[key] = place
    return place


def _photon_lookup(address: str) -> Place | None:
    resp = _get(_PHOTON, {"q": address, "limit": 1, "lang": "en"})
    if resp.status_code != 200:
        return None
    feats = resp.json().get("features") or []
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"][:2]
    p = feats[0].get("properties", {})
    label = ", ".join(
        x for x in (p.get("name"), p.get("city"), p.get("state"), p.get("country")) if x
    )
    return Place(address, float(lat), float(lon), label or address)


def _nominatim_lookup(address: str) -> Place:
    resp = _get(_NOMINATIM, {"q": address, "format": "jsonv2", "limit": 1, "addressdetails": 0})
    if resp.status_code != 200:
        raise GeocodeError(f"Nominatim HTTP {resp.status_code}")
    hits = resp.json()
    if not hits:
        raise GeocodeError(f"no match for {address!r}")
    top = hits[0]
    return Place(address, float(top["lat"]), float(top["lon"]), top.get("display_name", address))


def reverse(lat: float, lon: float) -> str:
    """Coordinates -> "City, ST" for the §395.8 remarks column. Best-effort:
    returns "" if the lookup fails so a trip never breaks on a label."""
    key = (round(lat, 3), round(lon, 3))
    if key in _reverse_cache:
        return _reverse_cache[key]
    try:
        resp = _get(_NOMINATIM_REVERSE, {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10})
        addr = resp.json().get("address", {}) if resp.status_code == 200 else {}
    except (requests.RequestException, ValueError):
        addr = {}

    city = (
        addr.get("city") or addr.get("town") or addr.get("village")
        or addr.get("hamlet") or addr.get("municipality") or addr.get("county") or ""
    )
    region = addr.get("state") or ""
    st = _US_STATE_ABBR.get(region.lower(), region)
    label = ", ".join(p for p in (city, st) if p)
    _reverse_cache[key] = label
    return label

