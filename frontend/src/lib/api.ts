const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export type DutyStatus = 'off' | 'sb' | 'drive' | 'onduty';

export interface Segment {
  status: DutyStatus;
  start: string;
  end: string;
  start_mi: number;
  end_mi: number;
  label: string;
  note: string;
  location: string;
}

export interface Remark {
  time: string;
  iso: string;
  status: string;
  label: string;
  location: string;
}

export interface LogDay {
  date: string;
  segments: Segment[];
  remarks: Remark[];
  totals: { off: string; sb: string; drive: string; onduty: string; total: string };
  totals_hours: { off: number; sb: number; drive: number; onduty: number };
  total_miles_driving: number;
}

export interface Stop {
  kind: string;
  status: DutyStatus;
  location: string;
  mile: number;
  start: string;
  end: string;
  hours: number;
  lat: number | null;
  lon: number | null;
}

export interface TripHeader {
  driver_name: string;
  co_driver_name: string;
  carrier_name: string;
  main_office_address: string;
  home_terminal_address: string;
  tractor_number: string;
  trailer_number: string;
  shipper_name: string;
  commodity: string;
  shipping_doc_number: string;
}

export interface TripPlan {
  id: number;
  created_at: string;
  input: {
    current_location: string;
    pickup_location: string;
    dropoff_location: string;
    current_cycle_used_h: number;
    departure_at: string;
    use_split_sleeper: boolean;
  };
  geocoded: Record<'current' | 'pickup' | 'dropoff', { query: string; lat: number; lon: number; label: string }>;
  route: {
    distance_mi: number;
    deadhead_mi: number;
    loaded_mi: number;
    duration_h: number;
    avg_speed_mph: number;
    is_estimate: boolean;
    geometry: [number, number][];
  };
  summary: {
    total_miles: number;
    total_drive_hours: number;
    total_duty_hours: number;
    total_days: number;
    num_stops: number;
    num_restarts: number;
    trip_start: string;
    trip_end: string;
  };
  timeline: Segment[];
  stops: Stop[];
  log_days: LogDay[];
  hos_notes: string[];
  compliance: { ok: boolean; violations: { rule: string; at: string; detail: string }[] };
  header: TripHeader;
}

export interface TripListRow {
  id: number;
  created_at: string;
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used_h: number;
  departure_at: string;
  use_split_sleeper: boolean;
  total_miles: number;
  total_drive_hours: number;
  total_duty_hours: number;
  total_days: number;
  num_stops: number;
  num_restarts: number;
  route_is_estimate: boolean;
  compliance_ok: boolean;
}

export interface PlanRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used_h: number;
  departure_at?: string | null;
  use_split_sleeper?: boolean;
  driver_name?: string;
  co_driver_name?: string;
  carrier_name?: string;
  main_office_address?: string;
  home_terminal_address?: string;
  tractor_number?: string;
  trailer_number?: string;
  shipper_name?: string;
  commodity?: string;
  shipping_doc_number?: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError(0, 'Could not reach the API. Is the backend running?');
  }
  const text = await resp.text();
  const body = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const msg =
      body?.error ||
      (body && typeof body === 'object' ? Object.values(body).flat().join(' ') : null) ||
      `Request failed (${resp.status})`;
    throw new ApiError(resp.status, msg);
  }
  return body as T;
}

export const api = {
  planTrip: (data: PlanRequest) => request<TripPlan>('/api/trips', { method: 'POST', body: JSON.stringify(data) }),
  getTrip: (id: number | string) => request<TripPlan>(`/api/trips/${id}`),
  listTrips: (page = 1) =>
    request<{ count: number; next: string | null; previous: string | null; results: TripListRow[] }>(`/api/trips?page=${page}`),
};

export const DUTY_LABEL: Record<DutyStatus, string> = {
  off: 'Off Duty',
  sb: 'Sleeper Berth',
  drive: 'Driving',
  onduty: 'On Duty (ND)',
};
