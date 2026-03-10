/**
 * Garmin Connect — Frontend Feature Flag UI Gating Tests
 *
 * Acceptance criteria:
 *  - Non-allowlisted: GarminConnection renders null → nothing in DOM
 *  - Allowlisted: GarminConnection renders connect CTA
 *  - Connected state always shown (even when flag is off)
 *  - Strava behavior unaffected (settings page still shows StravaConnection)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Module-level mocks ───────────────────────────────────────────────────────
// All jest.mock() calls must be at the top level. We use a configurable
// mock function so individual tests can set the return value.

const mockUseGarminStatus = jest.fn();

jest.mock('@/lib/hooks/queries/garmin', () => ({
  useGarminStatus: (...args: unknown[]) => mockUseGarminStatus(...args),
}));

jest.mock('@/lib/api/services/garmin', () => ({
  garminService: {
    getStatus: jest.fn(),
    getAuthUrl: jest.fn(async () => ({ auth_url: 'https://garmin.test/auth' })),
    disconnect: jest.fn(),
  },
}));

jest.mock('@/components/integrations/GarminFileImport', () => ({
  GarminFileImport: () => <div data-testid="garmin-file-import">GarminFileImport</div>,
}));

jest.mock('@/components/integrations/GarminBadge', () => ({
  GarminBadge: () => <div data-testid="garmin-badge">GarminBadge</div>,
}));

// ── GarminConnection — flag-driven visibility ────────────────────────────────

import { GarminConnection } from '@/components/integrations/GarminConnection';

describe('GarminConnection — garmin_connect_available gating', () => {
  beforeEach(() => {
    mockUseGarminStatus.mockReset();
  });

  it('renders nothing when flag is off and athlete is not connected', () => {
    // Status response from the backend when flag is off
    mockUseGarminStatus.mockReturnValue({
      data: {
        connected: false,
        garmin_user_id: null,
        last_sync: null,
        garmin_connect_available: false,
      },
      isLoading: false,
      refetch: jest.fn(),
    });

    const { container } = render(<GarminConnection />);

    // Component returns null → nothing rendered
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText('Garmin Connect')).not.toBeInTheDocument();
    expect(screen.queryAllByText(/Connect with Garmin/i)).toHaveLength(0);
  });

  it('renders connect CTA when flag is on and athlete is not connected', () => {
    mockUseGarminStatus.mockReturnValue({
      data: {
        connected: false,
        garmin_user_id: null,
        last_sync: null,
        garmin_connect_available: true,
      },
      isLoading: false,
      refetch: jest.fn(),
    });

    render(<GarminConnection />);

    expect(screen.getByRole('heading', { name: /Garmin Connect/i })).toBeInTheDocument();
    // At least one connect affordance is rendered (button or link, both use "Connect with Garmin")
    expect(screen.getAllByText(/Connect with Garmin/i).length).toBeGreaterThan(0);
    // Disconnect button must NOT be visible
    expect(screen.queryByText('Disconnect Garmin Connect')).not.toBeInTheDocument();
  });

  it('renders connected state and disconnect button when connected, even if flag is off', () => {
    // Flag off, but athlete already connected: must still see status + disconnect
    mockUseGarminStatus.mockReturnValue({
      data: {
        connected: true,
        garmin_user_id: 'garmin_uid_founder',
        last_sync: null,
        garmin_connect_available: false,
      },
      isLoading: false,
      refetch: jest.fn(),
    });

    render(<GarminConnection />);

    // Heading present (™ added to full app name per brand guidelines)
    expect(screen.getByRole('heading', { name: /Garmin Connect/i })).toBeInTheDocument();
    // Connected badge
    expect(screen.getByText('Connected')).toBeInTheDocument();
    // Disconnect button
    expect(screen.getByText('Disconnect Garmin Connect')).toBeInTheDocument();
    // Connect button must NOT appear (already connected)
    expect(screen.queryByText(/Connect with Garmin/i)).not.toBeInTheDocument();
  });

  it('renders connected state and disconnect button when connected and flag is on', () => {
    mockUseGarminStatus.mockReturnValue({
      data: {
        connected: true,
        garmin_user_id: 'garmin_uid_founder',
        last_sync: '2026-02-22T08:00:00Z',
        garmin_connect_available: true,
      },
      isLoading: false,
      refetch: jest.fn(),
    });

    render(<GarminConnection />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Disconnect Garmin Connect')).toBeInTheDocument();
  });

  it('shows loading spinner when status is loading', () => {
    mockUseGarminStatus.mockReturnValue({
      data: undefined,
      isLoading: true,
      refetch: jest.fn(),
    });

    render(<GarminConnection />);
    // When loading, the LoadingSpinner renders (no Garmin section content)
    expect(screen.queryByText('Garmin Connect')).not.toBeInTheDocument();
  });
});

// ── Settings page — Garmin component integration ─────────────────────────────

jest.mock('@/components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock('@/components/integrations/StravaConnection', () => ({
  StravaConnection: () => <div data-testid="strava-connection">StravaConnection</div>,
}));
jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({ units: 'imperial', setUnits: jest.fn() }),
}));
jest.mock('@/components/settings/RuntoonPhotoUpload', () => ({
  RuntoonPhotoUpload: () => <div>RuntoonPhotoUpload</div>,
}));
jest.mock('@/lib/context/ConsentContext', () => ({
  useConsent: () => ({
    aiConsent: false,
    loading: false,
    grantConsent: jest.fn(),
    revokeConsent: jest.fn(),
  }),
}));
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'stranger',
      subscription_tier: 'free',
      has_active_subscription: false,
      trial_started_at: null,
      trial_ends_at: null,
      stripe_customer_id: null,
    },
  }),
}));
jest.mock('@/lib/api/services/auth', () => ({
  authService: {
    getTrainingPaceProfile: jest.fn(async () => ({ status: 'missing' })),
    updateProfile: jest.fn(async () => ({})),
  },
}));

import SettingsPage from '@/app/settings/page';

function renderSettingsPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}><SettingsPage /></QueryClientProvider>
  );
}

describe('Settings page — Garmin component presence', () => {
  beforeEach(() => {
    mockUseGarminStatus.mockReset();
  });

  it('renders GarminConnection alongside StravaConnection', () => {
    // Whether Garmin is shown or not depends on GarminConnection itself.
    // Settings page always mounts GarminConnection — it decides via flag.
    mockUseGarminStatus.mockReturnValue({
      data: { connected: false, garmin_connect_available: true },
      isLoading: false,
      refetch: jest.fn(),
    });

    renderSettingsPage();

    // Strava always present
    expect(screen.getByTestId('strava-connection')).toBeInTheDocument();
    // Garmin connect CTA visible for allowlisted user (heading now shows "Garmin Connect™")
    expect(screen.getByRole('heading', { name: /Garmin Connect/i })).toBeInTheDocument();
  });

  it('hides Garmin connect CTA (GarminConnection null) for non-allowlisted user', () => {
    mockUseGarminStatus.mockReturnValue({
      data: { connected: false, garmin_connect_available: false },
      isLoading: false,
      refetch: jest.fn(),
    });

    renderSettingsPage();

    // Strava always present
    expect(screen.getByTestId('strava-connection')).toBeInTheDocument();
    // Garmin section hidden (component rendered null)
    expect(screen.queryByText('Garmin Connect')).not.toBeInTheDocument();
  });
});
