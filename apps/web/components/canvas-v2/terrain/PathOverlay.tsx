'use client';

/**
 * PathOverlay — glowing path drawn on the terrain surface.
 *
 * The path is rendered as a thin glowing line that follows the projected
 * GPS trace. Slightly offset above terrain to avoid z-fighting; the offset
 * is small enough that the path still reads as "on the ground", not floating.
 */

import React, { useMemo } from 'react';
import * as THREE from 'three';
import type { XYZ } from './projection';

const SURFACE_OFFSET_UNITS = 0.04;

export interface PathOverlayProps {
  path: XYZ[];
}

export function PathOverlay({ path }: PathOverlayProps) {
  const geometry = useMemo(() => {
    const points = path.map((p) => new THREE.Vector3(p.x, p.y + SURFACE_OFFSET_UNITS, p.z));
    const geom = new THREE.BufferGeometry().setFromPoints(points);
    return geom;
  }, [path]);

  React.useEffect(() => {
    return () => {
      geometry.dispose();
    };
  }, [geometry]);

  if (path.length < 2) return null;

  return (
    <line>
      <bufferGeometry attach="geometry" {...geometry} />
      <lineBasicMaterial
        attach="material"
        color="#ffb347"
        linewidth={2}
        transparent
        opacity={0.95}
      />
    </line>
  );
}
