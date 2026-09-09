import type { DutyStatus, LogDay, TripHeader } from "@/lib/api"
import { DUTY_HEX } from "@/lib/colors"

const ROWS: { key: DutyStatus; n: number; label: string }[] = [
  { key: "off", n: 1, label: "Off Duty" },
  { key: "sb", n: 2, label: "Sleeper Berth" },
  { key: "drive", n: 3, label: "Driving" },
  { key: "onduty", n: 4, label: "On Duty (not driving)" },
]

// The sheet always renders on white (it's a paper-form facsimile), so it uses
// the fixed hex palette rather than the theme-dependent --duty-* variables.
const DUTY_COLOR = DUTY_HEX

// geometry
const GX = 132 // grid left edge
const GW = 720 // grid width  (24h * 30px)
const HOUR = GW / 24
const GY = 92 // grid top
const RH = 34 // row height
const GH = RH * 4
const TOTX = GX + GW + 10 // "total hours" column
const REMARK_H = 96
const W = 980
const H = GY + GH + REMARK_H + 150

function minutes(iso: string): number {
  const d = new Date(iso)
  return d.getHours() * 60 + d.getMinutes()
}

function rowIndex(s: DutyStatus): number {
  return ROWS.findIndex((r) => r.key === s)
}

function rowCenterY(idx: number): number {
  return GY + idx * RH + RH / 2
}

function hm(min: number): string {
  const m = Math.round(min)
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`
}

export function LogSheet({
  day,
  header,
  index,
  count,
}: {
  day: LogDay
  header: TripHeader
  index: number
  count: number
}) {
  const date = new Date(day.date)
  const carrier = header.carrier_name || "—"

  // Build the duty-status polyline from the day's (gap-filled) segments.
  const pts: { x: number; y: number }[] = []
  for (const seg of day.segments) {
    const idx = rowIndex(seg.status)
    if (idx < 0) continue
    const x0 = GX + (minutes(seg.start) / 60) * HOUR
    let x1 = GX + (minutes(seg.end) / 60) * HOUR
    if (x1 <= x0) x1 = GX + GW // segment runs to midnight
    const y = rowCenterY(idx)
    pts.push({ x: x0, y }, { x: x1, y })
  }

  const grid = header.home_terminal_address || header.main_office_address

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-white">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="min-w-225 font-sans"
        role="img"
        aria-label={
          `Driver's daily log for ${day.date}. ` +
          `Off duty ${day.totals.off}, sleeper berth ${day.totals.sb}, ` +
          `driving ${day.totals.drive}, on duty not driving ${day.totals.onduty}, ` +
          `total ${day.totals.total}. ${Math.round(day.total_miles_driving)} miles driven.`
        }
      >
        <rect x="0" y="0" width={W} height={H} fill="white" />

        {/* ── header ─────────────────────────────────────────────── */}
        <text x="20" y="26" fontSize="15" fontWeight="700" fill="#111">
          Driver’s Daily Log
        </text>
        <text x="20" y="42" fontSize="10" fill="#555">
          (24 hours) · one calendar day
        </text>
        <text x={W - 20} y="22" fontSize="10" textAnchor="end" fill="#555">
          Sheet {index + 1} of {count}
        </text>

        {headerField(300, 20, "Date", date.toLocaleDateString(undefined, { month: "2-digit", day: "2-digit", year: "numeric" }))}
        {headerField(470, 20, "Total miles driving today", String(Math.round(day.total_miles_driving)))}
        {headerField(470, 44, "Total mileage today", String(Math.round(day.total_miles_driving)))}
        {headerField(680, 20, "Tractor / trailer no.", [header.tractor_number, header.trailer_number].filter(Boolean).join(" / ") || "—")}

        {headerField(20, 58, "Name of carrier", carrier || "—")}
        {headerField(300, 58, "Main office address", header.main_office_address || "—")}
        {headerField(560, 58, "Home terminal (time base)", grid || "—")}

        {/* ── grid ───────────────────────────────────────────────── */}
        {/* hour ticks + labels */}
        {Array.from({ length: 25 }, (_, h) => {
          const x = GX + h * HOUR
          const label = h === 0 || h === 24 ? "M" : h === 12 ? "N" : String(h % 12)
          return (
            <g key={h}>
              <line x1={x} y1={GY} x2={x} y2={GY + GH} stroke="#c8ccd2" strokeWidth={h % 6 === 0 ? 1.1 : 0.7} />
              <text x={x} y={GY - 6} fontSize="9" textAnchor="middle" fill="#555">
                {label}
              </text>
              {h < 24 &&
                [15, 30, 45].map((m) => {
                  const mx = x + (m / 60) * HOUR
                  const len = m === 30 ? 7 : 4
                  return ROWS.map((_, ri) => (
                    <line
                      key={`${h}-${m}-${ri}`}
                      x1={mx}
                      y1={GY + ri * RH}
                      x2={mx}
                      y2={GY + ri * RH + len}
                      stroke="#d7dade"
                      strokeWidth="0.6"
                    />
                  ))
                })}
            </g>
          )
        })}

        {/* rows */}
        {ROWS.map((r, i) => {
          const y = GY + i * RH
          const mins = day.totals_hours[r.key] * 60
          return (
            <g key={r.key}>
              <line x1={GX} y1={y} x2={GX + GW} y2={y} stroke="#9aa0a6" strokeWidth="0.9" />
              <text x={GX - 8} y={y + RH / 2 - 4} fontSize="9.5" textAnchor="end" fill="#333">
                {r.n}. {r.label.split(" (")[0]}
              </text>
              {r.label.includes("(") && (
                <text x={GX - 8} y={y + RH / 2 + 7} fontSize="8" textAnchor="end" fill="#888">
                  (not driving)
                </text>
              )}
              <rect x={GX} y={y} width={GW} height={RH} fill={DUTY_COLOR[r.key]} opacity="0.04" />
              <text x={TOTX} y={y + RH / 2 + 3} fontSize="10" fontWeight="600" fill="#222">
                {hm(mins)}
              </text>
            </g>
          )
        })}
        <line x1={GX} y1={GY + GH} x2={GX + GW} y2={GY + GH} stroke="#9aa0a6" strokeWidth="0.9" />
        <line x1={GX} y1={GY} x2={GX} y2={GY + GH} stroke="#9aa0a6" strokeWidth="0.9" />
        <line x1={GX + GW} y1={GY} x2={GX + GW} y2={GY + GH} stroke="#9aa0a6" strokeWidth="0.9" />
        <text x={TOTX} y={GY - 6} fontSize="8.5" fill="#555">
          Total hrs
        </text>
        <text x={TOTX} y={GY + GH + 14} fontSize="10" fontWeight="700" fill="#111">
          = {day.totals.total}
        </text>

        {/* duty-status line, colored per segment */}
        {day.segments.map((seg, k) => {
          const idx = rowIndex(seg.status)
          if (idx < 0) return null
          const x0 = GX + (minutes(seg.start) / 60) * HOUR
          let x1 = GX + (minutes(seg.end) / 60) * HOUR
          if (x1 <= x0) x1 = GX + GW
          const y = rowCenterY(idx)
          return (
            <line key={k} x1={x0} y1={y} x2={x1} y2={y} stroke={DUTY_COLOR[seg.status]} strokeWidth="2.4" strokeLinecap="round" />
          )
        })}
        {/* vertical connectors at each status change */}
        {pts.slice(1).map((p, k) => {
          const prev = pts[k]
          if (Math.abs(p.x - prev.x) > 0.5 || p.y === prev.y) return null
          return <line key={`c${k}`} x1={p.x} y1={prev.y} x2={p.x} y2={p.y} stroke="#111" strokeWidth="1.4" />
        })}

        {/* ── remarks ────────────────────────────────────────────── */}
        <text x="20" y={GY + GH + 30} fontSize="10" fontWeight="700" fill="#111">
          REMARKS
        </text>
        <line x1={GX} y1={GY + GH + 20} x2={GX + GW} y2={GY + GH + 20} stroke="#c8ccd2" strokeWidth="0.7" />
        {day.remarks.map((rm, k) => {
          const x = GX + (toMin(rm.time) / 60) * HOUR
          const yTop = GY + GH
          return (
            <g key={k}>
              <line x1={x} y1={yTop} x2={x} y2={yTop + 20} stroke="#111" strokeWidth="0.8" />
              <text
                x={x + 3}
                y={yTop + 26}
                fontSize="7.5"
                fill="#333"
                transform={`rotate(55 ${x + 3} ${yTop + 26})`}
              >
                {`${rm.time}  ${rm.location || rm.label}`.slice(0, 30)}
              </text>
            </g>
          )
        })}

        {/* ── recap ──────────────────────────────────────────────── */}
        {recap(GY + GH + REMARK_H + 30, day, header)}
      </svg>
    </div>
  )
}

