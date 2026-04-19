'use client';

/**
 * RunDetailsGrid — activity-level FIT metrics (Phase 1 / fit_run_001).
 *
 * Each card is *self-suppressing*: if the underlying metric is null
 * (no FIT file yet, or the athlete's sensor doesn't record it), the
 * card is not rendered. If no cards have data, the whole grid suppresses
 * — keeping the page clean for older Strava-only activities and for
 * watch-only setups (no HRM-Pro / no Stryd / no Forerunner Pro).
 *
 * No template narration. The cards display a measured number with
 * its unit. Interpretation belongs in the coach brief, not here.
 */

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';

const M_TO_FT = 3.28084;

export interface RunDetailsGridProps {
  /** Average running power (Watts). Stryd, Forerunner 9xx/Fenix native power, etc. */
  avgPowerW?: number | null;
  /** Peak running power (Watts). */
  maxPowerW?: number | null;
  /** Average stride length in meters. Foundational metric. */
  avgStrideLengthM?: number | null;
  /** Average ground contact time, milliseconds. HRM-Pro family. */
  avgGroundContactMs?: number | null;
  /** Ground contact L/R balance, percent (50% = perfect). */
  avgGroundContactBalancePct?: number | null;
  /** Average vertical oscillation, centimeters. */
  avgVerticalOscillationCm?: number | null;
  /** Average vertical ratio, percent. */
  avgVerticalRatioPct?: number | null;
  /** Total descent in meters. */
  totalDescentM?: number | null;
}

interface Card {
  label: string;
  value: string;
  hint?: string;
}

export function RunDetailsGrid(props: RunDetailsGridProps): React.ReactElement | null {
  const { units } = useUnits();
  const isImperial = units === 'imperial';

  const cards: Card[] = [];

  if (props.avgPowerW != null) {
    cards.push({
      label: 'Avg Power',
      value: `${Math.round(props.avgPowerW)} W`,
      hint: props.maxPowerW != null ? `peak ${Math.round(props.maxPowerW)} W` : undefined,
    });
  }
  if (props.avgStrideLengthM != null) {
    cards.push({
      label: 'Stride Length',
      value: `${props.avgStrideLengthM.toFixed(2)} m`,
    });
  }
  if (props.avgGroundContactMs != null) {
    const balance = props.avgGroundContactBalancePct;
    cards.push({
      label: 'Ground Contact',
      value: `${Math.round(props.avgGroundContactMs)} ms`,
      hint: balance != null ? `L/R ${balance.toFixed(1)}%` : undefined,
    });
  }
  if (props.avgVerticalOscillationCm != null) {
    cards.push({
      label: 'Vertical Osc.',
      value: `${props.avgVerticalOscillationCm.toFixed(1)} cm`,
    });
  }
  if (props.avgVerticalRatioPct != null) {
    cards.push({
      label: 'Vertical Ratio',
      value: `${props.avgVerticalRatioPct.toFixed(1)}%`,
    });
  }
  if (props.totalDescentM != null) {
    const descent = isImperial
      ? `${Math.round(props.totalDescentM * M_TO_FT)} ft`
      : `${Math.round(props.totalDescentM)} m`;
    cards.push({
      label: 'Descent',
      value: descent,
    });
  }

  if (cards.length === 0) return null;

  return (
    <section
      aria-label="Run details"
      className="rounded-xl border border-slate-700/40 bg-slate-900/30 p-4"
    >
      <h3 className="mb-3 text-[0.65rem] uppercase tracking-wider text-slate-500">
        Run Details
      </h3>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 md:grid-cols-6">
        {cards.map((c) => (
          <div key={c.label} className="min-w-0">
            <p className="text-lg md:text-xl font-semibold text-white tabular-nums leading-tight whitespace-nowrap">
              {c.value}
            </p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wide mt-0.5">
              {c.label}
            </p>
            {c.hint && (
              <p className="text-[10px] text-slate-400 mt-0.5">{c.hint}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
