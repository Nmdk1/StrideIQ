/**
 * MiniPaceChart — Unit tests for the home hero pace chart.
 *
 * Tests:
 * - Renders SVG with gradient pace line when valid data provided
 * - Renders elevation fill when elevation_stream is present
 * - Does not render elevation fill when elevation_stream is absent
 * - Returns null when paceStream is empty
 * - Handles mismatched array lengths gracefully (resamples)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock effortToColor to return predictable colors
jest.mock('@/components/activities/rsi/utils/effortColor', () => ({
  effortToColor: (value: number) => `hsl(${Math.round(value * 120)}, 80%, 50%)`,
}));

import { MiniPaceChart } from '@/components/home/MiniPaceChart';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PACE_50 = Array.from({ length: 50 }, (_, i) => 300 + i * 2);  // 300-398 s/km
const EFFORT_50 = Array.from({ length: 50 }, (_, i) => i / 49);      // 0..1
const ELEV_50 = Array.from({ length: 50 }, (_, i) => 40 + Math.sin(i / 5) * 20);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MiniPaceChart', () => {
  test('renders SVG with pace-line path when valid data', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={120}
      />
    );

    const svg = screen.getByTestId('mini-pace-chart');
    expect(svg).toBeInTheDocument();
    expect(svg.tagName.toLowerCase()).toBe('svg');

    const paceLine = screen.getByTestId('pace-line');
    expect(paceLine).toBeInTheDocument();
    expect(paceLine.getAttribute('d')).toMatch(/^M /);
    expect(paceLine.getAttribute('stroke')).toMatch(/^url\(#miniPaceGrad-/);
  });

  test('renders elevation fill when elevation_stream provided', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        elevationStream={ELEV_50}
        height={120}
      />
    );

    const elevFill = screen.getByTestId('elevation-fill');
    expect(elevFill).toBeInTheDocument();
    expect(elevFill.getAttribute('d')).toMatch(/^M 0/);
    expect(elevFill.getAttribute('fill')).toContain('rgba');
  });

  test('does not render elevation fill when elevation_stream absent', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={120}
      />
    );

    expect(screen.queryByTestId('elevation-fill')).not.toBeInTheDocument();
  });

  test('returns null when paceStream is empty', () => {
    const { container } = render(
      <MiniPaceChart
        paceStream={[]}
        effortIntensity={[]}
        height={120}
      />
    );

    expect(container.querySelector('svg')).toBeNull();
  });

  test('handles elevation_stream of different length (resamples)', () => {
    // Elevation has 30 points, pace has 50 — should resample elevation
    const shortElev = Array.from({ length: 30 }, (_, i) => 50 + i);

    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        elevationStream={shortElev}
        height={100}
      />
    );

    // Should still render both elements
    expect(screen.getByTestId('pace-line')).toBeInTheDocument();
    expect(screen.getByTestId('elevation-fill')).toBeInTheDocument();
  });

  test('gradient stops use effortToColor mapping', () => {
    render(
      <MiniPaceChart
        paceStream={PACE_50}
        effortIntensity={EFFORT_50}
        height={120}
      />
    );

    const svg = screen.getByTestId('mini-pace-chart');
    const stops = svg.querySelectorAll('stop');
    expect(stops.length).toBeGreaterThan(0);
    // Each stop should have an hsl color from our mock
    stops.forEach(stop => {
      expect(stop.getAttribute('stop-color')).toMatch(/^hsl\(/);
    });
  });
});
