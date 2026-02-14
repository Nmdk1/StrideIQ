/**
 * RSI-Alpha — AC-6: Segment Overlay Tests
 *
 * Verifies detected segments render as colored background bands
 * behind the trace lines, aligned with segment timestamps.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockEmptyResult, generateTestStreamData } from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  ...jest.requireActual('@/components/activities/rsi/hooks/useStreamAnalysis'),
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';
const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const streamData = generateTestStreamData(500);

describe('AC-6: Segment Overlay', () => {
  beforeEach(() => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);
  });

  test('renders segment bands for each segment in analysis result', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // mockTier1Result has 5 segments
    const segmentBands = document.querySelectorAll('[data-testid^="segment-band-"]');
    expect(segmentBands.length).toBe(5);
  });

  test('segment bands use correct colors per type', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // Check each segment type has appropriate color class or style
    const warmupBand = document.querySelector('[data-testid="segment-band-warmup"]') ||
                       document.querySelector('[data-segment-type="warmup"]');
    const workBand = document.querySelector('[data-testid="segment-band-work"]') ||
                     document.querySelector('[data-segment-type="work"]');
    const recoveryBand = document.querySelector('[data-testid="segment-band-recovery"]') ||
                         document.querySelector('[data-segment-type="recovery"]');
    const cooldownBand = document.querySelector('[data-testid="segment-band-cooldown"]') ||
                         document.querySelector('[data-segment-type="cooldown"]');

    // At least warmup, work, recovery, cooldown should be present in our fixture
    expect(warmupBand).toBeInTheDocument();
    expect(workBand).toBeInTheDocument();
    expect(recoveryBand).toBeInTheDocument();
    expect(cooldownBand).toBeInTheDocument();
  });

  test('segment bands align with start_time_s and end_time_s', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // First segment: warmup 0–480s
    const firstBand = document.querySelector('[data-testid="segment-band-0"]') ||
                      document.querySelectorAll('[data-testid^="segment-band-"]')[0];

    if (firstBand) {
      // Check data attributes for time alignment
      expect(firstBand.getAttribute('data-start') || '').toBe('0');
      expect(firstBand.getAttribute('data-end') || '').toBe('480');
    } else {
      // Component exists but uses different DOM structure
      expect(firstBand).toBeInTheDocument();
    }
  });

  test('no segment overlay when segments array is empty', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockEmptyResult, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const segmentBands = document.querySelectorAll('[data-testid^="segment-band-"]');
    expect(segmentBands.length).toBe(0);
  });
});
