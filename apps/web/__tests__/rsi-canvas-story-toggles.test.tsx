/**
 * RSI-Alpha — AC-4: Story-Layer Toggles Tests
 *
 * Verifies cadence/grade toggleable in Story layer,
 * default state (HR+pace+elevation visible), and persistence.
 *
 * Test strategy: query data-testid markers and accessible roles,
 * not Recharts internal class names.
 */
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
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

describe('AC-4: Story-Layer Toggles', () => {
  beforeEach(() => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: streamData },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);
  });

  test('default state: HR + pace + elevation visible, cadence and grade OFF', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    // Default-visible traces
    expect(screen.getByTestId('trace-hr')).toBeInTheDocument();
    expect(screen.getByTestId('trace-pace')).toBeInTheDocument();
    expect(screen.getByTestId('terrain-fill')).toBeInTheDocument();

    // Not visible by default
    expect(screen.queryByTestId('trace-cadence')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trace-grade')).not.toBeInTheDocument();
  });

  test('toggling cadence ON makes cadence trace visible', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const cadenceToggle = screen.getByRole('button', { name: /cadence/i });
    fireEvent.click(cadenceToggle);

    expect(screen.getByTestId('trace-cadence')).toBeInTheDocument();
  });

  test('toggling grade ON makes grade trace visible', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const gradeToggle = screen.getByRole('button', { name: /grade/i });
    fireEvent.click(gradeToggle);

    expect(screen.getByTestId('trace-grade')).toBeInTheDocument();
  });

  test('toggle state persists across rerender (no reset on resize)', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    const cadenceToggle = screen.getByRole('button', { name: /cadence/i });
    fireEvent.click(cadenceToggle);

    // Simulate window resize
    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Cadence should still be visible
    expect(screen.getByTestId('trace-cadence')).toBeInTheDocument();
  });

  test('multiple toggles can be active simultaneously', () => {
    render(<RunShapeCanvas activityId="test-123" />);

    fireEvent.click(screen.getByRole('button', { name: /cadence/i }));
    fireEvent.click(screen.getByRole('button', { name: /grade/i }));

    expect(screen.getByTestId('trace-cadence')).toBeInTheDocument();
    expect(screen.getByTestId('trace-grade')).toBeInTheDocument();
  });
});
