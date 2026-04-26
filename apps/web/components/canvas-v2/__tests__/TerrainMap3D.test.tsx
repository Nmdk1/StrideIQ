/**
 * @jest-environment jsdom
 *
 * TerrainMap3D — minimal coverage: the no-token guidance card.
 *
 * The Mapbox mount path is not unit-tested; mapbox-gl requires a real WebGL
 * context and is verified manually on the deployed sandbox route.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { TerrainMap3D } from '../TerrainMap3D';
import { ScrubProvider } from '../hooks/useScrubState';
import type { TrackPoint, TrackBounds } from '../hooks/useResampledTrack';

const fakeTrack: TrackPoint[] = [
  {
    index: 0,
    t: 0,
    distanceM: 0,
    timeS: 0,
    lat: 32.3,
    lng: -88.7,
    altitude: 100,
    hr: 130,
    pace: 300,
    grade: 0,
    cadence: 180,
  },
  {
    index: 1,
    t: 1,
    distanceM: 100,
    timeS: 60,
    lat: 32.301,
    lng: -88.701,
    altitude: 110,
    hr: 140,
    pace: 290,
    grade: 1,
    cadence: 180,
  },
];

const fakeBounds: TrackBounds = {
  minLat: 32.3,
  maxLat: 32.301,
  minLng: -88.701,
  maxLng: -88.7,
  minAltitude: 100,
  maxAltitude: 110,
  altitudeReliefM: 10,
};

describe('TerrainMap3D — no token', () => {
  const originalToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  });

  afterAll(() => {
    if (originalToken !== undefined) process.env.NEXT_PUBLIC_MAPBOX_TOKEN = originalToken;
  });

  it('renders the token-required guidance card when no token is set', () => {
    render(
      <ScrubProvider>
        <TerrainMap3D track={fakeTrack} bounds={fakeBounds} />
      </ScrubProvider>,
    );
    expect(screen.getByText(/Mapbox token required/i)).toBeInTheDocument();
    expect(screen.getByText(/NEXT_PUBLIC_MAPBOX_TOKEN/)).toBeInTheDocument();
  });

  it('does not attempt to mount the Mapbox container when no token is set', () => {
    const { container } = render(
      <ScrubProvider>
        <TerrainMap3D track={fakeTrack} bounds={fakeBounds} />
      </ScrubProvider>,
    );
    // Mapbox would mount into a <div ref={containerRef}> — the no-token
    // branch returns the guidance card instead, so no such div should
    // exist with mapbox-related dimensions.
    expect(container.querySelector('.mapboxgl-map')).toBeNull();
  });
});
