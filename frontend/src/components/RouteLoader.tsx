/** Route-planning loader: a map pin + road with a marching centerline.
 *  Pure CSS animation; the global prefers-reduced-motion rule freezes it. */
export function RouteLoader({ label = 'Planning route…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center" role="status" aria-live="polite">
      <svg viewBox="0 0 230 150" className="w-44 text-foreground" fill="none" aria-hidden="true">
        <path
          d="M16 140 C58 134 96 120 120 92 C144 64 182 46 220 52"
          stroke="currentColor"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d="M16 140 C58 134 96 120 120 92 C144 64 182 46 220 52"
          className="route-loader-dash"
          stroke="var(--primary)"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeDasharray="9 13"
        />
        <g className="route-loader-bob">
          <path
            d="M42 74 C31 52 20 44 20 24 A22 22 0 1 1 64 24 C64 44 53 52 42 74 Z"
            fill="var(--primary)"
          />
          <circle cx="42" cy="24" r="9" fill="var(--background)" />
        </g>
        <g className="route-loader-pulse">
          <path
            d="M156 74 C148 59 142 54 142 43 A14 14 0 1 1 170 43 C170 54 164 59 156 74 Z"
            fill="var(--background)"
            stroke="currentColor"
            strokeWidth="4"
          />
          <circle cx="156" cy="42" r="6" fill="var(--primary)" />
        </g>
      </svg>
      {label && <p className="text-sm font-medium text-muted-foreground">{label}</p>}
      <span className="sr-only">Loading</span>
    </div>
  );
}
