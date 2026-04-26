import React from 'react';
import { render, screen } from '@testing-library/react';
import { within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

import ProgressPage from '@/app/progress/page';

const mockUseProgressKnowledge = jest.fn();

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock('@/components/progress/ProgressHero', () => ({
  ProgressHero: () => <div data-testid="progress-hero" />,
}));
jest.mock('@/components/progress/RecoveryFingerprint', () => ({
  RecoveryFingerprint: () => <div data-testid="recovery-fingerprint" />,
}));
jest.mock('@/lib/hooks/queries/progress', () => ({
  useProgressKnowledge: () => mockUseProgressKnowledge(),
}));

describe('Progress knowledge page', () => {
  test('groups findings by domain and renders curated sections', () => {
    mockUseProgressKnowledge.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        hero: {
          date_label: 'Today',
          headline: 'Progress',
          headline_accent: 'stable',
          subtext: 'sub',
          stats: [],
        },
        correlation_web: { nodes: [], edges: [] },
        proved_facts: [
          {
            input_metric: 'sleep_score',
            output_metric: 'pace_efficiency',
            headline: 'Sleep quality supports pace consistency.',
            evidence: 'Observed across 14 runs.',
            implication: 'Protect sleep before key sessions.',
            times_confirmed: 14,
            confidence_tier: 'strong',
            direction: 'positive',
            correlation_coefficient: 0.41,
            lag_days: 1,
          },
          {
            input_metric: 'sleep_duration',
            output_metric: 'next_day_hr',
            headline: 'Sleep duration supports calmer next-day cardiac load.',
            evidence: 'Observed across 11 runs.',
            implication: 'Prioritize full nights before quality sessions.',
            times_confirmed: 11,
            confidence_tier: 'strong',
            direction: 'negative',
            correlation_coefficient: -0.39,
            lag_days: 1,
          },
          {
            input_metric: 'sleep_readiness',
            output_metric: 'pace_efficiency',
            headline: 'Readiness links with smoother pace control.',
            evidence: 'Observed across 9 runs.',
            implication: 'Lean into steady efforts on high-readiness days.',
            times_confirmed: 9,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.28,
            lag_days: 0,
          },
          {
            input_metric: 'sleep_hrv',
            output_metric: 'interval_completion',
            headline: 'Higher HRV precedes better interval completion.',
            evidence: 'Observed across 8 runs.',
            implication: 'Schedule harder reps when HRV is stable.',
            times_confirmed: 8,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.31,
            lag_days: 1,
          },
          {
            input_metric: 'distance_mi',
            output_metric: 'next_day_hr',
            headline: 'Longer volume can elevate next-day HR.',
            evidence: 'Observed across 6 runs.',
            implication: 'Keep recovery easy after long runs.',
            times_confirmed: 6,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.33,
            lag_days: 1,
          },
          {
            input_metric: 'heart_rate_variability',
            output_metric: 'next_day_hr',
            headline: 'Lower HRV predicts higher next-day HR.',
            evidence: 'Observed across 7 runs.',
            implication: 'Use easier effort after low-HRV mornings.',
            times_confirmed: 7,
            confidence_tier: 'confirmed',
            direction: 'negative',
            correlation_coefficient: -0.29,
            lag_days: 1,
          },
          {
            input_metric: 'morning_hr',
            output_metric: 'run_hr',
            headline: 'Higher morning HR tends to carry into run HR.',
            evidence: 'Observed across 5 runs.',
            implication: 'Use longer warmups when morning HR is elevated.',
            times_confirmed: 5,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.26,
            lag_days: 0,
          },
        ],
        patterns_forming: null,
        recovery_curve: {
          baseline_ready: 72,
          latest_ready: 68,
          trend: 'stable',
          data_points: [],
        },
        generated_at: new Date().toISOString(),
        data_coverage: {
          total_findings: 7,
          confirmed_findings: 7,
          emerging_findings: 0,
          checkin_count: 18,
        },
      },
    });

    render(<ProgressPage />);

    expect(screen.getByTestId('progress-hero')).toBeInTheDocument();
    expect(screen.getByTestId('top-findings')).toBeInTheDocument();
    expect(screen.getByText('Your strongest patterns')).toBeInTheDocument();
    expect(screen.getByText('Sleep and recovery')).toBeInTheDocument();
    expect(screen.getAllByText('Cardiac').length).toBeGreaterThan(0);
    expect(screen.getByTestId('show-all-sleep_recovery')).toBeInTheDocument();
    expect(screen.getAllByTestId('finding-expand-toggle').length).toBeGreaterThan(0);
    expect(screen.getByTestId('recovery-fingerprint')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Ask Coach About Your Progress/i })).toBeInTheDocument();
    expect(screen.getByText('7 patterns')).toBeInTheDocument();
    expect(screen.queryByText(/Correlation Web/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/What the Data Proved/i)).not.toBeInTheDocument();
  });

  test('caps domain findings to 3 then expands on show all', async () => {
    const user = userEvent.setup();
    mockUseProgressKnowledge.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        hero: {
          date_label: 'Today',
          headline: 'Progress',
          headline_accent: 'stable',
          subtext: 'sub',
          stats: [],
        },
        correlation_web: { nodes: [], edges: [] },
        proved_facts: Array.from({ length: 5 }, (_, i) => ({
          input_metric: 'sleep_score',
          output_metric: `pace_efficiency_${i}`,
          headline: `Sleep pattern ${i + 1}`,
          evidence: `Evidence ${i + 1}`,
          implication: `Implication ${i + 1}`,
          times_confirmed: 10 - i,
          confidence_tier: i < 2 ? 'strong' : 'confirmed',
          direction: 'positive',
          correlation_coefficient: 0.2,
          lag_days: 1,
        })),
        patterns_forming: null,
        recovery_curve: null,
        generated_at: new Date().toISOString(),
        data_coverage: {
          total_findings: 5,
          confirmed_findings: 5,
          emerging_findings: 0,
          checkin_count: 20,
        },
      },
    });

    render(<ProgressPage />);
    const sleepSection = screen.getByTestId('domain-section-sleep_recovery');
    expect(within(sleepSection).getAllByText(/Sleep pattern/).length).toBe(3);
    await user.click(screen.getByTestId('show-all-sleep_recovery'));
    expect(within(sleepSection).getAllByText(/Sleep pattern/).length).toBe(5);
  });

  test('top findings section renders deterministic top 5', () => {
    mockUseProgressKnowledge.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        hero: {
          date_label: 'Today',
          headline: 'Progress',
          headline_accent: 'stable',
          subtext: 'sub',
          stats: [],
        },
        correlation_web: { nodes: [], edges: [] },
        proved_facts: [
          {
            input_metric: 'hr',
            output_metric: 'pace',
            headline: 'A',
            evidence: 'e',
            implication: 'i',
            times_confirmed: 8,
            confidence_tier: 'strong',
            direction: 'positive',
            correlation_coefficient: 0.3,
            lag_days: 1,
          },
          {
            input_metric: 'sleep',
            output_metric: 'hr',
            headline: 'B',
            evidence: 'e',
            implication: 'i',
            times_confirmed: 8,
            confidence_tier: 'strong',
            direction: 'negative',
            correlation_coefficient: -0.2,
            lag_days: 1,
          },
          {
            input_metric: 'volume',
            output_metric: 'hr',
            headline: 'C',
            evidence: 'e',
            implication: 'i',
            times_confirmed: 9,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.2,
            lag_days: 1,
          },
          {
            input_metric: 'temp',
            output_metric: 'pace',
            headline: 'D',
            evidence: 'e',
            implication: 'i',
            times_confirmed: 7,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.2,
            lag_days: 1,
          },
          {
            input_metric: 'load',
            output_metric: 'hr',
            headline: 'E',
            evidence: 'e',
            implication: 'i',
            times_confirmed: 6,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.2,
            lag_days: 1,
          },
          {
            input_metric: 'readiness',
            output_metric: 'pace',
            headline: 'F',
            evidence: 'e',
            implication: 'i',
            times_confirmed: 5,
            confidence_tier: 'confirmed',
            direction: 'positive',
            correlation_coefficient: 0.2,
            lag_days: 1,
          },
        ],
        patterns_forming: null,
        recovery_curve: null,
        generated_at: new Date().toISOString(),
        data_coverage: {
          total_findings: 6,
          confirmed_findings: 6,
          emerging_findings: 0,
          checkin_count: 20,
        },
      },
    });

    render(<ProgressPage />);
    const top = screen.getByTestId('top-findings');
    expect(top).toBeInTheDocument();
    expect(within(top).getByText('A')).toBeInTheDocument();
    expect(within(top).getByText('B')).toBeInTheDocument();
    expect(within(top).queryByText('F')).not.toBeInTheDocument();
  });

  test('renders cold-start section when no proved facts', () => {
    mockUseProgressKnowledge.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        hero: {
          date_label: 'Today',
          headline: 'Progress',
          headline_accent: 'stable',
          subtext: 'sub',
          stats: [],
        },
        correlation_web: { nodes: [], edges: [] },
        proved_facts: [],
        patterns_forming: {
          checkin_count: 4,
          checkins_needed: 12,
          progress_pct: 33,
          message: 'Keep checking in to unlock findings.',
        },
        recovery_curve: null,
        generated_at: new Date().toISOString(),
        data_coverage: {
          total_findings: 0,
          confirmed_findings: 0,
          emerging_findings: 0,
          checkin_count: 4,
        },
      },
    });

    render(<ProgressPage />);
    expect(screen.getByText('Patterns building')).toBeInTheDocument();
    expect(screen.getByText(/Keep checking in/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Ask Coach About Your Progress/i })).toBeInTheDocument();
  });
});

