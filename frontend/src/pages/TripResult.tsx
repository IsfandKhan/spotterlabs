import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';

import { LogSheet } from '@/components/LogSheet';
import { RouteLoader } from '@/components/RouteLoader';
import { RouteMap } from '@/components/RouteMap';
import { StopTimeline } from '@/components/StopTimeline';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

import { ApiError, type TripPlan, api } from '@/lib/api';
import { DUTY_HEX } from '@/lib/colors';
import { fmtDate, fmtHours, fmtMiles } from '@/lib/format';

export function TripResult() {
  const { id } = useParams();
  const location = useLocation();
  const preloaded = (location.state as { plan?: TripPlan } | null)?.plan;
  const [plan, setPlan] = useState<TripPlan | null>(preloaded ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (plan && String(plan.id) === id) return;
    setPlan(null);
    api
      .getTrip(id!)
      .then(setPlan)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load trip'));
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load this trip</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!plan) return <RouteLoader label="Loading trip…" />;

  const s = plan.summary;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            {plan.input.pickup_location} → {plan.input.dropoff_location}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            From {plan.input.current_location} · departing {fmtDate(plan.summary.trip_start)}
          </p>
        </div>
        <Link
          to="/"
          className="rounded-sm text-sm font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Plan another →
        </Link>
      </div>

      {plan.compliance.ok ? (
        <Alert>
          <AlertTitle>HOS compliant</AlertTitle>
          <AlertDescription>Every generated log sheet stays within the 11/14/30-min/70-hour limits.</AlertDescription>
        </Alert>
      ) : (
        <Alert variant="destructive">
          <AlertTitle>{plan.compliance.violations.length} HOS violation(s)</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {plan.compliance.violations.map((v, i) => (
                <li key={i}>
                  {v.rule} — {v.detail}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Distance" value={fmtMiles(s.total_miles)} />
        <Stat label="Drive time" value={fmtHours(s.total_drive_hours)} />
        <Stat label="On-duty" value={fmtHours(s.total_duty_hours)} />
        <Stat label="Log sheets" value={String(s.total_days)} />
        <Stat label="Stops" value={String(s.num_stops)} />
        <Stat label="34-hr restarts" value={String(s.num_restarts)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-3">
          <RouteMap plan={plan} />
          {plan.route.is_estimate && (
            <p className="text-xs text-muted-foreground">
              Routing service was unavailable — distances are straight-line estimates.
            </p>
          )}
          <Legend />
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stops &amp; rests</CardTitle>
          </CardHeader>
          <CardContent>
            <StopTimeline stops={plan.stops} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Planning assumptions</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            {plan.hos_notes.map((n, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary">·</span>
                {n}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div>
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-lg font-semibold tracking-tight">Daily log sheets</h2>
          <Badge variant="secondary">{plan.log_days.length}</Badge>
        </div>
        <div className="space-y-5">
          {plan.log_days.map((d, i) => (
            <div key={d.date} className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">{fmtDate(d.date)}</h3>
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {fmtMiles(d.total_miles_driving)} driving · {d.totals.drive} drive · {d.totals.total} total
                </span>
              </div>
              <LogSheet day={d} header={plan.header} index={i} count={plan.log_days.length} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 font-mono text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Legend() {
  const items: [string, string][] = [
    ['Off duty', DUTY_HEX.off],
    ['Sleeper berth', DUTY_HEX.sb],
    ['Driving', DUTY_HEX.drive],
    ['On duty (ND)', DUTY_HEX.onduty],
  ];
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {items.map(([label, color]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ backgroundColor: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}

