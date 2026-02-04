import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// `react-markdown` is ESM-only; Jest in this repo runs in CJS mode.
// For UI smoke, a simple passthrough renderer is sufficient.
jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import InsightsPage from '@/app/insights/page';
import PersonalBestsPage from '@/app/personal-bests/page';
import CoachPage from '@/app/coach/page';

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/insights',
}));

// AuthContext is used by Insights (AthleteIntelligenceSection)
const useAuthMock = jest.fn();
jest.mock('@/lib/context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

// Insights hooks
const useInsightFeedMock = jest.fn();
const useActiveInsightsMock = jest.fn();
const useBuildStatusMock = jest.fn();
const useAthleteIntelligenceMock = jest.fn();

jest.mock('@/lib/hooks/queries/insights', () => ({
  useInsightFeed: (...args: any[]) => useInsightFeedMock(...args),
  useActiveInsights: (...args: any[]) => useActiveInsightsMock(...args),
  useBuildStatus: (...args: any[]) => useBuildStatusMock(...args),
  useAthleteIntelligence: (...args: any[]) => useAthleteIntelligenceMock(...args),
  useDismissInsight: () => ({ mutate: jest.fn(), isPending: false }),
  useSaveInsight: () => ({ mutate: jest.fn(), isPending: false }),
  useGenerateInsights: () => ({ mutate: jest.fn(), isPending: false }),
}));

// Personal Bests uses apiClient directly
const apiGetMock = jest.fn();
const apiPostMock = jest.fn();
jest.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: any[]) => apiGetMock(...args),
    post: (...args: any[]) => apiPostMock(...args),
  },
}));

// Coach service (evidence/receipts)
const coachGetHistoryMock = jest.fn();
const coachGetSuggestionsMock = jest.fn();
const coachChatMock = jest.fn();
const coachNewConversationMock = jest.fn();

jest.mock('@/lib/api/services/ai-coach', () => ({
  aiCoachService: {
    getHistory: (...args: any[]) => coachGetHistoryMock(...args),
    getSuggestions: (...args: any[]) => coachGetSuggestionsMock(...args),
    chat: (...args: any[]) => coachChatMock(...args),
    newConversation: (...args: any[]) => coachNewConversationMock(...args),
  },
}));

describe('Subscriber value deep-dive (Insights + PBs + Coach evidence)', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    useInsightFeedMock.mockReset();
    useActiveInsightsMock.mockReset();
    useBuildStatusMock.mockReset();
    useAthleteIntelligenceMock.mockReset();

    apiGetMock.mockReset();
    apiPostMock.mockReset();

    coachGetHistoryMock.mockReset();
    coachGetSuggestionsMock.mockReset();
    coachChatMock.mockReset();
    coachNewConversationMock.mockReset();
  });

  it('renders Insights cards with evidence and Personal Bests table rows', async () => {
    useAuthMock.mockReturnValue({ user: { subscription_tier: 'free' } });

    useInsightFeedMock.mockReturnValue({
      data: {
        cards: [
          {
            key: 'card_1',
            type: 'trend_alert',
            title: 'Efficiency improved',
            summary: 'Your efficiency improved vs baseline.',
            confidence: { label: 'high' },
            evidence: [{ label: 'CTL', value: '42' }],
            actions: [{ href: '/analytics', label: 'Review' }],
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    useActiveInsightsMock.mockReturnValue({ data: { insights: [] }, isLoading: false, error: null });
    useBuildStatusMock.mockReturnValue({ data: { has_active_plan: false }, isLoading: false });
    useAthleteIntelligenceMock.mockReturnValue({ data: null, isLoading: false, error: new Error('locked') });

    render(<InsightsPage />);
    expect(await screen.findByRole('heading', { name: '🧠 Insights' })).toBeInTheDocument();
    expect(screen.getByText('Top Insights (Ranked)')).toBeInTheDocument();
    expect(screen.getByText('Efficiency improved')).toBeInTheDocument();
    expect(screen.getByText('CTL')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();

    // Personal Bests table uses react-query + apiClient; render with QueryClientProvider.
    apiGetMock.mockImplementation((path: string) => {
      if (path === '/v1/athletes/me') {
        return Promise.resolve({ id: 'athlete-1', display_name: 'Test' });
      }
      if (path === '/v1/athletes/athlete-1/personal-bests') {
        return Promise.resolve([
          {
            id: 'pb-1',
            distance_category: '5k',
            distance_meters: 5000,
            time_seconds: 1200,
            pace_per_mile: 6.5,
            achieved_at: new Date('2026-01-01T00:00:00Z').toISOString(),
            is_race: true,
            age_at_achievement: null,
          },
        ]);
      }
      if (path === '/v1/athletes/athlete-1/best-efforts/status') {
        return Promise.resolve({
          status: 'success',
          best_efforts: {
            athlete_id: 'athlete-1',
            provider: 'strava',
            total_activities: 10,
            activities_processed: 10,
            remaining_activities: 0,
            coverage_pct: 100,
            best_effort_rows: 100,
            activities_with_efforts: 10,
            last_provider_sync_at: null,
          },
        });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <PersonalBestsPage />
      </QueryClientProvider>
    );

    expect(await screen.findByText('Personal Bests')).toBeInTheDocument();
    expect(await screen.findByText('5K')).toBeInTheDocument();
    expect(await screen.findByText('20:00')).toBeInTheDocument();
    // Race badge indicates this is a race-derived PB.
    expect(await screen.findByText('Race')).toBeInTheDocument();
  });

  it('renders Coach evidence/receipts as an expandable section', async () => {
    // Provide a history message containing an Evidence section so receipts parsing is exercised.
    coachGetHistoryMock.mockResolvedValue({
      messages: [
        {
          role: 'assistant',
          content: 'Here is the answer.\n\n## Evidence\n- 2026-01-10: Long run 18mi @ MP finish\n',
          created_at: new Date('2026-01-20T00:00:00Z').toISOString(),
        },
      ],
    });
    coachGetSuggestionsMock.mockResolvedValue({ suggestions: [] });

    render(<CoachPage />);

    expect(await screen.findByText('Coach')).toBeInTheDocument();

    // Evidence should be present as a collapsed <details>.
    const summary = await screen.findByText('Evidence (expand)');
    expect(summary).toBeInTheDocument();

    fireEvent.click(summary);

    await waitFor(() => {
      expect(screen.getByText(/Long run 18mi/i)).toBeInTheDocument();
    });
  });
});

