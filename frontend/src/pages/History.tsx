import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type TripListRow } from "@/lib/api"
import { fmtDateTime, fmtHours, fmtMiles } from "@/lib/format"

export function History() {
  const [rows, setRows] = useState<TripListRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listTrips()
      .then((r) => setRows(r.results))
      .catch(() => setError("Could not load history"))
  }, [])

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold tracking-tight">Trip history</h1>
      <p className="mb-6 text-sm text-muted-foreground">Every planned trip, most recent first.</p>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!rows && !error && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}
      {rows && rows.length === 0 && (
        <div className="rounded-lg border border-dashed border-border p-10 text-center">
          <p className="text-sm text-muted-foreground">No trips yet.</p>
          <Link
            to="/"
            className="mt-2 inline-block rounded-sm text-sm font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Plan your first trip →
          </Link>
        </div>
      )}

      <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
        {rows?.map((t) => (
          <li key={t.id}>
            <Link
              to={`/trips/${t.id}`}
              className="flex items-center justify-between gap-4 p-4 transition-colors outline-none hover:bg-accent/40 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {t.pickup_location} → {t.dropoff_location}
                  </span>
                  {!t.compliance_ok && <Badge variant="destructive">HOS issue</Badge>}
                  {t.use_split_sleeper && <Badge variant="secondary">split SB</Badge>}
                  {t.route_is_estimate && <Badge variant="outline">est.</Badge>}
                </div>
                <div className="mt-0.5 truncate text-xs text-muted-foreground">
                  from {t.current_location} · {fmtDateTime(t.created_at)}
                </div>
              </div>
              <div className="shrink-0 text-right font-mono text-xs tabular-nums text-muted-foreground">
                <div>{fmtMiles(t.total_miles)}</div>
                <div>
                  {fmtHours(t.total_drive_hours)} drive · {t.total_days} sheet{t.total_days === 1 ? "" : "s"}
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
