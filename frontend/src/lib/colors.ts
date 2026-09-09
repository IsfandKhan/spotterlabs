/** Concrete colors for the always-white log sheet and canvas/SVG libs (Leaflet)
 *  that can't read CSS variables. Kept in sync with --duty-* in index.css. */
export const DUTY_HEX = {
  off: '#6b7280', // ~3.9:1 on white — readable as a data line, not just a tint
  sb: '#6d5cc9',
  drive: '#2f9e6b',
  onduty: '#d38a2c',
} as const;

export const BRAND_HEX = '#2f5ea8';
export const DANGER_HEX = '#c0392b';
export const INK_HEX = '#1c1f24';

export const STOP_HEX: Record<string, string> = {
  Pickup: DUTY_HEX.onduty,
  Dropoff: BRAND_HEX,
  'Fuel stop': DUTY_HEX.onduty,
  '30-minute break': DUTY_HEX.off,
  '10-hour rest': DUTY_HEX.sb,
  '34-hour restart': DANGER_HEX,
  'Sleeper berth': DUTY_HEX.sb,
  'Split break (2 hr)': DUTY_HEX.off,
};
