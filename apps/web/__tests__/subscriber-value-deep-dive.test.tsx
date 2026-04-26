import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
  window.requestAnimationFrame = (cb) => { cb(0); return 0; };
});

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

const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: mockReplace }),
  usePathname: () => '/insights',
  useSearchParams: () => new URLSearchParams(),
}));

const useAuthMock = jest.fn();
// CoachPage now consumes useUnits() for the "This week" volume render.
// This test exercises subscriber-tier behavior, not unit formatting, so a
// static stub is sufficient.
jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial' as const,
    formatDistance: (m: number, decimals = 1) => `${(m / 1609.344).toFixed(decimals)} mi`,
    formatPace: (sPerKm: number) => `${Math.floor((sPerKm * 1.60934) / 60)}:00/mi`,
    distanceUnitShort: 'mi',
  }),
}));

jest.mock('@/lib/context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

jest.mock('@/lib/hooks/queries/progress', () => ({
  useProgressSummary: () => ({ data: null }),
}));

const apiGetMock = jest.fn();
const apiPostMock = jest.fn();
jest.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: any[]) => apiGetMock(...args),
    post: (...args: any[]) => apiPostMock(...args),
  },
}));

const coachGetHistoryMock = jest.fn();
const coachGetSuggestionsMock = jest.fn();
const coachChatMock = jest.fn();
const coachChatStreamMock = jest.fn();
const coachNewConversationMock = jest.fn();

jest.mock('@/lib/api/services/ai-coach', () => ({
  aiCoachService: {
    getHistory: (...args: any[]) => coachGetHistoryMock(...args),
    getSuggestions: (...args: any[]) => coachGetSuggestionsMock(...args),
    chat: (...args: any[]) => coachChatMock(...args),
    chatStream: (...args: any[]) => coachChatStreamMock(...args),
    newConversation: (...args: any[]) => coachNewConversationMock(...args),
  },
}));

describe('Subscriber value deep-dive (Manual redirect + PBs + Coach evidence)', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    mockReplace.mockReset();
    apiGetMock.mockReset();
    apiPostMock.mockReset();
    coachGetHistoryMock.mockReset();
    coachGetSuggestionsMock.mockReset();
    coachChatMock.mockReset();
    coachChatStreamMock.mockReset();
    coachNewConversationMock.mockReset();
  });

  it('redirects /insights to /manual and renders Personal Bests table rows', async () => {
    render(<InsightsPage />);
    expect(mockReplace).toHaveBeenCalledWith('/manual');

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
    expect(await screen.findByText('Race')).toBeInTheDocument();
  });

  it('renders Coach evidence/receipts as an expandable section', async () => {
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

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <CoachPage />
      </QueryClientProvider>
    );

    expect(await screen.findByText('Coach')).toBeInTheDocument();

    const summary = await screen.findByText('Evidence (expand)');
    expect(summary).toBeInTheDocument();

    fireEvent.click(summary);

    await waitFor(() => {
      expect(screen.getByText(/Long run 18mi/i)).toBeInTheDocument();
    });
  });
});
