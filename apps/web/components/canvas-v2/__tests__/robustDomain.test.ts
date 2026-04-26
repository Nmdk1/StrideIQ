import { quantile, robustDomain, type SeriesPoint } from '../StreamsStack';

const pts = (vs: number[]): SeriesPoint[] => vs.map((v, i) => ({ t: i / (vs.length - 1 || 1), v }));

describe('quantile', () => {
  it('returns 0 for empty arrays', () => {
    expect(quantile([], 0.5)).toBe(0);
  });

  it('returns the only value for single-element arrays', () => {
    expect(quantile([42], 0.5)).toBe(42);
    expect(quantile([42], 0)).toBe(42);
    expect(quantile([42], 1)).toBe(42);
  });

  it('matches median for an odd-length sorted array', () => {
    expect(quantile([1, 2, 3, 4, 5], 0.5)).toBe(3);
  });

  it('linearly interpolates between adjacent values', () => {
    // For [0, 10, 20, 30] and q=0.5, position = 1.5,
    // halfway between 10 and 20 → 15.
    expect(quantile([0, 10, 20, 30], 0.5)).toBe(15);
  });

  it('returns extremes at q=0 and q=1', () => {
    expect(quantile([1, 2, 3, 4, 5], 0)).toBe(1);
    expect(quantile([1, 2, 3, 4, 5], 1)).toBe(5);
  });
});

describe('robustDomain', () => {
  it('returns a unit domain for empty series', () => {
    expect(robustDomain([])).toEqual({ vMin: 0, vMax: 1 });
  });

  it('expands single-value series so the chart still renders', () => {
    const out = robustDomain(pts([5]));
    expect(out.vMin).toBeLessThan(out.vMax);
  });

  it('clips a single severe outlier so the bulk of data fills the band', () => {
    // 99 typical pace values around 270 s/km plus one GPS-skip 10000.
    const series = pts([
      ...Array.from({ length: 99 }, (_, i) => 266 + (i % 10)),
      10000,
    ]);
    const { vMin, vMax } = robustDomain(series);
    expect(vMax).toBeLessThan(500);
    expect(vMin).toBeLessThanOrEqual(270);
    expect(vMax - vMin).toBeGreaterThan(0);
  });

  // Regression for the Coke 10K case. Bare percentile (2/98) failed
  // because the haywire end-of-run cluster was big enough to live
  // inside the percentile window. IQR/Tukey is frequency-independent.
  it('clips a frequent outlier cluster (cool-down walking + GPS jitter)', () => {
    const raceBody = Array.from({ length: 1000 }, (_, i) => 250 + (i % 25)); // 250-274
    const haywire = Array.from({ length: 60 }, (_, i) =>
      i % 3 === 0 ? 100 : i % 3 === 1 ? 1500 : 700,
    );
    const series = pts([...raceBody, ...haywire]);
    const { vMin, vMax } = robustDomain(series);
    // Real race body lives in 250-274 (24 s/km of true variation).
    // Domain must be tight enough to actually show that variation, NOT
    // get pulled out to ~700-1500 by the haywire cluster.
    expect(vMax).toBeLessThan(330);
    expect(vMin).toBeGreaterThan(220);
    expect(vMax - vMin).toBeLessThan(110);
  });

  it('clips truly extreme outliers on both sides', () => {
    // Body is [200, 240]. Outliers at -50000 and +50000 are both
    // dramatically beyond Tukey's fence and must be excluded.
    // (Note: a value sitting just outside the body — say 0 here —
    // would NOT be clipped, because Q1 − 3·IQR is well below 0.
    // That's the correct IQR semantics: only EXTREME outliers go.)
    const series = pts([
      -50000,
      ...Array.from({ length: 100 }, (_, i) => 200 + (i % 41)),
      50000,
    ]);
    const { vMin, vMax } = robustDomain(series);
    expect(vMin).toBeGreaterThan(-1000);
    expect(vMax).toBeLessThan(1000);
  });

  it('preserves intentional wide variation like interval workouts', () => {
    // Cruise 240, recovery 360 — both legitimate, alternating.
    const series = pts(
      Array.from({ length: 200 }, (_, i) => (Math.floor(i / 10) % 2 === 0 ? 240 : 360)),
    );
    const { vMin, vMax } = robustDomain(series);
    // Both ends of the legitimate range must remain in the domain.
    expect(vMin).toBeLessThanOrEqual(245);
    expect(vMax).toBeGreaterThanOrEqual(355);
  });
});
