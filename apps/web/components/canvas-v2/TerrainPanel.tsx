'use client';

/**
 * TerrainPanel — the 3D hero of Canvas v2.
 *
 * Mounts the react-three-fiber Canvas and assembles:
 *   - Lighting rig
 *   - TerrainStyleProvider (picks abstract/photoreal renderer)
 *   - PathOverlay (glowing trace on the terrain surface)
 *   - PositionMarker (sphere + pole at scrub position)
 *   - OrbitControls (camera)
 *
 * The whole panel is hidden when the run has no GPS (the parent decides;
 * this component still renders gracefully if given an empty track but the
 * container is intended to be unmounted for indoor runs).
 */

import React, { Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { TrackBounds, TrackPoint } from './hooks/useResampledTrack';
import { computeProjection, projectTrack } from './terrain/projection';
import { TerrainStyleProvider, type TerrainStyleId } from './terrain/TerrainStyleProvider';
import { PathOverlay } from './terrain/PathOverlay';
import { PositionMarker } from './terrain/PositionMarker';
import { Lighting } from './terrain/Lighting';

export interface TerrainPanelProps {
  track: TrackPoint[];
  bounds: TrackBounds;
  /** Approx panel height. Width fills container. */
  height?: number;
  forceStyle?: TerrainStyleId;
}

export function TerrainPanel({ track, bounds, height = 360, forceStyle }: TerrainPanelProps) {
  const projection = useMemo(() => computeProjection(bounds, { worldSize: 20, targetReliefUnits: 2.8 }), [bounds]);
  const projected = useMemo(() => projectTrack(track, projection), [track, projection]);

  const cameraPosition: [number, number, number] = [16, 11, 16];

  return (
    <div
      className="relative rounded-2xl overflow-hidden border border-slate-800/60 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950"
      style={{ height }}
    >
      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: cameraPosition, fov: 38, near: 0.1, far: 200 }}
        gl={{ antialias: true, alpha: false }}
        onCreated={({ scene }) => {
          scene.background = null;
        }}
      >
        <fog attach="fog" args={['#0a0a18', 22, 55]} />
        <Lighting />
        <Suspense fallback={null}>
          <TerrainStyleProvider
            path={projected}
            reliefM={bounds.altitudeReliefM}
            forceStyle={forceStyle}
          />
          <PathOverlay path={projected} />
          <PositionMarker projected={projected} />
        </Suspense>
        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.08}
          minDistance={8}
          maxDistance={36}
          minPolarAngle={Math.PI / 8}
          maxPolarAngle={Math.PI / 2.05}
          target={[0, 0, 0]}
        />
      </Canvas>
      <div className="absolute top-3 left-3 px-2 py-1 rounded-md bg-slate-950/60 backdrop-blur-sm text-[10px] uppercase tracking-wider text-slate-400 pointer-events-none">
        Terrain · Abstract
      </div>
      <div className="absolute bottom-3 right-3 px-2 py-1 rounded-md bg-slate-950/60 backdrop-blur-sm text-[10px] text-slate-500 pointer-events-none">
        {bounds.altitudeReliefM.toFixed(0)} m relief · drag to orbit
      </div>
    </div>
  );
}
