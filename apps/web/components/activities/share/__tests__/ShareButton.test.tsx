/**
 * ShareButton is intentionally tiny: a chrome pill that fires its
 * onClick.  These tests guard the contract the page relies on (a real
 * <button>, accessible name, click delivery).
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ShareButton } from '../ShareButton';

describe('ShareButton', () => {
  test('renders an accessible Share button', () => {
    render(<ShareButton onClick={jest.fn()} />);
    const btn = screen.getByRole('button', { name: /share this run/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent(/share/i);
  });

  test('fires onClick when pressed', () => {
    const onClick = jest.fn();
    render(<ShareButton onClick={onClick} />);
    fireEvent.click(screen.getByRole('button', { name: /share this run/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
