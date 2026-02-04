import React from 'react';
import { render, screen } from '@testing-library/react';

import Pricing from '@/app/components/Pricing';

describe('Landing conversion CTA', () => {
  it('links Get Started / Start Elite to /register', () => {
    render(<Pricing />);

    const getStarted = screen.getByRole('link', { name: 'Get Started' });
    expect(getStarted).toHaveAttribute('href', '/register');

    const startElite = screen.getByRole('link', { name: 'Start Elite' });
    expect(startElite).toHaveAttribute('href', '/register');

    // Paid surface is visible on the landing page (monthly price).
    expect(screen.getByText('$14.99/month')).toBeInTheDocument();
  });
});

