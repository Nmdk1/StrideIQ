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

describe('RunShapeCanvas adjusted pace overlay', () => {
  beforeEach(() => {
    mockUseStreamAnalysis.mockReturnValue({
      data: { ...mockTier1Result, stream: generateTestStreamData(220) },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as any);
  });

  test('shows overlay and label when heat adjustment is above threshold', () => {
    render(<RunShapeCanvas activityId="a1" heatAdjustmentPct={8} temperatureF={86} />);
    expect(screen.getByTestId('trace-adjusted-pace')).toBeInTheDocument();
    expect(screen.getByTestId('trace-adjusted-pace')).toHaveAttribute('data-adjustment-factor', '1.0800');
    expect(screen.getByTestId('adjusted-pace-label')).toBeInTheDocument();
  });

  test('hides overlay when heat adjustment is 3 or below', () => {
    render(<RunShapeCanvas activityId="a2" heatAdjustmentPct={3} />);
    expect(screen.queryByTestId('trace-adjusted-pace')).not.toBeInTheDocument();
    expect(screen.queryByTestId('adjusted-pace-label')).not.toBeInTheDocument();
  });
});

