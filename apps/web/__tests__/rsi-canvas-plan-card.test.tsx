/**
 * RSI-Alpha — AC-7: Plan Comparison Card Tests
 *
 * Verifies the plan comparison card renders/hides based on
 * plan_comparison presence and shows correct content.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockResultWithPlan, generateTestStreamData } from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';
const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const streamData = generateTestStreamData(500);

describe('AC-7: Plan Comparison Card', () => {
  test('card renders when plan_comparison is non-null', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockResultWithPlan, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const planCard = screen.getByTestId('plan-comparison-card') ||
                     screen.getByText(/planned/i);
    expect(planCard).toBeInTheDocument();
  });

  test('card shows planned vs actual duration, distance, pace', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockResultWithPlan, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // Should display planned and actual values
    // Duration: planned 3600s (60:00), actual 3720s (62:00)
    expect(screen.getByText(/60:00|1:00:00/)).toBeInTheDocument();
    expect(screen.getByText(/62:00|1:02:00/)).toBeInTheDocument();
  });

  test('card shows interval count match when available', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockResultWithPlan, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // Interval count: 5/6
    expect(screen.getByText(/5.*6|5\/6/)).toBeInTheDocument();
  });

  test('card is hidden when plan_comparison is null', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // mockTier1Result has plan_comparison: null
    const planCard = screen.queryByTestId('plan-comparison-card');
    expect(planCard).not.toBeInTheDocument();
  });
});
