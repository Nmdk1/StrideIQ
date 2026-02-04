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

jest.mock('@/lib/hooks/queries/admin', () => ({
  useAdminUsers: () => ({ data: { users: [], total: 0 }, isLoading: false }),
  useAdminUser: () => ({ data: null, isLoading: false }),
  useSystemHealth: () => ({ data: null, isLoading: false }),
  useSiteMetrics: () => ({ data: null, isLoading: false }),
  useImpersonateUser: () => ({ mutate: jest.fn(), isPending: false }),
  useCompAccess: () => ({ mutate: jest.fn(), isPending: false }),
  useGrantTrial: () => ({ mutate: jest.fn(), isPending: false }),
  useRevokeTrial: () => ({ mutate: jest.fn(), isPending: false }),
  useResetOnboarding: () => ({ mutate: jest.fn(), isPending: false }),
  useResetPassword: () => ({ mutate: jest.fn(), isPending: false }),
  useRetryIngestion: () => ({ mutate: jest.fn(), isPending: false }),
  useRegenerateStarterPlan: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useSetBlocked: () => ({ mutate: jest.fn(), isPending: false }),
  useSetCoachVip: () => ({ mutate: jest.fn(), isPending: false }),
  useDeleteUser: () => ({ mutate: jest.fn(), isPending: false }),
  useAdminFeatureFlags: () => ({ data: { flags: [] }, isLoading: false }),
  useSet3dQualitySelectionMode: () => ({ mutate: jest.fn(), isPending: false, isSuccess: false, isError: false }),
  useOpsQueue: () => ({
    isLoading: false,
    data: { available: true, active_count: 1, reserved_count: 2, scheduled_count: 3, workers_seen: ['worker-1'] },
  }),
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

jest.mock('@/lib/hooks/queries/query-engine', () => ({
  useQueryTemplates: () => ({ data: { templates: [] } }),
  useQueryEntities: () => ({ data: { entities: {} } }),
  useExecuteTemplate: () => ({ mutateAsync: jest.fn(), isPending: false }),
  useExecuteCustomQuery: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

describe('Admin ops visibility v0', () => {
  it('renders ops tab queue snapshot', async () => {
    render(<AdminPage />);

    fireEvent.click(screen.getByText('Ops'));

    expect(await screen.findByText('Queue snapshot')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Reserved')).toBeInTheDocument();
    expect(screen.getByText('Scheduled')).toBeInTheDocument();
  });
});

