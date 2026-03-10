/**
 * ADR-064 effort intensity → color mapping.
 *
 * 6-stop muted F1 palette: steel-blue → teal → warm amber → orange → red → deep crimson.
 * All stops have lightness ≤ 45% and saturation ≤ 75% for dark-background rendering.
 * Input: effort scalar in [0.0, 1.0].
 * Output: CSS rgb() string.
 *
 * Palette tuned against real run data on slate-900 background.
 * No neon. F1 telemetry aesthetic.
 */

interface RGB {
  r: number;
  g: number;
  b: number;
}

// HSL → RGB conversion for defining stops in HSL then converting
function hslToRgb(h: number, s: number, l: number): RGB {
  h /= 360; s /= 100; l /= 100;
  let r: number, g: number, b: number;
  if (s === 0) {
    r = g = b = l;
  } else {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
}

// 6-stop muted palette — all L ≤ 45%, all S ≤ 75%
const STOPS: Array<{ t: number; color: RGB }> = [
  { t: 0.0,  color: hslToRgb(205, 55, 35) },   // Steel blue (recovery)
  { t: 0.3,  color: hslToRgb(175, 45, 32) },   // Muted teal (easy)
  { t: 0.5,  color: hslToRgb(38,  60, 38) },   // Warm amber (moderate)
  { t: 0.7,  color: hslToRgb(18,  62, 36) },   // Burnt orange (tempo)
  { t: 0.85, color: hslToRgb(5,   65, 35) },   // Red-orange (threshold)
  { t: 1.0,  color: hslToRgb(350, 70, 28) },   // Deep crimson (max)
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
