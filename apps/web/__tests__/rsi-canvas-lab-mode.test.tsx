/**
 * RSI-Alpha — AC-9: Lab Mode Tests
 *
 * Verifies Lab toggle shows raw data mode with full-precision traces,
 * athlete-specific zone overlays, segment table, and drift metrics.
 */
import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockTier4Result, generateTestStreamData } from './rsi-fixtures';

import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';

jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  ...jest.requireActual('@/components/activities/rsi/hooks/useStreamAnalysis'),
  useStreamAnalysis: jest.fn(),
}));

import { useStreamAnalysis } from '@/components/activities/rsi/hooks/useStreamAnalysis';
const mockUseStreamAnalysis = useStreamAnalysis as jest.MockedFunction<typeof useStreamAnalysis>;

const streamData = generateTestStreamData(500);

function renderAndSwitchToLab(analysisResult = mockTier1Result) {
  mockUseStreamAnalysis.mockReturnValue({
    data: { ...analysisResult, stream: streamData },
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  } as any);

  render(<RunShapeCanvas activityId="test-123" />);

  // Switch to Lab mode
  const labToggle = screen.getByRole('button', { name: /lab/i });
  fireEvent.click(labToggle);
}

describe('AC-9: Lab Mode', () => {
  test('Lab toggle switches to raw data mode', () => {
    renderAndSwitchToLab();

    // Lab mode should show full-precision data elements
    const labContainer = screen.getByTestId('lab-mode') ||
                         document.querySelector('[data-testid="lab-mode"]');
    expect(labContainer).toBeInTheDocument();
  });

  test('zone overlays use athlete physiological data', () => {
    // Tier 1 result (has threshold_hr, max_hr, resting_hr)
    renderAndSwitchToLab(mockTier1Result);

    // Zone overlay should reference athlete's own threshold (165 bpm)
    const zoneOverlay = document.querySelector('[data-testid="zone-overlay"]') ||
                        screen.queryByText(/165/);
    expect(zoneOverlay).toBeInTheDocument();
  });

  test('zone overlays hidden when no physiological data exists', () => {
    // Tier 4 result (no physiological data)
    renderAndSwitchToLab(mockTier4Result);

    // NO zone overlay should render — not population defaults
    const zoneOverlay = document.querySelector('[data-testid="zone-overlay"]');
    expect(zoneOverlay).not.toBeInTheDocument();
  });

  test('segment table shows required columns', () => {
    renderAndSwitchToLab();

    // Segment table should have columns: type, duration, avg pace, avg HR
    // Scoped to within the table to avoid collisions with drift metrics
    // and tier badge text (e.g., "Pace Drift", "Threshold HR").
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();

    // Check column headers within the table
    const tableScope = within(table);
    expect(tableScope.getByText(/Type/i)).toBeInTheDocument();
    expect(tableScope.getByText(/Duration/i)).toBeInTheDocument();
    expect(tableScope.getByText(/Avg Pace|Pace/i)).toBeInTheDocument();
    expect(tableScope.getByText(/Avg HR|HR/i)).toBeInTheDocument();
  });

  test('drift metrics are displayed with neutral language', () => {
    renderAndSwitchToLab();

    // Cardiac drift should be shown
    expect(screen.getByText(/cardiac drift/i)).toBeInTheDocument();
    expect(screen.getByText(/4\.2%|4\.2/)).toBeInTheDocument();

    // Trust contract: ambiguous metrics must NOT use directional language
    const driftSection = screen.getByText(/cardiac drift/i).closest('div');
    if (driftSection) {
      const text = driftSection.textContent || '';
      expect(text).not.toMatch(/improved|worsened|better|concerning|declining/i);
    }
  });

  test('Lab mode does not render coach interaction elements', () => {
    renderAndSwitchToLab();

    // AC-12 enforcement: no coach surface in RSI-Alpha
    expect(screen.queryByText(/ask coach/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/tell me about/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('moment-marker')).not.toBeInTheDocument();
  });
});
