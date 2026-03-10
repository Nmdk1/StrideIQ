import React from 'react';
import { render, screen } from '@testing-library/react';

import Pricing from '@/app/components/Pricing';

// Pricing uses useAuth to choose between Settings deep-link (authed) and /register (unauthed).
// Render as unauthenticated visitor — all paid CTAs must point to /register.
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: false }),
}));

describe('Landing conversion CTA', () => {
  it('renders all 4 tiers with correct CTA links for unauthenticated visitors', () => {
    render(<Pricing />);

    // Free tier
    const freeLink = screen.getByRole('link', { name: 'Get started free' });
    expect(freeLink).toHaveAttribute('href', '/register');

    // One-time plan unlock ($5)
    const planLink = screen.getByRole('link', { name: 'Get a plan — $5' });
    expect(planLink).toHaveAttribute('href', '/register');

    // Guided tier — default period is annual
    const guidedLink = screen.getByRole('link', { name: /Start Guided/i });
    expect(guidedLink).toHaveAttribute('href', '/register?tier=guided&period=annual');

    // Premium tier
    const premiumLink = screen.getByRole('link', { name: /Start Premium/i });
    expect(premiumLink).toHaveAttribute('href', '/register?tier=premium&period=annual');
  });

  it('shows annual prices by default', () => {
    render(<Pricing />);

    // Annual is the default: $150/yr for Guided, $250/yr for Premium.
    // These appear in the price display row (not the CTA button).
    expect(screen.getAllByText('$150/yr').length).toBeGreaterThan(0);
    expect(screen.getAllByText('$250/yr').length).toBeGreaterThan(0);

    // Monthly prices must NOT appear in the default view.
    expect(screen.queryByText('$15/mo')).not.toBeInTheDocument();
    expect(screen.queryByText('$25/mo')).not.toBeInTheDocument();
  });

  it('shows the Most Popular badge on the Guided tier', () => {
    render(<Pricing />);

    expect(screen.getByText('Most Popular')).toBeInTheDocument();
  });
});
