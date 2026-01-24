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
      ingestion_paused: true,
    },
  }),
}));

jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: () => ({ data: { cards: [] }, isLoading: false, error: null }),
}));

import HomePage from '@/app/home/page';

describe('Home ingestion paused banner', () => {
  test('shows calm banner when ingestion is globally paused', () => {
    render(<HomePage />);
    expect(screen.getByText('Import delayed')).toBeInTheDocument();
    expect(screen.getByText(/High traffic volume/i)).toBeInTheDocument();
  });
});