function toMin(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number)
  return h * 60 + m
}

function headerField(x: number, y: number, label: string, value: string) {
  return (
    <g>
      <text x={x} y={y} fontSize="7.5" fill="#888" style={{ textTransform: "uppercase", letterSpacing: "0.03em" }}>
        {label}
      </text>
      <text x={x} y={y + 12} fontSize="10" fill="#111" fontWeight="600">
        {value}
      </text>
      <line x1={x} y1={y + 16} x2={x + 160} y2={y + 16} stroke="#dfe1e5" strokeWidth="0.6" />
    </g>
  )
}

function recap(y: number, day: LogDay, header: TripHeader) {
  const onDutyToday = day.totals_hours.drive + day.totals_hours.onduty
  const cells: [string, string][] = [
    ["On-duty hours today (lines 3 + 4)", hm(onDutyToday * 60)],
    ["Driving today (line 3)", hm(day.totals_hours.drive * 60)],
    ["Shipper & commodity", [header.shipper_name, header.commodity].filter(Boolean).join(" · ") || "—"],
    ["Shipping doc / manifest no.", header.shipping_doc_number || "—"],
  ]
  return (
    <g>
      <text x="20" y={y - 8} fontSize="10" fontWeight="700" fill="#111">
        RECAP · 70 hr / 8 day
      </text>
      {cells.map(([label, value], i) => {
        const cx = 20 + (i % 2) * 470
        const cy = y + Math.floor(i / 2) * 34
        return (
          <g key={label}>
            <text x={cx} y={cy + 6} fontSize="8" fill="#888">
              {label}
            </text>
            <text x={cx} y={cy + 20} fontSize="11" fontWeight="600" fill="#111">
              {value}
            </text>
          </g>
        )
      })}
    </g>
  )
}
