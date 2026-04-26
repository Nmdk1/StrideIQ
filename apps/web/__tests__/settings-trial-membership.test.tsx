import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import SettingsPage from '@/app/settings/page';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/components/integrations/StravaConnection', () => ({
  StravaConnection: () => <div>StravaConnection</div>,
}));

jest.mock('@/components/integrations/GarminConnection', () => ({
  GarminConnection: () => <div>GarminConnection</div>,
}));

jest.mock('@/components/settings/RuntoonPhotoUpload', () => ({
  RuntoonPhotoUpload: () => <div>RuntoonPhotoUpload</div>,
}));

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({ units: 'imperial', setUnits: jest.fn() }),
}));

function createTestQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

const useAuthMock = jest.fn();
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => useAuthMock(),
}));

describe('Settings membership trial UI', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(() => 'token'),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      },
      writable: true,
    });
  });

  it('shows Start 30-day trial + Upgrade toggle when free and trial not used', () => {
    useAuthMock.mockReturnValue({
      user: {
        subscription_tier: 'free',
        onboarding_completed: true,
        has_active_subscription: false,
        trial_started_at: null,
        trial_ends_at: null,
        stripe_customer_id: null,
      },
    });

    renderWithProviders(<SettingsPage />);

    expect(screen.getByText('Start 30-day trial')).toBeInTheDocument();
    // Upgrade panel toggle button (replaces the old single "Upgrade to Pro" button).
    expect(screen.getByRole('button', { name: /Upgrade/i })).toBeInTheDocument();
  });

  it('shows trial end copy when trial is active', () => {
    useAuthMock.mockReturnValue({
      user: {
        subscription_tier: 'free',
        onboarding_completed: true,
        has_active_subscription: true,
        trial_started_at: new Date().toISOString(),
        trial_ends_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
        stripe_customer_id: null,
      },
    });

    renderWithProviders(<SettingsPage />);

    // Trial end date copy is visible.
    expect(screen.getByText(/Trial ends/i)).toBeInTheDocument();
    // Canonical copy (no "Pro" phrasing in current UI).
    expect(screen.getByText(/Upgrade to keep full access/i)).toBeInTheDocument();
    // Upgrade panel toggle button is present (trial user is still 'free' tier — upgrade path shown).
    expect(screen.getByRole('button', { name: /Upgrade/i })).toBeInTheDocument();
    // Start 30-day trial button must NOT appear — trial already used.
    expect(screen.queryByText('Start 30-day trial')).not.toBeInTheDocument();
  });
});
