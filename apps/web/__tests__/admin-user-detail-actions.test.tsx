import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import AdminPage from '@/app/admin/page';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace: jest.fn() }),
}));

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, user: { role: 'admin', display_name: 'Admin' } }),
}));

const mutateComp = jest.fn();
const mutateRegenStarterPlan = jest.fn();

jest.mock('@/lib/hooks/queries/admin', () => ({
  useAdminUsers: () => ({
    isLoading: false,
    data: {
      total: 1,
      users: [
        {
          id: 'u1',
          email: 'user@example.com',
          display_name: 'User',
          role: 'athlete',
          subscription_tier: 'free',
          created_at: new Date().toISOString(),
          onboarding_completed: false,
        },
      ],
      offset: 0,
      limit: 50,
    },
  }),
  useAdminUser: (id: string) => ({
    isLoading: false,
    data:
      id === 'u1'
        ? {
            id: 'u1',
            email: 'user@example.com',
            display_name: 'User',
            role: 'athlete',
            subscription_tier: 'free',
            created_at: new Date().toISOString(),
            onboarding_completed: false,
            onboarding_stage: 'initial',
            stripe_customer_id: null,
            is_blocked: false,
            integrations: { preferred_units: 'imperial', strava_athlete_id: 123, last_strava_sync: null },
            ingestion_state: null,
            intake_history: [],
            active_plan: {
              id: 'p1',
              name: 'Half Marathon Starter Plan',
              status: 'active',
              plan_type: 'half_marathon',
              plan_start_date: new Date().toISOString(),
              plan_end_date: new Date().toISOString(),
              goal_race_name: null,
              goal_race_date: '2026-04-11',
            },
            stats: { activities: 0, nutrition_entries: 0, work_patterns: 0, body_composition_entries: 0 },
          }
        : null,
  }),
  useSystemHealth: () => ({ isLoading: false, data: null }),
  useSiteMetrics: () => ({ isLoading: false, data: null }),
  useImpersonateUser: () => ({ mutate: jest.fn(), isPending: false }),
  useAdminFeatureFlags: () => ({ isLoading: false, data: { flags: [] } }),
  useSet3dQualitySelectionMode: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useCompAccess: () => ({ mutate: mutateComp, isPending: false }),
  useGrantTrial: () => ({ mutate: jest.fn(), isPending: false }),
  useRevokeTrial: () => ({ mutate: jest.fn(), isPending: false }),
  useResetOnboarding: () => ({ mutate: jest.fn(), isPending: false }),
  useRetryIngestion: () => ({ mutate: jest.fn(), isPending: false }),
  useRegenerateStarterPlan: () => ({ mutate: mutateRegenStarterPlan, isPending: false }),
  useSetBlocked: () => ({ mutate: jest.fn(), isPending: false }),
  useOpsQueue: () => ({ isLoading: false, data: { available: false, active_count: 0, reserved_count: 0, scheduled_count: 0, workers_seen: [] } }),
  useOpsIngestionPause: () => ({ isLoading: false, data: { paused: false } }),
  useSetOpsIngestionPause: () => ({ mutate: jest.fn(), isPending: false }),
  useOpsStuckIngestion: () => ({ isLoading: false, data: { cutoff: new Date().toISOString(), count: 0, items: [] } }),
  useOpsIngestionErrors: () => ({ isLoading: false, data: { cutoff: new Date().toISOString(), count: 0, items: [] } }),
  useOpsDeferredIngestion: () => ({ isLoading: false, data: { now: new Date().toISOString(), count: 0, items: [] } }),
}));

jest.mock('@/lib/hooks/queries/query-engine', () => ({
  useQueryTemplates: () => ({ data: { templates: [] } }),
  useQueryEntities: () => ({ data: { entities: {} } }),
  useExecuteTemplate: () => ({ mutateAsync: jest.fn(), isPending: false }),
  useExecuteCustomQuery: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

describe('Admin user detail panel', () => {
  beforeEach(() => {
    mutateComp.mockClear();
    mutateRegenStarterPlan.mockClear();
  });

  it('allows selecting a user and applying comp access', () => {
    render(<AdminPage />);

    fireEvent.click(screen.getByText('View'));
    expect(screen.getByText('User detail')).toBeInTheDocument();
    expect(screen.getAllByText('user@example.com').length).toBeGreaterThan(0);

    fireEvent.change(screen.getByPlaceholderText(/VIP tester/i), { target: { value: 'VIP tester' } });
    fireEvent.click(screen.getByText('Apply'));

    expect(mutateComp).toHaveBeenCalledWith({ userId: 'u1', tier: 'pro', reason: 'VIP tester' });
  });

  it('allows regenerating starter plan from admin panel', () => {
    render(<AdminPage />);

    fireEvent.click(screen.getByText('View'));
    expect(screen.getByText('Active plan')).toBeInTheDocument();

    // Use default reason when the reason field is blank.
    fireEvent.click(screen.getByText('Regenerate starter plan'));
    expect(mutateRegenStarterPlan).toHaveBeenCalledWith({
      userId: 'u1',
      reason: 'beta support: regenerate starter plan',
    });
  });
});

