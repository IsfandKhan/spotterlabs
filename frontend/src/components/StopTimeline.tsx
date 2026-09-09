import type { Stop } from '@/lib/api';
import { DUTY_HEX, STOP_HEX } from '@/lib/colors';
import { fmtDateTime, fmtHours, fmtMiles } from '@/lib/format';

export function StopTimeline({ stops }: { stops: Stop[] }) {
  if (!stops.length) return <p className="text-sm text-muted-foreground">No intermediate stops — a single continuous run.</p>;

  return (
    <ol className="relative space-y-0">
      {stops.map((s, i) => (
        <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
          <div className="flex flex-col items-center">
            <span
              className="mt-1 size-2.5 shrink-0 rounded-full ring-2 ring-background"
              style={{ backgroundColor: STOP_HEX[s.kind] ?? DUTY_HEX.off }}
            />
            {i < stops.length - 1 && <span className="w-px flex-1 bg-border" />}
          </div>
          <div className="min-w-0 flex-1 -mt-0.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-medium">{s.kind}</span>
              <span className="shrink-0 font-mono text-xs text-muted-foreground">{fmtHours(s.hours)}</span>
            </div>
            <div className="truncate text-xs text-muted-foreground">
              {s.location || 'en route'} · {fmtMiles(s.mile)} · {fmtDateTime(s.start)}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
