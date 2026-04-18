import {
  computeProjection,
  projectLatLng,
  projectTrack,
  sampleProjectedTrack,
} from '../projection';
import type { TrackBounds, TrackPoint } from '../../hooks/useResampledTrack';

const flatBounds: TrackBounds = {
  minLat: 32.0,
  maxLat: 32.1,
  minLng: -88.1,
  maxLng: -88.0,
  minAltitude: 100,
  maxAltitude: 150,
  altitudeReliefM: 50,
};

describe('computeProjection', () => {
  it('centers on the bounding box centroid', () => {
    const p = computeProjection(flatBounds);
    expect(p.centerLat).toBeCloseTo(32.05, 6);
    expect(p.centerLng).toBeCloseTo(-88.05, 6);
  });

  it('produces a positive metersPerUnit', () => {
    const p = computeProjection(flatBounds);
    expect(p.metersPerUnit).toBeGreaterThan(0);
  });

  it('clamps vertical exaggeration to [1, 12]', () => {
    const tinyRelief: TrackBounds = { ...flatBounds, minAltitude: 100, maxAltitude: 100.5, altitudeReliefM: 0.5 };
    const dramatic: TrackBounds = { ...flatBounds, minAltitude: 0, maxAltitude: 3000, altitudeReliefM: 3000 };
    const p1 = computeProjection(tinyRelief);
    const p2 = computeProjection(dramatic);
    expect(p1.verticalExaggeration).toBeGreaterThanOrEqual(1);
    expect(p1.verticalExaggeration).toBeLessThanOrEqual(12);
    expect(p2.verticalExaggeration).toBeGreaterThanOrEqual(1);
    expect(p2.verticalExaggeration).toBeLessThanOrEqual(12);
  });

  it('survives degenerate (single-point) bounds without NaN', () => {
    const point: TrackBounds = {
      minLat: 32,
      maxLat: 32,
      minLng: -88,
      maxLng: -88,
      minAltitude: 100,
      maxAltitude: 100,
      altitudeReliefM: 0,
    };
    const p = computeProjection(point);
    expect(Number.isFinite(p.metersPerUnit)).toBe(true);
    expect(Number.isFinite(p.verticalExaggeration)).toBe(true);
  });
});

describe('projectLatLng', () => {
  it('projects the center point to ~origin', () => {
    const p = computeProjection(flatBounds);
    const xyz = projectLatLng(p.centerLat, p.centerLng, p.altitudeBaseM, p);
    expect(Math.abs(xyz.x)).toBeLessThan(1e-9);
    expect(Math.abs(xyz.y)).toBeLessThan(1e-9);
    expect(Math.abs(xyz.z)).toBeLessThan(1e-9);
  });

  it('projects east of center to positive x', () => {
    const p = computeProjection(flatBounds);
    const xyz = projectLatLng(p.centerLat, p.centerLng + 0.01, p.altitudeBaseM, p);
    expect(xyz.x).toBeGreaterThan(0);
  });

  it('projects north of center to negative z (camera-friendly handedness)', () => {
    const p = computeProjection(flatBounds);
    const xyz = projectLatLng(p.centerLat + 0.01, p.centerLng, p.altitudeBaseM, p);
    expect(xyz.z).toBeLessThan(0);
  });

  it('projects higher altitude to higher y', () => {
    const p = computeProjection(flatBounds);
    const lo = projectLatLng(p.centerLat, p.centerLng, flatBounds.minAltitude, p);
    const hi = projectLatLng(p.centerLat, p.centerLng, flatBounds.maxAltitude, p);
    expect(hi.y).toBeGreaterThan(lo.y);
  });
});

describe('projectTrack', () => {
  it('returns one xyz per input point', () => {
    const p = computeProjection(flatBounds);
    const track: TrackPoint[] = Array(5).fill(null).map((_, i) => ({
      index: i,
      t: i / 4,
      distanceM: i * 100,
      timeS: i * 30,
      lat: 32.0 + i * 0.02,
      lng: -88.1 + i * 0.025,
      altitude: 100 + i * 10,
      hr: 140,
      pace: 300,
      grade: 1,
      cadence: 180,
    }));
    const projected = projectTrack(track, p);
    expect(projected).toHaveLength(5);
  });
});

describe('sampleProjectedTrack', () => {
  const projected = [
    { x: 0, y: 0, z: 0 },
    { x: 10, y: 5, z: 0 },
    { x: 20, y: 0, z: 0 },
  ];

  it('returns null on empty', () => {
    expect(sampleProjectedTrack([], 0.5)).toBeNull();
  });

  it('returns first at t=0, last at t=1', () => {
    expect(sampleProjectedTrack(projected, 0)).toEqual(projected[0]);
    expect(sampleProjectedTrack(projected, 1)).toEqual(projected[2]);
  });

  it('interpolates linearly between samples', () => {
    const mid = sampleProjectedTrack(projected, 0.5);
    expect(mid).not.toBeNull();
    expect(mid!.x).toBeCloseTo(10, 5);
    expect(mid!.y).toBeCloseTo(5, 5);
  });

  it('clamps t out of range', () => {
    expect(sampleProjectedTrack(projected, -0.5)).toEqual(projected[0]);
    expect(sampleProjectedTrack(projected, 1.5)).toEqual(projected[2]);
  });
});
