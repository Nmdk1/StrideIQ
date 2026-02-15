/**
 * Tier A — Effort-Colored Pace Line Tests
 *
 * The pace trace must use an effort-colored gradient (not flat #60a5fa).
 * When effort data is missing, it falls back to slate-400.
 *
 * These tests are written RED-first: they will fail against the current
 * flat blue pace line and pass after the gradient is implemented.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, generateTestStreamData, mockUnitsImperial } from './rsi-fixtures';

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

const streamDataWithEffort = generateTestStreamData(500);

// Stream data with no effort (all zeros) — still has pace so gradient should render
const streamDataNoEffort = streamDataWithEffort.map((p) => ({ ...p, effort: 0 }));

// Stream data with no pace data at all — gradient should fallback
const streamDataNoPace = streamDataWithEffort.map((p) => ({ ...p, pace: null, effort: 0 }));

describe('Tier A: Effort-colored pace line', () => {
  test('pace stroke marker indicates gradient mode when effort data present', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamDataWithEffort },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const tracePace = screen.getByTestId('trace-pace');
    expect(tracePace).toHaveAttribute('data-stroke-type', 'effort-gradient');
  });

  test('pace effort gradient definition exists when effort data present', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamDataWithEffort },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.getByTestId('pace-effort-gradient-def')).toBeInTheDocument();
  });

  test('pace stroke is NOT flat #60a5fa when effort data present (anti-regression)', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamDataWithEffort },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const tracePace = screen.getByTestId('trace-pace');
    expect(tracePace).not.toHaveAttribute('data-stroke-type', 'flat');
  });

  test('pace stroke still uses gradient when effort is zero but pace exists', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: {
        ...mockTier1Result,
        effort_intensity: [],
        stream: streamDataNoEffort,
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const tracePace = screen.getByTestId('trace-pace');
    // Gradient is now pace-based, so it renders even when effort is zero
    expect(tracePace).toHaveAttribute('data-stroke-type', 'effort-gradient');
  });

  test('pace stroke falls back to slate-400 when no pace data at all', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: {
        ...mockTier1Result,
        effort_intensity: [],
        stream: streamDataNoPace,
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const tracePace = screen.getByTestId('trace-pace');
    expect(tracePace).toHaveAttribute('data-stroke-type', 'fallback');
  });

  test('pace gradient fallback color is slate-400 (#94a3b8)', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: {
        ...mockTier1Result,
        effort_intensity: [],
        stream: streamDataNoPace,
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const tracePace = screen.getByTestId('trace-pace');
    expect(tracePace).toHaveAttribute('data-fallback-color', '#94a3b8');
  });
});
