/**
 * Heightfield generation for the abstract sculptural terrain.
 *
 * Strategy: build a regular MxM grid covering the projected path bounding
 * box (plus generous padding), and assign each vertex a height computed by
 * inverse-distance-squared weighting over nearby path points. Far from the
 * path, height fades to zero (the "ground level" of the world). Near the
 * path, height matches the path's actual altitude.
 *
 * This produces a terrain that:
 *   - Rises and falls *with* the run's actual elevation profile
 *   - Has smooth, sculptural rolling forms around the path
 *   - Doesn't pretend to be the real surrounding ground (it's not)
 *
 * Pure function; no react/three deps. The heavy work runs once per track.
 */

import type { XYZ } from './projection';

export interface HeightfieldOptions {
  /** Grid resolution per side (NxN). 64 ~= 4096 verts, fast and smooth. */
  resolution?: number;
  /** World-space half-width of the terrain plane (centered on path bounds). */
  halfExtent?: number;
  /** Maximum influence radius (world units) for any single path point. */
  influenceRadius?: number;
  /** Minimum padding in world units around the projected bounds. */
  paddingFactor?: number;
}

export interface HeightfieldData {
  resolution: number;
  size: number;
  /** Flat array of length resolution*resolution, row-major (z then x). */
  heights: Float32Array;
  /** World-space center (x, z) the grid is built around. */
  centerX: number;
  centerZ: number;
}

/**
 * Compute bounding box of the projected path on the (x, z) plane.
 */
function pathXZBounds(path: XYZ[]): { minX: number; maxX: number; minZ: number; maxZ: number } {
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const p of path) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.z < minZ) minZ = p.z;
    if (p.z > maxZ) maxZ = p.z;
  }
  return { minX, maxX, minZ, maxZ };
}

export function buildHeightfield(
  path: XYZ[],
  opts: HeightfieldOptions = {},
): HeightfieldData {
  const resolution = opts.resolution ?? 64;
  const paddingFactor = opts.paddingFactor ?? 0.35;
  const influenceRadius = opts.influenceRadius ?? 6;

  if (path.length === 0) {
    return {
      resolution,
      size: 1,
      heights: new Float32Array(resolution * resolution),
      centerX: 0,
      centerZ: 0,
    };
  }

  const { minX, maxX, minZ, maxZ } = pathXZBounds(path);
  const spanX = maxX - minX;
  const spanZ = maxZ - minZ;
  const baseSpan = Math.max(spanX, spanZ, 1);
  const pad = baseSpan * paddingFactor;
  const halfExtent = opts.halfExtent ?? baseSpan / 2 + pad;
  const size = halfExtent * 2;

  const centerX = (minX + maxX) / 2;
  const centerZ = (minZ + maxZ) / 2;

  const heights = new Float32Array(resolution * resolution);
  const cellSize = size / (resolution - 1);
  const r2 = influenceRadius * influenceRadius;
  const epsilon = 0.05;

  for (let zi = 0; zi < resolution; zi++) {
    const wz = centerZ - halfExtent + zi * cellSize;
    for (let xi = 0; xi < resolution; xi++) {
      const wx = centerX - halfExtent + xi * cellSize;

      // Inverse-distance-squared weighting over path points within radius.
      let weightSum = 0;
      let heightSum = 0;
      for (let pi = 0; pi < path.length; pi++) {
        const p = path[pi];
        const dx = wx - p.x;
        const dz = wz - p.z;
        const d2 = dx * dx + dz * dz;
        if (d2 > r2) continue;
        const w = 1 / (d2 + epsilon);
        weightSum += w;
        heightSum += w * p.y;
      }
      // Smooth fade: beyond influence radius, height → 0. Within, blend.
      const blendedHeight = weightSum > 0 ? heightSum / weightSum : 0;
      // Falloff factor: 1 when at least one path point is within radius/2,
      // 0 when none are within radius. Smooth.
      let nearestD2 = Infinity;
      for (let pi = 0; pi < path.length; pi++) {
        const p = path[pi];
        const dx = wx - p.x;
        const dz = wz - p.z;
        const d2 = dx * dx + dz * dz;
        if (d2 < nearestD2) nearestD2 = d2;
      }
      const nearestD = Math.sqrt(nearestD2);
      const falloff = smoothstep(influenceRadius, influenceRadius * 0.25, nearestD);
      heights[zi * resolution + xi] = blendedHeight * falloff;
    }
  }

  return { resolution, size, heights, centerX, centerZ };
}

/**
 * GLSL-style smoothstep, with edges in either order so it interpolates
 * regardless of direction.
 */
export function smoothstep(edge0: number, edge1: number, x: number): number {
  const lo = Math.min(edge0, edge1);
  const hi = Math.max(edge0, edge1);
  if (x <= lo) return edge0 < edge1 ? 0 : 1;
  if (x >= hi) return edge0 < edge1 ? 1 : 0;
  const t = (x - lo) / (hi - lo);
  const eased = t * t * (3 - 2 * t);
  return edge0 < edge1 ? eased : 1 - eased;
}
