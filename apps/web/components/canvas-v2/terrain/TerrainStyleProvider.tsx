'use client';

/**
 * TerrainStyleProvider — picks the terrain renderer based on the run's
 * altitude relief and (eventually) sport type.
 *
 * v1: always returns TerrainStyleAbstract. The photoreal renderer slots in
 * here when it ships — this is the only file that changes to add it.
 *
 *   reliefM < 500 → abstract sculptural (everyday roads, recovery loops)
 *   reliefM >= 500 → photoreal mountain (trail, ultra) — TBD
 */

import React from 'react';
import type { XYZ } from './projection';
import { TerrainStyleAbstract } from './TerrainStyleAbstract';

export type TerrainStyleId = 'abstract' | 'photoreal';

export interface TerrainStyleProviderProps {
  path: XYZ[];
  reliefM: number;
  /** Force a specific style (for explicit override or sandbox A/B). */
  forceStyle?: TerrainStyleId;
}

export function pickTerrainStyle(reliefM: number): TerrainStyleId {
  // Photoreal renderer not yet implemented. When it ships, flip this gate to
  // return 'photoreal' for trail/mountain runs.
  void reliefM;
  return 'abstract';
}

export function TerrainStyleProvider({ path, reliefM, forceStyle }: TerrainStyleProviderProps) {
  const style = forceStyle ?? pickTerrainStyle(reliefM);
  switch (style) {
    case 'abstract':
      return <TerrainStyleAbstract path={path} />;
    case 'photoreal':
      // Photoreal renderer placeholder — falls back to abstract until it ships.
      return <TerrainStyleAbstract path={path} />;
    default: {
      // Exhaustiveness guard.
      const _exhaustive: never = style;
      void _exhaustive;
      return <TerrainStyleAbstract path={path} />;
    }
  }
}
