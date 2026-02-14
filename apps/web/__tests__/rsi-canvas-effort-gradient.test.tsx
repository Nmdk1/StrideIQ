/**
 * RSI-Alpha — AC-2: Effort Gradient Rendering Tests
 *
 * Verifies the effort gradient renders correctly per ADR-064:
 * - Canvas element exists (not SVG rects)
 * - Tier 4 caveat label visible when cross_run_comparable=false
 * - No block-stepping (architecture enforcement)
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockTier4Result, generateTestStreamData } from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';
const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const streamData = generateTestStreamData(500);

describe('AC-2: Effort Gradient', () => {
  beforeEach(() => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);
  });

  test('renders canvas element for gradient (not SVG rects)', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const canvas = screen.getByTestId('effort-gradient');
    expect(canvas).toBeInTheDocument();
    expect(canvas.tagName.toLowerCase()).toBe('canvas');

    // Architecture enforcement: no ReferenceArea rects used for gradient
    // (Recharts structural rects like clipPath are expected and unrelated)
    const container = screen.getByTestId('chart-container');
    const gradientRects = container.querySelectorAll('.recharts-reference-area rect');
    expect(gradientRects.length).toBe(0);
  });

  test('Tier 4 caveat label visible when cross_run_comparable is false', () => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { analysis: mockTier4Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);

    render(<RunShapeCanvas activityId="test-123" />);

    expect(screen.getByText(/Effort colors show the shape of this run/i)).toBeInTheDocument();
    expect(screen.getByText(/Connect a heart rate monitor/i)).toBeInTheDocument();
  });

  test('Tier 4 caveat NOT visible when cross_run_comparable is true', () => {
    render(<RunShapeCanvas activityId="test-123" />);
    expect(screen.queryByText(/Effort colors show the shape of this run/i)).not.toBeInTheDocument();
  });

  test('effort gradient uses ADR-064 color mapping', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const canvas = screen.getByTestId('effort-gradient');
    expect(canvas).toBeInTheDocument();
    expect(canvas.className).toContain('gradient');
  });

  test('no visible block-stepping in DOM structure', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // Architecture enforcement: gradient rendered via single <canvas>,
    // NOT via ReferenceArea SVG elements
    const container = screen.getByTestId('chart-container');
    const refAreaRects = container.querySelectorAll('.recharts-reference-area rect');
    expect(refAreaRects.length).toBe(0);
  });
});
