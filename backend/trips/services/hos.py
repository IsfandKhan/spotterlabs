"""FMCSA Hours-of-Service simulator + compliance checker.

Pure Python, no Django. Every limit traces to the repo's copy of the FMCSA
*Interstate Truck Driver's Guide to Hours of Service*
(`fmcsa-hos-395-drivers-guide-to-hos-2022-04-28-0-1-.md`); section refs are inline.

Two public entry points:
  * ``simulate(params)``        -> list[Segment]   the trip planner
  * ``check_compliance(segs)``  -> list[Violation] validator / test oracle

Modeling decisions that are not verbatim in the reg live in ``PLAN.md`` (flat-debit
cycle, 30-min fuel stop every 1000 mi, 15-min pre/post-trip inspection).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# ── HOS limits — property-carrying driver, 70 hr / 8 day ─────────────────────
DRIVE_LIMIT_H = 11.0          # §395.3(a)(3)      max driving per shift
WINDOW_LIMIT_H = 14.0         # §395.3(a)(2)      consecutive-hour driving window
BREAK_AFTER_DRIVE_H = 8.0     # §395.3(a)(3)(ii)  30-min break after 8h cumulative driving
BREAK_MIN_H = 0.5
CYCLE_LIMIT_H = 70.0          # §395.3(b)         70 hr on-duty / rolling 8 days
RESTART_H = 34.0             # §395.3(c)         34 consecutive hr off -> cycle resets
DAILY_RESET_H = 10.0         # §395.3(a)         10 consecutive hr off -> 11h & 14h restart
SPLIT_LONG_MIN_H = 7.0       # §395.1(g)         sleeper leg of a split (>=7, sleeper berth)
SPLIT_SHORT_MIN_H = 2.0      # §395.1(g)         other leg (>=2, sleeper or off duty)
SPLIT_PAIR_MIN_H = 10.0

# ── assessment / PLAN.md assumptions ────────────────────────────────────────
PICKUP_H = 1.0
DROPOFF_H = 1.0
FUEL_EVERY_MI = 1000.0
FUEL_H = 0.5
PRETRIP_H = 0.25
POSTTRIP_H = 0.25
SPLIT_LONG_H = 8.0           # planner uses an 8/2 split
SPLIT_SHORT_H = 2.0
DEFAULT_SPEED_MPH = 55.0

EPS = 1e-6
_ITER_GUARD = 5000


class Status(str, Enum):
    OFF = "off"       # line 1  off duty
    SB = "sb"         # line 2  sleeper berth
    DRIVE = "drive"   # line 3  driving
    ONDUTY = "onduty" # line 4  on duty (not driving)


@dataclass
class Segment:
    status: Status
    start: datetime
    end: datetime
    start_mi: float
    end_mi: float
    label: str
    note: str = ""
    location: str = ""          # "City, ST" — filled by the caller (reverse geocode)

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0

    @property
    def miles(self) -> float:
        return self.end_mi - self.start_mi

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "start_mi": round(self.start_mi, 1),
            "end_mi": round(self.end_mi, 1),
            "label": self.label,
            "note": self.note,
            "location": self.location,
        }


@dataclass
class TripParams:
    start_dt: datetime
    cycle_used_h: float
    deadhead_mi: float          # current location -> pickup
    loaded_mi: float            # pickup -> dropoff
    avg_speed_mph: float = DEFAULT_SPEED_MPH
    use_split_sleeper: bool = False


@dataclass
class Violation:
    rule: str
    at: datetime
    detail: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "at": self.at.isoformat(), "detail": self.detail}


# ───────────────────────────────────────────────────────────────────────────
# Planner
# ───────────────────────────────────────────────────────────────────────────
def simulate(p: TripParams) -> list[Segment]:
    """Walk the route mile by mile, inserting rests / breaks / fuel / restarts
    so the resulting duty-status timeline never violates the HOS rules.

    Route = deadhead leg (current -> pickup) + loaded leg (pickup -> dropoff).
    Distances only; the caller interpolates lat/lon for each milepost.
    """
    speed = p.avg_speed_mph or DEFAULT_SPEED_MPH
    pickup_mi = max(0.0, p.deadhead_mi)
    total_mi = pickup_mi + max(0.0, p.loaded_mi)

    segs: list[Segment] = []
    now = p.start_dt
    pos = 0.0

    shift_drive = 0.0            # driving hours this shift (since last full reset)
    since_break = 0.0           # cumulative driving since last >=30 min non-driving
    window_start: datetime | None = None
    cycle = max(0.0, p.cycle_used_h)
    mi_since_fuel = 0.0
    picked_up = pickup_mi <= EPS
    split_long_pending = False   # took the 8h sleeper leg, owe the 2h partner

    def emit(status: Status, hours: float, mi: float, label: str, note: str = "") -> None:
        nonlocal now, pos
        end = now + timedelta(hours=hours)
        segs.append(Segment(status, now, end, pos, pos + mi, label, note))
        now = end
        pos += mi

    # §395.3(b): already at/over the cycle -> cannot drive until a 34-hr restart.
    if cycle >= CYCLE_LIMIT_H - EPS:
        emit(Status.OFF, RESTART_H, 0.0, "34-hour restart", "Cycle exhausted at trip start")
        cycle = 0.0

    guard = 0
    while not (picked_up and pos >= total_mi - EPS):
        guard += 1
        if guard > _ITER_GUARD:  # pragma: no cover - safety net
            raise RuntimeError(f"simulate: iteration guard tripped at mi={pos:.1f}")

        # §395.3(b): no useful shift left in the cycle -> 34-hr restart now,
        # rather than burn a 10-hr rest first and restart anyway.
        if window_start is None and cycle >= CYCLE_LIMIT_H - PRETRIP_H - EPS:
            emit(Status.OFF, RESTART_H, 0.0, "34-hour restart")
            cycle = 0.0
            shift_drive = since_break = 0.0
            split_long_pending = False
            continue

        if window_start is None:                      # start / resume a shift
            emit(Status.ONDUTY, PRETRIP_H, 0.0, "Pre-trip inspection")
            window_start = segs[-1].start
            cycle += PRETRIP_H
            shift_drive = 0.0
            since_break = 0.0

        target_mi = (pickup_mi if not picked_up else total_mi) - pos
        window_elapsed = _hours(now - window_start)

        drive_h = max(0.0, min(
            DRIVE_LIMIT_H - shift_drive,
            WINDOW_LIMIT_H - window_elapsed,
            BREAK_AFTER_DRIVE_H - since_break,
            CYCLE_LIMIT_H - cycle,
            target_mi / speed,
            (FUEL_EVERY_MI - mi_since_fuel) / speed,
        ))

        if drive_h > EPS:
            mi = drive_h * speed
            emit(Status.DRIVE, drive_h, mi, "Driving")
            shift_drive += drive_h
            since_break += drive_h
            cycle += drive_h
            mi_since_fuel += mi
            window_elapsed = _hours(now - window_start)

        # ── next event, highest priority first ─────────────────────────────
        if picked_up and pos >= total_mi - EPS:
            emit(Status.ONDUTY, DROPOFF_H, 0.0, "Dropoff", "Unload / paperwork")
            cycle += DROPOFF_H
            emit(Status.ONDUTY, POSTTRIP_H, 0.0, "Post-trip inspection")
            cycle += POSTTRIP_H
            break

        if not picked_up and pos >= pickup_mi - EPS:
            emit(Status.ONDUTY, PICKUP_H, 0.0, "Pickup", "Load / paperwork")
            cycle += PICKUP_H
            since_break = 0.0                          # >=30 min non-driving
            picked_up = True
            continue

        if mi_since_fuel >= FUEL_EVERY_MI - EPS:
            emit(Status.ONDUTY, FUEL_H, 0.0, "Fuel stop")
            cycle += FUEL_H
            mi_since_fuel = 0.0
            since_break = 0.0
            continue

        # §395.1(g): in split mode, take the 8h sleeper leg as the shift's first
        # break — when the 30-min break comes due, or when driving hours run out
        # while the 14h window still has room to use after the sleeper.
        want_long_leg = (
            p.use_split_sleeper
            and not split_long_pending
            and (since_break >= BREAK_AFTER_DRIVE_H - EPS or shift_drive >= DRIVE_LIMIT_H - EPS)
        )
        if want_long_leg:
            emit(Status.SB, SPLIT_LONG_H, 0.0, "Sleeper berth", "Split 8/2 — long leg")
            window_start = window_start + timedelta(hours=SPLIT_LONG_H)
            split_long_pending = True
            since_break = 0.0
            continue

        if since_break >= BREAK_AFTER_DRIVE_H - EPS:
            emit(Status.OFF, BREAK_MIN_H, 0.0, "30-minute break")
            since_break = 0.0
            continue

        if cycle >= CYCLE_LIMIT_H - EPS:
            emit(Status.OFF, RESTART_H, 0.0, "34-hour restart")
            cycle = 0.0
            shift_drive = since_break = 0.0
            window_start = None
            split_long_pending = False
            continue

        if shift_drive >= DRIVE_LIMIT_H - EPS or window_elapsed >= WINDOW_LIMIT_H - EPS:
            if split_long_pending:
                emit(Status.OFF, SPLIT_SHORT_H, 0.0, "Split break (2 hr)", "Split 8/2 — short leg completes 10h")
                split_long_pending = False
            else:
                emit(Status.OFF, DAILY_RESET_H, 0.0, "10-hour rest")
            shift_drive = since_break = 0.0
            window_start = None
            continue

        raise RuntimeError(  # pragma: no cover - means the cap logic has a hole
            f"simulate: stuck at mi={pos:.1f} "
            f"drive={DRIVE_LIMIT_H - shift_drive:.2f} window={WINDOW_LIMIT_H - window_elapsed:.2f} "
            f"break={BREAK_AFTER_DRIVE_H - since_break:.2f} cycle={CYCLE_LIMIT_H - cycle:.2f}"
        )

    return segs


# ───────────────────────────────────────────────────────────────────────────
# Compliance checker  (validates planner output; oracle for the golden tests)
# ───────────────────────────────────────────────────────────────────────────
def check_compliance(segments: list[Segment], start_cycle_h: float = 0.0) -> list[Violation]:
    """Walk any duty-status timeline and return every HOS violation found.

    Split-sleeper handling covers the 8/2 / 7/3 shape the planner emits (a
    >=7h sleeper-berth leg, later paired with a >=2h off/sleeper leg). Exotic
    orderings (short leg first, three-way stacks) are validated approximately.
    """
    v: list[Violation] = []
    shift_drive = 0.0
    since_break = 0.0
    cycle = max(0.0, start_cycle_h)
    window_start: datetime | None = None
    window_excluded_h = 0.0        # paired sleeper time removed from this window
    long_leg_pending = False

    def flag(rule: str, at: datetime, detail: str) -> None:
        v.append(Violation(rule, at, detail))

    i, n = 0, len(segments)
    while i < n:
        s = segments[i]

        if s.status in (Status.OFF, Status.SB):
            # collapse a maximal off/sleeper run
            run_h = sb_h = 0.0
            j = i
            while j < n and segments[j].status in (Status.OFF, Status.SB):
                run_h += segments[j].hours
                if segments[j].status == Status.SB:
                    sb_h += segments[j].hours
                j += 1

            if run_h >= DAILY_RESET_H - EPS:                       # full reset
                shift_drive = since_break = 0.0
                window_start = None
                window_excluded_h = 0.0
                long_leg_pending = False
                if run_h >= RESTART_H - EPS:                       # §395.3(c): cycle resets
                    cycle = 0.0
            elif sb_h >= SPLIT_LONG_MIN_H - EPS:                   # long leg of a split
                if window_start is not None:
                    window_excluded_h += run_h
                long_leg_pending = True
                if run_h >= BREAK_MIN_H - EPS:
                    since_break = 0.0
            elif long_leg_pending and run_h >= SPLIT_SHORT_MIN_H - EPS:  # short leg -> pair
                shift_drive = since_break = 0.0
                window_start = None
                window_excluded_h = 0.0
                long_leg_pending = False
            else:                                                 # ordinary non-driving time
                if run_h >= BREAK_MIN_H - EPS:
                    since_break = 0.0
            i = j
            continue

        if window_start is None:
            window_start = s.start

        if s.status == Status.ONDUTY:
            cycle += s.hours
            if s.hours >= BREAK_MIN_H - EPS:
                since_break = 0.0
            i += 1
            continue

        # Status.DRIVE — check limits at both the start and end of the segment
        for when, extra_drive in ((s.start, 0.0), (s.end, s.hours)):
            d = shift_drive + extra_drive
            w = _hours(when - window_start) - window_excluded_h
            b = since_break + extra_drive
            c = cycle + extra_drive
            if d > DRIVE_LIMIT_H + EPS:
                flag("11h driving limit", when, f"{d:.2f}h driving this shift")
            if w > WINDOW_LIMIT_H + EPS:
                flag("14h driving window", when, f"{w:.2f}h since shift start")
            if b > BREAK_AFTER_DRIVE_H + EPS:
                flag("30-min break", when, f"{b:.2f}h driving since last break")
            if c > CYCLE_LIMIT_H + EPS:
                flag("70h/8day cycle", when, f"{c:.2f}h on duty this cycle")
        shift_drive += s.hours
        since_break += s.hours
        cycle += s.hours
        i += 1

    # one violation per (rule, timestamp)
    seen: set[tuple[str, datetime]] = set()
    out: list[Violation] = []
    for x in v:
        key = (x.rule, x.at)
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def _hours(td: timedelta) -> float:
    return td.total_seconds() / 3600.0
