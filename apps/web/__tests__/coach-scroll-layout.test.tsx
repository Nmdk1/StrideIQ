import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// The Coach page is wrapped in auth + makes network calls on mount.
// For this regression test, we only care about the DOM structure/classes
// that make the transcript the ONLY scroll container.

// react-markdown ships ESM; mock it to keep Jest config simple.
jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('@/lib/api/services/ai-coach', () => ({
  // Return never-resolving promises so the component doesn't set state during the test.
  // This keeps the test focused on DOM structure rather than async effects.
  aiCoachService: {
    getHistory: jest.fn().mockReturnValue(new Promise(() => {})),
    getSuggestions: jest.fn().mockReturnValue(new Promise(() => {})),
    chat: jest.fn(),
    newConversation: jest.fn(),
  },
}));

import CoachPage from '@/app/coach/page';

describe('Coach scroll layout regression', () => {
  beforeAll(() => {
    // JSDOM may not provide rAF; Coach uses it for scroll-to-bottom.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).requestAnimationFrame =
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (globalThis as any).requestAnimationFrame || ((cb: any) => setTimeout(cb, 0));
    // Mock scrollIntoView (not implemented in JSDOM)
    Element.prototype.scrollIntoView = jest.fn();
  });

  test('transcript is the scroll container; shell is overflow-hidden', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <CoachPage />
      </QueryClientProvider>
    );

    const shell = screen.getByTestId('coach-shell');
    expect(shell).toHaveClass('overflow-hidden');

    const inner = screen.getByTestId('coach-shell-inner');
    // The key to making nested flex scroll work: allow shrinking.
    expect(inner).toHaveClass('min-h-0');

    const cardContent = screen.getByTestId('coach-chat-cardcontent');
    expect(cardContent).toHaveClass('min-h-0');

    const transcript = screen.getByTestId('coach-transcript');
    expect(transcript).toHaveClass('overflow-y-auto');
    expect(transcript).toHaveClass('min-h-0');
  });
});

