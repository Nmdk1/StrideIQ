import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import { ImpersonationBanner } from '@/components/admin/ImpersonationBanner';

describe('ImpersonationBanner', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders when impersonation_active is true and clears on stop', async () => {
    localStorage.setItem('impersonation_active', 'true');
    localStorage.setItem('impersonation_token', 'tok');
    localStorage.setItem('impersonation_original_auth_token', 'orig');
    localStorage.setItem('impersonated_user', JSON.stringify({ id: 'u1', email: 'user@example.com' }));
    localStorage.setItem('auth_token', 'tok');

    render(<ImpersonationBanner />);

    expect(await screen.findByText(/Impersonation active/i)).toBeInTheDocument();
    expect(screen.getByText(/user@example\.com/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/Stop impersonating/i));

    expect(localStorage.getItem('auth_token')).toBe('orig');
    expect(localStorage.getItem('impersonation_active')).toBeNull();
    expect(localStorage.getItem('impersonation_token')).toBeNull();

  });
});

