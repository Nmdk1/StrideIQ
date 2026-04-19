/**
 * ShareDrawer tests pin down the founder-mandated invariants for the
 * Phase 4 share surface:
 *
 *   • The drawer is closed by default — no auto-open, no global popup.
 *   • Closing affordances exist (X button, backdrop click, Escape key);
 *     none of them are required for the drawer to *appear*, only to
 *     dismiss it once the athlete opens it.
 *   • The runtoon is rendered *inside* the drawer, not on the page
 *     bottom — that is the whole point of Phase 4.
 *
 * RuntoonCard itself is mocked here because its full render path
 * (auth, photo query, runtoon polling) is exercised in its own suite
 * and would only add flake to a layout test.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ShareDrawer } from '../ShareDrawer';

jest.mock('@/components/activities/RuntoonCard', () => ({
  RuntoonCard: ({ activityId }: { activityId: string }) => (
    <div data-testid="runtoon-card-stub">runtoon for {activityId}</div>
  ),
}));

describe('ShareDrawer', () => {
  test('renders nothing when closed (no global popup behaviour)', () => {
    const { container } = render(
      <ShareDrawer activityId="act-1" open={false} onClose={jest.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('renders dialog with runtoon inside when open', () => {
    render(<ShareDrawer activityId="act-1" open onClose={jest.fn()} />);
    expect(screen.getByRole('dialog', { name: /share this run/i })).toBeInTheDocument();
    expect(screen.getByTestId('runtoon-card-stub')).toHaveTextContent('runtoon for act-1');
  });

  test('close button fires onClose', () => {
    const onClose = jest.fn();
    render(<ShareDrawer activityId="act-1" open onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /close share drawer/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('Escape key fires onClose', () => {
    const onClose = jest.fn();
    render(<ShareDrawer activityId="act-1" open onClose={onClose} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('backdrop click fires onClose; inner click does not', () => {
    const onClose = jest.fn();
    render(<ShareDrawer activityId="act-1" open onClose={onClose} />);
    const dialog = screen.getByRole('dialog');
    // The backdrop is the dialog wrapper itself.
    fireEvent.click(dialog);
    expect(onClose).toHaveBeenCalledTimes(1);

    // Clicking the runtoon stub (inside the inner panel) must not close.
    fireEvent.click(screen.getByTestId('runtoon-card-stub'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('shows roadmap placeholder so the drawer is not a one-trick room', () => {
    render(<ShareDrawer activityId="act-1" open onClose={jest.fn()} />);
    expect(
      screen.getByText(/more share styles are on the way/i),
    ).toBeInTheDocument();
  });
});
