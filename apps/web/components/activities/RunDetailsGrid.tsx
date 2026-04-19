'use client';

/**
 * RunDetailsGrid — activity-level FIT metrics (Phase 1 / fit_run_001).
 *
 * Each card is *self-suppressing*: if the underlying metric is null
 * (no FIT file yet, or the athlete's sensor doesn't record it), the
 * card is not rendered.
 *
 * Empty-state policy (added Apr 19, 2026):
 *   When no cards have data we still owe the athlete the truth, because
 *   silently disappearing makes the page look broken (the founder asked
 *   "did they ship it or not?" when this happened on historical runs).
 *   If `showMissingNote` is true and the activity *should* have had FIT
 *   data (a real outdoor movement: run, walk, hike, cycle), we render a
 *   single honest line instead of nothing. For sports where FIT
 *   running-dynamics never apply (strength, yoga, swim, etc.) the
 *   component still suppresses entirely.
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
  /**
   * When true and no cards have data, render a single small line
   * explaining that FIT-derived metrics weren't captured for this
   * activity (instead of suppressing entirely).
   *
   * Caller is expected to gate on sport_type so we don't show it for
   * activities where these metrics never apply (strength, yoga, swim).
   */
  showMissingNote?: boolean;
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

  if (cards.length === 0) {
    if (!props.showMissingNote) return null;
    return (
      <section
        aria-label="Run details"
        className="rounded-xl border border-slate-700/40 bg-slate-900/30 px-4 py-3"
      >
        <p className="text-[11px] text-slate-500 leading-snug">
          Power, stride, and form metrics weren&apos;t captured for this run.
        </p>
      </section>
    );
  }

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
