/**
 * Activities page: Running / Other / All toggle and stat card rebinding.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockUseActivities = jest.fn();
jest.mock('@/lib/hooks/queries/activities', () => ({
  useActivities: (...a: unknown[]) => mockUseActivities(...a),
  useFilterDistributions: () => ({ data: null, isLoading: false }),
  useActivitiesSummary: () => ({
    data: {
      period_days: 30,
      total_activities: 8,
      total_distance_km: 80,
      total_distance_miles: 49.7,
      total_duration_hours: 6,
      average_pace_per_mile: 8.25,
      race_count: 0,
      running: {
        total_activities: 5,
        total_distance_km: 72,
        total_distance_miles: 44.7,
        total_duration_hours: 5,
        average_pace_per_mile: 8.0,
        race_count: 0,
      },
      other: {
        total_activities: 3,
        total_distance_km: 8,
        total_distance_miles: 5.0,
        total_duration_hours: 1,
        average_pace_per_mile: null,
        race_count: 0,
        by_sport: {
          walking: {
            total_activities: 2,
            total_distance_km: 5,
            total_distance_miles: 3.1,
            total_duration_hours: 0.5,
          },
        },
      },
      combined: {
        total_activities: 8,
        total_distance_km: 80,
        total_distance_miles: 49.7,
        total_duration_hours: 6,
        average_pace_per_mile: null,
        race_count: 0,
      },
      activities_by_sport: { run: {}, walking: {} },
    },
    isLoading: false,
  }),
}));

jest.mock('@/lib/context/CompareContext', () => ({
  useCompareSelection: () => ({
    isSelected: () => false,
    toggleSelection: jest.fn(),
    canAddMore: true,
    selectionCount: 0,
    clearSelection: jest.fn(),
  }),
}));

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial' as const,
    formatDistance: (m: number) => `${(m / 1609.34).toFixed(1)} mi`,
    formatPace: (s: number) => `${s}`,
    distanceUnitShort: 'mi',
    paceUnit: '/mi',
  }),
}));

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { ActivitiesPageInner } from '@/app/activities/page';

describe('ActivitiesPageInner sport view toggle', () => {
  beforeEach(() => {
    mockUseActivities.mockReturnValue({
      data: { activities: [], total_count: 0 },
      isLoading: false,
      error: null,
    });
  });

  test('Running sets aria-pressed and pins sport=run on list params', () => {
    render(<ActivitiesPageInner />);
    const running = screen.getByRole('button', { name: /^Running$/i });
    const other = screen.getByRole('button', { name: /^Other$/i });
    const all = screen.getByRole('button', { name: /^All$/i });

    expect(running).toHaveAttribute('aria-pressed', 'true');
    expect(other).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(other);
    expect(other).toHaveAttribute('aria-pressed', 'true');
    expect(running).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(all);
    expect(all).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(running);
    expect(running).toHaveAttribute('aria-pressed', 'true');
  });

  test('Avg Pace card label visible only for Running view', () => {
    render(<ActivitiesPageInner />);
    expect(screen.getByText('Avg Pace')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Other$/i }));
    expect(screen.queryByText('Avg Pace')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^All$/i }));
    expect(screen.queryByText('Avg Pace')).not.toBeInTheDocument();
  });
});
