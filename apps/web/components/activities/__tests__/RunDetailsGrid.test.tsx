/**
 * RunDetailsGrid renders FIT-derived activity-level metrics. The
 * critical contract is *self-suppression*: cards for null metrics
 * are not rendered, and when no metric is populated the entire grid
 * disappears (so older Strava-only activities and watch-only setups
 * see nothing here, keeping the page clean).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { RunDetailsGrid } from '../RunDetailsGrid';

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({ units: 'imperial' }),
}));

describe('RunDetailsGrid', () => {
  test('renders nothing when every metric is null and showMissingNote is not set', () => {
    const { container } = render(<RunDetailsGrid />);
    expect(container).toBeEmptyDOMElement();
  });

  test('renders the honest missing-data line when showMissingNote=true and all metrics are null', () => {
    render(<RunDetailsGrid showMissingNote />);
    expect(
      screen.getByText(/Power, stride, and form metrics weren['’]t captured for this run/i),
    ).toBeInTheDocument();
  });

  test('does NOT render the missing-data line when at least one metric is present', () => {
    render(<RunDetailsGrid showMissingNote avgPowerW={245} />);
    expect(screen.getByText('245 W')).toBeInTheDocument();
    expect(
      screen.queryByText(/weren['’]t captured/i),
    ).not.toBeInTheDocument();
  });

  test('renders only the cards whose metrics are populated', () => {
    render(
      <RunDetailsGrid
        avgPowerW={245}
        maxPowerW={310}
        avgStrideLengthM={1.18}
      />,
    );
    expect(screen.getByText('245 W')).toBeInTheDocument();
    expect(screen.getByText('peak 310 W')).toBeInTheDocument();
    expect(screen.getByText('1.18 m')).toBeInTheDocument();
    // Other cards must not show.
    expect(screen.queryByText(/Ground Contact/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Vert/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Descent/i)).not.toBeInTheDocument();
  });

  test('shows ground-contact balance hint when present', () => {
    render(
      <RunDetailsGrid
        avgGroundContactMs={228}
        avgGroundContactBalancePct={50.4}
      />,
    );
    expect(screen.getByText('228 ms')).toBeInTheDocument();
    expect(screen.getByText('L/R 50.4%')).toBeInTheDocument();
  });

  test('formats descent in feet when imperial', () => {
    render(<RunDetailsGrid totalDescentM={150} />);
    // 150 m * 3.28084 ≈ 492 ft
    expect(screen.getByText('492 ft')).toBeInTheDocument();
  });
});
