/**
 * RSI-Alpha — Splits Tests
 *
 * After the activity detail simplification, splits are always rendered below
 * the chart — no tab click needed. The Story/Splits/Lab tab bar is gone.
 */
import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, generateTestStreamData, mockUnitsImperial } from './rsi-fixtures';
import type { Split } from '@/lib/types/splits';

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
  { split_number: 1, distance: 1609, elapsed_time: 200, moving_time: 195, average_heartrate: 140, max_heartrate: 155, average_cadence: 85, gap_seconds_per_mile: 720 },
  { split_number: 2, distance: 1609, elapsed_time: 180, moving_time: 175, average_heartrate: 155, max_heartrate: 170, average_cadence: 88, gap_seconds_per_mile: 680 },
  { split_number: 3, distance: 800,  elapsed_time: 80,  moving_time: 78,  average_heartrate: 165, max_heartrate: 180, average_cadence: 92, gap_seconds_per_mile: 650 },
];

function renderWithSplits(splits: Split[] | null = mockSplits) {
  mockUseStreamAnalysis.mockReturnValue({
    data: { ...mockTier1Result, stream: streamData },
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  } as any);
  return render(<RunShapeCanvas activityId="test-123" splits={splits} />);
}

describe('Tab System: Removed', () => {
  test('Story/Splits/Lab tab bar is not rendered', () => {
    renderWithSplits();

    expect(screen.queryByTestId('tab-story')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tab-splits')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tab-lab')).not.toBeInTheDocument();
  });
});

describe('Splits: Always Visible', () => {
  test('splits panel renders without any tab interaction', () => {
    renderWithSplits();

    expect(screen.getByTestId('splits-panel')).toBeInTheDocument();
  });

  test('lab mode panel is not in the document', () => {
    renderWithSplits();

    expect(screen.queryByTestId('lab-mode')).not.toBeInTheDocument();
  });
});

describe('Splits: Table Rendering', () => {
  test('splits table renders correct number of rows', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    // Header row + 3 data rows = 4
    expect(rows.length).toBe(4);
  });

  test('splits table shows pace formatted via useUnits', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    expect(panel.textContent).toMatch(/\/mi/);
  });

  test('splits table shows distance formatted via useUnits', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    expect(panel.textContent).toMatch(/mi/);
  });
});

describe('Splits: Empty State', () => {
  test('empty splits array shows empty state message', () => {
    renderWithSplits([]);

    expect(screen.getByTestId('splits-panel-empty')).toBeInTheDocument();
    expect(screen.getByText(/no splits data/i)).toBeInTheDocument();
  });

  test('null splits does not render splits panel', () => {
    renderWithSplits(null);

    expect(screen.queryByTestId('splits-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('splits-panel-empty')).not.toBeInTheDocument();
  });
});

describe('Splits: Layout', () => {
  test('splits panel renders without scroll constraint so all splits are visible', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    expect(panel).not.toHaveClass('max-h-[300px]');
    expect(panel).not.toHaveClass('overflow-y-auto');
  });
});

describe('Splits: Two-Way Hover', () => {
  test('hovering a split row triggers highlight overlay on chart', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    // rows[0] is header, rows[1] is first data row
    fireEvent.mouseEnter(rows[1]);

    expect(screen.getByTestId('highlight-overlay')).toBeInTheDocument();
  });

  test('leaving a split row removes highlight overlay', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    const firstDataRow = rows[1];

    fireEvent.mouseEnter(firstDataRow);
    expect(screen.getByTestId('highlight-overlay')).toBeInTheDocument();

    fireEvent.mouseLeave(firstDataRow);
    expect(screen.queryByTestId('highlight-overlay')).not.toBeInTheDocument();
  });

  test('highlight overlay has border-line styling (distinct from segment bands)', () => {
    renderWithSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    fireEvent.mouseEnter(rows[1]);

    const overlay = screen.getByTestId('highlight-overlay');
    expect(overlay.style.borderLeft).toContain('solid');
    expect(overlay.style.borderRight).toContain('solid');
  });
});
