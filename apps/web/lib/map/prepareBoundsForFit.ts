import L, { LatLngBoundsExpression } from 'leaflet';

/** Below ~30m span, Leaflet fitBounds often leaves the map zoomed far out (tiny “blip”). */
const MIN_SPAN_DEG = 0.0003;

/**
 * Expands near-degenerate bounds so fitBounds can pick a meaningful zoom.
 * Safe for normal routes (large spans pass through unchanged).
 */
export function prepareBoundsForFit(expr: LatLngBoundsExpression): L.LatLngBounds {
  const b = expr instanceof L.LatLngBounds ? expr : L.latLngBounds(expr);
  if (!b.isValid()) return b;
  const sw = b.getSouthWest();
  const ne = b.getNorthEast();
  const latSpan = Math.abs(ne.lat - sw.lat);
  const lngSpan = Math.abs(ne.lng - sw.lng);
  if (Math.max(latSpan, lngSpan) >= MIN_SPAN_DEG) {
    return b;
  }
  const c = b.getCenter();
  const half = MIN_SPAN_DEG / 2;
  return L.latLngBounds(
    [c.lat - half, c.lng - half],
    [c.lat + half, c.lng + half],
  );
}
