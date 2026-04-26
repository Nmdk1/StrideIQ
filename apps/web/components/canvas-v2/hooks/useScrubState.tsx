'use client';

/**
 * useScrubState — shared scrub coordination for Canvas v2.
 *
 * Single source of truth for "where is the cursor along the run", expressed
 * as a normalized [0, 1] position (or null when nothing is hovered).
 *
 * Every panel that drives the scrub (streams, terrain, future overlays)
 * writes through `setPosition`. Every panel that displays an indicator
 * (marker on terrain, vertical line on streams, moment readout) reads
 * `position`. One source, many followers — no panel coordinates with
 * any other panel directly.
 */

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export function clampScrub(t: number | null): number | null {
  if (t === null) return null;
  if (Number.isNaN(t)) return null;
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  return t;
}

export interface ScrubContextValue {
  /** Normalized position [0, 1] or null when not hovering anywhere. */
  position: number | null;
  /** Set the normalized position; out-of-range values are clamped. */
  setPosition: (t: number | null) => void;
  /** Convenience for mouseLeave / blur — same as setPosition(null). */
  clear: () => void;
}

const ScrubContext = createContext<ScrubContextValue | null>(null);

export function ScrubProvider({ children }: { children: React.ReactNode }) {
  const [position, setPositionRaw] = useState<number | null>(null);

  const setPosition = useCallback((t: number | null) => {
    setPositionRaw(clampScrub(t));
  }, []);

  const clear = useCallback(() => {
    setPositionRaw(null);
  }, []);

  const value = useMemo<ScrubContextValue>(
    () => ({ position, setPosition, clear }),
    [position, setPosition, clear]
  );

  return <ScrubContext.Provider value={value}>{children}</ScrubContext.Provider>;
}

export function useScrubState(): ScrubContextValue {
  const ctx = useContext(ScrubContext);
  if (!ctx) {
    throw new Error('useScrubState must be used inside <ScrubProvider>');
  }
  return ctx;
}
