/**
 * MiniPaceChart — Unit tests for the home hero pace chart.
 *
 * Tests:
 * - Renders SVG with classification-colored pace line + area fill
 * - Renders elevation fill when elevation_stream is present
 * - Does not render elevation fill when elevation_stream is absent
 * - Returns null when paceStream is empty
 * - Handles mismatched array lengths gracefully (resamples)
 * - Classification color mapping and fallback behavior
 * - Heat-adjusted overlay appears only when threshold passes
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock useUnits for imperial pace formatting
jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    formatPace: (sPerKm: number) => {
      const sPerMi = sPerKm * 1.60934;
      const m = Math.floor(sPerMi / 60);
      const s = Math.round(sPerMi % 60);
      return `${m}:${s.toString().padStart(2, '0')}/mi`;
    },
  }),
}));

import { MiniPaceChart, getWorkoutClassificationStyle } from '@/components/home/MiniPaceChart';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PACE_50 = Array.from({ length: 50 }, (_, i) => 300 + i * 2);
const EFFORT_50 = Array.from({ length: 50 }, (_, i) => i / 49);
const ELEV_50 = Array.from({ length: 50 }, (_, i) => 40 + Math.sin(i / 5) * 20);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MiniPaceChart', () => {
  test('renders SVG with pace-line and pace-area', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={140}
      />
    );

    const svg = screen.getByTestId('mini-pace-chart');
    expect(svg).toBeInTheDocument();
    expect(svg.tagName.toLowerCase()).toBe('svg');

    const paceLine = screen.getByTestId('pace-line');
    expect(paceLine).toBeInTheDocument();
    expect(paceLine.getAttribute('d')).toMatch(/^M /);
    // Solid classification stroke (not per-point gradient)
    expect(paceLine.getAttribute('stroke')).toBe('#94a3b8');

    // Area fill exists
    const paceArea = screen.getByTestId('pace-area');
    expect(paceArea).toBeInTheDocument();
    expect(paceArea.getAttribute('fill')).toMatch(/^url\(#paceAreaGrad-/);
  });

  test('renders elevation fill when elevation_stream provided', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        elevationStream={ELEV_50}
        height={140}
      />
    );

    const elevFill = screen.getByTestId('elevation-fill');
    expect(elevFill).toBeInTheDocument();
    expect(elevFill.getAttribute('d')).toMatch(/^M 0/);
  });

  test('does not render elevation fill when elevation_stream absent', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={140}
      />
    );

    expect(screen.queryByTestId('elevation-fill')).not.toBeInTheDocument();
  });

  test('returns null when paceStream is empty', () => {
    const { container } = render(
      <MiniPaceChart
        paceStream={[]}
        effortIntensity={[]}
        height={140}
      />
    );

    expect(container.querySelector('svg')).toBeNull();
  });

  test('handles elevation_stream of different length (resamples)', () => {
    const shortElev = Array.from({ length: 30 }, (_, i) => 50 + i);

    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        elevationStream={shortElev}
        height={140}
      />
    );

    expect(screen.getByTestId('pace-line')).toBeInTheDocument();
    expect(screen.getByTestId('elevation-fill')).toBeInTheDocument();
  });

  test('does not use line linearGradient for pace coloring', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={140}
      />
    );

    const svg = screen.getByTestId('mini-pace-chart');
    const lineGradient = svg.querySelector('linearGradient[id^="paceLineGrad-"]');
    expect(lineGradient).toBeNull();
    expect(screen.getByTestId('pace-line').getAttribute('stroke')).not.toMatch(/^url\(#/);
  });

  test('maps workout classification to expected line colors', () => {
    expect(getWorkoutClassificationStyle('easy').line).toBe('#94a3b8');
    expect(getWorkoutClassificationStyle('long_run').line).toBe('#60a5fa');
    expect(getWorkoutClassificationStyle('progression').line).toBe('#2dd4bf');
    expect(getWorkoutClassificationStyle('strides').line).toBe('#a78bfa');
    expect(getWorkoutClassificationStyle('tempo').line).toBe('#f59e0b');
    expect(getWorkoutClassificationStyle('intervals').line).toBe('#f97316');
    expect(getWorkoutClassificationStyle('race').line).toBe('#f59e0b');
    expect(getWorkoutClassificationStyle('unknown_value').line).toBe('#94a3b8');
  });

  test('renders dashed heat-adjusted overlay only when adjustment > 3', () => {
    const { rerender } = render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        heatAdjustmentPct={4.2}
        height={140}
      />
    );
    expect(screen.getByTestId('mini-adjusted-pace-line')).toBeInTheDocument();
    rerender(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        heatAdjustmentPct={2.9}
        height={140}
      />
    );
    expect(screen.queryByTestId('mini-adjusted-pace-line')).not.toBeInTheDocument();
  });

  test('has interactive container with cursor-crosshair', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={140}
      />
    );
    const container = screen.getByTestId('mini-pace-chart-container');
    expect(container.className).toContain('cursor-crosshair');
  });
});
