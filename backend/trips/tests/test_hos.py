"""Tests for the HOS simulator + compliance checker.

Golden tests come straight from the FMCSA guide and its worked examples:
  * ``test_john_doe_*``  -> guide "A Completed Grid / A Completed Log" (Richmond -> Newark)
  * ``test_split_*``     -> §395.1(g) split sleeper berth (7/3 and 8/2)

The rest exercise the planner's event handling.
"""

from datetime import datetime, timedelta

import pytest

from trips.services.hos import (
    CYCLE_LIMIT_H,
    DRIVE_LIMIT_H,
    Segment,
    Status,
    TripParams,
    WINDOW_LIMIT_H,
    check_compliance,
    simulate,
)

MIN = timedelta(minutes=1)


def seg(status, day, h0, m0, h1, m1, label="", note=""):
    """Build a Segment on `day` (a date) from h0:m0 to h1:m1 (24h clock, no miles)."""
    start = datetime(day.year, day.month, day.day) + timedelta(hours=h0, minutes=m0)
    end = datetime(day.year, day.month, day.day) + timedelta(hours=h1, minutes=m1)
    return Segment(status, start, end, 0.0, 0.0, label, note)


def totals_by_status(segments):
    out = {s: 0.0 for s in Status}
    for x in segments:
        out[x.status] += x.hours
    return out


# ───────────────────────────────────────────────────────────────────────────
# Golden test 2 — FMCSA guide "A Completed Log": John Doe, Richmond VA -> Newark NJ
# ───────────────────────────────────────────────────────────────────────────
def john_doe_timeline():
    d = datetime(2021, 4, 9).date()
    return [
        seg(Status.OFF, d, 0, 0, 6, 0),                       # midnight -> report
        seg(Status.ONDUTY, d, 6, 0, 7, 30, "Load / dispatch / pre-trip"),  # Richmond, VA
        seg(Status.DRIVE, d, 7, 30, 9, 0),
        seg(Status.ONDUTY, d, 9, 0, 9, 30, "Fuel"),           # Fredericksburg, VA
        seg(Status.DRIVE, d, 9, 30, 12, 0),
        seg(Status.OFF, d, 12, 0, 13, 0, "Lunch"),            # Baltimore, MD (carrier says off duty)
        seg(Status.DRIVE, d, 13, 0, 15, 0),
        seg(Status.ONDUTY, d, 15, 0, 15, 30, "Delivery"),     # Philadelphia, PA
        seg(Status.DRIVE, d, 15, 30, 16, 0),
        seg(Status.SB, d, 16, 0, 17, 45),                     # Cherry Hill, NJ
        seg(Status.DRIVE, d, 17, 45, 19, 0),
        seg(Status.ONDUTY, d, 19, 0, 21, 0, "Post-trip / paperwork"),  # Newark, NJ
        seg(Status.OFF, d, 21, 0, 24, 0),
    ]


def test_john_doe_grid_totals_match_guide():
    t = totals_by_status(john_doe_timeline())
    assert round(t[Status.OFF], 2) == 10.00
    assert round(t[Status.SB], 2) == 1.75
    assert round(t[Status.DRIVE], 2) == 7.75
    assert round(t[Status.ONDUTY], 2) == 4.50
    assert round(sum(t.values()), 2) == 24.00


def test_john_doe_has_no_violations():
    # Guide: "There is no problem with being on duty longer than 14 hours as long
    # as there is no CMV driving time after the 14th hour."
    assert check_compliance(john_doe_timeline(), start_cycle_h=0.0) == []


# ───────────────────────────────────────────────────────────────────────────
# Golden test 1 — §395.1(g) split sleeper berth
#
# The guide's own worked example (p. 7-9) targets these per-calculation-period
# numbers: driving 10 / 11 / 10.5 h (each <= 11) and window 12 / 12 / 12 h
# (each <= 14), with no violation. The OCR'd diagram in the repo copy is not
# recoverable to an exact minute-by-minute timeline, so the golden cases below
# use the two canonical split shapes (7/3 and 8/2) that §395.1(g) defines, each
# with a known-good answer, and assert the same substance: a full split rotation
# keeps driving <= 11 across the pair and the 14-hour window intact.
# ───────────────────────────────────────────────────────────────────────────
def split_8_2_timeline():
    d = datetime(2026, 1, 5).date()
    nxt = d + timedelta(days=1)
    return [
        seg(Status.DRIVE, d, 6, 0, 14, 0),          # 8h driving
        seg(Status.SB, d, 14, 0, 22, 0),            # 8h sleeper — long leg
        seg(Status.DRIVE, d, 22, 0, 24, 0),         # 2h driving  (10h total this pair)
        seg(Status.DRIVE, nxt, 0, 0, 1, 0),         #   +1h  -> 11h across the pair
        seg(Status.OFF, nxt, 1, 0, 3, 0, "split short leg"),  # 2h off — completes 10h
        seg(Status.DRIVE, nxt, 3, 0, 6, 0),         # fresh shift after the pair
    ]


