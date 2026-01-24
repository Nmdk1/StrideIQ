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
      ingestion_state: {
        last_index_status: 'running',
        last_index_pages_fetched: 1,
        last_index_created: 25,
      },
    },
  }),
}));

// Home imports this; keep it from doing any real work
jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: () => ({ data: { cards: [] }, isLoading: false, error: null }),
}));

import HomePage from '@/app/home/page';

describe('Home latency bridge (import-in-progress UI)', () => {
  test('shows Import in progress card when Strava connected but no activities yet', () => {
    render(<HomePage />);

    expect(screen.getByText('Import in progress')).toBeInTheDocument();
    expect(screen.getByText(/Indexing activities/i)).toBeInTheDocument();

    // Welcome CTA should not show when already connected.
    expect(screen.queryByText('Welcome to StrideIQ')).not.toBeInTheDocument();
  });
});

