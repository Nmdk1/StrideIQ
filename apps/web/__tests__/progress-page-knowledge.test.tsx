import React from 'react';
import { render, screen } from '@testing-library/react';
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
  test('groups findings by domain and renders expandable cards', () => {
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
        ],
        patterns_forming: null,
        recovery_curve: null,
        generated_at: new Date().toISOString(),
        data_coverage: {
          total_findings: 2,
          confirmed_findings: 2,
          emerging_findings: 0,
          checkin_count: 18,
        },
      },
    });

    render(<ProgressPage />);

    expect(screen.getByTestId('progress-hero')).toBeInTheDocument();
    expect(screen.getByText('Sleep and recovery')).toBeInTheDocument();
    expect(screen.getAllByText('Cardiac').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('finding-expand-toggle').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Correlation Web/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/What the Data Proved/i)).not.toBeInTheDocument();
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

