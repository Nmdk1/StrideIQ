import {
  buildTrack,
  resampleTrack,
  computeTrackBounds,
  haversineMeters,
  type RawStreamLike,
} from '../useResampledTrack';

const baseStream = (over: Partial<RawStreamLike>[] = []): RawStreamLike[] =>
  over.map((o, i) => ({
    time: i,
    hr: 140,
    pace: 300,
    altitude: 100,
    grade: 0,
    cadence: 180,
    lat: 32.0 + i * 0.001,
    lng: -88.0 + i * 0.001,
    ...o,
  }));

describe('haversineMeters', () => {
  it('returns 0 for identical points', () => {
    expect(haversineMeters(32.0, -88.0, 32.0, -88.0)).toBe(0);
  });

  it('returns ~111m per degree of latitude', () => {
    const m = haversineMeters(32.0, -88.0, 32.001, -88.0);
    expect(m).toBeGreaterThan(105);
    expect(m).toBeLessThan(115);
  });
});

describe('buildTrack', () => {
  it('returns empty array for null/empty input', () => {
    expect(buildTrack(null)).toEqual([]);
    expect(buildTrack([])).toEqual([]);
  });

  it('drops points missing lat/lng/altitude', () => {
    const stream = baseStream([
      { lat: 32.0, lng: -88.0, altitude: 100 },
      { lat: null, lng: -88.001, altitude: 101 },
      { lat: 32.001, lng: null, altitude: 102 },
      { lat: 32.002, lng: -88.002, altitude: null },
      { lat: 32.003, lng: -88.003, altitude: 103 },
    ]);
    const track = buildTrack(stream);
    expect(track).toHaveLength(2);
    expect(track[0].lat).toBe(32.0);
    expect(track[1].lat).toBe(32.003);
  });

  it('assigns t=0 to first point and t=1 to last', () => {
    const track = buildTrack(baseStream(Array(10).fill({})));
    expect(track[0].t).toBe(0);
    expect(track[track.length - 1].t).toBe(1);
  });

  it('computes monotonically increasing distance and t', () => {
    const track = buildTrack(baseStream(Array(20).fill({})));
    for (let i = 1; i < track.length; i++) {
      expect(track[i].distanceM).toBeGreaterThanOrEqual(track[i - 1].distanceM);
      expect(track[i].t).toBeGreaterThanOrEqual(track[i - 1].t);
    }
  });

  it('preserves altitude and time channels', () => {
    const stream = baseStream([
      { time: 0, altitude: 100, lat: 32.0, lng: -88.0 },
      { time: 30, altitude: 110, lat: 32.001, lng: -88.001 },
      { time: 60, altitude: 105, lat: 32.002, lng: -88.002 },
    ]);
    const track = buildTrack(stream);
    expect(track.map((p) => p.altitude)).toEqual([100, 110, 105]);
    expect(track.map((p) => p.timeS)).toEqual([0, 30, 60]);
  });

  it('handles a single valid point gracefully (t=0)', () => {
    const track = buildTrack(baseStream([{ lat: 32.0, lng: -88.0, altitude: 100 }]));
    expect(track).toHaveLength(1);
    expect(track[0].t).toBe(0);
    expect(track[0].distanceM).toBe(0);
  });
});

describe('resampleTrack', () => {
  it('returns input unchanged when shorter than target', () => {
    const track = buildTrack(baseStream(Array(50).fill({})));
    const out = resampleTrack(track, 1000);
    expect(out).toBe(track);
  });

  it('returns input unchanged when target is 0 or negative (no-op safety)', () => {
    const track = buildTrack(baseStream(Array(500).fill({})));
    expect(resampleTrack(track, 0)).toBe(track);
    expect(resampleTrack(track, -5)).toBe(track);
  });

  it('downsamples to approximately the target count', () => {
    const track = buildTrack(baseStream(Array(2000).fill({})));
    const out = resampleTrack(track, 500);
    expect(out.length).toBeLessThanOrEqual(500);
    expect(out.length).toBeGreaterThan(400);
  });

  it('always retains first and last points', () => {
    const track = buildTrack(baseStream(Array(3000).fill({})));
    const out = resampleTrack(track, 200);
    expect(out[0].t).toBe(0);
    expect(out[out.length - 1].t).toBe(1);
  });

  it('keeps t monotonically increasing after resample', () => {
    const track = buildTrack(baseStream(Array(2000).fill({})));
    const out = resampleTrack(track, 250);
    for (let i = 1; i < out.length; i++) {
      expect(out[i].t).toBeGreaterThanOrEqual(out[i - 1].t);
    }
  });
});

describe('computeTrackBounds', () => {
  it('returns null for empty track', () => {
    expect(computeTrackBounds([])).toBeNull();
  });

  it('finds min/max lat, lng, altitude correctly', () => {
    const track = buildTrack([
      { time: 0, lat: 32.5, lng: -88.5, altitude: 100, hr: null, pace: null, grade: null, cadence: null },
      { time: 1, lat: 32.6, lng: -88.4, altitude: 150, hr: null, pace: null, grade: null, cadence: null },
      { time: 2, lat: 32.4, lng: -88.6, altitude: 80, hr: null, pace: null, grade: null, cadence: null },
    ]);
    const b = computeTrackBounds(track);
    expect(b).not.toBeNull();
    expect(b!.minLat).toBe(32.4);
    expect(b!.maxLat).toBe(32.6);
    expect(b!.minLng).toBe(-88.6);
    expect(b!.maxLng).toBe(-88.4);
    expect(b!.minAltitude).toBe(80);
    expect(b!.maxAltitude).toBe(150);
    expect(b!.altitudeReliefM).toBe(70);
  });

  it('reports zero relief for flat terrain', () => {
    const track = buildTrack(baseStream(Array(10).fill({ altitude: 100 })));
    const b = computeTrackBounds(track);
    expect(b!.altitudeReliefM).toBe(0);
  });
});
