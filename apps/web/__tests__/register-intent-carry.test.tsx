/**
 * Register intent carry-through tests.
 *
 * Verifies that ?tier=<tier>&period=<period> params on /register are:
 *   1. Shown as a contextual hint on the form.
 *   2. Used to route to /settings?upgrade=<tier>&period=<period> after signup.
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
    expect(screen.queryByText(/signing up for the/i)).not.toBeInTheDocument();
  });
});

describe('Register page — guided annual intent', () => {
  beforeEach(() => setSearchParams({ tier: 'guided', period: 'annual' }));

  it('shows tier intent hint for guided', () => {
    render(<RegisterPage />);
    expect(screen.getByText(/signing up for the/i)).toBeInTheDocument();
    expect(screen.getByText(/Guided/)).toBeInTheDocument();
  });

  it('routes to /settings?upgrade=guided&period=annual after signup', async () => {
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=guided&period=annual',
      ),
    );
  });
});

describe('Register page — guided monthly intent', () => {
  beforeEach(() => setSearchParams({ tier: 'guided', period: 'monthly' }));

  it('routes to /settings?upgrade=guided&period=monthly after signup', async () => {
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=guided&period=monthly',
      ),
    );
  });
});

describe('Register page — premium annual intent', () => {
  beforeEach(() => setSearchParams({ tier: 'premium', period: 'annual' }));

  it('shows tier intent hint for premium', () => {
    render(<RegisterPage />);
    expect(screen.getByText(/signing up for the/i)).toBeInTheDocument();
    expect(screen.getByText(/Premium/)).toBeInTheDocument();
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

describe('Register page — invalid tier params (fallback)', () => {
  it('ignores unknown tier and routes to /onboarding', async () => {
    setSearchParams({ tier: 'elite', period: 'annual' });
    render(<RegisterPage />);
    expect(screen.queryByText(/signing up for the/i)).not.toBeInTheDocument();
    await submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/onboarding'));
  });

  it('ignores free tier param (not a paid tier) and routes to /onboarding', async () => {
    setSearchParams({ tier: 'free', period: 'annual' });
    render(<RegisterPage />);
    expect(screen.queryByText(/signing up for the/i)).not.toBeInTheDocument();
    await submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/onboarding'));
  });

  it('tier present without period defaults to annual', async () => {
    setSearchParams({ tier: 'premium' });
    render(<RegisterPage />);
    await submitForm();
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(
        '/settings?upgrade=premium&period=annual',
      ),
    );
  });
});
