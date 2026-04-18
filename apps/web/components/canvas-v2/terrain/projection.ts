/**
 * Projection utilities for translating GPS+altitude → local 3D world space.
 *
 * Pure functions, no React or three.js types — kept small and unit-testable.
 *
 * Convention: world is right-handed,
 *   x = east  (lng)
 *   y = up    (altitude)
 *   z = south (negative lat increases north)
 *
 * The projection is intentionally simple — equirectangular with longitude
 * scaled by cos(centerLat) so circular-ish bounding boxes don't stretch.
 * The whole bounding box is normalized to fit in a square of `worldSize`
 * units, centered on world origin. Altitude is mapped through a separate
 * vertical-exaggeration step so low-relief runs don't render as flat plates.
 */

import type { TrackBounds, TrackPoint } from '../hooks/useResampledTrack';

export interface ProjectionParams {
  centerLat: number;
  centerLng: number;
  /** World-space scale: meters → world units, equal for x and z. */
  metersPerUnit: number;
  /** Altitude offset (meters): subtract before exaggeration to center vertically. */
  altitudeBaseM: number;
  /** Vertical-exaggeration multiplier applied AFTER subtracting altitudeBaseM. */
  verticalExaggeration: number;
  /** Final world units per (exaggerated) meter on the y axis. */
  yMetersPerUnit: number;
}

const METERS_PER_DEG_LAT = 111_320;

export interface ComputeProjectionOptions {
  /** Width/depth of the world square in r3f units. */
  worldSize?: number;
  /** Altitude relief (m) that should map to roughly 1 world unit of height. */
  targetReliefUnits?: number;
}

/**
 * Compute a projection that frames the bounding box inside a world square,
 * with altitude exaggerated so that the run's relief reads cleanly even on
 * low-relief profiles (e.g. 50m relief over 22km).
 */
export function computeProjection(
  bounds: TrackBounds,
  opts: ComputeProjectionOptions = {},
): ProjectionParams {
  const worldSize = opts.worldSize ?? 20;
  const targetReliefUnits = opts.targetReliefUnits ?? 2.5;

  const centerLat = (bounds.minLat + bounds.maxLat) / 2;
  const centerLng = (bounds.minLng + bounds.maxLng) / 2;

  // Bounding box dimensions in meters.
  const latRangeM = (bounds.maxLat - bounds.minLat) * METERS_PER_DEG_LAT;
  const lngRangeM =
    (bounds.maxLng - bounds.minLng) * METERS_PER_DEG_LAT * Math.cos((centerLat * Math.PI) / 180);
  const maxRangeM = Math.max(latRangeM, lngRangeM, 1);
  const metersPerUnit = maxRangeM / worldSize;

  const reliefM = Math.max(bounds.altitudeReliefM, 0.1);
  // Pick exaggeration so reliefM maps to targetReliefUnits in world space.
  // We split this into two factors: vertical exaggeration (clamped 1..12 so
  // dramatic terrain doesn't get squashed) and a final y scale.
  const desiredYUnitsPerMeter = targetReliefUnits / reliefM;
  const verticalExaggeration = Math.max(1, Math.min(12, desiredYUnitsPerMeter * metersPerUnit));
  const yMetersPerUnit = (reliefM * verticalExaggeration) / targetReliefUnits;

  return {
    centerLat,
    centerLng,
    metersPerUnit,
    altitudeBaseM: (bounds.minAltitude + bounds.maxAltitude) / 2,
    verticalExaggeration,
    yMetersPerUnit,
  };
}

export interface XYZ {
  x: number;
  y: number;
  z: number;
}

export function projectLatLng(
  lat: number,
  lng: number,
  altitudeM: number,
  proj: ProjectionParams,
): XYZ {
  const cosLat = Math.cos((proj.centerLat * Math.PI) / 180);
  const dLngM = (lng - proj.centerLng) * METERS_PER_DEG_LAT * cosLat;
  const dLatM = (lat - proj.centerLat) * METERS_PER_DEG_LAT;
  return {
    x: dLngM / proj.metersPerUnit,
    y: ((altitudeM - proj.altitudeBaseM) * proj.verticalExaggeration) / proj.yMetersPerUnit,
    z: -dLatM / proj.metersPerUnit,
  };
}

export function projectTrack(track: TrackPoint[], proj: ProjectionParams): XYZ[] {
  const out: XYZ[] = new Array(track.length);
  for (let i = 0; i < track.length; i++) {
    const p = track[i];
    out[i] = projectLatLng(p.lat, p.lng, p.altitude, proj);
  }
  return out;
}

/**
 * Linearly interpolate the projected path at scrub t∈[0,1].
 * Returns null when track is empty.
 */
export function sampleProjectedTrack(projected: XYZ[], t: number): XYZ | null {
  if (projected.length === 0) return null;
  if (projected.length === 1) return projected[0];
  const tt = Math.max(0, Math.min(1, t));
  const idxF = tt * (projected.length - 1);
  const i0 = Math.floor(idxF);
  const i1 = Math.min(projected.length - 1, i0 + 1);
  const frac = idxF - i0;
  const a = projected[i0];
  const b = projected[i1];
  return {
    x: a.x + (b.x - a.x) * frac,
    y: a.y + (b.y - a.y) * frac,
    z: a.z + (b.z - a.z) * frac,
  };
}
