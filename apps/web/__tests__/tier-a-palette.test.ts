/**
 * Tier A — Muted F1 Palette Tests
 *
 * ADR-064 color spec: 6-stop gradient, steel-blue through deep-crimson.
 * All stops must have lightness ≤ 45% (dark background, no neon).
 * Effort 0.0 is cool blue, 1.0 is deep crimson.
 *
 * These tests are written RED-first: they will fail against the current
 * 4-stop neon palette and pass after the palette is replaced.
 */

import { effortToColor } from '@/components/activities/rsi/utils/effortColor';

// --- Helpers ---

function parseRgb(color: string): { r: number; g: number; b: number } {
  const match = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (!match) throw new Error(`Invalid rgb string: ${color}`);
  return { r: parseInt(match[1]), g: parseInt(match[2]), b: parseInt(match[3]) };
}

function rgbToHsl(r: number, g: number, b: number): { h: number; s: number; l: number } {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

function getHsl(effort: number) {
  const rgb = parseRgb(effortToColor(effort));
  return rgbToHsl(rgb.r, rgb.g, rgb.b);
}

// --- Tests ---

describe('Tier A: Muted F1 palette — lightness cap', () => {
  const samplePoints = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0];

  test.each(samplePoints)('effort=%f has lightness ≤ 45%%', (effort) => {
    const hsl = getHsl(effort);
    expect(hsl.l).toBeLessThanOrEqual(45);
  });
});

describe('Tier A: Muted F1 palette — color range', () => {
  test('effort=0.0 is cool blue (hue 180–220)', () => {
    const hsl = getHsl(0.0);
    expect(hsl.h).toBeGreaterThanOrEqual(180);
    expect(hsl.h).toBeLessThanOrEqual(220);
  });

  test('effort=1.0 is deep crimson (hue 340–360 or 0–10)', () => {
    const hsl = getHsl(1.0);
    // Crimson wraps around 360, so either >= 340 or <= 10
    expect(hsl.h >= 340 || hsl.h <= 10).toBe(true);
  });

  test('mid-range effort (0.5) is warm, not green (hue 20–60)', () => {
    const hsl = getHsl(0.5);
    expect(hsl.h).toBeGreaterThanOrEqual(20);
    expect(hsl.h).toBeLessThanOrEqual(60);
  });
});

describe('Tier A: Muted F1 palette — 6 stops', () => {
  test('6 stop positions produce 6 distinct colors', () => {
    // The 6 stops should be at approximately these effort positions
    const stopPositions = [0.0, 0.3, 0.5, 0.7, 0.85, 1.0];
    const colors = stopPositions.map((e) => effortToColor(e));
    const unique = new Set(colors);
    expect(unique.size).toBe(6);
  });
});

describe('Tier A: Anti-regression — no neon', () => {
  test('no color in the palette has saturation > 75%', () => {
    const samplePoints = [0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.85, 0.95, 1.0];
    for (const effort of samplePoints) {
      const hsl = getHsl(effort);
      expect(hsl.s).toBeLessThanOrEqual(75);
    }
  });

  test('old neon green-500 (rgb 34,197,94) does not appear at any effort value', () => {
    const samplePoints = Array.from({ length: 20 }, (_, i) => i / 19);
    for (const effort of samplePoints) {
      const color = effortToColor(effort);
      expect(color).not.toBe('rgb(34,197,94)');
    }
  });

  test('old neon yellow-400 (rgb 250,204,21) does not appear at any effort value', () => {
    const samplePoints = Array.from({ length: 20 }, (_, i) => i / 19);
    for (const effort of samplePoints) {
      const color = effortToColor(effort);
      expect(color).not.toBe('rgb(250,204,21)');
    }
  });
});