def split_7_3_timeline():
    d = datetime(2026, 1, 5).date()
    nxt = d + timedelta(days=1)
    return [
        seg(Status.DRIVE, d, 6, 0, 13, 0),          # 7h driving
        seg(Status.SB, d, 13, 0, 20, 0),            # 7h sleeper — long leg
        seg(Status.DRIVE, d, 20, 0, 24, 0),         # 4h driving -> 11h across the pair
        seg(Status.OFF, nxt, 0, 0, 3, 0),           # 3h off — completes 10h
        seg(Status.DRIVE, nxt, 3, 0, 6, 0),
    ]


@pytest.mark.parametrize("timeline", [split_8_2_timeline(), split_7_3_timeline()])
def test_split_sleeper_rotation_is_compliant(timeline):
    assert check_compliance(timeline, start_cycle_h=0.0) == []


def test_split_long_leg_pauses_the_14h_window():
    # Without the sleeper-berth exclusion this rotation drives past hour 14 of the
    # window and must fail; the checker must NOT flag it because the 8h sleeper
    # leg is excluded from the window.
    d = datetime(2026, 1, 5).date()
    nxt = d + timedelta(days=1)
    timeline = [
        seg(Status.DRIVE, d, 6, 0, 14, 0),      # 8h drive, window now at 8h
        seg(Status.SB, d, 14, 0, 22, 0),        # 8h sleeper (excluded)
        seg(Status.DRIVE, d, 22, 0, 24, 0),     # window elapsed = 18h wall - 8h = 10h
        seg(Status.DRIVE, nxt, 0, 0, 1, 0),     # window elapsed = 19h wall - 8h = 11h  <= 14
        seg(Status.OFF, nxt, 1, 0, 3, 0),
    ]
    assert check_compliance(timeline) == []


def test_checker_flags_a_plain_14h_window_bust():
    d = datetime(2026, 1, 5).date()
    timeline = [
        seg(Status.ONDUTY, d, 6, 0, 8, 0),
        seg(Status.DRIVE, d, 8, 0, 16, 0),
        seg(Status.ONDUTY, d, 16, 0, 20, 0),
        seg(Status.DRIVE, d, 20, 0, 21, 0),      # 15h after shift start -> bust
    ]
    rules = {v.rule for v in check_compliance(timeline)}
    assert "14h driving window" in rules


def test_checker_flags_11h_driving_bust():
    d = datetime(2026, 1, 5).date()
    timeline = [
        seg(Status.DRIVE, d, 6, 0, 12, 0),      # 6h
        seg(Status.OFF, d, 12, 0, 12, 45),      # 45-min break
        seg(Status.DRIVE, d, 12, 45, 18, 45),   # +6h -> 12h this shift
    ]
    rules = {v.rule for v in check_compliance(timeline)}
    assert "11h driving limit" in rules


def test_checker_flags_missing_30min_break():
    d = datetime(2026, 1, 5).date()
    timeline = [seg(Status.DRIVE, d, 6, 0, 15, 0)]  # 9h straight, no break
    rules = {v.rule for v in check_compliance(timeline)}
    assert "30-min break" in rules


# ───────────────────────────────────────────────────────────────────────────
# Planner
# ───────────────────────────────────────────────────────────────────────────
START = datetime(2026, 1, 5, 6, 0)


def assert_well_formed(segs, total_mi):
    assert segs, "no segments produced"
    for a, b in zip(segs, segs[1:]):
        assert a.end == b.start, "segments must be contiguous in time"
        assert b.start_mi >= a.start_mi - 1e-6, "mileposts must be monotonic"
    assert abs(segs[-1].end_mi - total_mi) < 1e-3, "final milepost must equal route length"
    assert segs[-1].label == "Post-trip inspection"


