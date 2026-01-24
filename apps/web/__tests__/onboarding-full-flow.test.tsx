import React from 'react';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const push = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

// Mutable user object so updateProfile can "persist" stage.
const mockUser: any = {
  id: 'athlete-1',
  onboarding_completed: false,
  onboarding_stage: 'initial',
};

const refreshUser = jest.fn(async () => mockUser);

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    refreshUser,
  }),
}));

jest.mock('@/lib/api/services/auth', () => ({
  authService: {
    updateProfile: jest.fn(async (updates: any) => {
      if (updates?.onboarding_stage !== undefined) mockUser.onboarding_stage = updates.onboarding_stage;
      if (updates?.onboarding_completed !== undefined) mockUser.onboarding_completed = updates.onboarding_completed;
      return { ...mockUser };
    }),
  },
  __mocks: {
    updateProfile: undefined as any,
  },
}));

jest.mock('@/lib/api/services/onboarding', () => ({
  onboardingService: {
    getIntake: jest.fn(async () => ({
      stage: 'goals',
      responses: { goal_event_type: '5k' },
      completed_at: null,
    })),
    saveIntake: jest.fn(async () => ({ ok: true, status: 'missing_anchor' })),
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

describe('Onboarding full flow (skip Strava)', () => {
  test('progresses through stages and completes', async () => {
    const authMod = require('@/lib/api/services/auth');
    authMod.__mocks.updateProfile = authMod.authService.updateProfile;
    const onboardingMod = require('@/lib/api/services/onboarding');
    onboardingMod.__mocks.getIntake = onboardingMod.onboardingService.getIntake;
    onboardingMod.__mocks.saveIntake = onboardingMod.onboardingService.saveIntake;

    const user = userEvent.setup();

    await act(async () => {
      render(<OnboardingPage />);
    });

    // Initial stage
    expect(await screen.findByText("Let's Start")).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Next' }));
    });

    // Basic profile stage -> skip
    expect(await screen.findByText('Basic Profile')).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Skip' }));
    });

    // Goals stage -> load + next (saves intake)
    expect(await screen.findByText('Interview')).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Next' }));
    });

    // Connect stage -> continue without connecting
    expect(await screen.findByRole('heading', { name: 'Connect Strava' })).toBeInTheDocument();
    // Trust contract: explicit "no paces yet" if no recent race/time trial was provided
    expect(await screen.findByText(/No prescriptive paces yet/i)).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Continue Without Connecting' }));
    });

    // Nutrition stage -> skip
    expect(await screen.findByText('Nutrition')).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Skip' }));
    });

    // Work stage -> complete setup
    expect(await screen.findByText('Work Patterns')).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Complete Setup' }));
    });

    // Persisted stage updates
    expect(mockUser.onboarding_stage).toBe('complete');
    expect(mockUser.onboarding_completed).toBe(true);
    expect(push).toHaveBeenCalledWith('/dashboard');

    // Calls: we should have saved intake once
    expect(onboardingMod.__mocks.getIntake).toHaveBeenCalledWith('goals');
    expect(onboardingMod.__mocks.saveIntake).toHaveBeenCalled();
    // And updated profile multiple times
    expect(authMod.__mocks.updateProfile).toHaveBeenCalled();
  });
});

