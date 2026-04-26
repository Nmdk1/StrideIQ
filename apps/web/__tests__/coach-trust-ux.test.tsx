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

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial' as const,
    formatDistance: (m: number, decimals = 1) => `${(m / 1609.344).toFixed(decimals)} mi`,
    formatPace: (sPerKm: number) => `${Math.floor((sPerKm * 1.60934) / 60)}:00/mi`,
    distanceUnitShort: 'mi',
  }),
}));

jest.mock('@/lib/hooks/queries/progress', () => ({
  useProgressSummary: () => ({ data: null }),
}));

const onboardingGetStatusMock = jest.fn();
jest.mock('@/lib/api/services/onboarding', () => ({
  onboardingService: {
    getStatus: (...args: any[]) => onboardingGetStatusMock(...args),
  },
}));

jest.mock('@/lib/api/client', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
  ApiClientError: class ApiClientError extends Error {
    status?: number;
  },
}));

const coachGetHistoryMock = jest.fn();
const coachGetSuggestionsMock = jest.fn();
const coachChatStreamMock = jest.fn();
const coachNewConversationMock = jest.fn();

jest.mock('@/lib/api/services/ai-coach', () => ({
  aiCoachService: {
    getHistory: (...args: any[]) => coachGetHistoryMock(...args),
    getSuggestions: (...args: any[]) => coachGetSuggestionsMock(...args),
    chatStream: (...args: any[]) => coachChatStreamMock(...args),
    newConversation: (...args: any[]) => coachNewConversationMock(...args),
  },
}));

import CoachPage from '@/app/coach/page';

function renderCoachPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CoachPage />
    </QueryClientProvider>
  );
}

describe('Coach trust UX', () => {
  beforeEach(() => {
    coachGetHistoryMock.mockReset();
    coachGetSuggestionsMock.mockReset();
    coachChatStreamMock.mockReset();
    coachNewConversationMock.mockReset();
    onboardingGetStatusMock.mockReset();
    coachGetSuggestionsMock.mockResolvedValue({ suggestions: [] });
    onboardingGetStatusMock.mockResolvedValue({ baseline_needed: false });
  });

  it('renders persisted tool metadata as checked-source chips', async () => {
    coachGetHistoryMock.mockResolvedValue({
      messages: [
        {
          role: 'assistant',
          content: 'Move the threshold 24 hours if warm-up stays flat.',
          created_at: new Date('2026-04-24T12:00:00Z').toISOString(),
          tools_used: ['get_training_load', 'get_plan_week'],
          tool_count: 2,
          conversation_contract: 'decision_point',
        },
      ],
    });

    renderCoachPage();

    expect(await screen.findByText('Checked: Training Load')).toBeInTheDocument();
    expect(screen.getByText('Checked: Plan Week')).toBeInTheDocument();
    expect(screen.getByText('Decision Point')).toBeInTheDocument();
  });

  it('prefills an athlete-led correction prompt', async () => {
    coachGetHistoryMock.mockResolvedValue({
      messages: [
        {
          role: 'assistant',
          content: 'That race does not exist in your history.',
          created_at: new Date('2026-04-24T12:00:00Z').toISOString(),
          tools_used: [],
          tool_count: 0,
          conversation_contract: 'correction_dispute',
        },
      ],
    });

    renderCoachPage();

    const correctionButton = await screen.findByRole('button', { name: "That's wrong" });
    fireEvent.click(correctionButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask your coach anything...')).toHaveValue(
        'That\'s wrong. Please verify the data and correct this answer: "That race does not exist in your history."'
      );
    });
  });

  it('applies stream done metadata to the active assistant message', async () => {
    coachGetHistoryMock.mockResolvedValue({ messages: [] });
    coachChatStreamMock.mockImplementation(async (_request, handlers) => {
      handlers.onDelta('I checked the actual log.');
      handlers.onDone({
        tools_used: ['get_nutrition_log'],
        tool_count: 1,
        conversation_contract: 'general',
      });
    });

    renderCoachPage();

    const input = await screen.findByPlaceholderText('Ask your coach anything...');
    fireEvent.change(input, { target: { value: 'How many calories today?' } });
    fireEvent.click(screen.getByLabelText('Send message'));

    expect(await screen.findByText('Checked: Nutrition Log')).toBeInTheDocument();
  });
});
