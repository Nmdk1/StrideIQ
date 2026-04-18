import React from 'react';
import { render, screen } from '@testing-library/react';

let mockStatus: { connected: boolean; previously_connected?: boolean } | undefined = undefined;

jest.mock('next/navigation', () => ({
  usePathname: () => '/home',
}));

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, token: 'tok' }),
}));

jest.mock('@/lib/hooks/queries/strava', () => ({
  useStravaStatus: () => ({ data: mockStatus }),
}));

jest.mock('@/lib/api/services/strava', () => ({
  stravaService: {
    getAuthUrl: jest.fn(),
  },
}));

import StravaBanner from '@/app/components/StravaBanner';

describe('StravaBanner suppression', () => {
  it('hides for athletes who never connected Strava (Garmin-only users)', () => {
    mockStatus = { connected: false, previously_connected: false };
    const { container } = render(<StravaBanner />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/Strava disconnected/i)).toBeNull();
  });

  it('hides when previously_connected flag is missing (legacy/safe default)', () => {
    mockStatus = { connected: false };
    const { container } = render(<StravaBanner />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/Strava disconnected/i)).toBeNull();
  });

  it('shows for athletes who lost their Strava connection', () => {
    mockStatus = { connected: false, previously_connected: true };
    render(<StravaBanner />);
    expect(screen.getByText(/Strava disconnected/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reconnect Now/i })).toBeInTheDocument();
  });

  it('hides while Strava is connected', () => {
    mockStatus = { connected: true, previously_connected: true };
    const { container } = render(<StravaBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('hides while status is still loading (undefined)', () => {
    mockStatus = undefined;
    const { container } = render(<StravaBanner />);
    expect(container).toBeEmptyDOMElement();
  });
});
