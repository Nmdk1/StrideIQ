/**
 * RSI-Alpha — AC-8: Confidence + Tier Badge Tests
 *
 * Verifies the tier badge renders on every view with correct label,
 * confidence percentage, and Tier 4 caveat visibility.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockTier4Result, generateTestStreamData } from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  ...jest.requireActual('@/components/activities/rsi/hooks/useStreamAnalysis'),
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';
const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const streamData = generateTestStreamData(500);

describe('AC-8: Confidence + Tier Badge', () => {
  test('badge renders on every canvas view', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const badge = screen.getByTestId('tier-badge') ||
                  screen.getByText(/Tier \d/i);
    expect(badge).toBeInTheDocument();
  });

  test('badge shows correct tier label for Tier 1', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.getByText(/Tier 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Threshold HR/i)).toBeInTheDocument();
  });

  test('badge shows correct tier label for Tier 4', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier4Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.getByText(/Tier 4/i)).toBeInTheDocument();
    expect(screen.getByText(/Relative to this run/i)).toBeInTheDocument();
  });

  test('badge shows confidence as percentage', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // confidence=0.88 → "88%"
    expect(screen.getByText(/88%/)).toBeInTheDocument();
  });

  test('Tier 4 caveat subtitle is always visible, not tooltip-gated', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier4Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // Caveat text should be in the document directly (not inside a tooltip)
    const caveatText = screen.getByText(/Effort colors show the shape of this run/i);
    expect(caveatText).toBeInTheDocument();

    // Verify it's not hidden in a tooltip (visible without hover)
    expect(caveatText).toBeVisible();
  });
});
