/**
 * RSI chart scaling honesty — pace domain, altitude domain, separate cadence/grade axes.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockUnitsImperial, type StreamPoint } from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => mockUnitsImperial,
}));
jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  ...jest.requireActual('@/components/activities/rsi/hooks/useStreamAnalysis'),
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';

const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const PACE_MIN_SPAN = 30;

function steadyPaceNarrowStream(count: number): StreamPoint[] {
  const points: StreamPoint[] = [];
  for (let i = 0; i < count; i++) {
    points.push({
      time: i,
      hr: 140,
      pace: 300 + (i % 3),
      altitude: 150,
      grade: 0,
      cadence: 175,
      effort: 0.5,
    });
  }
  return points;
}

function altitudeReliefStream(count: number): StreamPoint[] {
  const points: StreamPoint[] = [];
  const last = Math.max(count - 1, 1);
  for (let i = 0; i < count; i++) {
    const alt = 100 + (i / last) * 70;
    points.push({
      time: i,
      hr: 140,
      pace: 360,
      altitude: alt,
      grade: 0,
      cadence: 175,
      effort: 0.5,
    });
  }
  return points;
}

describe('RSI canvas scaling honesty', () => {
  beforeEach(() => {
    mockUseStreamAnalysis.mockReset();
  });

  test('pace domain includes full smoothed range (no percentile edge pinning)', () => {
    const points: StreamPoint[] = [];
    for (let i = 0; i < 60; i++) {
      const pace = i < 30 ? 385 : 305;
      points.push({
        time: i,
        hr: 140,
        pace,
        altitude: 100,
        grade: 0,
        cadence: 175,
        effort: 0.5,
      });
    }
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: points },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="bimodal-pace" />);

    const marker = screen.getByTestId('pace-domain-marker');
    const lo = parseFloat(marker.getAttribute('data-min') || '0');
    const hi = parseFloat(marker.getAttribute('data-max') || '0');
    expect(hi - lo).toBeGreaterThanOrEqual(PACE_MIN_SPAN);
    expect(lo).toBeLessThanOrEqual(320);
    expect(hi).toBeGreaterThanOrEqual(375);
  });

  test('pace domain enforces minimum span for steady pace', () => {
    const stream = steadyPaceNarrowStream(40);
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="steady-pace" />);

    const marker = screen.getByTestId('pace-domain-marker');
    const dMin = parseFloat(marker.getAttribute('data-min') || '0');
    const dMax = parseFloat(marker.getAttribute('data-max') || '0');
    expect(Number.isFinite(dMin) && Number.isFinite(dMax)).toBe(true);
    expect(dMax - dMin).toBeGreaterThanOrEqual(PACE_MIN_SPAN);
  });

  test('altitude domain is relief-aware and non-flat', () => {
    const stream = altitudeReliefStream(50);
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="alt-relief" />);

    expect(screen.getByTestId('terrain-fill')).toBeInTheDocument();

    const marker = screen.getByTestId('altitude-domain-marker');
    const dMin = parseFloat(marker.getAttribute('data-min') || '');
    const dMax = parseFloat(marker.getAttribute('data-max') || '');
    expect(dMax).toBeGreaterThan(dMin);
    expect(dMax - dMin).toBeGreaterThan(40);
  });

  test('cadence and grade use distinct axes when both toggled on', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: steadyPaceNarrowStream(40) },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="axes" />);

    fireEvent.click(screen.getByRole('button', { name: /cadence/i }));
    fireEvent.click(screen.getByRole('button', { name: /grade/i }));

    expect(screen.getByTestId('trace-cadence')).toBeInTheDocument();
    expect(screen.getByTestId('trace-grade')).toBeInTheDocument();

    const cadAxis = screen.getByTestId('axis-marker-cadence');
    const grAxis = screen.getByTestId('axis-marker-grade');
    expect(cadAxis.getAttribute('data-axis-id')).toBe('cadence');
    expect(grAxis.getAttribute('data-axis-id')).toBe('grade');
    expect(cadAxis.getAttribute('data-axis-id')).not.toBe(grAxis.getAttribute('data-axis-id'));
  });

  test('terrain baseValue marker documents dataMin anchor', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: altitudeReliefStream(30) },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="baseval" />);

    const marker = screen.getByTestId('terrain-basevalue-marker');
    expect(marker.getAttribute('data-basevalue')).toBe('dataMin');
  });
});
