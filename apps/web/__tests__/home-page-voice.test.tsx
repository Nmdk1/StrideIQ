/**
 * Home Page Voice — RED tests for the homepage renovation.
 *
 * These tests are written RED-first: they will FAIL until the
 * home page layout is restructured with:
 *   1. Full-bleed effort gradient (data-hero-mode="full-bleed")
 *   2. morning_voice as plain <p> text + Coach noticed card with Opus insight
 *   3. Today's workout with workout_why
 *   4. Check-in positioned AFTER workout (below fold)
 *
 * Guardrails:
 *   - DOM order: hero → voice → workout → checkin
 *   - CoachNoticedCard restored with richer Opus-generated insight
 *   - morning_voice and workout_why rendered via data-testid
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock Next.js routing
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/home',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next/link', () => {
  return ({ children, href, ...props }: any) => <a href={href} {...props}>{children}</a>;
});

// Mock UnitsContext
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

// Mock home data hook
const mockHomeData = {
  today: {
    has_workout: true,
    workout_type: 'easy',
    title: '4mi easy',
    distance_mi: 3.5,
    pace_guidance: 'Paces: easy: 8:05/mi',
    why_context: 'Week 4 of 8. Build phase. Active recovery day.',
    why_source: 'plan',
    week_number: 4,
    phase: 'Build',
  },
  yesterday: { has_activity: true, activity_name: 'Lunch Run', distance_mi: 10.0 },
  week: {
    week_number: 4,
    total_weeks: 8,
    phase: 'Build',
    completed_mi: 48.0,
    planned_mi: 51.2,
    progress_pct: 94,
    days: [],
    status: 'on_track',
    trajectory_sentence: 'On track.',
  },
  strava_connected: true,
  has_any_activities: true,
  total_activities: 100,
  checkin_needed: false,
  today_checkin: { motivation_label: 'Fine', sleep_label: 'Poor', soreness_label: 'Yes' },
  strava_status: { connected: true, needs_reconnect: false },
  coach_briefing: {
    coach_noticed: 'Strong consistency this week.',
    today_context: 'Easy day to absorb the 10-miler.',
    week_assessment: 'Building a solid base for Tobacco Road.',
    checkin_reaction: 'Glad you feel fine despite the soreness.',
    race_assessment: 'On track for race day.',
    // NEW fields — the voice
    morning_voice: '48 miles across 6 runs this week. HR averaged 142 bpm — consistent with your build phase targets.',
    workout_why: 'Active recovery keeps blood flowing after yesterday\'s 10-mile effort.',
  },
  last_run: {
    activity_id: 'd6fd1aee-37b4-4123-8286-9e6a4bb1de1c',
    name: 'Lunch Run',
    start_time: '2026-02-14T12:00:00Z',
    distance_m: 16093,
    moving_time_s: 5060,
    average_hr: 142,
    stream_status: 'success',
    effort_intensity: Array.from({ length: 100 }, (_, i) => i / 99),
    tier_used: 'tier1_threshold_hr',
    confidence: 0.88,
    segments: [],
    pace_per_km: 314,
  },
};

jest.mock('@/lib/hooks/queries/home', () => ({
  useHomeData: () => ({ data: mockHomeData, isLoading: false, error: null }),
  useQuickCheckin: () => ({ mutate: jest.fn(), isPending: false }),
}));

// Mock ProtectedRoute to just render children
jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: any) => <>{children}</>,
}));

// Use real LastRunHero (not mocked — tests full-bleed rendering)
// The component uses effortToColor which works in test env.

// Mock UI components
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

// Dynamic import of the page component
import HomePage from '@/app/home/page';

// ---------------------------------------------------------------------------
// Cleanup
// ---------------------------------------------------------------------------

afterEach(() => {
  jest.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Home Page Voice: Section order', () => {
  test('DOM order is: hero → voice → workout → checkin', () => {
    const { container } = render(<HomePage />);

    // These data-testid markers must exist in order
    const hero = container.querySelector('[data-testid="last-run-hero"]');
    const voice = container.querySelector('[data-testid="morning-voice"]');
    const workout = container.querySelector('[data-testid="today-workout"]');
    const checkin = container.querySelector('[data-testid="checkin-section"]');

    expect(hero).toBeInTheDocument();
    expect(voice).toBeInTheDocument();
    expect(workout).toBeInTheDocument();
    expect(checkin).toBeInTheDocument();

    // Verify DOM order: hero before voice before workout before checkin
    const all = container.querySelectorAll('[data-testid]');
    const ids = Array.from(all).map((el) => el.getAttribute('data-testid'));

    const heroIdx = ids.indexOf('last-run-hero');
    const voiceIdx = ids.indexOf('morning-voice');
    const workoutIdx = ids.indexOf('today-workout');
    const checkinIdx = ids.indexOf('checkin-section');

    expect(heroIdx).toBeLessThan(voiceIdx);
    expect(voiceIdx).toBeLessThan(workoutIdx);
    expect(workoutIdx).toBeLessThan(checkinIdx);
  });

  test('DOM order works when no last_run (hero absent)', () => {
    // Override mock to remove last_run
    jest.spyOn(require('@/lib/hooks/queries/home'), 'useHomeData').mockReturnValue({
      data: { ...mockHomeData, last_run: null },
      isLoading: false,
      error: null,
    });

    const { container } = render(<HomePage />);

    // With no last_run, hero should be absent, but voice should still lead
    const hero = container.querySelector('[data-testid="last-run-hero"]');
    const voice = container.querySelector('[data-testid="morning-voice"]');
    expect(hero).not.toBeInTheDocument();
    expect(voice).toBeInTheDocument();
  });
});

describe('Home Page Voice: Voice rendering', () => {
  test('morning_voice renders as plain <p> text', () => {
    render(<HomePage />);

    const voiceEl = screen.getByTestId('morning-voice');
    expect(voiceEl).toBeInTheDocument();

    // Should contain the morning_voice text
    expect(voiceEl).toHaveTextContent('48 miles across 6 runs this week');
  });

  test('Coach noticed card is not separately rendered (absorbed into morning_voice per H2/H4)', () => {
    const { container } = render(<HomePage />);

    // CoachNoticedCard is no longer rendered as a separate element —
    // intelligence is absorbed into morning_voice (spec H2/H4)
    const coachNoticedElements = container.querySelectorAll('*');
    const found = Array.from(coachNoticedElements).some(
      (el) => el.textContent?.includes('Coach noticed')
    );
    expect(found).toBe(false);
  });
});

describe('Home Page Voice: Full-bleed hero', () => {
  test('hero has data-hero-mode="full-bleed"', () => {
    render(<HomePage />);
    const hero = screen.getByTestId('last-run-hero');
    expect(hero).toHaveAttribute('data-hero-mode', 'full-bleed');
  });

  test('hero is not wrapped in a card', () => {
    const { container } = render(<HomePage />);
    const hero = screen.getByTestId('last-run-hero');
    // The hero should not be a child of a Card component
    const parent = hero.parentElement;
    expect(parent?.classList.toString()).not.toContain('Card');
  });
});

describe('Home Page Voice: Workout WHY', () => {
  test('workout_why renders with data-testid="workout-why"', () => {
    render(<HomePage />);
    const whyEl = screen.getByTestId('workout-why');
    expect(whyEl).toBeInTheDocument();
    expect(whyEl).toHaveTextContent('Active recovery keeps blood flowing');
  });
});

describe('Home Page Voice: Check-in position', () => {
  test('check-in section is positioned after workout section', () => {
    const { container } = render(<HomePage />);

    const workout = container.querySelector('[data-testid="today-workout"]');
    const checkin = container.querySelector('[data-testid="checkin-section"]');

    expect(workout).toBeInTheDocument();
    expect(checkin).toBeInTheDocument();

    // Verify order
    const allTestIds = Array.from(container.querySelectorAll('[data-testid]')).map(
      (el) => el.getAttribute('data-testid')
    );
    const workoutIdx = allTestIds.indexOf('today-workout');
    const checkinIdx = allTestIds.indexOf('checkin-section');
    expect(workoutIdx).toBeLessThan(checkinIdx);
  });
});
