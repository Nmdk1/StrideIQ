/**
 * Plan create — readiness-gate refusal renders cleanly.
 *
 * When an athlete asks for a race distance their training history doesn't
 * yet support (marathon without a 12mi long run AND no lifetime evidence
 * of one), the API returns a structured 422 with
 * `error_code: 'readiness_gate_blocked'`.
 *
 * The UI must:
 *  - render the API's `display_message` verbatim (not raw error text)
 *  - NOT show the "Use safe range" CTA (that's for quality_gate failures)
 *  - NOT collapse into a generic "Request failed (422)" string
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ApiClientError } from '@/lib/api/client';

const createConstraintAware = jest.fn();
const previewConstraintAware = jest.fn();

jest.mock('@/lib/api/services/plans', () => ({
  planService: {
    createConstraintAware: (...args: unknown[]) => createConstraintAware(...args),
    previewConstraintAware: (...args: unknown[]) => previewConstraintAware(...args),
    createCustom: jest.fn(),
    createModelDriven: jest.fn(),
  },
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), prefetch: jest.fn() }),
}));

jest.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

const useAuthMock = jest.fn();
jest.mock('@/lib/context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

const useUnitsMock = jest.fn();
jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => useUnitsMock(),
}));

import CreatePlanPage from '@/app/plans/create/page';

function setUnits(units: 'metric' | 'imperial') {
  useUnitsMock.mockReturnValue({
    units,
    setUnits: jest.fn(),
    formatPace: jest.fn(),
    formatDistance: jest.fn(),
    formatSpeed: jest.fn(),
  });
}

const READINESS_DISPLAY = (
  "Your training history doesn't yet support a Marathon program. " +
  "To start safely you need a long run of at least 12 miles in the past 4 weeks " +
  '(or proven lifetime evidence of running that distance). Build to a 12-mile long run, ' +
  "then come back — or pick a shorter goal distance and we'll build you a plan today."
);

function makeReadinessGateError(): ApiClientError {
  return new ApiClientError('Unprocessable Entity', 422, {
    detail: {
      error_code: 'readiness_gate_blocked',
      display_message: READINESS_DISPLAY,
      reason:
        'Marathon readiness gate: current long run is 10mi (lifetime peak 11mi). ' +
        'Must complete 12mi before starting a marathon program.',
      race_distance: 'marathon',
      required_long_run_miles: 12,
      suggested_alternatives: ['half_marathon', '10k'],
    },
  } as unknown as Parameters<typeof ApiClientError>[2]);
}

async function navigateToMarathonGenerate() {
  fireEvent.click(screen.getByRole('button', { name: /Fitness Bank Plan/i }));
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  const buttons = screen.getAllByRole('button');
  const marathon = buttons.find(
    (b) => /Marathon/.test(b.textContent ?? '') && !/Half/.test(b.textContent ?? ''),
  );
  if (!marathon) throw new Error('Marathon button not found');
  fireEvent.click(marathon);
  const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
  fireEvent.change(dateInput, {
    target: {
      value: new Date(Date.now() + 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    },
  });
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  fireEvent.click(screen.getByRole('button', { name: /Generate Plan/i }));
}

describe('Plan create — readiness gate refusal', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    useUnitsMock.mockReset();
    createConstraintAware.mockReset();
    previewConstraintAware.mockReset();
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(() => 'token'),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      },
      writable: true,
    });
    useAuthMock.mockReturnValue({
      user: { subscription_tier: 'pro', has_active_subscription: true },
      isAuthenticated: true,
    });
    setUnits('imperial');
  });

  it('renders the structured display_message instead of a raw 422 error', async () => {
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeReadinessGateError());

    render(<CreatePlanPage />);
    await navigateToMarathonGenerate();

    await waitFor(() => {
      expect(
        screen.getByText(/Your training history doesn't yet support a Marathon program/i),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/Request failed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Marathon readiness gate:/)).not.toBeInTheDocument();
  });

  it('does NOT show the safe-range CTA (that is for quality-gate failures only)', async () => {
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeReadinessGateError());

    render(<CreatePlanPage />);
    await navigateToMarathonGenerate();

    await waitFor(() => {
      expect(
        screen.getByText(/Your training history doesn't yet support a Marathon program/i),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/Use safe range/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Safe range from your training history/i)).not.toBeInTheDocument();
  });
});
