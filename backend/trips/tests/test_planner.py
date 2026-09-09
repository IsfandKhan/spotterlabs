"""_label_locations must stop reverse-geocoding once its time budget is spent,
so a pathological route can't stall the gunicorn worker. No network here."""

from datetime import datetime

from trips.services import planner
from trips.services.hos import Segment, Status


def _seg(status, mi):
    t = datetime(2026, 1, 1)
    return Segment(status=status, start=t, end=t, start_mi=mi, end_mi=mi, label="Driving")


def test_label_locations_honors_time_budget(monkeypatch):
    # clock jumps 8s per read: deadline = 0 + 20, so calls at t=8 and t=16 pass, t>=24 stop
    clock = iter(range(0, 10_000, 8))
    monkeypatch.setattr(planner.time, "monotonic", lambda: next(clock))

    calls = []
    monkeypatch.setattr(planner.geocode, "reverse", lambda lat, lon: calls.append((lat, lon)) or "X")

    segments = [_seg(Status.DRIVE if i % 2 else Status.OFF, i * 100) for i in range(50)]
    planner._label_locations(segments, [(0.0, 0.0), (1.0, 1.0)], "PU", "DO")

    assert len(calls) == 2  # not one per milepost
