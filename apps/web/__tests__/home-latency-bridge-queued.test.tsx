import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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
      ingestion_state: null,
      coach_noticed: null,
      race_countdown: null,
      checkin_needed: false,
      strava_status: null,
    },
  }),
  useQuickCheckin: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: () => ({ data: { cards: [] }, isLoading: false, error: null }),
}));

import HomePage from '@/app/home/page';

describe('Home page (queued state)', () => {
  test('renders home page without crashing when ingestion not started', () => {
    render(<HomePage />);
    // H3: workout section renders plain text when no workout
    expect(screen.getByText('Create a plan to see workouts.')).toBeInTheDocument();
    // Welcome card removed in Phase 2
    expect(screen.queryByText('Welcome to StrideIQ')).not.toBeInTheDocument();
  });
});
