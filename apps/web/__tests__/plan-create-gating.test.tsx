import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import CreatePlanPage from '@/app/plans/create/page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
}));

jest.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: jest.fn(),
  }),
}));

const useAuthMock = jest.fn();
jest.mock('@/lib/context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

describe('Plan create gating (CTA + copy)', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(() => 'token'),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      },
      writable: true,
    });
  });

  it('disables Pro plan types for free users and shows membership CTA', () => {
    useAuthMock.mockReturnValue({
      user: { subscription_tier: 'free', has_active_subscription: false },
      isAuthenticated: true,
    });

    render(<CreatePlanPage />);

    // Baseline: plan type selector is visible
    expect(screen.getByRole('heading', { name: 'Create Your Training Plan' })).toBeInTheDocument();
    expect(screen.getByText('How do you want to create your plan?')).toBeInTheDocument();

    // Pro options are gated.
    expect(screen.getByRole('button', { name: /Model-Driven Plan/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Fitness Bank Plan/i })).toBeDisabled();

    // Gating copy points to membership management.
    expect(screen.getAllByRole('link', { name: /Manage membership/i })[0]).toHaveAttribute('href', '/settings');
  });

  it('enables Pro plan types for paid users', () => {
    useAuthMock.mockReturnValue({
      user: { subscription_tier: 'pro', has_active_subscription: true },
      isAuthenticated: true,
    });

    render(<CreatePlanPage />);

    expect(screen.getByRole('button', { name: /Model-Driven Plan/i })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: /Fitness Bank Plan/i })).not.toBeDisabled();
  });
});

