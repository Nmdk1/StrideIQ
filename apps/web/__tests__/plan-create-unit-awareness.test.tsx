import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

const useUnitsMock = jest.fn();
jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => useUnitsMock(),
}));

function setUnits(units: 'metric' | 'imperial') {
  useUnitsMock.mockReturnValue({
    units,
    setUnits: jest.fn(),
    formatPace: jest.fn(),
    formatDistance: jest.fn(),
    formatSpeed: jest.fn(),
  });
}

function navigateToTemplateDistanceStep() {
  fireEvent.click(screen.getByRole('button', { name: /Template Plan/i }));
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
}

function navigateToTemplateFitnessStep() {
  navigateToTemplateDistanceStep();
  // Click the 5K race-distance card.
  const distanceButtons = screen.getAllByRole('button');
  const fiveK = distanceButtons.find((b) => /5K/.test(b.textContent ?? ''));
  if (!fiveK) throw new Error('5K button not found');
  fireEvent.click(fiveK);
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
  const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
  fireEvent.change(dateInput, {
    target: { value: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0] },
  });
  fireEvent.click(screen.getByRole('button', { name: /^Next$/i }));
}

describe('Plan create form unit awareness (Dejan)', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    useUnitsMock.mockReset();
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

  it('shows imperial subtitles on Race Distance buttons for imperial athletes', () => {
    setUnits('imperial');
    render(<CreatePlanPage />);
    navigateToTemplateDistanceStep();

    expect(screen.getByText('26.2 miles')).toBeInTheDocument();
    expect(screen.getByText('13.1 miles')).toBeInTheDocument();
    expect(screen.getByText('6.2 miles')).toBeInTheDocument();
    expect(screen.getByText('3.1 miles')).toBeInTheDocument();
  });

  it('shows metric subtitles on Race Distance buttons for metric athletes (Dejan case)', () => {
    setUnits('metric');
    render(<CreatePlanPage />);
    navigateToTemplateDistanceStep();

    expect(screen.getByText('42.2 km')).toBeInTheDocument();
    expect(screen.getByText('21.1 km')).toBeInTheDocument();
    expect(screen.getByText('10 km')).toBeInTheDocument();
    expect(screen.getByText('5 km')).toBeInTheDocument();
    expect(screen.queryByText('26.2 miles')).not.toBeInTheDocument();
    expect(screen.queryByText('13.1 miles')).not.toBeInTheDocument();
  });

  it('renders the current weekly volume slider in km for metric athletes', () => {
    setUnits('metric');
    render(<CreatePlanPage />);
    navigateToTemplateFitnessStep();

    expect(screen.getByText(/Current Weekly Volume/i)).toBeInTheDocument();
    // Default 30 mi → 48 km
    expect(screen.getByText('48 km')).toBeInTheDocument();
    // Slider ticks present (values may be shared with long-run slider)
    expect(screen.getAllByText('16 km').length).toBeGreaterThan(0);
    expect(screen.getByText('80 km')).toBeInTheDocument();
    expect(screen.getByText('160 km')).toBeInTheDocument();
    // No imperial leakage on this step
    expect(screen.queryByText(/\bmiles\b/)).not.toBeInTheDocument();
  });

  it('renders the current weekly mileage slider in miles for imperial athletes', () => {
    setUnits('imperial');
    render(<CreatePlanPage />);
    navigateToTemplateFitnessStep();

    expect(screen.getByText(/Current Weekly Volume/i)).toBeInTheDocument();
    expect(screen.getByText('30 mi')).toBeInTheDocument();
    // Slider ticks may share values with the long-run slider, so use getAllByText.
    expect(screen.getAllByText('10 mi').length).toBeGreaterThan(0);
    expect(screen.getByText('50 mi')).toBeInTheDocument();
    expect(screen.getByText('100 mi')).toBeInTheDocument();
  });
});
