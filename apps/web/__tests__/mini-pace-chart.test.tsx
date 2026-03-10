/**
 * MiniPaceChart — Unit tests for the home hero pace chart.
 *
 * Tests:
 * - Renders SVG with gradient pace line + area fill
 * - Renders elevation fill when elevation_stream is present
 * - Does not render elevation fill when elevation_stream is absent
 * - Returns null when paceStream is empty
 * - Handles mismatched array lengths gracefully (resamples)
 * - Gradient stops use boosted effortToColor
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock effortToColor to return predictable colors
jest.mock('@/components/activities/rsi/utils/effortColor', () => ({
  effortToColor: (value: number) => `rgb(${Math.round(value * 120)},${Math.round(value * 80)},50)`,
}));

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

import { MiniPaceChart } from '@/components/home/MiniPaceChart';

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
    // Gradient stroke
    expect(paceLine.getAttribute('stroke')).toMatch(/^url\(#paceLineGrad-/);

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

  test('gradient stops use boosted colors', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={140}
      />
    );

    const svg = screen.getByTestId('mini-pace-chart');
    const stops = svg.querySelectorAll('stop');
    expect(stops.length).toBeGreaterThan(0);
    stops.forEach(stop => {
      expect(stop.getAttribute('stop-color')).toMatch(/^rgb/);
    });
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
