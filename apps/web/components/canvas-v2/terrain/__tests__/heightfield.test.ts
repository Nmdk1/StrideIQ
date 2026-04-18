import { buildHeightfield, smoothstep } from '../heightfield';

describe('smoothstep', () => {
  it('returns 0 below low edge and 1 above high edge (ascending)', () => {
    expect(smoothstep(0, 1, -0.5)).toBe(0);
    expect(smoothstep(0, 1, 1.5)).toBe(1);
  });

  it('returns midpoint smoothly', () => {
    const v = smoothstep(0, 1, 0.5);
    expect(v).toBeCloseTo(0.5, 6);
  });

  it('returns inverted result when edge0 > edge1', () => {
    expect(smoothstep(1, 0, -0.5)).toBe(1);
    expect(smoothstep(1, 0, 1.5)).toBe(0);
  });
});

describe('buildHeightfield', () => {
  it('returns zeroed grid for empty path', () => {
    const hf = buildHeightfield([], { resolution: 8 });
    expect(hf.heights.length).toBe(64);
    for (let i = 0; i < hf.heights.length; i++) {
      expect(hf.heights[i]).toBe(0);
    }
  });

  it('produces a grid of the requested resolution^2', () => {
    const path = [
      { x: 0, y: 1, z: 0 },
      { x: 1, y: 2, z: 0 },
      { x: 2, y: 1, z: 1 },
    ];
    const hf = buildHeightfield(path, { resolution: 16 });
    expect(hf.heights.length).toBe(256);
  });

  it('elevates terrain near the path', () => {
    const path = [
      { x: 0, y: 5, z: 0 },
      { x: 1, y: 5, z: 0 },
      { x: 2, y: 5, z: 0 },
    ];
    const hf = buildHeightfield(path, { resolution: 32, influenceRadius: 4 });
    // Find the cell closest to a path point and assert it's > 0.
    let maxH = -Infinity;
    for (let i = 0; i < hf.heights.length; i++) {
      if (hf.heights[i] > maxH) maxH = hf.heights[i];
    }
    expect(maxH).toBeGreaterThan(0);
  });

  it('falls toward zero far from the path', () => {
    const path = [
      { x: 0, y: 5, z: 0 },
      { x: 1, y: 5, z: 0 },
    ];
    const hf = buildHeightfield(path, { resolution: 32, influenceRadius: 2, paddingFactor: 2 });
    // Corner cells (far from path) should be near zero.
    const corner = hf.heights[0];
    expect(Math.abs(corner)).toBeLessThan(0.5);
  });

  it('center coordinates equal the path centroid', () => {
    const path = [
      { x: 0, y: 0, z: 0 },
      { x: 10, y: 0, z: 0 },
      { x: 5, y: 0, z: 10 },
    ];
    const hf = buildHeightfield(path, { resolution: 8 });
    expect(hf.centerX).toBeCloseTo(5, 6);
    expect(hf.centerZ).toBeCloseTo(5, 6);
  });

  it('size is positive and scales with path bounding box', () => {
    const small = buildHeightfield(
      [
        { x: 0, y: 0, z: 0 },
        { x: 1, y: 0, z: 0 },
      ],
      { resolution: 8 },
    );
    const large = buildHeightfield(
      [
        { x: 0, y: 0, z: 0 },
        { x: 100, y: 0, z: 100 },
      ],
      { resolution: 8 },
    );
    expect(small.size).toBeGreaterThan(0);
    expect(large.size).toBeGreaterThan(small.size);
  });
});
