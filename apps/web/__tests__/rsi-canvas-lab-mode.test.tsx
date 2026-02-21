/**
 * RSI-Alpha — Drift Metrics Tests
 *
 * After the activity detail simplification, Lab mode is removed. The segment
 * table and HR Zones card are gone. Drift metrics are now always rendered
 * inline below the chart — no tab click needed. AC-12 (no coach surface) still applies.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { mockTier1Result, mockTier4Result, generateTestStreamData, mockUnitsImperial } from './rsi-fixtures';

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

function renderCanvas(analysisResult = mockTier1Result) {
  mockUseStreamAnalysis.mockReturnValue({
    data: { ...analysisResult, stream: streamData },
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  } as any);

  return render(<RunShapeCanvas activityId="test-123" />);
}

describe('Lab Mode: Removed', () => {
  test('lab mode panel is not rendered', () => {
    renderCanvas();

    expect(screen.queryByTestId('lab-mode')).not.toBeInTheDocument();
  });

  test('segment table is not rendered', () => {
    renderCanvas();

    expect(screen.queryByTestId('segment-table')).not.toBeInTheDocument();
  });

  test('zone overlay card is not rendered', () => {
    renderCanvas();

    expect(screen.queryByTestId('zone-overlay')).not.toBeInTheDocument();
  });
});

describe('Drift Metrics: Always Visible', () => {
  test('drift metrics render without any tab interaction', () => {
    renderCanvas();

    expect(screen.getByTestId('drift-metrics')).toBeInTheDocument();
  });

  test('cardiac drift is displayed with neutral language', () => {
    renderCanvas();

    expect(screen.getByText(/cardiac drift/i)).toBeInTheDocument();
    expect(screen.getByText(/4\.2%|4\.2/)).toBeInTheDocument();

    // Trust contract: must not use directional coaching language
    const driftSection = screen.getByText(/cardiac drift/i).closest('div');
    if (driftSection) {
      const text = driftSection.textContent || '';
      expect(text).not.toMatch(/improved|worsened|better|concerning|declining/i);
    }
  });

  test('pace drift is displayed', () => {
    renderCanvas();

    expect(screen.getByText(/pace drift/i)).toBeInTheDocument();
  });

  test('AC-12 enforcement: no coach interaction elements anywhere on the page', () => {
    renderCanvas();

    expect(screen.queryByText(/ask coach/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/tell me about/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('moment-marker')).not.toBeInTheDocument();
  });
});
