"""Tests for timeline -> daily log sheet conversion.

Golden test: the FMCSA guide's "A Completed Log" (John Doe, Richmond -> Newark)
must produce one sheet whose duty-status totals are Off 10 / SB 1.75 / Drive
7.75 / On Duty 4.5, summing to exactly 24:00.
"""

from datetime import datetime, timedelta

from trips.services.hos import Segment, Status, TripParams, simulate
from trips.services.logsheet import build_log_days
from trips.tests.test_hos import john_doe_timeline


def test_john_doe_single_sheet_totals_match_the_guide():
    days = build_log_days(john_doe_timeline())
    assert len(days) == 1
    d = days[0].to_dict()["totals_hours"]
    assert d == {"off": 10.0, "sb": 1.75, "drive": 7.75, "onduty": 4.5}
    assert days[0].total_min == 1440
    assert days[0].to_dict()["total_miles_driving"] == 0.0  # timeline carries no miles


def test_every_day_sums_to_24h():
    p = TripParams(datetime(2026, 1, 5, 6, 0), cycle_used_h=0, deadhead_mi=0, loaded_mi=1600)
    days = build_log_days(simulate(p))
    assert len(days) >= 3
    for ld in days:
        assert ld.total_min == 1440


def test_segments_split_at_midnight():
    segs = [
        Segment(Status.OFF, datetime(2026, 1, 5, 0, 0), datetime(2026, 1, 5, 6, 0), 0, 0, "off"),
        Segment(Status.DRIVE, datetime(2026, 1, 5, 6, 0), datetime(2026, 1, 6, 4, 0), 0, 1100, "drive"),
        Segment(Status.OFF, datetime(2026, 1, 6, 4, 0), datetime(2026, 1, 7, 0, 0), 1100, 1100, "off"),
    ]
    days = build_log_days(segs)
    assert len(days) == 2
    # day 1 gets driving midnight-boundary clipped at 18h, day 2 gets 4h
    assert days[0].drive_min == 18 * 60
    assert days[1].drive_min == 4 * 60
    # miles are split proportionally
    assert 890 <= days[0].to_dict()["total_miles_driving"] <= 910


def test_remarks_recorded_at_each_duty_change():
    p = TripParams(datetime(2026, 1, 5, 6, 0), cycle_used_h=0, deadhead_mi=30, loaded_mi=300)
    segs = simulate(p)
    for i, s in enumerate(segs):
        s.location = f"City{i}, ST"
    days = build_log_days(segs)
    all_remarks = [r for ld in days for r in ld.remarks]
    labels = {r["label"] for r in all_remarks}
    assert "Pickup" in labels
    assert "Dropoff" in labels
    assert all("location" in r and "time" in r for r in all_remarks)


def test_full_trip_miles_driving_conserved_across_sheets():
    p = TripParams(datetime(2026, 1, 5, 6, 0), cycle_used_h=0, deadhead_mi=0, loaded_mi=1400)
    segs = simulate(p)
    days = build_log_days(segs)
    total = sum(ld.total_miles_driving for ld in days)
    assert abs(total - 1400) < 1.0
