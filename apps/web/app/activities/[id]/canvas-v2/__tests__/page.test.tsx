/**
 * Route gate test for /activities/[id]/canvas-v2.
 *
 * Verifies the gate logic from `lib/canvasV2/featureGate.ts` is actually
 * applied at the route entry. The gate logic itself has its own unit tests
 * in `lib/canvasV2/__tests__/featureGate.test.ts` — this file just guards
 * against the route forgetting to call it.
 *
 * We mock useAuth and useParams; the page should:
 *   - Call notFound() when the user is not on the allowlist
 *   - Render without crashing for an allowed user (terrain panel + heavy
 *     children are not exercised — they're dynamic-imported and gated by
 *     stream availability)
 */

import React from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// In real Next.js, notFound() throws to trigger the not-found boundary.
// For this test we only need to confirm the route INVOKED the gate, so a
// no-op mock is sufficient and lets the test assert cleanly without React
// blowing up on the thrown error inside a useEffect.
const notFoundMock = jest.fn();

jest.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-activity-id' }),
  notFound: () => notFoundMock(),
}));

const useAuthMock = jest.fn();
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => useAuthMock(),
}));

// Stub the heavy CanvasV2 child so the route test isn't dragged into r3f
// land (which doesn't render in jsdom without a WebGL stub).
jest.mock('@/components/canvas-v2/CanvasV2', () => ({
  CanvasV2: () => <div data-testid="canvas-v2-stub" />,
}));

// Stream analysis hook — return a stable null for the route test.
jest.mock('@/components/activities/rsi/hooks/useStreamAnalysis', () => ({
  useStreamAnalysis: () => ({ data: null, isLoading: false, error: null, refetch: () => {} }),
  isAnalysisData: () => false,
  isLifecycleResponse: () => false,
}));

import CanvasV2Page from '../page';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CanvasV2Page />
    </QueryClientProvider>,
  );
}

describe('canvas-v2 route gate', () => {
  beforeEach(() => {
    notFoundMock.mockClear();
    useAuthMock.mockReset();
  });

  it('calls notFound() when user is not on the allowlist', async () => {
    useAuthMock.mockReturnValue({
      user: { email: 'random@example.com', id: '1', subscription_tier: 'pro' },
      token: 'tok',
      isAuthenticated: true,
      isLoading: false,
    });
    renderPage();
    // notFound() is invoked from a useEffect; flush the microtask queue.
    await Promise.resolve();
    expect(notFoundMock).toHaveBeenCalled();
  });

  it('calls notFound() when unauthenticated', async () => {
    useAuthMock.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
    renderPage();
    await Promise.resolve();
    expect(notFoundMock).toHaveBeenCalled();
  });

  it('does NOT call notFound() while auth is still loading', async () => {
    useAuthMock.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
    });
    renderPage();
    await Promise.resolve();
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  it('renders the canvas for the founder email (no notFound)', async () => {
    useAuthMock.mockReturnValue({
      user: { email: 'mbshaf@gmail.com', id: '1', subscription_tier: 'pro' },
      token: 'tok',
      isAuthenticated: true,
      isLoading: false,
    });
    const { findByTestId } = renderPage();
    await Promise.resolve();
    expect(notFoundMock).not.toHaveBeenCalled();
    await findByTestId('canvas-v2-stub');
  });

  it('is case-insensitive on founder email', async () => {
    useAuthMock.mockReturnValue({
      user: { email: 'MBshaf@Gmail.com', id: '1', subscription_tier: 'pro' },
      token: 'tok',
      isAuthenticated: true,
      isLoading: false,
    });
    renderPage();
    await Promise.resolve();
    expect(notFoundMock).not.toHaveBeenCalled();
  });
});
