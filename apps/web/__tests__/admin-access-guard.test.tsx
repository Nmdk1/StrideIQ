import React from 'react';
import { render, screen } from '@testing-library/react';

import AdminPage from '@/app/admin/page';

jest.mock('@/lib/hooks/queries/admin', () => ({
  useAdminUsers: () => ({ data: { users: [], total: 0 }, isLoading: false }),
  useAdminUser: () => ({ data: null, isLoading: false }),
  useSystemHealth: () => ({ data: null, isLoading: false }),
  useSiteMetrics: () => ({ data: null, isLoading: false }),
  useImpersonateUser: () => ({ mutate: jest.fn(), isPending: false }),
  useCompAccess: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useGrantTrial: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useRevokeTrial: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useResetOnboarding: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useResetPassword: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useRetryIngestion: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useRegenerateStarterPlan: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useSetBlocked: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useSetCoachVip: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useDeleteUser: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useAdminFeatureFlags: () => ({ data: { flags: [] }, isLoading: false }),
  useSet3dQualitySelectionMode: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useOpsQueue: () => ({ data: { available: false, active_count: 0, reserved_count: 0, scheduled_count: 0, workers_seen: [] }, isLoading: false }),
  useOpsIngestionPause: () => ({ data: { paused: false }, isLoading: false }),
  useSetOpsIngestionPause: () => ({ mutate: jest.fn(), isPending: false }),
  useOpsStuckIngestion: () => ({ data: { cutoff: new Date().toISOString(), count: 0, items: [] }, isLoading: false }),
  useOpsIngestionErrors: () => ({ data: { cutoff: new Date().toISOString(), count: 0, items: [] }, isLoading: false }),
  useOpsDeferredIngestion: () => ({ data: { now: new Date().toISOString(), count: 0, items: [] }, isLoading: false }),
  useAdminInvites: () => ({ data: { invites: [] }, isLoading: false }),
  useCreateInvite: () => ({ mutate: jest.fn(), isPending: false }),
  useRevokeInvite: () => ({ mutate: jest.fn(), isPending: false }),
  useAdminRaceCodes: () => ({ data: { codes: [] }, isLoading: false }),
  useCreateRaceCode: () => ({ mutate: jest.fn(), isPending: false }),
  useDeactivateRaceCode: () => ({ mutate: jest.fn(), isPending: false }),
  getRaceCodeQrUrl: () => '',
}));

jest.mock('@/lib/hooks/queries/query-engine', () => ({
  useQueryTemplates: () => ({ data: { templates: [] } }),
  useQueryEntities: () => ({ data: { entities: {} } }),
  useExecuteTemplate: () => ({ mutateAsync: jest.fn(), isPending: false }),
  useExecuteCustomQuery: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const replaceMock = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

const useAuthMock = jest.fn();
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => useAuthMock(),
}));

describe('AdminPage access guard', () => {
  beforeEach(() => {
    replaceMock.mockClear();
    useAuthMock.mockReset();
  });

  it('redirects authenticated non-admin users away from /admin and does not render admin content', async () => {
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { role: 'athlete', display_name: 'Test User' },
    });

    render(<AdminPage />);

    expect(replaceMock).toHaveBeenCalledWith('/home');
    expect(screen.queryByText('Admin Dashboard')).toBeNull();
  });

  it('renders admin content for admin users', async () => {
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { role: 'admin', display_name: 'Admin User' },
    });

    render(<AdminPage />);

    expect(replaceMock).not.toHaveBeenCalled();
    expect(await screen.findByText('Admin Dashboard')).toBeInTheDocument();
  });
});

