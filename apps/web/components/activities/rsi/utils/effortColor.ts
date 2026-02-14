/**
 * ADR-064 effort intensity → color mapping.
 *
 * Continuous gradient: blue (easy) → green (steady) → yellow (threshold) → red (hard).
 * Input: effort scalar in [0.0, 1.0].
 * Output: CSS rgb() string.
 */

interface RGB {
  r: number;
  g: number;
  b: number;
}

const STOPS: Array<{ t: number; color: RGB }> = [
  { t: 0.0, color: { r: 59, g: 130, b: 246 } },  // blue-400
  { t: 0.5, color: { r: 34, g: 197, b: 94 } },   // green-500
  { t: 0.75, color: { r: 250, g: 204, b: 21 } },  // yellow-400
  { t: 1.0, color: { r: 239, g: 68, b: 68 } },   // red-500
];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function effortToColor(effort: number): string {
  const e = Math.max(0, Math.min(1, effort));

  // Find surrounding stops
  for (let i = 0; i < STOPS.length - 1; i++) {
    if (e >= STOPS[i].t && e <= STOPS[i + 1].t) {
      const range = STOPS[i + 1].t - STOPS[i].t;
      const t = range > 0 ? (e - STOPS[i].t) / range : 0;
      const r = Math.round(lerp(STOPS[i].color.r, STOPS[i + 1].color.r, t));
      const g = Math.round(lerp(STOPS[i].color.g, STOPS[i + 1].color.g, t));
      const b = Math.round(lerp(STOPS[i].color.b, STOPS[i + 1].color.b, t));
      return `rgb(${r},${g},${b})`;
    }
  }

  // Fallback (should not reach)
  const last = STOPS[STOPS.length - 1].color;
  return `rgb(${last.r},${last.g},${last.b})`;
}
