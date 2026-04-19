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
    // Naive min/max would yield [266, 10000] and the real data would
    // collapse to a flat line at the bottom.
    const series = pts([
      ...Array.from({ length: 99 }, (_, i) => 266 + (i % 10)),
      10000,
    ]);
    const { vMin, vMax } = robustDomain(series);
    // 98th percentile of the ~typical values should be ≤ ~280, well
    // below the outlier at 10000.
    expect(vMax).toBeLessThan(500);
    expect(vMin).toBeLessThanOrEqual(270);
    expect(vMax - vMin).toBeGreaterThan(0);
  });

  it('handles symmetric outliers on both sides', () => {
    const series = pts([0, ...Array.from({ length: 100 }, (_, i) => 100 + i), 99999]);
    const { vMin, vMax } = robustDomain(series);
    expect(vMin).toBeGreaterThan(0);
    expect(vMax).toBeLessThan(99999);
  });
});
