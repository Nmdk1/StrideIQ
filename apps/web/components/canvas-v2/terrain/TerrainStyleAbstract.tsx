'use client';

/**
 * TerrainStyleAbstract — golden sculptural heightfield mesh.
 *
 * Renders the run's elevation profile as smooth rolling forms in warm gold.
 * Doesn't pretend to be the actual surrounding ground (it isn't) — it's a
 * stylized representation that reads at a glance regardless of the run's
 * relief. For 169 ft of relief over 14 mi (Meridian Running) it produces
 * visible rolling hills; for 5000 ft of mountain relief it would still
 * fit cleanly into the same panel.
 */

import React, { useMemo } from 'react';
import * as THREE from 'three';
import type { XYZ } from './projection';
import { buildHeightfield } from './heightfield';

export interface TerrainStyleAbstractProps {
  path: XYZ[];
  /** Override the resolution of the underlying grid (perf vs smoothness). */
  resolution?: number;
}

function buildGeometry(path: XYZ[], resolution: number): THREE.PlaneGeometry {
  const hf = buildHeightfield(path, { resolution });
  const geom = new THREE.PlaneGeometry(hf.size, hf.size, hf.resolution - 1, hf.resolution - 1);
  // PlaneGeometry is built in the XY plane; rotate to lie on XZ (y-up).
  geom.rotateX(-Math.PI / 2);
  // Translate to be centered on the path, not on world origin.
  geom.translate(hf.centerX, 0, hf.centerZ);

  // Apply heights to the y-component of each vertex.
  const positions = geom.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < positions.count; i++) {
    // After rotation+translation, vertex order maps to the same row-major
    // (zi, xi) grid we built in heightfield.ts.
    positions.setY(i, hf.heights[i]);
  }
  positions.needsUpdate = true;
  geom.computeVertexNormals();
  return geom;
}

export function TerrainStyleAbstract({ path, resolution = 64 }: TerrainStyleAbstractProps) {
  const geometry = useMemo(() => buildGeometry(path, resolution), [path, resolution]);

  // Dispose old geometry when path changes.
  React.useEffect(() => {
    return () => {
      geometry.dispose();
    };
  }, [geometry]);

  return (
    <mesh geometry={geometry} receiveShadow castShadow>
      <meshStandardMaterial
        color="#d4a347"
        emissive="#3a2a08"
        emissiveIntensity={0.15}
        metalness={0.45}
        roughness={0.55}
        flatShading={false}
      />
    </mesh>
  );
}
