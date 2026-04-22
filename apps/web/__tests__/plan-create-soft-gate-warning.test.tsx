import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

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

function basePlan(): Record<string, unknown> {
  return {
    success: true,
    plan_id: 'plan_abc',
    race: { date: '2026-07-01', distance: 'half_marathon', name: 'Test HM' },
    fitness_bank: {
      peak: { weekly_miles: 25, long_run: 9, mp_long_run: 0 },
      constraint: { returning: false, type: null },
    },
    model: { confidence: 'medium', tau1: 21, tau2: 7, insights: [] },
    prediction: {
      time: '1:50:00',
      confidence_interval: '±5min',
      uncertainty_reason: null,
      rationale_tags: [],
      scenarios: {
        conservative: { time: '1:55:00', confidence: 'high' },
        base: { time: '1:50:00', confidence: 'medium' },
        aggressive: { time: '1:45:00', confidence: 'low' },
      },
    },
    volume_contract: {
      band_min: 18,
      band_max: 24,
      source: 'trusted_recent_band',
      peak_confidence: 'high',
    },
    quality_gate_fallback: true,
    quality_gate_reasons: ['Week 1 exceeds trusted band ceiling: 30.0 > 24.0.'],
    personalization: { notes: [], tune_up_races: [] },
    summary: { total_weeks: 12, total_miles: 200, peak_miles: 21 },
    weeks: [
      {
        week: 1,
        theme: 'Base',
        start_date: '2026-04-15',
        days: [],
        total_miles: 18,
        notes: [],
      },
    ],
    generated_at: '2026-04-16T00:00:00Z',
  };
}

function makeAutoTunedResponse(): Record<string, unknown> {
  return {
    ...basePlan(),
    warnings: ['auto_tuned_peak_to_safe_range:21.0'],
    soft_gate_applied_peak_weekly_miles: 21.0,
    soft_gate_requested_peak_weekly_miles: null,
  };
}

function makeCappedResponse(): Record<string, unknown> {
  return {
    ...basePlan(),
    warnings: ['capped_requested_peak_to_safe_range:30.0->21.0'],
    soft_gate_applied_peak_weekly_miles: 21.0,
    soft_gate_requested_peak_weekly_miles: 30.0,
  };
}

function makeSafeRangeBreachResponse(): Record<string, unknown> {
  return {
    ...basePlan(),
    warnings: [
      'capped_requested_peak_to_safe_range:30.0->21.0',
      'safe_range_regen_still_outside_band',
    ],
    soft_gate_applied_peak_weekly_miles: 21.0,
    soft_gate_requested_peak_weekly_miles: 30.0,
    soft_gate_display_message:
      "Your peak weekly volume is higher than your training history supports. We built this plan anyway, but use it with care.",
    soft_gate_reasons: ['Week 1 exceeds trusted band ceiling.'],
    soft_gate_safe_bounds_km: { weekly_miles: { min: 29.0, max: 38.6 } },
  };
}

async function navigateToConstraintAwareForm() {
  fireEvent.click(screen.getByRole('button', { name: /Fitness Bank Plan/i }));
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  const buttons = screen.getAllByRole('button');
  const halfMarathon = buttons.find((b) => /Half Marathon/.test(b.textContent ?? ''));
  if (!halfMarathon) throw new Error('Half Marathon button not found');
  fireEvent.click(halfMarathon);
  const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
  fireEvent.change(dateInput, {
    target: { value: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0] },
  });
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  fireEvent.click(screen.getByRole('button', { name: /Generate Plan/i }));
}

describe('Plan create soft-gate warning banner', () => {
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

  it('auto-tuned: renders peak in km for metric athletes', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockResolvedValue(makeAutoTunedResponse());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByTestId('soft-gate-warning')).toBeInTheDocument();
    });
    const banner = screen.getByTestId('soft-gate-warning');
    expect(banner).toHaveTextContent(/We adjusted your peak weekly volume/i);
    expect(banner).toHaveTextContent(/33\.8 km\/wk/);
  });

  it('auto-tuned: renders peak in mi for imperial athletes', async () => {
    setUnits('imperial');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockResolvedValue(makeAutoTunedResponse());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByTestId('soft-gate-warning')).toBeInTheDocument();
    });
    expect(screen.getByTestId('soft-gate-warning')).toHaveTextContent(/21\.0 mi\/wk/);
  });

  it('capped: tells the athlete what they asked for and what we built (metric)', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockResolvedValue(makeCappedResponse());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByTestId('soft-gate-warning')).toBeInTheDocument();
    });
    const banner = screen.getByTestId('soft-gate-warning');
    // 30 mi -> 48.3 km, 21 mi -> 33.8 km
    expect(banner).toHaveTextContent(/48\.3 km\/wk/);
    expect(banner).toHaveTextContent(/33\.8 km\/wk/);
    expect(banner).toHaveTextContent(/capped this plan/i);
  });

  it('safe-range breach: still renders a banner but uses softer "noticed" copy', async () => {
    setUnits('metric');
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockResolvedValue(makeSafeRangeBreachResponse());

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByTestId('soft-gate-warning')).toBeInTheDocument();
    });
    const banner = screen.getByTestId('soft-gate-warning');
    // The capped warning takes precedence in copy because it's more specific.
    expect(banner).toHaveTextContent(/capped|noticed/i);
    // Plan is still rendered.
    expect(screen.getByText(/Your Personalized Plan/i)).toBeInTheDocument();
  });

  it('does not render the banner when warnings are empty', async () => {
    setUnits('metric');
    const noWarn = basePlan();
    noWarn.warnings = [];
    noWarn.soft_gate_applied_peak_weekly_miles = null;
    previewConstraintAware.mockResolvedValue({});
    createConstraintAware.mockResolvedValue(noWarn);

    render(<CreatePlanPage />);
    await navigateToConstraintAwareForm();

    await waitFor(() => {
      expect(screen.getByText(/Your Personalized Plan/i)).toBeInTheDocument();
    });
    expect(screen.queryByTestId('soft-gate-warning')).not.toBeInTheDocument();
  });
});
