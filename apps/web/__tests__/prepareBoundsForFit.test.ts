import L from 'leaflet';
import { prepareBoundsForFit } from '@/lib/map/prepareBoundsForFit';

describe('prepareBoundsForFit', () => {
  it('expands a degenerate point box so max span reaches the minimum', () => {
    const b = prepareBoundsForFit([[40.0, -74.0], [40.0, -74.0]]);
    const sw = b.getSouthWest();
    const ne = b.getNorthEast();
    expect(Math.abs(ne.lat - sw.lat)).toBeGreaterThan(0.0002);
    expect(Math.abs(ne.lng - sw.lng)).toBeGreaterThan(0.0002);
    expect(b.contains(L.latLng(40, -74))).toBe(true);
  });

  it('passes through normal activity bounds unchanged', () => {
    const input: [[number, number], [number, number]] = [
      [40.0, -74.05],
      [40.02, -73.98],
    ];
    const b = prepareBoundsForFit(input);
    expect(b.getSouthWest().lat).toBe(40.0);
    expect(b.getNorthEast().lat).toBe(40.02);
  });
});
