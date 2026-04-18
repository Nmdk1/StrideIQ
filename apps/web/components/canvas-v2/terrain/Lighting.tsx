'use client';

/**
 * Lighting rig for Canvas v2 terrain.
 *
 * Single key directional light + soft ambient. Tuned for the warm gold
 * sculptural style — low-angled key gives the rolling forms strong shadows,
 * which is what makes the terrain read as 3D rather than as a tinted plane.
 */

import React from 'react';

export function Lighting() {
  return (
    <>
      <ambientLight intensity={0.35} color="#1a1a2a" />
      <directionalLight
        position={[12, 14, 8]}
        intensity={1.4}
        color="#fff4d6"
        castShadow
      />
      <directionalLight position={[-10, 6, -8]} intensity={0.25} color="#5a4a1a" />
    </>
  );
}