def labels(segs):
    return [s.label for s in segs]


def test_short_trip_needs_no_rest():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=30, loaded_mi=100)
    segs = simulate(p)
    assert_well_formed(segs, 130)
    assert "10-hour rest" not in labels(segs)
    assert "34-hour restart" not in labels(segs)
    assert "Pickup" in labels(segs) and "Dropoff" in labels(segs)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_trip_over_11h_driving_inserts_10h_rest():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=750)
    segs = simulate(p)
    assert_well_formed(segs, 750)
    assert "10-hour rest" in labels(segs)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_trip_over_8h_driving_inserts_30min_break():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=20, loaded_mi=470)
    segs = simulate(p)
    assert "30-minute break" in labels(segs)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_fuel_stop_every_1000_miles():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=1300)
    segs = simulate(p)
    fuel = [s for s in segs if s.label == "Fuel stop"]
    assert len(fuel) == 1
    assert 990 <= fuel[0].start_mi <= 1000 + 1e-6
    assert check_compliance(segs, p.cycle_used_h) == []


def test_two_fuel_stops_on_a_long_trip():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=2200)
    segs = simulate(p)
    assert len([s for s in segs if s.label == "Fuel stop"]) == 2


def test_long_trip_triggers_34h_restart():
    p = TripParams(START, cycle_used_h=50, deadhead_mi=0, loaded_mi=2400)
    segs = simulate(p)
    assert "34-hour restart" in labels(segs)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_cycle_already_exhausted_restarts_before_driving():
    p = TripParams(START, cycle_used_h=70, deadhead_mi=0, loaded_mi=200)
    segs = simulate(p)
    assert segs[0].label == "34-hour restart"
    assert segs[0].status == Status.OFF
    assert check_compliance(segs, p.cycle_used_h) == []


def test_cycle_nearly_exhausted_restarts_early():
    p = TripParams(START, cycle_used_h=69, deadhead_mi=0, loaded_mi=600)
    segs = simulate(p)
    restart = next(s for s in segs if s.label == "34-hour restart")
    assert restart.start - START < timedelta(hours=2)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_split_sleeper_mode_uses_sleeper_berth():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=900, use_split_sleeper=True)
    segs = simulate(p)
    sb = [s for s in segs if s.status == Status.SB]
    assert sb, "split mode should produce sleeper-berth segments"
    assert any("Split" in s.note for s in sb)
    assert "10-hour rest" not in labels(segs)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_split_sleeper_off_by_default_uses_plain_rest():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=900)
    segs = simulate(p)
    assert not [s for s in segs if s.status == Status.SB]
    assert "10-hour rest" in labels(segs)


def test_multi_day_trip_spans_calendar_days():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=1500)
    segs = simulate(p)
    days = {s.start.date() for s in segs} | {s.end.date() for s in segs}
    assert len(days) >= 3


@pytest.mark.parametrize("cycle", [0, 10, 35, 55, 68])
@pytest.mark.parametrize("deadhead,loaded", [(0, 120), (40, 600), (0, 1800), (150, 2600)])
def test_planner_output_is_always_compliant(cycle, deadhead, loaded):
    p = TripParams(START, cycle_used_h=cycle, deadhead_mi=deadhead, loaded_mi=loaded)
    segs = simulate(p)
    assert_well_formed(segs, deadhead + loaded)
    assert check_compliance(segs, p.cycle_used_h) == []


@pytest.mark.parametrize("deadhead,loaded", [(0, 120), (40, 600), (0, 1800)])
def test_planner_split_mode_is_always_compliant(deadhead, loaded):
    p = TripParams(START, cycle_used_h=20, deadhead_mi=deadhead, loaded_mi=loaded, use_split_sleeper=True)
    segs = simulate(p)
    assert_well_formed(segs, deadhead + loaded)
    assert check_compliance(segs, p.cycle_used_h) == []


def test_no_driving_segment_exceeds_a_single_shift_limit():
    p = TripParams(START, cycle_used_h=0, deadhead_mi=0, loaded_mi=1800)
    segs = simulate(p)
    for s in segs:
        if s.status == Status.DRIVE:
            assert s.hours <= DRIVE_LIMIT_H + 1e-6
            assert s.hours <= WINDOW_LIMIT_H + 1e-6
