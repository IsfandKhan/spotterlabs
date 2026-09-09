import { useEffect } from "react"
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet"

import type { Stop, TripPlan } from "@/lib/api"
import { BRAND_HEX, DUTY_HEX, INK_HEX, STOP_HEX } from "@/lib/colors"
import { fmtDateTime, fmtHours } from "@/lib/format"

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length) map.fitBounds(points, { padding: [40, 40] })
  }, [map, points])
  return null
}

export function RouteMap({ plan }: { plan: TripPlan }) {
  const line = plan.route.geometry
  const endpoints: [number, number][] = [
    [plan.geocoded.current.lat, plan.geocoded.current.lon],
    [plan.geocoded.pickup.lat, plan.geocoded.pickup.lon],
    [plan.geocoded.dropoff.lat, plan.geocoded.dropoff.lon],
  ]
  const bounds = line.length ? line : endpoints
  const stops = plan.stops.filter((s) => s.lat != null && s.lon != null)

  return (
    <MapContainer
      className="h-105 w-full rounded-lg border border-border"
      center={endpoints[1]}
      zoom={5}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {line.length > 1 && <Polyline positions={line} pathOptions={{ color: BRAND_HEX, weight: 4, opacity: 0.85 }} />}

      <Endpoint pos={endpoints[0]} label="Current location" sub={plan.geocoded.current.label} color={INK_HEX} />
      <Endpoint pos={endpoints[1]} label="Pickup" sub={plan.geocoded.pickup.label} color={DUTY_HEX.onduty} />
      <Endpoint pos={endpoints[2]} label="Dropoff" sub={plan.geocoded.dropoff.label} color={BRAND_HEX} />

      {stops.map((s: Stop, i) => (
        <CircleMarker
          key={i}
          center={[s.lat as number, s.lon as number]}
          radius={6}
          pathOptions={{ color: "white", weight: 1.5, fillColor: STOP_HEX[s.kind] ?? DUTY_HEX.off, fillOpacity: 1 }}
        >
          <Tooltip>
            {s.kind} · {fmtHours(s.hours)}
          </Tooltip>
          <Popup>
            <div className="text-xs">
              <div className="font-semibold">{s.kind}</div>
              <div>{s.location || `Mile ${Math.round(s.mile)}`}</div>
              <div className="text-muted-foreground">
                {fmtDateTime(s.start)} · {fmtHours(s.hours)}
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}

      <FitBounds points={bounds} />
    </MapContainer>
  )
}

function Endpoint({
  pos,
  label,
  sub,
  color,
}: {
  pos: [number, number]
  label: string
  sub: string
  color: string
}) {
  return (
    <CircleMarker center={pos} radius={8} pathOptions={{ color: "white", weight: 2, fillColor: color, fillOpacity: 1 }}>
      <Popup>
        <div className="text-xs">
          <div className="font-semibold">{label}</div>
          <div className="text-muted-foreground">{sub}</div>
        </div>
      </Popup>
    </CircleMarker>
  )
}
