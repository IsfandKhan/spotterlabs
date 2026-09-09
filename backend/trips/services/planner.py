"""Orchestrates a trip plan: geocode -> route -> HOS simulate -> daily logs.

Returns a plain dict (the API response shape). The view persists it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import geocode, routing
from .hos import Segment, Status, TripParams, check_compliance, simulate
from .logsheet import build_log_days

_MAX_GEOMETRY_POINTS = 500
_STOP_LABELS = {
    "Pickup", "Dropoff", "Fuel stop", "30-minute break",
    "10-hour rest", "34-hour restart", "Sleeper berth", "Split break (2 hr)",
}


@dataclass
class PlanInput:
    current_location: str
    pickup_location: str
    dropoff_location: str
    current_cycle_used_h: float
    departure_at: datetime
    use_split_sleeper: bool = False


def plan_trip(inp: PlanInput) -> dict:
    cur = geocode.geocode(inp.current_location)
    pick = geocode.geocode(inp.pickup_location)
    drop = geocode.geocode(inp.dropoff_location)

    rt = routing.route([(cur.lat, cur.lon), (pick.lat, pick.lon), (drop.lat, drop.lon)])
    deadhead_mi = rt.legs[0].distance_mi
    loaded_mi = rt.legs[1].distance_mi if len(rt.legs) > 1 else 0.0

    params = TripParams(
        start_dt=inp.departure_at.replace(tzinfo=None),
        cycle_used_h=inp.current_cycle_used_h,
        deadhead_mi=deadhead_mi,
        loaded_mi=loaded_mi,
        avg_speed_mph=rt.avg_speed_mph(),
        use_split_sleeper=inp.use_split_sleeper,
    )
    segments = simulate(params)
    pickup_label = geocode.reverse(pick.lat, pick.lon) or _short(pick.display_name)
    dropoff_label = geocode.reverse(drop.lat, drop.lon) or _short(drop.display_name)
    _label_locations(segments, rt.geometry, pickup_label, dropoff_label)

    violations = check_compliance(segments, inp.current_cycle_used_h)
    log_days = build_log_days(segments)

    drive_h = sum(s.hours for s in segments if s.status == Status.DRIVE)
    duty_h = sum(s.hours for s in segments if s.status in (Status.DRIVE, Status.ONDUTY))
    stops = _stops(segments, rt.geometry)

    return {
        "input": {
            "current_location": inp.current_location,
            "pickup_location": inp.pickup_location,
            "dropoff_location": inp.dropoff_location,
            "current_cycle_used_h": inp.current_cycle_used_h,
            "departure_at": params.start_dt.isoformat(),
            "use_split_sleeper": inp.use_split_sleeper,
        },
        "geocoded": {"current": cur.to_dict(), "pickup": pick.to_dict(), "dropoff": drop.to_dict()},
        "route": {
            "distance_mi": round(rt.distance_mi, 1),
            "deadhead_mi": round(deadhead_mi, 1),
            "loaded_mi": round(loaded_mi, 1),
            "duration_h": round(rt.duration_h, 2),
            "avg_speed_mph": round(rt.avg_speed_mph(), 1),
            "is_estimate": rt.is_estimate,
            "geometry": _downsample(rt.geometry),
        },
        "summary": {
            "total_miles": round(rt.distance_mi, 1),
            "total_drive_hours": round(drive_h, 2),
            "total_duty_hours": round(duty_h, 2),
            "total_days": len(log_days),
            "num_stops": len(stops),
            "num_restarts": sum(1 for s in segments if s.label == "34-hour restart"),
            "trip_start": segments[0].start.isoformat(),
            "trip_end": segments[-1].end.isoformat(),
        },
        "timeline": [s.to_dict() for s in segments],
        "stops": stops,
        "log_days": [d.to_dict() for d in log_days],
        "hos_notes": _notes(params, rt, violations),
        "compliance": {"ok": not violations, "violations": [v.to_dict() for v in violations]},
    }


# ── helpers ────────────────────────────────────────────────────────────────
def _label_locations(segments, geometry, pickup_label, dropoff_label):
    """Reverse-geocode the milepost of every duty-status change (guide §395.8)."""
    prev_status = None
    for s in segments:
        if s.status == prev_status:
            continue
        prev_status = s.status
        if s.label == "Pickup":
            s.location = pickup_label
        elif s.label in ("Dropoff", "Post-trip inspection"):
            s.location = dropoff_label
        elif geometry:
            lat, lon = routing.point_at_mile(geometry, s.start_mi)
            s.location = geocode.reverse(lat, lon)


def _stops(segments, geometry):
    out = []
    for s in segments:
        if s.label not in _STOP_LABELS:
            continue
        lat, lon = routing.point_at_mile(geometry, s.start_mi) if geometry else (None, None)
        out.append({
            "kind": s.label,
            "status": s.status.value,
            "location": s.location,
            "mile": round(s.start_mi, 1),
            "start": s.start.isoformat(),
            "end": s.end.isoformat(),
            "hours": round(s.hours, 2),
            "lat": lat,
            "lon": lon,
        })
    return out


def _notes(params, rt, violations):
    notes = [
        f"Route {rt.distance_mi:.0f} mi total "
        f"({params.deadhead_mi:.0f} mi deadhead + {params.loaded_mi:.0f} mi loaded) "
        f"at ~{rt.avg_speed_mph():.0f} mph.",
        "70 hr / 8 day cycle modeled as a flat debit from the entered "
        "‘current cycle used’ — hours do not age out mid-trip; only a 34-hour "
        "restart clears the cycle (see PLAN.md).",
        "Fuel stop (30 min on duty) every 1,000 mi; 15-min pre-trip and post-trip "
        "inspection each driving day; 1 hr on duty for pickup and for dropoff.",
    ]
    if params.use_split_sleeper:
        notes.append("Split sleeper berth enabled: 8/2 split (8 hr sleeper + 2 hr off).")
    if rt.is_estimate:
        notes.append("Routing service unavailable — distances are straight-line "
                     "estimates ×1.2 at 55 mph.")
    if violations:
        notes.append(f"WARNING: {len(violations)} HOS violation(s) in the generated schedule.")
    return notes


def _downsample(geometry):
    if len(geometry) <= _MAX_GEOMETRY_POINTS:
        return [[round(lat, 5), round(lon, 5)] for lat, lon in geometry]
    step = len(geometry) / _MAX_GEOMETRY_POINTS
    idx = sorted({int(i * step) for i in range(_MAX_GEOMETRY_POINTS)} | {len(geometry) - 1})
    return [[round(geometry[i][0], 5), round(geometry[i][1], 5)] for i in idx]


def _short(display_name: str) -> str:
    parts = [p.strip() for p in display_name.split(",")]
    return ", ".join(parts[:2]) if len(parts) >= 2 else display_name
