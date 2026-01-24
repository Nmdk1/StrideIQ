import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const push = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

jest.mock('@/lib/api/services/auth', () => ({
  authService: {
    updateProfile: jest.fn(async () => ({
      onboarding_stage: 'connect_strava',
      onboarding_completed: false,
    })),
  },
  __mocks: {
    // expose mocks for assertions without hoist/TDZ issues
    updateProfile: undefined as any,
  },
}));

const refreshUser = jest.fn(async () => undefined);
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'athlete-1',
      onboarding_completed: false,
      onboarding_stage: 'goals',
    },
    refreshUser,
  }),
}));

jest.mock('@/lib/api/services/onboarding', () => ({
  onboardingService: {
    getIntake: jest.fn(async () => ({
      stage: 'goals',
      responses: { goal_event_type: '5k' },
      completed_at: null,
    })),
    saveIntake: jest.fn(async () => ({ ok: true })),
  },
  __mocks: {
    getIntake: undefined as any,
    saveIntake: undefined as any,
  },
}));

jest.mock('@/lib/hooks/queries/onboarding', () => ({
  useOnboardingStatus: () => ({
    data: { strava_connected: false, ingestion_state: null, last_sync: null },
    isLoading: false,
    error: null,
  }),
  useBootstrapOnboarding: () => ({
    mutateAsync: async () => ({ queued: true }),
    isPending: false,
  }),
}));

import OnboardingPage from '@/app/onboarding/page';

describe('Onboarding interview (goals stage)', () => {
  test('loads saved intake and saves before advancing stage', async () => {
    const authMod = require('@/lib/api/services/auth');
    authMod.__mocks.updateProfile = authMod.authService.updateProfile;
    const onboardingMod = require('@/lib/api/services/onboarding');
    onboardingMod.__mocks.getIntake = onboardingMod.onboardingService.getIntake;
    onboardingMod.__mocks.saveIntake = onboardingMod.onboardingService.saveIntake;

    await act(async () => {
      render(<OnboardingPage />);
    });

    expect(await screen.findByText('Interview')).toBeInTheDocument();
    await waitFor(() => expect(onboardingMod.__mocks.getIntake).toHaveBeenCalledWith('goals'));

    const user = userEvent.setup();
    const next = screen.getByRole('button', { name: 'Next' });
    await act(async () => {
      await user.click(next);
    });

    await waitFor(() => expect(onboardingMod.__mocks.saveIntake).toHaveBeenCalled());
    await waitFor(() => expect(authMod.__mocks.updateProfile).toHaveBeenCalled());
  });
});

