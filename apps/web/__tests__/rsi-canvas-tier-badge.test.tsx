/**
 * RSI-Alpha — Tier Badge + Tier 4 Caveat Tests
 *
 * After the activity detail simplification (tab removal), the TierBadge component
 * is no longer rendered on the page. The Tier 4 caveat remains because it honestly
 * communicates that effort colors are relative to this run only, which is useful.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockTier4Result, generateTestStreamData, mockUnitsImperial } from './rsi-fixtures';

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

const streamData = generateTestStreamData(500);

describe('Tier Badge: Removed', () => {
  test('tier badge is NOT rendered (removed as misleading)', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.queryByTestId('tier-badge')).not.toBeInTheDocument();
  });

  test('tier badge absent for Tier 4 result too', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier4Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.queryByTestId('tier-badge')).not.toBeInTheDocument();
  });
});

describe('Tier 4 Caveat: Still Visible', () => {
  test('Tier 4 caveat is always visible and not tooltip-gated', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier4Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const caveatText = screen.getByText(/Effort colors show the shape of this run/i);
    expect(caveatText).toBeInTheDocument();
    expect(caveatText).toBeVisible();
  });

  test('Tier 4 caveat absent for Tier 1 result (no misleading message)', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.queryByTestId('tier4-caveat')).not.toBeInTheDocument();
  });
});
