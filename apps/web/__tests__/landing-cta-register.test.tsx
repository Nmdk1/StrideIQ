import React from 'react';
import { render, screen } from '@testing-library/react';

import Pricing from '@/app/components/Pricing';

// Pricing uses useAuth to choose between Settings deep-link (authed) and /register (unauthed).
// Render as unauthenticated visitor — all paid CTAs must point to /register.
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: false }),
}));

describe('Landing conversion CTA', () => {
  it('renders updated pricing CTAs for unauthenticated visitors', () => {
    render(<Pricing />);

    // Free trial CTA
    const freeLink = screen.getAllByRole('link', { name: 'Start 30-Day Free Trial' })[0];
    expect(freeLink).toHaveAttribute('href', '/register');

    // StrideIQ paid tier
    const premiumLink = screen.getAllByRole('link', { name: 'Start 30-Day Free Trial' })[1];
    expect(premiumLink).toHaveAttribute('href', '/register?tier=subscriber&period=annual');
  });

  it('shows annual prices by default', () => {
    render(<Pricing />);

    // Annual is the default for the single paid tier.
    expect(screen.getAllByText('$199/yr').length).toBeGreaterThan(0);

    // Monthly paid price should not appear by default.
    expect(screen.queryByText('$24.99/mo')).not.toBeInTheDocument();
  });

  it('shows the Full Access badge on the paid tier', () => {
    render(<Pricing />);

    expect(screen.getByText('Full Access')).toBeInTheDocument();
  });
});
