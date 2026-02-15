/**
 * A2: HR Sanity Check — Frontend Tests
 *
 * Verifies:
 *   1. HR toggle button shows/hides HR trace
 *   2. HR unreliable note appears when hr_reliable === false
 *   3. HR unreliable note does NOT appear when hr_reliable === true
 *   4. HR toggle defaults to ON
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

describe('A2: HR Sanity Check — Frontend', () => {
  describe('HR Toggle', () => {
    beforeEach(() => {
      mockUseStreamAnalysis.mockReturnValue({
        data: { ...mockTier1Result, stream: streamData },
        isLoading: false,
        error: null,
        refetch: jest.fn(),
      } as any);
    });

    test('HR toggle button exists', () => {
      render(<RunShapeCanvas activityId="test-123" />);
      const hrToggle = screen.getByTestId('hr-toggle');
      expect(hrToggle).toBeInTheDocument();
      expect(hrToggle).toHaveTextContent('HR');
    });

    test('HR trace visible by default (toggle ON)', () => {
      render(<RunShapeCanvas activityId="test-123" />);
      expect(screen.getByTestId('trace-hr')).toBeInTheDocument();
    });

    test('toggling HR OFF hides HR trace', () => {
      render(<RunShapeCanvas activityId="test-123" />);
      const hrToggle = screen.getByTestId('hr-toggle');
      fireEvent.click(hrToggle);
      expect(screen.queryByTestId('trace-hr')).not.toBeInTheDocument();
    });

    test('toggling HR OFF then ON restores HR trace', () => {
      render(<RunShapeCanvas activityId="test-123" />);
      const hrToggle = screen.getByTestId('hr-toggle');
      fireEvent.click(hrToggle); // OFF
      expect(screen.queryByTestId('trace-hr')).not.toBeInTheDocument();
      fireEvent.click(hrToggle); // ON
      expect(screen.getByTestId('trace-hr')).toBeInTheDocument();
    });
  });

  describe('HR Unreliable Note', () => {
    test('shows unreliable note when hr_reliable is false', () => {
      mockUseStreamAnalysis.mockReturnValue({
        data: {
          ...mockTier1Result,
          stream: streamData,
          hr_reliable: false,
          hr_note: 'Heart rate inversely correlated with pace',
        },
        isLoading: false,
        error: null,
        refetch: jest.fn(),
      } as any);

      render(<RunShapeCanvas activityId="test-123" />);
      const note = screen.getByTestId('hr-unreliable-note');
      expect(note).toBeInTheDocument();
      expect(note).toHaveTextContent(/HR data appears unreliable/i);
    });

    test('does NOT show unreliable note when hr_reliable is true', () => {
      mockUseStreamAnalysis.mockReturnValue({
        data: {
          ...mockTier1Result,
          stream: streamData,
          hr_reliable: true,
          hr_note: null,
        },
        isLoading: false,
        error: null,
        refetch: jest.fn(),
      } as any);

      render(<RunShapeCanvas activityId="test-123" />);
      expect(screen.queryByTestId('hr-unreliable-note')).not.toBeInTheDocument();
    });
  });
});
