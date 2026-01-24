import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import SettingsPage from '@/app/settings/page';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/components/integrations/StravaConnection', () => ({
  StravaConnection: () => <div>StravaConnection</div>,
}));

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({ units: 'imperial', setUnits: jest.fn() }),
}));

const useAuthMock = jest.fn();
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => useAuthMock(),
}));

describe('Settings membership trial UI', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    // auth_token read
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(() => 'token'),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      },
      writable: true,
    });
  });

  it('shows Start 7-day trial + Upgrade when free and trial not used', () => {
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

    render(<SettingsPage />);

    expect(screen.getByText('Start 7-day trial')).toBeInTheDocument();
    expect(screen.getByText(/Upgrade to Pro/i)).toBeInTheDocument();
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

    render(<SettingsPage />);

    expect(screen.getByText(/Trial ends/i)).toBeInTheDocument();
    expect(screen.getByText(/Upgrade anytime to keep Pro/i)).toBeInTheDocument();
    // Paid access but no stripe_customer_id -> "Start Pro billing"
    expect(screen.getByText(/Start Pro billing/i)).toBeInTheDocument();
  });
});

