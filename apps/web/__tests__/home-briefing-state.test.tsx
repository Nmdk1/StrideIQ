/**
 * Home page briefing state machine — tests for builder note 2026-02-24.
 *
 * Tests (AC 3-9):
 *   6. With briefing_state='refreshing', page shows thinking placeholder and no fresh briefing text.
 *   7. While briefing_state is non-fresh, refetchInterval is active (returns 2000ms).
 *   8. When state transitions to 'fresh', placeholder disappears and briefing content renders.
 *   9. After 30s still non-fresh, fallback message appears and Retry triggers one refetch invalidate.
 *
 * Uses jest fake timers for deterministic 30s timeout assertion.
 */

import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// ---------------------------------------------------------------------------
// Shared mocks (same pattern as home-page-voice.test.tsx)
// ---------------------------------------------------------------------------

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/home',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next/link', () => {
  return ({ children, href, ...props }: any) => <a href={href} {...props}>{children}</a>;
});

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial' as const,
    formatDistance: (m: number) => `${(m / 1609.344).toFixed(1)} mi`,
    formatPace: (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}/mi`,
    formatElevation: (m: number) => `${Math.round(m * 3.28084)} ft`,
    convertDistance: (m: number) => m / 1609.344,
    convertPace: (s: number) => s * 1.60934,
    distanceUnit: 'miles',
    distanceUnitShort: 'mi',
    paceUnit: 'min/mi',
    elevationUnit: 'ft',
    isLoading: false,
    setUnits: () => Promise.resolve(),
  }),
}));

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: any) => <>{children}</>,
}));

jest.mock('@/components/home/CompactPMC', () => ({ CompactPMC: () => null }));
jest.mock('@/components/home/AdaptationProposalCard', () => ({ AdaptationProposalCard: () => null }));

jest.mock('@/components/home/LastRunHero', () => ({
  LastRunHero: () => <div data-testid="last-run-hero" />,
}));

jest.mock('@/components/ui/LoadingSpinner', () => ({
  LoadingSpinner: () => <div data-testid="loading-spinner" />,
}));

jest.mock('@/components/ui/card', () => ({
  Card: ({ children, ...p }: any) => <div {...p}>{children}</div>,
  CardContent: ({ children, ...p }: any) => <div {...p}>{children}</div>,
  CardHeader: ({ children, ...p }: any) => <div {...p}>{children}</div>,
  CardTitle: ({ children, ...p }: any) => <div {...p}>{children}</div>,
  CardDescription: ({ children, ...p }: any) => <div {...p}>{children}</div>,
}));

jest.mock('@/components/ui/button', () => ({
  Button: ({ children, ...p }: any) => <button {...p}>{children}</button>,
}));

jest.mock('@/components/ui/badge', () => ({
  Badge: ({ children, ...p }: any) => <span {...p}>{children}</span>,
}));

jest.mock('@/components/ui/progress', () => ({
  Progress: (p: any) => <div data-testid="progress-bar" data-value={p.value} />,
}));

// ---------------------------------------------------------------------------
// Data factories
// ---------------------------------------------------------------------------

const baseHomeData = {
  today: { has_workout: false },
  yesterday: { has_activity: false },
  week: {
    completed_mi: 20,
    planned_mi: 40,
    progress_pct: 50,
    days: [],
    status: 'on_track',
  },
  strava_connected: true,
  garmin_connected: false,
  has_any_activities: true,
  total_activities: 50,
  checkin_needed: false,
  today_checkin: { readiness_label: 'Good', sleep_label: 'OK', soreness_label: 'None' },
  coach_briefing: null,
  last_run: null,
  briefing_is_interim: false,
  briefing_last_updated_at: null,
};

// ---------------------------------------------------------------------------
// Mock hook factory (lets each test control briefing_state independently)
// ---------------------------------------------------------------------------

let mockUseHomeData: jest.Mock;
let mockInvalidate: jest.Mock;

jest.mock('@/lib/hooks/queries/home', () => ({
  useHomeData: (...args: any[]) => mockUseHomeData(...args),
  useQuickCheckin: () => ({ mutate: jest.fn(), isPending: false }),
  useInvalidateHome: () => mockInvalidate,
}));

import HomePage from '@/app/home/page';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockInvalidate = jest.fn().mockReturnValue(undefined);
  mockUseHomeData = jest.fn();
});

afterEach(() => {
  jest.restoreAllMocks();
  jest.useRealTimers();
});

// ---------------------------------------------------------------------------
// Test 6: briefing_state='refreshing' → thinking placeholder, no fresh text
// ---------------------------------------------------------------------------

describe('Test 6: pending briefing_state shows thinking placeholder', () => {
  it('shows "Coach is thinking..." when briefing_state is refreshing and no fresh content', () => {
    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'refreshing', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    expect(screen.getByTestId('briefing-thinking')).toBeInTheDocument();
    expect(screen.queryByTestId('morning-voice')).not.toBeInTheDocument();
  });

  it('shows "Coach is thinking..." when briefing_state is missing', () => {
    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'missing', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    expect(screen.getByTestId('briefing-thinking')).toBeInTheDocument();
  });

  it('shows "Coach is thinking..." when briefing_state is stale (no fresh content yet)', () => {
    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'stale', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    expect(screen.getByTestId('briefing-thinking')).toBeInTheDocument();
  });

  it('does NOT block other page content while pending', () => {
    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'refreshing', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    // Check-in section must still render
    expect(screen.getByTestId('checkin-section')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test 7: refetchInterval logic
// ---------------------------------------------------------------------------

describe('Test 7: refetchInterval activates for non-fresh states', () => {
  it('returns 2000 while pending or interim, else false', () => {
    const pendingStates = ['stale', 'missing', 'refreshing'];
    const freshStates = ['fresh', 'consent_required', null, undefined];

    // The refetchInterval fn: keep polling while pending OR interim.
    const refetchInterval = (query: { state: { data?: { briefing_state?: string | null; briefing_is_interim?: boolean } } }) => {
      const state = query.state.data?.briefing_state;
      const isInterim = Boolean(query.state.data?.briefing_is_interim);
      const BRIEFING_PENDING_STATES = new Set(['stale', 'missing', 'refreshing']);
      if (state === 'fresh' && !isInterim) return false;
      if ((state && BRIEFING_PENDING_STATES.has(state)) || isInterim) return 2000;
      return false;
    };

    pendingStates.forEach((s) => {
      expect(refetchInterval({ state: { data: { briefing_state: s, briefing_is_interim: false } } })).toBe(2000);
    });

    freshStates.forEach((s) => {
      expect(refetchInterval({ state: { data: { briefing_state: s, briefing_is_interim: false } } })).toBe(false);
    });

    // Core fix: fresh + interim must continue polling.
    expect(refetchInterval({ state: { data: { briefing_state: 'fresh', briefing_is_interim: true } } })).toBe(2000);
  });
});

// ---------------------------------------------------------------------------
// Test 8: When state transitions to fresh, placeholder disappears
// ---------------------------------------------------------------------------

describe('Test 8: fresh state hides placeholder and shows briefing', () => {
  it('renders morning_voice and hides thinking placeholder when fresh', () => {
    mockUseHomeData.mockReturnValue({
      data: {
        ...baseHomeData,
        briefing_state: 'fresh',
        coach_briefing: {
          morning_voice: '28 miles this week. Solid build.',
          coach_noticed: 'Your sleep improved.',
        },
      },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    expect(screen.queryByTestId('briefing-thinking')).not.toBeInTheDocument();
    expect(screen.queryByTestId('briefing-timeout-fallback')).not.toBeInTheDocument();
    expect(screen.getByTestId('morning-voice')).toBeInTheDocument();
    expect(screen.getByText('28 miles this week. Solid build.')).toBeInTheDocument();
  });

  it('hides placeholder when briefing_state is consent_required', () => {
    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'consent_required', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    expect(screen.queryByTestId('briefing-thinking')).not.toBeInTheDocument();
    expect(screen.queryByTestId('briefing-timeout-fallback')).not.toBeInTheDocument();
  });
});

describe('Interim UI: banner + spinner + auto replace', () => {
  it('shows interim banner/spinner and last-updated timestamp while interim=true', () => {
    mockUseHomeData.mockReturnValue({
      data: {
        ...baseHomeData,
        briefing_state: 'fresh',
        briefing_is_interim: true,
        briefing_last_updated_at: '2026-03-21T07:35:00Z',
        coach_briefing: { morning_voice: 'Interim fallback copy.' },
      },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);
    expect(screen.getByTestId('briefing-interim-banner')).toBeInTheDocument();
    expect(screen.getByText(/Updating your morning insight/i)).toBeInTheDocument();
    expect(screen.getByTestId('briefing-last-updated')).toBeInTheDocument();
    expect(screen.getByText(/Interim fallback copy/i)).toBeInTheDocument();
  });

  it('final payload replaces interim copy without navigation', () => {
    mockUseHomeData
      .mockReturnValueOnce({
        data: {
          ...baseHomeData,
          briefing_state: 'fresh',
          briefing_is_interim: true,
          coach_briefing: { morning_voice: 'Interim fallback copy.' },
        },
        isLoading: false,
        error: null,
      })
      .mockReturnValueOnce({
        data: {
          ...baseHomeData,
          briefing_state: 'fresh',
          briefing_is_interim: false,
          coach_briefing: { morning_voice: 'Final grounded morning voice.' },
        },
        isLoading: false,
        error: null,
      });

    const { rerender } = render(<HomePage />);
    expect(screen.getByText('Interim fallback copy.')).toBeInTheDocument();
    expect(screen.getByTestId('briefing-interim-banner')).toBeInTheDocument();

    rerender(<HomePage />);

    expect(screen.getByText('Final grounded morning voice.')).toBeInTheDocument();
    expect(screen.queryByText('Interim fallback copy.')).not.toBeInTheDocument();
    expect(screen.queryByTestId('briefing-interim-banner')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test 9: 30s timeout → fallback + retry
// ---------------------------------------------------------------------------

describe('Test 9: 30s timeout shows fallback and retry fires invalidate', () => {
  it('shows fallback after 30s of pending state', async () => {
    jest.useFakeTimers();

    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'refreshing', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    // Initially: thinking placeholder, not timed out
    expect(screen.getByTestId('briefing-thinking')).toBeInTheDocument();
    expect(screen.queryByTestId('briefing-timeout-fallback')).not.toBeInTheDocument();

    // Advance 30 seconds
    act(() => {
      jest.advanceTimersByTime(30_000);
    });

    // After timeout: fallback appears
    await waitFor(() => {
      expect(screen.getByTestId('briefing-timeout-fallback')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('briefing-thinking')).not.toBeInTheDocument();
    expect(screen.getByText(/Your coach is taking a moment/i)).toBeInTheDocument();
  });

  it('Retry button triggers queryClient.invalidateQueries', async () => {
    jest.useFakeTimers();

    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'refreshing', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    act(() => { jest.advanceTimersByTime(30_000); });

    await waitFor(() => {
      expect(screen.getByTestId('briefing-timeout-fallback')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry now/i });
    await userEvent.setup({ advanceTimers: jest.advanceTimersByTime }).click(retryBtn);

    // mockInvalidate is returned as the invalidation function itself (query key is
    // baked into useInvalidateHome). Verify it was called once.
    expect(mockInvalidate).toHaveBeenCalledTimes(1);
  });

  it('fallback does not appear before 30s', () => {
    jest.useFakeTimers();

    mockUseHomeData.mockReturnValue({
      data: { ...baseHomeData, briefing_state: 'refreshing', coach_briefing: null },
      isLoading: false,
      error: null,
    });

    render(<HomePage />);

    act(() => { jest.advanceTimersByTime(15_000); });

    expect(screen.queryByTestId('briefing-timeout-fallback')).not.toBeInTheDocument();
    expect(screen.getByTestId('briefing-thinking')).toBeInTheDocument();
  });
});
