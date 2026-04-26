/**
 * RSI — RunShapeCanvas no longer embeds the splits table (Apr 2026 tabbed activity page).
 * Splits render on the activity page Splits tab (see BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT).
 */
import React from 'react';
import { screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, generateTestStreamData, mockUnitsImperial } from './rsi-fixtures';
import type { Split } from '@/lib/types/splits';
import { renderWithStreamHover } from '@/test-utils/renderWithStreamHover';

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

const mockSplits: Split[] = [
  { split_number: 1, distance: 1609, elapsed_time: 200, moving_time: 195, average_heartrate: 140, max_heartrate: 155, average_cadence: 85, gap_s_per_km: 447, lap_type: null, interval_number: null },
];

function renderCanvas(splits: Split[] | null = mockSplits) {
  mockUseStreamAnalysis.mockReturnValue({
    data: { ...mockTier1Result, stream: streamData },
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  } as never);
  return renderWithStreamHover(<RunShapeCanvas activityId="test-123" splits={splits} />);
}

describe('RunShapeCanvas: legacy Story/Splits/Lab tabs', () => {
  test('Story/Splits/Lab tab bar is not rendered', () => {
    renderCanvas();
    expect(screen.queryByTestId('tab-story')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tab-splits')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tab-lab')).not.toBeInTheDocument();
  });
});

describe('RunShapeCanvas: splits table moved off canvas', () => {
  test('splits panel is not rendered inside RunShapeCanvas', () => {
    renderCanvas();
    expect(screen.queryByTestId('splits-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('splits-panel-empty')).not.toBeInTheDocument();
  });

  test('lab mode panel is not in the document', () => {
    renderCanvas();
    expect(screen.queryByTestId('lab-mode')).not.toBeInTheDocument();
  });

  test('chart surface still mounts with splits prop for boundary math', () => {
    renderCanvas();
    expect(screen.getByTestId('rsi-canvas')).toBeInTheDocument();
  });
});
