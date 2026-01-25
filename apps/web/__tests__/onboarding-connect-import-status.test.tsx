import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Keep router pushes inert.
const push = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

// Minimal auth mock: start directly on connect_strava stage.
const mockUser: any = {
  id: 'athlete-1',
  onboarding_completed: false,
  onboarding_stage: 'connect_strava',
};

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    refreshUser: jest.fn(async () => mockUser),
  }),
}));

jest.mock('@/lib/api/services/auth', () => ({
  authService: {
    updateProfile: jest.fn(async () => ({ ...mockUser })),
  },
}));

jest.mock('@/lib/api/services/strava', () => ({
  stravaService: {
    getAuthUrl: jest.fn(async () => ({ auth_url: 'https://strava.test/auth' })),
  },
}));

jest.mock('@/lib/hooks/queries/onboarding', () => ({
  useOnboardingStatus: () => ({
    data: {
      strava_connected: true,
      ingestion_state: { last_index_status: 'running' },
    },
    isLoading: false,
    error: null,
  }),
  useBootstrapOnboarding: () => ({
    mutateAsync: async () => ({ queued: true }),
    isPending: false,
  }),
}));

import OnboardingPage from '@/app/onboarding/page';

describe('Onboarding connect stage status', () => {
  it('shows Import in progress when Strava connected and ingestion running', async () => {
    render(<OnboardingPage />);

    expect(await screen.findByRole('heading', { name: 'Connect Strava' })).toBeInTheDocument();
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(await screen.findByText(/Import in progress/i)).toBeInTheDocument();
    // Connected users get a Continue button (not "Continue Without Connecting").
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
  });
});

