/**
 * RSI-Alpha — AC-3: Unified Crosshair Tests
 *
 * Verifies crosshair spans all visible trace layers and shows
 * exact values for every visible channel at the hovered timestamp.
 *
 * Architecture: Tests fire mouseMove on [data-testid="chart-overlay"],
 * which is our interaction overlay — not a Recharts internal element.
 * The component computes the hovered index from clientX and renders
 * the tooltip from state.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

const streamData = generateTestStreamData(500);

/**
 * Helper: simulate hover at a fraction of the chart width.
 * The overlay uses getBoundingClientRect to compute the data index,
 * so we mock it to return a known rect.
 */
function hoverAtFraction(overlay: Element, fraction: number) {
  // Mock getBoundingClientRect so the overlay can compute position
  Object.defineProperty(overlay, 'getBoundingClientRect', {
    value: () => ({
      left: 0, top: 0, right: 800, bottom: 256,
      width: 800, height: 256, x: 0, y: 0,
      toJSON: () => {},
    }),
    configurable: true,
  });

  fireEvent.mouseMove(overlay, {
    clientX: Math.round(fraction * 800),
    clientY: 128,
  });
}

describe('AC-3: Unified Crosshair', () => {
  beforeEach(() => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);
  });

  test('hovering shows values for all visible channels', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const overlay = screen.getByTestId('chart-overlay');
    hoverAtFraction(overlay, 0.5);

    // Scope to the tooltip to avoid collision with inline drift metrics
    const tooltip = screen.getByTestId('crosshair-tooltip');
    expect(tooltip).toHaveTextContent(/bpm/i);
    expect(tooltip).toHaveTextContent(/\/mi/i);
  });

  test('crosshair shows values for toggled-on secondary channels', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // Toggle cadence ON
    const cadenceToggle = screen.getByRole('button', { name: /cadence/i });
    fireEvent.click(cadenceToggle);

    // Hover
    const overlay = screen.getByTestId('chart-overlay');
    hoverAtFraction(overlay, 0.5);

    // Cadence should appear in the tooltip (not just in drift metrics)
    const tooltip = screen.getByTestId('crosshair-tooltip');
    expect(tooltip).toHaveTextContent(/spm/i);
  });

  test('crosshair hides values for toggled-off channels', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // Hover without toggling cadence
    const overlay = screen.getByTestId('chart-overlay');
    hoverAtFraction(overlay, 0.5);

    // Cadence should NOT appear in the tooltip (default off)
    const tooltip = screen.getByTestId('crosshair-tooltip');
    expect(tooltip).not.toHaveTextContent(/\d+ spm/i);
  });

  test('crosshair line persists while hovering (no view switching needed)', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const overlay = screen.getByTestId('chart-overlay');
    hoverAtFraction(overlay, 0.5);

    // Crosshair line exists
    expect(screen.getByTestId('crosshair-line')).toBeInTheDocument();

    // Move to another position — line stays visible
    hoverAtFraction(overlay, 0.8);
    expect(screen.getByTestId('crosshair-line')).toBeInTheDocument();
  });
});
