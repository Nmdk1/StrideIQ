import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const push = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

const updateProfile = jest.fn(async () => ({
  onboarding_stage: 'connect_strava',
  onboarding_completed: false,
}));
jest.mock('@/lib/api/services/auth', () => ({
  authService: {
    updateProfile: (...args: any[]) => updateProfile(...args),
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

const getIntake = jest.fn(async () => ({
  stage: 'goals',
  responses: { goal_event_type: '5k' },
  completed_at: null,
}));
const saveIntake = jest.fn(async () => ({ ok: true }));
jest.mock('@/lib/api/services/onboarding', () => ({
  onboardingService: {
    getIntake: (...args: any[]) => getIntake(...args),
    saveIntake: (...args: any[]) => saveIntake(...args),
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
    render(<OnboardingPage />);

    expect(await screen.findByText('Interview')).toBeInTheDocument();
    await waitFor(() => expect(getIntake).toHaveBeenCalledWith('goals'));

    const user = userEvent.setup();
    const next = screen.getByRole('button', { name: 'Next' });
    await user.click(next);

    await waitFor(() => expect(saveIntake).toHaveBeenCalled());
    await waitFor(() => expect(updateProfile).toHaveBeenCalled());
  });
});

