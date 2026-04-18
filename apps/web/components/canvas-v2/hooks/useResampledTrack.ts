'use client';

/**
 * useResampledTrack — turn a stream-analysis StreamPoint[] into a clean
 * track suitable for the 3D terrain mesh + path overlay.
 *
 * Responsibilities:
 *   - Drop points missing GPS or altitude (terrain has no use for them).
 *   - Assign a normalized t = i / (n-1) by index so scrub state translates
 *     to a path index in O(1) at render time.
 *   - Compute cumulative haversine distance for path tessellation.
 *   - Optionally downsample to a target point count (linear stride; the
 *     server already LTTB-downsamples to ~500 so this is usually a no-op).
 *
 * Pure functions are exported for unit testing. The React hook just memoizes
 * the pipeline against the stream identity.
 */

import { useMemo } from 'react';

export interface RawStreamLike {
  time: number;
  hr: number | null;
  pace: number | null;
  altitude: number | null;
  grade: number | null;
  cadence: number | null;
  lat: number | null;
  lng: number | null;
}

export interface TrackPoint {
  /** Index into the post-filter track (0..n-1). */
  index: number;
  /** Normalized position [0, 1]. */
  t: number;
  /** Cumulative distance from start in meters. */
  distanceM: number;
  /** Activity time in seconds. */
  timeS: number;
  lat: number;
  lng: number;
  altitude: number;
  hr: number | null;
  pace: number | null;
  grade: number | null;
  cadence: number | null;
}

export interface TrackBounds {
  minLat: number;
  maxLat: number;
  minLng: number;
  maxLng: number;
  minAltitude: number;
  maxAltitude: number;
  altitudeReliefM: number;
}

const EARTH_RADIUS_M = 6_371_000;

export function haversineMeters(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return EARTH_RADIUS_M * c;
}

export function buildTrack(stream: RawStreamLike[] | null | undefined): TrackPoint[] {
  if (!stream || stream.length === 0) return [];

  const filtered = stream.filter(
    (p) =>
      typeof p.lat === 'number' &&
      typeof p.lng === 'number' &&
      typeof p.altitude === 'number',
  );
  const n = filtered.length;
  if (n === 0) return [];

  const out: TrackPoint[] = new Array(n);
  let cumDist = 0;
  for (let i = 0; i < n; i++) {
    const p = filtered[i];
    if (i > 0) {
      const prev = filtered[i - 1];
      cumDist += haversineMeters(prev.lat as number, prev.lng as number, p.lat as number, p.lng as number);
    }
    out[i] = {
      index: i,
      t: n === 1 ? 0 : i / (n - 1),
      distanceM: cumDist,
      timeS: p.time,
      lat: p.lat as number,
      lng: p.lng as number,
      altitude: p.altitude as number,
      hr: p.hr,
      pace: p.pace,
      grade: p.grade,
      cadence: p.cadence,
    };
  }
  return out;
}

/**
 * Linear-stride downsample to ~target points. First and last are always kept.
 * No-op when the input is already at or below the target, or target <= 0.
 *
 * The server-side stream is already LTTB-downsampled to ~500 points, so this
 * is a backstop, not the primary downsampler.
 */
export function resampleTrack(track: TrackPoint[], target: number): TrackPoint[] {
  if (target <= 0) return track;
  if (track.length <= target) return track;

  const stride = (track.length - 1) / (target - 1);
  const out: TrackPoint[] = new Array(target);
  for (let i = 0; i < target; i++) {
    const srcIdx = i === target - 1 ? track.length - 1 : Math.round(i * stride);
    out[i] = track[srcIdx];
  }
  return out;
}

export function computeTrackBounds(track: TrackPoint[]): TrackBounds | null {
  if (track.length === 0) return null;
  let minLat = Infinity,
    maxLat = -Infinity,
    minLng = Infinity,
    maxLng = -Infinity,
    minAlt = Infinity,
    maxAlt = -Infinity;
  for (const p of track) {
    if (p.lat < minLat) minLat = p.lat;
    if (p.lat > maxLat) maxLat = p.lat;
    if (p.lng < minLng) minLng = p.lng;
    if (p.lng > maxLng) maxLng = p.lng;
    if (p.altitude < minAlt) minAlt = p.altitude;
    if (p.altitude > maxAlt) maxAlt = p.altitude;
  }
  return {
    minLat,
    maxLat,
    minLng,
    maxLng,
    minAltitude: minAlt,
    maxAltitude: maxAlt,
    altitudeReliefM: maxAlt - minAlt,
  };
}

export interface UseResampledTrackOptions {
  /** Target post-resample point count. Defaults to 500. */
  targetPoints?: number;
}

export interface UseResampledTrackResult {
  track: TrackPoint[];
  bounds: TrackBounds | null;
  hasGps: boolean;
}

/**
 * React hook wrapper. Memoizes against stream identity; returns the empty
 * shape (no track, no bounds, hasGps=false) for null / no-GPS inputs so
 * components can render a clean empty state without branching on undefined.
 */
export function useResampledTrack(
  stream: RawStreamLike[] | null | undefined,
  opts: UseResampledTrackOptions = {},
): UseResampledTrackResult {
  const target = opts.targetPoints ?? 500;
  return useMemo(() => {
    const raw = buildTrack(stream);
    const track = resampleTrack(raw, target);
    const bounds = computeTrackBounds(track);
    return { track, bounds, hasGps: track.length > 0 };
  }, [stream, target]);
}
