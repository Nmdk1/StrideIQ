/**
 * @jest-environment jsdom
 *
 * CanvasHelpHint — verifies the once-per-browser hint contract:
 *   1. shows on first visit (localStorage flag absent)
 *   2. dismisses on first interaction and sets the flag
 *   3. stays hidden on subsequent visits
 *   4. re-shows when the persistent help button asks via `force`
 */

import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { CanvasHelpHint } from '../help/CanvasHelpHint';

describe('CanvasHelpHint', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('shows on first visit when the seen flag is absent', async () => {
    render(<CanvasHelpHint />);
    expect(await screen.findByText(/Quick tour/i)).toBeInTheDocument();
    expect(screen.getByText(/Hover any chart/i)).toBeInTheDocument();
    expect(screen.getByText(/Right-click drag the map/i)).toBeInTheDocument();
  });

  it('dismisses on first user interaction and persists the seen flag', async () => {
    jest.useFakeTimers();
    render(<CanvasHelpHint />);
    expect(await screen.findByText(/Quick tour/i)).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove'));
    });
    // Fade-out timer is 250ms, then the node unmounts.
    act(() => {
      jest.advanceTimersByTime(300);
    });
    expect(screen.queryByText(/Quick tour/i)).not.toBeInTheDocument();
    expect(window.localStorage.getItem('canvasV2:hintsSeen')).toBe('1');
    jest.useRealTimers();
  });

  it('stays hidden when the seen flag is already set', () => {
    window.localStorage.setItem('canvasV2:hintsSeen', '1');
    render(<CanvasHelpHint />);
    expect(screen.queryByText(/Quick tour/i)).not.toBeInTheDocument();
  });

  it('re-shows when force is true even if the seen flag is set', async () => {
    window.localStorage.setItem('canvasV2:hintsSeen', '1');
    render(<CanvasHelpHint force />);
    expect(await screen.findByText(/Quick tour/i)).toBeInTheDocument();
  });

  it('auto-dismisses after the timeout fires with no interaction', async () => {
    jest.useFakeTimers();
    render(<CanvasHelpHint />);
    expect(await screen.findByText(/Quick tour/i)).toBeInTheDocument();
    act(() => {
      jest.advanceTimersByTime(8000 + 300);
    });
    expect(screen.queryByText(/Quick tour/i)).not.toBeInTheDocument();
    expect(window.localStorage.getItem('canvasV2:hintsSeen')).toBe('1');
    jest.useRealTimers();
  });

  it('explicit ✕ button dismisses immediately', async () => {
    jest.useFakeTimers();
    render(<CanvasHelpHint />);
    expect(await screen.findByText(/Quick tour/i)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Dismiss tour/i));
    act(() => {
      jest.advanceTimersByTime(250);
    });
    expect(screen.queryByText(/Quick tour/i)).not.toBeInTheDocument();
    jest.useRealTimers();
  });
});
