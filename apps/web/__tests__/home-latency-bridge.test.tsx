import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/components/home/CompactPMC', () => ({ CompactPMC: () => null }));
jest.mock('@/components/home/TrialBanner', () => ({ TrialBanner: () => null }));
jest.mock('@/components/home/FirstInsightsBanner', () => ({ FirstInsightsBanner: () => null }));
jest.mock('@/components/home/AdaptationProposalCard', () => ({ AdaptationProposalCard: () => null }));

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial' as const,
    formatDistance: (m: number) => `${(m / 1609.344).toFixed(1)} mi`,
    formatPace: (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}/mi`,
    formatElevation: (m: number) => `${Math.round(m * 3.28084)} ft`,
    convertDistance: (m: number) => m / 1609.344,
    convertPace: (s: number) => s * 1.60934,
    distanceUnit: 'miles',
    distanceUnitShort: 'mi',
    paceUnit: 'min/mi',
    elevationUnit: 'ft',
    isLoading: false,
    setUnits: () => Promise.resolve(),
  }),
}));

jest.mock('@/lib/hooks/queries/home', () => ({
  useHomeData: () => ({
    isLoading: false,
    error: null,
    data: {
      today: { has_workout: false },
      yesterday: { has_activity: false },
      week: { completed_mi: 0, planned_mi: 0, progress_pct: 0, days: [], status: 'no_plan' },
      hero_narrative: null,
      strava_connected: true,
      has_any_activities: false,
      total_activities: 0,
      last_sync: null,
      ingestion_state: { last_index_status: 'running' },
      coach_noticed: null,
      race_countdown: null,
      checkin_needed: false,
      strava_status: null,
    },
  }),
  useQuickCheckin: () => ({ mutate: jest.fn(), isPending: false }),
  useInvalidateHome: () => jest.fn(),
}));

jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: () => ({ data: { cards: [] }, isLoading: false, error: null }),
}));

jest.mock('@/lib/hooks/queries/strength', () => ({
  useStrengthNudges: () => ({ data: { nudges: [] }, isLoading: false, error: null }),
}));

import HomePage from '@/app/home/page';

describe('Home page (connected, no activities)', () => {
  test('renders home page without crashing when Strava connected but no activities', () => {
    render(<HomePage />);
    // H3: workout section renders plain text when no workout
    expect(screen.getByText('Create a plan to see workouts.')).toBeInTheDocument();
    // Welcome card removed in Phase 2
    expect(screen.queryByText('Welcome to StrideIQ')).not.toBeInTheDocument();
  });
});
