/**
 * RSI-Alpha — Splits Mode Tests
 *
 * Verifies the Splits tab: tab switching, SplitsModePanel rendering,
 * two-way hover binding (row↔chart), scroll container, and empty states.
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

// Mock splits matching a ~500s run with 3 splits
const mockSplits: Split[] = [
  { split_number: 1, distance: 1609, elapsed_time: 200, moving_time: 195, average_heartrate: 140, max_heartrate: 155, average_cadence: 85, gap_seconds_per_mile: 720 },
  { split_number: 2, distance: 1609, elapsed_time: 180, moving_time: 175, average_heartrate: 155, max_heartrate: 170, average_cadence: 88, gap_seconds_per_mile: 680 },
  { split_number: 3, distance: 800,  elapsed_time: 80,  moving_time: 78,  average_heartrate: 165, max_heartrate: 180, average_cadence: 92, gap_seconds_per_mile: 650 },
];

function setupMock() {
  mockUseStreamAnalysis.mockReturnValue({
    data: { ...mockTier1Result, stream: streamData },
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  } as any);
}

function renderWithSplits(splits: Split[] | null = mockSplits) {
  setupMock();
  return render(<RunShapeCanvas activityId="test-123" splits={splits} />);
}

function renderAndSwitchToSplits(splits: Split[] | null = mockSplits) {
  const result = renderWithSplits(splits);
  const splitsTab = screen.getByRole('button', { name: /splits/i });
  fireEvent.click(splitsTab);
  return result;
}

describe('Splits Mode: Tab System', () => {
  test('three tabs are rendered: Story, Splits, Lab', () => {
    renderWithSplits();

    expect(screen.getByTestId('tab-story')).toBeInTheDocument();
    expect(screen.getByTestId('tab-splits')).toBeInTheDocument();
    expect(screen.getByTestId('tab-lab')).toBeInTheDocument();
  });

  test('Story tab is active by default', () => {
    renderWithSplits();

    const storyTab = screen.getByTestId('tab-story');
    expect(storyTab).toHaveClass('bg-blue-600');

    const splitsTab = screen.getByTestId('tab-splits');
    expect(splitsTab).toHaveClass('bg-slate-700');
  });

  test('clicking Splits tab activates it and shows splits panel', () => {
    renderAndSwitchToSplits();

    const splitsTab = screen.getByTestId('tab-splits');
    expect(splitsTab).toHaveClass('bg-blue-600');

    expect(screen.getByTestId('splits-panel')).toBeInTheDocument();
  });

  test('splits panel is not visible in Story mode', () => {
    renderWithSplits();

    expect(screen.queryByTestId('splits-panel')).not.toBeInTheDocument();
  });

  test('Lab mode is not visible when Splits is active', () => {
    renderAndSwitchToSplits();

    expect(screen.queryByTestId('lab-mode')).not.toBeInTheDocument();
  });
});

describe('Splits Mode: Table Rendering', () => {
  test('splits table renders correct number of rows', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    // Header row + 3 data rows = 4
    expect(rows.length).toBe(4);
  });

  test('splits table shows pace formatted via useUnits', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    // Should contain /mi (imperial mock), not /km
    expect(panel.textContent).toMatch(/\/mi/);
  });

  test('splits table shows distance formatted via useUnits', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    // Should contain 'mi' unit
    expect(panel.textContent).toMatch(/mi/);
  });
});

describe('Splits Mode: Empty State', () => {
  test('empty splits shows message', () => {
    renderAndSwitchToSplits([]);

    expect(screen.getByTestId('splits-panel-empty')).toBeInTheDocument();
    expect(screen.getByText(/no splits data/i)).toBeInTheDocument();
  });

  test('null splits does not render splits panel', () => {
    renderAndSwitchToSplits(null);

    expect(screen.queryByTestId('splits-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('splits-panel-empty')).not.toBeInTheDocument();
  });
});

describe('Splits Mode: Layout', () => {
  test('splits panel renders without scroll constraint so all splits are visible', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    expect(panel).not.toHaveClass('max-h-[300px]');
    expect(panel).not.toHaveClass('overflow-y-auto');
  });
});

describe('Splits Mode: Two-Way Hover', () => {
  test('hovering a split row triggers highlight overlay on chart', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    // rows[0] is header, rows[1] is first data row
    const firstDataRow = rows[1];

    fireEvent.mouseEnter(firstDataRow);

    // HighlightOverlay should appear
    expect(screen.getByTestId('highlight-overlay')).toBeInTheDocument();
  });

  test('leaving a split row removes highlight overlay', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    const firstDataRow = rows[1];

    fireEvent.mouseEnter(firstDataRow);
    expect(screen.getByTestId('highlight-overlay')).toBeInTheDocument();

    fireEvent.mouseLeave(firstDataRow);
    expect(screen.queryByTestId('highlight-overlay')).not.toBeInTheDocument();
  });

  test('highlight overlay has border-line styling (distinct from segment bands)', () => {
    renderAndSwitchToSplits();

    const panel = screen.getByTestId('splits-panel');
    const rows = within(panel).getAllByRole('row');
    fireEvent.mouseEnter(rows[1]);

    const overlay = screen.getByTestId('highlight-overlay');
    expect(overlay.style.borderLeft).toContain('solid');
    expect(overlay.style.borderRight).toContain('solid');
  });
});
