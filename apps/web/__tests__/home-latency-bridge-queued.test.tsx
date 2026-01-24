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
    },
  }),
}));

jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: () => ({ data: { cards: [] }, isLoading: false, error: null }),
}));

import HomePage from '@/app/home/page';

describe('Home latency bridge (queued UI, no dead air)', () => {
  test('shows Import queued card when connected but ingestion_state not yet available', () => {
    render(<HomePage />);

    expect(screen.getByText('Import queued')).toBeInTheDocument();
    expect(screen.getByText(/Import will start in the background/i)).toBeInTheDocument();

    // Welcome CTA should not show when already connected.
    expect(screen.queryByText('Welcome to StrideIQ')).not.toBeInTheDocument();
  });
});

