import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ConnectStravaStage now reads useUnits() to render the saved pace
// profile in the athlete's preferred units; stub it to keep this flow
// test focused on stage transitions rather than provider plumbing.
jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial',
    setUnits: () => {},
    distanceUnitShort: 'mi',
    formatDistance: (m: number) => `${(m / 1609.344).toFixed(1)} mi`,
    formatPace: (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}/mi`,
  }),
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

jest.mock('@/lib/api/services/garmin', () => ({
  garminService: {
    getAuthUrl: jest.fn(async () => ({ auth_url: 'https://garmin.test/auth' })),
  },
}));

jest.mock('@/lib/hooks/queries/garmin', () => ({
  useGarminStatus: () => ({
    data: { connected: false, garmin_user_id: null, last_sync: null, garmin_connect_available: false },
    isLoading: false,
    refetch: jest.fn(),
  }),
}));

jest.mock('@/lib/hooks/queries/onboarding', () => ({
  useOnboardingStatus: () => ({
    data: {
      strava_connected: true,
      ingestion_state: { last_index_status: null },
      last_sync: null,
    },
    isLoading: false,
    error: null,
  }),
  useBootstrapOnboarding: () => ({
    mutateAsync: async () => ({ queued: true }),
    isPending: false,
  }),
}));

jest.mock('@/lib/context/ConsentContext', () => ({
  useConsent: () => ({
    aiConsent: false,
    grantedAt: null,
    revokedAt: null,
    loading: false,
    grantConsent: jest.fn(async () => {}),
    revokeConsent: jest.fn(async () => {}),
  }),
}));

import OnboardingPage from '@/app/onboarding/page';

describe('Onboarding full flow (skip Strava)', () => {
  beforeEach(() => {
    push.mockClear();
    mockUser.onboarding_completed = false;
    mockUser.onboarding_stage = 'initial';
    localStorage.setItem('auth_token', 'test-token');
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 400,
        json: async () => ({}),
      } as Response),
    );
  });

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

    expect(await screen.findByRole('heading', { name: "Let's Start" })).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Next' }));
    });

    expect(await screen.findByRole('heading', { name: 'About You' })).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Skip' }));
    });

    expect(await screen.findByRole('heading', { name: 'Interview' })).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Next' }));
    });

    expect(await screen.findByRole('heading', { name: 'AI Coaching Insights' })).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Skip for now' }));
    });

    expect(await screen.findByRole('heading', { name: 'Connect Your Watch' })).toBeInTheDocument();
    expect(await screen.findByText(/No prescriptive paces yet/i)).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Continue' }));
    });

    await waitFor(() => {
      expect(mockUser.onboarding_completed).toBe(true);
    });
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith('/home');
    });

    expect(onboardingMod.__mocks.getIntake).toHaveBeenCalledWith('goals');
    expect(onboardingMod.__mocks.saveIntake).toHaveBeenCalled();
    expect(authMod.__mocks.updateProfile).toHaveBeenCalled();
  });
});
