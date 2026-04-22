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

function makeQualityGateError(): ApiClientError {
  return new ApiClientError(
    'Plan quality gate failed',
    422,
    {
      detail: {
        error_code: 'quality_gate_failed',
        quality_gate_failed: true,
        reasons: ['Week 1 exceeds trusted band ceiling: 30.0 > 24.0.'],
        invariant_conflicts: ['weekly_volume_exceeds_trusted_band'],
        suggested_safe_bounds: { weekly_miles: { min: 18.0, max: 24.0 }, long_run_miles: { min: 8.0, max: 14.0 } },
        safe_bounds_km: { weekly_miles: { min: 29.0, max: 38.6 }, long_run_miles: { min: 12.9, max: 22.5 } },
        display_message:
          'Your peak weekly volume is higher than your training history supports. Try a peak inside the safe range below.',
        recommended_peak_weekly_miles: 21.0,
        recommended_peak_weekly_km: 33.8,
        next_action: 'adjust_inputs_or_accept_safe_bounds',
      },
    },
  );
}

async function navigateToConstraintAwareForm() {
  fireEvent.click(screen.getByRole('button', { name: /Fitness Bank Plan/i }));
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  // On constraint-aware-form: click any race distance and pick a date.
  const buttons = screen.getAllByRole('button');
  const halfMarathon = buttons.find((b) => /Half Marathon/.test(b.textContent ?? ''));
  if (!halfMarathon) throw new Error('Half Marathon button not found');
  fireEvent.click(halfMarathon);
  const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
  fireEvent.change(dateInput, {
    target: { value: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0] },
  });
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  // Skip tune-up race step
  fireEvent.click(screen.getByRole('button', { name: /Generate Plan/i }));
}

describe('Plan create quality gate recovery (Dejan)', () => {
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
  });

  it('renders the athlete-language display_message as the primary error', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeQualityGateError());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(
        screen.getByText(
          /Your peak weekly volume is higher than your training history supports/i,
        ),
      ).toBeInTheDocument();
    });
    // The technical reason exists only inside the collapsed <details> element.
    const details = document.querySelector('details');
    expect(details).not.toBeNull();
    expect(details?.textContent).toContain('Week 1 exceeds trusted band ceiling');
    // The technical reason is NOT inside the primary banner message paragraph.
    const primary = screen.getByText(
      /Your peak weekly volume is higher than your training history supports/i,
    );
    expect(primary.textContent).not.toContain('Week 1 exceeds trusted band ceiling');
  });

  it('renders safe range in km for metric athletes (Dejan case)', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeQualityGateError());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      // 18-24 mi → 29-39 km/week
      expect(screen.getByText(/29-39 km\/week/i)).toBeInTheDocument();
    });
    // CTA shows the recommended peak in km (21 mi → 34 km).
    expect(screen.getByRole('button', { name: /Use safe range \(34 km\/week\)/i })).toBeInTheDocument();
  });

  it('renders safe range in miles for imperial athletes', async () => {
    setUnits('imperial');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeQualityGateError());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByText(/18-24 mi\/week/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Use safe range \(21 mi\/week\)/i })).toBeInTheDocument();
  });

  it('clicking Use safe range re-submits the constraint-aware plan with the recommended peak', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeQualityGateError());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Use safe range/i })).toBeInTheDocument();
    });

    // Reset the mock so we can verify the second call
    createConstraintAware.mockReset();
    createConstraintAware.mockRejectedValue(makeQualityGateError());

    fireEvent.click(screen.getByRole('button', { name: /Use safe range/i }));

    await waitFor(() => {
      expect(createConstraintAware).toHaveBeenCalledTimes(1);
    });
    const lastCall = createConstraintAware.mock.calls.at(-1)?.[0] as { target_peak_weekly_miles?: number };
    expect(lastCall?.target_peak_weekly_miles).toBe(21.0);
  });

  it('exposes technical reasons under a collapsed details disclosure', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockRejectedValue(makeQualityGateError());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByText(/Show technical details/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Show technical details/i));
    expect(screen.getByText(/Week 1 exceeds trusted band ceiling/i)).toBeInTheDocument();
  });
});
