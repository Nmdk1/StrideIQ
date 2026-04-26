/**
 * Register intent carry-through tests.
 *
 * Verifies that ?tier=<any>&period=<period> params on /register are:
 *   1. Shown as a contextual hint on the form.
 *   2. Used to route to /settings?upgrade=premium&period=<period> after signup.
 *   3. Gracefully ignored for invalid or missing values (falls back to /onboarding).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ── Next.js navigation mocks ──────────────────────────────────────────────────

const mockPush = jest.fn();
let mockSearchParams = new URLSearchParams();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => mockSearchParams,
}));

// ── Auth mock — register resolves by default; override per test as needed ─────

const mockRegister = jest.fn();
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({
    register: mockRegister,
    isLoading: false,
  }),
}));

// ── Import the page component AFTER mocks ─────────────────────────────────────
// RegisterPage wraps RegisterForm in <Suspense>; we render RegisterPage so the
// Suspense boundary is exercised just like in production.
import RegisterPage from '@/app/register/page';

// ── Test helpers ──────────────────────────────────────────────────────────────

function setSearchParams(params: Record<string, string>) {
  mockSearchParams = new URLSearchParams(params);
}

async function submitForm() {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'test@example.com' },
  });
  fireEvent.change(screen.getByLabelText(/^password \*/i), {
    target: { value: 'password123' },
  });
  fireEvent.change(screen.getByLabelText(/confirm password/i), {
    target: { value: 'password123' },
  });
  fireEvent.click(screen.getByRole('button', { name: /create account/i }));
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockPush.mockReset();
  mockRegister.mockReset();
  mockRegister.mockResolvedValue(undefined);
  setSearchParams({});
});

describe('Register page — no tier intent (baseline)', () => {
  it('routes to /onboarding after successful registration', async () => {
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/onboarding'));
  });

  it('does not show tier intent hint', () => {
    render(<RegisterPage />);
    expect(screen.queryByText(/signing up for/i)).not.toBeInTheDocument();
  });
});

describe('Register page — subscriber annual intent', () => {
  beforeEach(() => setSearchParams({ tier: 'subscriber', period: 'annual' }));

  it('shows upgrade intent hint', () => {
    render(<RegisterPage />);
    expect(screen.getByText(/signing up for/i)).toBeInTheDocument();
    expect(screen.getByText(/StrideIQ/)).toBeInTheDocument();
  });

  it('routes to /settings?upgrade=premium&period=annual after signup', async () => {
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=premium&period=annual',
      ),
    );
  });
});

describe('Register page — subscriber monthly intent', () => {
  beforeEach(() => setSearchParams({ tier: 'subscriber', period: 'monthly' }));

  it('routes to /settings?upgrade=premium&period=monthly after signup', async () => {
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=premium&period=monthly',
      ),
    );
  });
});

describe('Register page — legacy tier params still work', () => {
  it('guided param routes to upgrade path', async () => {
    setSearchParams({ tier: 'guided', period: 'annual' });
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=premium&period=annual',
      ),
    );
  });

  it('premium param routes to upgrade path', async () => {
    setSearchParams({ tier: 'premium', period: 'monthly' });
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=premium&period=monthly',
      ),
    );
  });
});

describe('Register page — invalid tier params (fallback)', () => {
  it('ignores free tier param and routes to /onboarding', async () => {
    setSearchParams({ tier: 'free', period: 'annual' });
    render(<RegisterPage />);
    expect(screen.queryByText(/signing up for/i)).not.toBeInTheDocument();
    await submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/onboarding'));
  });

  it('tier present without period defaults to annual', async () => {
    setSearchParams({ tier: 'subscriber' });
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=premium&period=annual',
      ),
    );
  });
});
