"""Driving route via the public OSRM server (no API key), with a straight-line
fallback so a trip still plans when OSRM is unreachable or rate-limited.

OSRM demo server has no SLA — see PLAN.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import requests

_OSRM = "https://router.project-osrm.org/route/v1/driving/"
_TIMEOUT_S = 20
_FALLBACK_DETOUR = 1.2          # straight-line miles -> road miles
_FALLBACK_SPEED_MPH = 55.0
_METERS_PER_MILE = 1609.344


@dataclass
class Leg:
    distance_mi: float
    duration_h: float


@dataclass
class Route:
    distance_mi: float
    duration_h: float
    legs: list[Leg]
    geometry: list[tuple[float, float]]   # [(lat, lon), ...] along the whole route
    is_estimate: bool = False             # True when the fallback was used

    def avg_speed_mph(self) -> float:
        return self.distance_mi / self.duration_h if self.duration_h > 0 else _FALLBACK_SPEED_MPH

    def to_dict(self) -> dict:
        return {
            "distance_mi": round(self.distance_mi, 1),
            "duration_h": round(self.duration_h, 2),
            "legs": [{"distance_mi": round(l.distance_mi, 1), "duration_h": round(l.duration_h, 2)} for l in self.legs],
            "geometry": [[round(lat, 5), round(lon, 5)] for lat, lon in self.geometry],
            "is_estimate": self.is_estimate,
        }


def haversine_mi(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    d = 2 * math.asin(math.sqrt(
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    ))
    return d * 3958.7613


def route(points: list[tuple[float, float]]) -> Route:
    """`points` = [(lat, lon), ...], at least 2 (current, pickup, dropoff)."""
    if len(points) < 2:
        raise ValueError("need at least two points")
    try:
        return _osrm_route(points)
    except (requests.RequestException, ValueError, KeyError):
        return _straight_line_route(points)


def _osrm_route(points: list[tuple[float, float]]) -> Route:
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    resp = requests.get(
        _OSRM + coords,
        params={"overview": "full", "geometries": "geojson", "annotations": "false"},
        timeout=_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM: {data.get('code')}")

    r = data["routes"][0]
    legs = [Leg(l["distance"] / _METERS_PER_MILE, l["duration"] / 3600.0) for l in r["legs"]]
    geometry = [(lat, lon) for lon, lat in r["geometry"]["coordinates"]]
    return Route(
        distance_mi=r["distance"] / _METERS_PER_MILE,
        duration_h=r["duration"] / 3600.0,
        legs=legs,
        geometry=geometry,
    )


def _straight_line_route(points: list[tuple[float, float]]) -> Route:
    legs, geometry, total_mi = [], [points[0]], 0.0
    for a, b in zip(points, points[1:]):
        mi = haversine_mi(a, b) * _FALLBACK_DETOUR
        legs.append(Leg(mi, mi / _FALLBACK_SPEED_MPH))
        geometry.append(b)
        total_mi += mi
    return Route(
        distance_mi=total_mi,
        duration_h=total_mi / _FALLBACK_SPEED_MPH,
        legs=legs,
        geometry=geometry,
        is_estimate=True,
    )


def point_at_mile(geometry: list[tuple[float, float]], target_mi: float) -> tuple[float, float]:
    """Interpolate a (lat, lon) `target_mi` miles along the route polyline."""
    if not geometry:
        raise ValueError("empty geometry")
    if target_mi <= 0:
        return geometry[0]
    walked = 0.0
    for a, b in zip(geometry, geometry[1:]):
        step = haversine_mi(a, b)
        if walked + step >= target_mi:
            frac = (target_mi - walked) / step if step > 0 else 0.0
            return (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)
        walked += step
    return geometry[-1]
