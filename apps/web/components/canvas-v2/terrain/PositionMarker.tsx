'use client';

/**
 * PositionMarker — sphere + vertical pole + percent label at the current
 * scrub position along the projected path.
 *
 * Reads scrub state from the shared context. Hidden when scrub is inactive.
 */

import React, { useMemo } from 'react';
import { Html } from '@react-three/drei';
import { useScrubState } from '../hooks/useScrubState';
import { sampleProjectedTrack, type XYZ } from './projection';

const POLE_HEIGHT_UNITS = 1.6;
const SPHERE_RADIUS = 0.18;
const POLE_RADIUS = 0.018;

export interface PositionMarkerProps {
  projected: XYZ[];
}

export function PositionMarker({ projected }: PositionMarkerProps) {
  const { position } = useScrubState();
  const point = useMemo(
    () => (position === null ? null : sampleProjectedTrack(projected, position)),
    [position, projected],
  );

  if (!point) return null;

  const poleCenterY = point.y + POLE_HEIGHT_UNITS / 2;
  const sphereY = point.y + POLE_HEIGHT_UNITS;
  const labelText = `${Math.round((position ?? 0) * 100)}%`;

  return (
    <group>
      <mesh position={[point.x, poleCenterY, point.z]}>
        <cylinderGeometry args={[POLE_RADIUS, POLE_RADIUS, POLE_HEIGHT_UNITS, 8]} />
        <meshStandardMaterial color="#ff6b6b" emissive="#ff4040" emissiveIntensity={0.6} />
      </mesh>
      <mesh position={[point.x, sphereY, point.z]} castShadow>
        <sphereGeometry args={[SPHERE_RADIUS, 24, 16]} />
        <meshStandardMaterial
          color="#ff5252"
          emissive="#ff3030"
          emissiveIntensity={1.1}
          roughness={0.35}
        />
      </mesh>
      <Html
        position={[point.x, sphereY + 0.45, point.z]}
        center
        distanceFactor={10}
        style={{ pointerEvents: 'none' }}
      >
        <div className="text-rose-300 text-xs font-semibold tabular-nums whitespace-nowrap drop-shadow">
          {labelText}
        </div>
      </Html>
    </group>
  );
}
