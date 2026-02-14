/**
 * RSI-Alpha — AC-10: Loading States Tests
 *
 * Verifies correct UI for each stream lifecycle state:
 * pending/fetching → spinner, failed → retry, unavailable → hidden, success → canvas.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import {
  mockTier1Result,
  mockPendingResponse,
  mockUnavailableResponse,
  generateTestStreamData,
} from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';
const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const streamData = generateTestStreamData(500);

describe('AC-10: Loading States', () => {
  test('pending status shows loading spinner', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: mockPendingResponse,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // Spinner or loading indicator
    const spinner = screen.getByTestId('loading-spinner') ||
                    screen.getByRole('progressbar') ||
                    document.querySelector('[class*="spinner"]') ||
                    document.querySelector('[class*="animate-spin"]');
    expect(spinner).toBeInTheDocument();

    // Loading text
    expect(screen.getByText(/stream data loading/i)).toBeInTheDocument();
  });

  test('failed status shows retry hint', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error('Stream fetch failed'),
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.getByText(/stream data unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/retry/i)).toBeInTheDocument();
  });

  test('unavailable status hides stream panel entirely', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: mockUnavailableResponse,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // Entire RSI canvas should NOT be in the document
    const canvas = document.querySelector('[data-testid="rsi-canvas"]');
    expect(canvas).not.toBeInTheDocument();

    // No spinner either
    expect(screen.queryByText(/stream data loading/i)).not.toBeInTheDocument();
  });

  test('success status renders full canvas', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    // Canvas container should be present
    const canvasContainer = document.querySelector('[data-testid="rsi-canvas"]') ||
                            document.querySelector('canvas');
    expect(canvasContainer).toBeInTheDocument();
  });

  test('retry action triggers refetch', () => {
    const mockRefetch = jest.fn();
    mockUseStreamAnalysis.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error('Stream fetch failed'),
      refetch: mockRefetch,
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    const retryButton = screen.getByText(/retry/i);
    fireEvent.click(retryButton);

    expect(mockRefetch).toHaveBeenCalled();
  });
});
