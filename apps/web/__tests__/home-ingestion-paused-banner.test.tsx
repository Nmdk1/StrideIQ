import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: () => ({ data: { cards: [] }, isLoading: false, error: null }),
}));

let homeData: any = {
  today: { has_workout: false },
  yesterday: { has_activity: false },
  week: { completed_mi: 0, planned_mi: 0, progress_pct: 0, days: [], status: 'no_plan' },
  hero_narrative: null,
  strava_connected: true,
  has_any_activities: false,
  total_activities: 0,
  last_sync: null,
  ingestion_state: null,
  ingestion_paused: true,
  coach_noticed: null,
  race_countdown: null,
  checkin_needed: false,
  strava_status: null,
};

jest.mock('@/lib/hooks/queries/home', () => ({
  useHomeData: () => ({
    isLoading: false,
    error: null,
    data: homeData,
  }),
  useQuickCheckin: () => ({ mutate: jest.fn(), isPending: false }),
}));

import HomePage from '@/app/home/page';

describe('Home page renders without crash (ADR-17 Phase 2)', () => {
  beforeEach(() => {
    homeData = {
      today: { has_workout: false },
      yesterday: { has_activity: false },
      week: { completed_mi: 0, planned_mi: 0, progress_pct: 0, days: [], status: 'no_plan' },
      hero_narrative: null,
      strava_connected: true,
      has_any_activities: false,
      total_activities: 0,
      last_sync: null,
      ingestion_state: null,
      ingestion_paused: true,
      coach_noticed: null,
      race_countdown: null,
      checkin_needed: false,
      strava_status: null,
    };
  });

  test('renders home page with no activities and no crash', () => {
    render(<HomePage />);
    // H3: workout section renders plain text when no workout
    expect(screen.getByText('Create a plan to see workouts.')).toBeInTheDocument();
  });

  test('does not show old ingestion cards (removed in Phase 2)', () => {
    render(<HomePage />);
    expect(screen.queryByText('Import delayed')).not.toBeInTheDocument();
    expect(screen.queryByText('Import in progress')).not.toBeInTheDocument();
    expect(screen.queryByText('Import queued')).not.toBeInTheDocument();
  });
});
