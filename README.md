# ELD Trip Planner

Enter a trip — current location, pickup, dropoff, and hours already used on the
70-hour cycle — and get back a **route with fuel/rest stops** and a **filled-out
FMCSA daily log sheet for every day of the trip**.

| | |
|---|---|
| **Live app** | https://spotterlabs-eld.vercel.app |
| **API** | https://eld-trip-planner-api-qmml.onrender.com |
| **Walkthrough** | _<Loom URL>_ |

> The API runs on Render's free tier and spins down after ~15 min idle — the
> first request after a cold start takes ~50 s, then it's fast.

Backend: Django + DRF. Frontend: React + Vite + Tailwind + shadcn/ui, with
system dark mode. Map/routing: Leaflet + OpenStreetMap + OSRM; address
autocomplete via Photon. No API keys anywhere.

---

## What it does

**Inputs** — current location, pickup location, dropoff location, current cycle
used (hrs). The three location fields autocomplete as you type (Photon / OSM).
Optional: departure datetime (defaults to now), split-sleeper toggle, and the
§395.8 log-header fields (carrier, truck, shipper, …).

**Outputs**
- An interactive map: the driving route plus a marker for every pickup, dropoff,
  fuel stop, 30-minute break, 10-hour reset and 34-hour restart.
- One **FMCSA driver's daily log** per calendar day — the 24-hour grid with the
  duty-status line drawn on it, the Remarks row (city/state at each change), the
  per-status totals, and the recap box. Long trips produce multiple sheets.
- An explicit compliance check — every generated sheet is verified against the
  11-hour / 14-hour / 30-minute / 70-hour rules.

## Hours-of-service model

Everything is checked against the repo's copy of the FMCSA
[*Interstate Truck Driver's Guide to Hours of Service*](fmcsa-hos-395-drivers-guide-to-hos-2022-04-28-0-1-.md).
Rules implemented (`backend/trips/services/hos.py`):

| Rule | § | Behaviour |
|---|---|---|
| 11-hour driving limit | 395.3(a)(3) | Max 11 h driving per shift |
| 14-hour window | 395.3(a)(2) | No driving after 14 **consecutive** hours from shift start; breaks don't pause it |
| 30-minute break | 395.3(a)(3)(ii) | Required after 8 h cumulative driving; any ≥30 min non-driving satisfies it |
| 60/70-hour limit | 395.3(b) | 70 h on-duty per rolling 8 days |
| 10-hour reset | 395.3(a) | 10 consecutive hours off restarts the 11 h & 14 h clocks |
| 34-hour restart | 395.3(c) | 34 consecutive hours off (duty or sleeper) clears the cycle |
| Split sleeper berth | 395.1(g) | Optional 8/2 split — ≥7 h sleeper + ≥2 h off, sleeper leg excluded from the 14 h window |
| On-duty past hour 14 | guide | Non-driving work after the window is allowed; only driving is barred |

### Golden tests (from the guide itself)

`backend/trips/tests/` reproduces the guide's worked examples:
- **John Doe, Richmond → Newark** ("A Completed Log") — asserts grid totals
  Off 10 / SB 1.75 / Drive 7.75 / On-Duty 4.5 = 24:00 and no violation.
- **Split sleeper rotation** (§395.1(g)) — 7/3 and 8/2 splits stay within
  11 h driving across the pair and keep the 14 h window intact.

Plus a property test: **every** planned trip the simulator emits passes the
independent compliance checker.

### Assumptions & deliberate simplifications

Stated on every result page and here:

- **Property-carrying driver, 70 hr / 8 day, no adverse conditions** (per the assessment).
- **Cycle model — flat debit.** "Current cycle used" is a fixed starting balance;
  hours do **not** age out mid-trip, and only a 34-hour restart clears it. This is
  *stricter* than the rolling §395.3(b) calculation — it never generates an illegal
  log, but on 8+ day trips it can schedule one extra restart. Forced by the
  single-number input.
- **Fuel** every 1,000 mi = 30 min on-duty.
- **Pickup / dropoff** = 1 hr on-duty each.
- **Pre-trip / post-trip inspection** = 15 min on-duty each driving day.
- **Speed** from the OSRM route; 55 mph fallback if OSRM is unreachable.
- **Split-sleeper planning** uses a fixed 8/2 strategy (heuristic, not an optimizer);
  the compliance checker validates whatever it produces.
- **Home-terminal time** = the start location's local wall-clock; the app works in
  naive datetimes throughout (§395.8 "time zone in effect at your home terminal").

## Architecture

```
backend/                Django + DRF
  trips/services/
    hos.py              HOS simulator + compliance checker (pure Python)
    geocode.py          OpenStreetMap Nominatim wrapper (rate-limited, cached)
    routing.py          OSRM wrapper + straight-line fallback
    logsheet.py         segment timeline -> one 24h log sheet per day
    planner.py          geocode -> route -> simulate -> logs
  trips/models.py       Trip (summary columns + full plan payload as JSON)
  trips/views.py        POST/GET /api/trips, GET /api/trips/{id}

frontend/               React + Vite
  src/pages/            PlanTrip · TripResult · History
  src/components/
    LogSheet.tsx        the FMCSA grid, drawn as SVG
    RouteMap.tsx        react-leaflet map
    StopTimeline.tsx    ordered stop list
```

The API returns the whole plan (route geometry, timeline, stops, per-day sheets,
compliance) and persists it; `GET /api/trips/{id}` is a straight read.

## Local development

**Backend** (Python 3.12+):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # http://localhost:8000
pytest                            # 56 tests
```

**Frontend** (Node 20+):
```bash
cd frontend
pnpm install
pnpm dev                          # http://localhost:5173
```
`frontend/.env` → `VITE_API_BASE_URL=http://localhost:8000`

## Deployment (already live)

- **Backend → Render** (`eld-trip-planner-api-qmml`, free web service + free
  Postgres, Oregon). `render.yaml` is the blueprint. `settings.py` reads
  `RENDER_EXTERNAL_HOSTNAME` for `ALLOWED_HOSTS`; `DATABASE_URL`,
  `DJANGO_SECRET_KEY`, `CORS_ALLOWED_ORIGINS` and `DJANGO_DEBUG=0` are set on the
  service. Build: `backend/build.sh` (pip install → collectstatic → migrate).
- **Frontend → Vercel** (`spotterlabs-eld`, personal scope). Root directory
  `frontend`; `vercel.json` handles SPA rewrites; `VITE_API_BASE_URL` env var
  points at the Render URL.

Redeploy: backend auto-deploys on push to `main`; frontend redeploys with
`cd frontend && vercel deploy --prod` (the Vercel project is CLI-linked, not
git-connected — the repo's SSH host alias blocks Vercel's git integration).

## Not legal advice

A planning aid. Drivers are responsible for their own compliance.
