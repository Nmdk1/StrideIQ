/**
 * Frontend tests for:
 * 5. Admin page mutation error rendering (comp + VIP isError shows red error text)
 * 6. Admin page override controls (badge + clear button rendering and click)
 */
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

jest.mock('@/lib/hooks/queries/query-engine', () => ({
  useQueryTemplates: () => ({ data: { templates: [] } }),
  useQueryEntities: () => ({ data: { entities: {} } }),
  useExecuteTemplate: () => ({ mutateAsync: jest.fn(), isPending: false }),
  useExecuteCustomQuery: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

// These are overridden per-test via mockReturnValue.
const mockUseCompAccess = jest.fn();
const mockUseSetCoachVip = jest.fn();
const mockClearOverrideMutate = jest.fn();

const BASE_USER_DETAIL = {
  id: 'u1',
  email: 'user@example.com',
  display_name: 'User',
  role: 'athlete',
  subscription_tier: 'premium',
  created_at: new Date().toISOString(),
  onboarding_completed: false,
  onboarding_stage: 'initial',
  stripe_customer_id: null,
  is_blocked: false,
  is_coach_vip: false,
  admin_tier_override: null as string | null,
  admin_tier_override_set_at: null as string | null,
  admin_tier_override_reason: null as string | null,
  integrations: { preferred_units: 'imperial', strava_athlete_id: null, last_strava_sync: null },
  ingestion_state: null,
  intake_history: [],
  active_plan: null,
  stats: { activities: 0, nutrition_entries: 0, work_patterns: 0, body_composition_entries: 0 },
};

let userDetailOverride: typeof BASE_USER_DETAIL = { ...BASE_USER_DETAIL };

jest.mock('@/lib/hooks/queries/admin', () => ({
  useAdminUsers: () => ({
    isLoading: false,
    data: {
      total: 1,
      users: [{ id: 'u1', email: 'user@example.com', display_name: 'User', role: 'athlete', subscription_tier: 'premium', created_at: new Date().toISOString(), onboarding_completed: false }],
      offset: 0,
      limit: 50,
    },
  }),
  useAdminUser: (id: string) => ({ isLoading: false, data: id === 'u1' ? userDetailOverride : null }),
  useSystemHealth: () => ({ isLoading: false, data: null }),
  useSiteMetrics: () => ({ isLoading: false, data: null }),
  useImpersonateUser: () => ({ mutate: jest.fn(), isPending: false }),
  useAdminFeatureFlags: () => ({ isLoading: false, data: { flags: [] } }),
  useSet3dQualitySelectionMode: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useCompAccess: (...args: unknown[]) => mockUseCompAccess(...args),
  useGrantTrial: () => ({ mutate: jest.fn(), isPending: false }),
  useRevokeTrial: () => ({ mutate: jest.fn(), isPending: false }),
  useResetOnboarding: () => ({ mutate: jest.fn(), isPending: false }),
  useResetPassword: () => ({ mutate: jest.fn(), isPending: false }),
  useRetryIngestion: () => ({ mutate: jest.fn(), isPending: false }),
  useRegenerateStarterPlan: () => ({ mutate: jest.fn(), isPending: false }),
  useSetBlocked: () => ({ mutate: jest.fn(), isPending: false }),
  useSetCoachVip: (...args: unknown[]) => mockUseSetCoachVip(...args),
  useDeleteUser: () => ({ mutate: jest.fn(), isPending: false }),
  useClearCompOverride: () => ({ mutate: mockClearOverrideMutate, isPending: false, isError: false, error: null }),
  useOpsQueue: () => ({ isLoading: false, data: { available: false, active_count: 0, reserved_count: 0, scheduled_count: 0, workers_seen: [] } }),
  useOpsIngestionPause: () => ({ isLoading: false, data: { paused: false } }),
  useSetOpsIngestionPause: () => ({ mutate: jest.fn(), isPending: false }),
  useOpsStuckIngestion: () => ({ isLoading: false, data: { cutoff: new Date().toISOString(), count: 0, items: [] } }),
  useOpsIngestionErrors: () => ({ isLoading: false, data: { cutoff: new Date().toISOString(), count: 0, items: [] } }),
  useOpsDeferredIngestion: () => ({ isLoading: false, data: { now: new Date().toISOString(), count: 0, items: [] } }),
  useAdminInvites: () => ({ data: { invites: [] }, isLoading: false }),
  useCreateInvite: () => ({ mutate: jest.fn(), isPending: false }),
  useRevokeInvite: () => ({ mutate: jest.fn(), isPending: false }),
  useAdminRaceCodes: () => ({ data: { codes: [] }, isLoading: false }),
  useCreateRaceCode: () => ({ mutate: jest.fn(), isPending: false }),
  useDeactivateRaceCode: () => ({ mutate: jest.fn(), isPending: false }),
  getRaceCodeQrUrl: () => '',
}));

function defaultCompMock(overrides?: Partial<{ isError: boolean; isSuccess: boolean; error: Error | null }>) {
  return { mutate: jest.fn(), isPending: false, isSuccess: false, isError: false, error: null, ...overrides };
}

function defaultVipMock(overrides?: Partial<{ isError: boolean; isSuccess: boolean; error: Error | null }>) {
  return { mutate: jest.fn(), isPending: false, isSuccess: false, isError: false, error: null, ...overrides };
}

beforeEach(() => {
  userDetailOverride = { ...BASE_USER_DETAIL };
  mockClearOverrideMutate.mockClear();
  mockUseCompAccess.mockReturnValue(defaultCompMock());
  mockUseSetCoachVip.mockReturnValue(defaultVipMock());
});

// ---------------------------------------------------------------------------
// Test 5a: comp mutation error renders inline error text
// ---------------------------------------------------------------------------

describe('Admin mutation error rendering', () => {
  it('shows inline error when comp mutation isError', () => {
    mockUseCompAccess.mockReturnValue(
      defaultCompMock({ isError: true, error: new Error('Insufficient permissions') })
    );

    render(<AdminPage />);
    fireEvent.click(screen.getByText('View'));

    expect(screen.getByText(/Failed to update tier/i)).toBeInTheDocument();
    expect(screen.getByText(/Insufficient permissions/i)).toBeInTheDocument();
  });

  it('shows inline error when VIP mutation isError', () => {
    mockUseSetCoachVip.mockReturnValue(
      defaultVipMock({ isError: true, error: new Error('VIP quota exceeded') })
    );

    render(<AdminPage />);
    fireEvent.click(screen.getByText('View'));

    expect(screen.getByText(/VIP quota exceeded/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test 6: override badge + clear button
// ---------------------------------------------------------------------------

describe('Admin comp override controls', () => {
  it('renders override badge and clear button when admin_tier_override is set', () => {
    userDetailOverride = {
      ...BASE_USER_DETAIL,
      admin_tier_override: 'premium',
      admin_tier_override_set_at: '2026-03-15T12:00:00Z',
      admin_tier_override_reason: 'sponsor deal',
    };

    render(<AdminPage />);
    fireEvent.click(screen.getByText('View'));

    expect(screen.getByText(/Comp override active/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Clear override/i })).toBeInTheDocument();
  });

  it('calls useClearCompOverride mutate with userId when clear button clicked', () => {
    userDetailOverride = {
      ...BASE_USER_DETAIL,
      admin_tier_override: 'premium',
      admin_tier_override_set_at: '2026-03-15T12:00:00Z',
    };

    render(<AdminPage />);
    fireEvent.click(screen.getByText('View'));
    fireEvent.click(screen.getByRole('button', { name: /Clear override/i }));

    expect(mockClearOverrideMutate).toHaveBeenCalledWith({ userId: 'u1' });
  });
});
