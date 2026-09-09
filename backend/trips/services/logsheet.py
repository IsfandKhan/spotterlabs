"""Duty-status timeline -> one FMCSA daily log sheet per calendar day.

Pure Python. Splits segments at midnight, gap-fills each day to a full 24:00
with off-duty time (guide: John Doe's log runs midnight-to-midnight), totals
each duty status, and builds the §395.8 "Remarks" list (a line at every change
of duty status).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .hos import Segment, Status

_DAY = timedelta(days=1)
_STATUS_LABEL = {
    Status.OFF: "Off Duty",
    Status.SB: "Sleeper Berth",
    Status.DRIVE: "Driving",
    Status.ONDUTY: "On Duty (not driving)",
}


@dataclass
class LogDay:
    day: date
    segments: list[Segment]
    remarks: list[dict] = field(default_factory=list)
    off_min: int = 0
    sb_min: int = 0
    drive_min: int = 0
    onduty_min: int = 0
    total_miles_driving: float = 0.0

    @property
    def total_min(self) -> int:
        return self.off_min + self.sb_min + self.drive_min + self.onduty_min

    def to_dict(self) -> dict:
        return {
            "date": self.day.isoformat(),
            "segments": [s.to_dict() for s in self.segments],
            "remarks": self.remarks,
            "totals": {
                "off": _hm(self.off_min),
                "sb": _hm(self.sb_min),
                "drive": _hm(self.drive_min),
                "onduty": _hm(self.onduty_min),
                "total": _hm(self.total_min),
            },
            "totals_hours": {
                "off": round(self.off_min / 60, 2),
                "sb": round(self.sb_min / 60, 2),
                "drive": round(self.drive_min / 60, 2),
                "onduty": round(self.onduty_min / 60, 2),
            },
            "total_miles_driving": round(self.total_miles_driving, 1),
        }


def build_log_days(segments: list[Segment]) -> list[LogDay]:
    if not segments:
        return []
    pieces = _split_at_midnight(segments)

    by_day: dict[date, list[Segment]] = {}
    for s in pieces:
        by_day.setdefault(s.start.date(), []).append(s)

    days = sorted(by_day)
    out: list[LogDay] = []
    for d in _date_range(days[0], days[-1]):
        out.append(_assemble_day(d, by_day.get(d, [])))

    _attach_remarks(out)
    for ld in out:
        assert ld.total_min == 1440, f"{ld.day}: log totals {ld.total_min} min, expected 1440"
    return out


# ── internals ──────────────────────────────────────────────────────────────
def _split_at_midnight(segments: list[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for s in segments:
        start, start_mi = s.start, s.start_mi
        while start.date() != s.end.date():
            midnight = datetime.combine(start.date() + _DAY, datetime.min.time())
            frac = (midnight - start) / (s.end - s.start)
            cut_mi = s.start_mi + (s.end_mi - s.start_mi) * ((midnight - s.start) / (s.end - s.start))
            out.append(Segment(s.status, start, midnight, start_mi, cut_mi, s.label, s.note, s.location))
            start, start_mi = midnight, cut_mi
        if start < s.end:
            out.append(Segment(s.status, start, s.end, start_mi, s.end_mi, s.label, s.note, s.location))
    return out


def _assemble_day(d: date, segs: list[Segment]) -> LogDay:
    day_start = datetime.combine(d, datetime.min.time())
    day_end = day_start + _DAY
    segs = sorted(segs, key=lambda s: s.start)

    filled: list[Segment] = []
    cursor = day_start
    for s in segs:
        if s.start > cursor:
            filled.append(Segment(Status.OFF, cursor, s.start, s.start_mi, s.start_mi, "__pad__"))
        filled.append(s)
        cursor = s.end
    if cursor < day_end:
        end_mi = segs[-1].end_mi if segs else 0.0
        filled.append(Segment(Status.OFF, cursor, day_end, end_mi, end_mi, "__pad__"))

    ld = LogDay(day=d, segments=filled)
    for s in filled:
        minutes = round(s.hours * 60)
        if s.status == Status.OFF:
            ld.off_min += minutes
        elif s.status == Status.SB:
            ld.sb_min += minutes
        elif s.status == Status.DRIVE:
            ld.drive_min += minutes
            ld.total_miles_driving += s.miles
        else:
            ld.onduty_min += minutes
    _fix_rounding(ld)
    return ld


def _fix_rounding(ld: LogDay) -> None:
    """Nudge the largest bucket so per-minute rounding still sums to exactly 1440."""
    drift = 1440 - ld.total_min
    if drift == 0:
        return
    biggest = max(("off_min", "sb_min", "drive_min", "onduty_min"), key=lambda a: getattr(ld, a))
    setattr(ld, biggest, getattr(ld, biggest) + drift)


def _attach_remarks(days: list[LogDay]) -> None:
    """One remark per change of duty status (§395.8). Skips the midnight/​tail
    padding and collapses a repeat of the same location."""
    prev_status: Status | None = None
    prev_location = None
    for ld in days:
        for s in ld.segments:
            changed = s.status != prev_status
            prev_status = s.status
            if not changed or s.label == "__pad__":         # padding, not a real change
                continue
            if s.location and s.location == prev_location:  # same place as last mark
                continue
            prev_location = s.location or prev_location
            ld.remarks.append({
                "time": s.start.strftime("%H:%M"),
                "iso": s.start.isoformat(),
                "status": _STATUS_LABEL[s.status],
                "label": s.label,
                "location": s.location,
            })


def _date_range(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += _DAY


def _hm(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"
