/**
 * @jest-environment jsdom
 *
 * MomentReadout — verifies the Distance card shows distance + elapsed time
 * with two decimals on imperial units, and that all five cards render.
 */

import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { MomentReadout } from '../MomentReadout';
import { ScrubProvider, useScrubState } from '../hooks/useScrubState';
import type { TrackPoint } from '../hooks/useResampledTrack';

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial',
    formatDistance: (m: number | null | undefined, decimals = 1) => {
      if (m === null || m === undefined) return '-';
      const miles = (m / 1000) * 0.621371;
      return `${miles.toFixed(decimals)} mi`;
    },
  }),
}));

const track: TrackPoint[] = [
  {
    index: 0,
    t: 0,
    distanceM: 0,
    timeS: 0,
    lat: 0, lng: 0, altitude: 0,
    hr: 130, pace: 300, grade: 0, cadence: 180,
  },
  {
    index: 1,
    t: 0.5,
    // 2.41 mi == 3878 m
    distanceM: 3878,
    timeS: 23 * 60 + 14, // 23:14
    lat: 0, lng: 0, altitude: 0,
    hr: 155, pace: 270, grade: 2, cadence: 184,
  },
  {
    index: 2,
    t: 1,
    distanceM: 7400,
    timeS: 60 * 60 + 5 * 60 + 9, // 1:05:09
    lat: 0, lng: 0, altitude: 0,
    hr: 160, pace: 260, grade: 0, cadence: 186,
  },
];

function ScrubTo({ pos }: { pos: number | null }) {
  const { setPosition } = useScrubState();
  React.useEffect(() => {
    setPosition(pos);
  }, [pos, setPosition]);
  return null;
}

describe('MomentReadout', () => {
  it('renders all five labels including Distance', () => {
    render(
      <ScrubProvider>
        <MomentReadout track={track} />
      </ScrubProvider>,
    );
    expect(screen.getByText('Distance')).toBeInTheDocument();
    expect(screen.getByText('Pace')).toBeInTheDocument();
    expect(screen.getByText('Grade')).toBeInTheDocument();
    expect(screen.getByText('HR')).toBeInTheDocument();
    expect(screen.getByText('Cadence')).toBeInTheDocument();
  });

  it('shows distance with two decimals and MM:SS elapsed time at scrub position', () => {
    render(
      <ScrubProvider>
        <ScrubTo pos={0.5} />
        <MomentReadout track={track} />
      </ScrubProvider>,
    );
    expect(screen.getByText(/^2\.\d{2} mi$/)).toBeInTheDocument();
    expect(screen.getByText('23:14')).toBeInTheDocument();
  });

  it('shows H:MM:SS elapsed time when run exceeds an hour', () => {
    render(
      <ScrubProvider>
        <ScrubTo pos={1} />
        <MomentReadout track={track} />
      </ScrubProvider>,
    );
    expect(screen.getByText('1:05:09')).toBeInTheDocument();
  });

  it('renders em-dash placeholders when no scrub position is set', () => {
    const { container } = render(
      <ScrubProvider>
        <MomentReadout track={track} />
      </ScrubProvider>,
    );
    // All five values default to '—' before any hover.
    const dashCount = (container.textContent ?? '').split('—').length - 1;
    expect(dashCount).toBeGreaterThanOrEqual(5);
  });
});
