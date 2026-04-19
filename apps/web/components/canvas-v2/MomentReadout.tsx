'use client';

/**
 * MomentReadout — horizontal strip that shows the moment under the cursor:
 * Distance (with elapsed time) · Pace · Grade · HR · Cadence.
 *
 * Distance is leftmost because it answers "where am I in the run?" before
 * the others answer "what was happening?" Empty until first hover, fills
 * on scrub. Stays empty (not duplicated with the always-on summary cards
 * at the top of the page) so this row reads as a hover affordance.
 */

import React, { useMemo } from 'react';
import { useScrubState } from './hooks/useScrubState';
import type { TrackPoint } from './hooks/useResampledTrack';
import { useUnits } from '@/lib/context/UnitsContext';

export interface MomentReadoutProps {
  track: TrackPoint[];
}

function paceSecPerKmToMiles(sec: number | null): string {
  if (sec === null || !Number.isFinite(sec) || sec <= 0) return '—';
  const secPerMile = sec * 1.609344;
  const m = Math.floor(secPerMile / 60);
  const s = Math.round(secPerMile % 60);
  return `${m}:${s.toString().padStart(2, '0')}/mi`;
}

function gradePct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function hrBpm(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—';
  return `${Math.round(v)} bpm`;
}

function cadenceSpm(v: number | null): string {
  if (v === null || !Number.isFinite(v) || v <= 0) return '—';
  // Some sources record per-leg cadence; double if low.
  const spm = v < 120 ? v * 2 : v;
  return `${Math.round(spm)} spm`;
}

function elapsedTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function pickAt(track: TrackPoint[], t: number): TrackPoint | null {
  if (track.length === 0) return null;
  const target = Math.max(0, Math.min(1, t));
  let lo = 0;
  let hi = track.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (track[mid].t < target) lo = mid + 1;
    else hi = mid;
  }
  return track[lo] ?? null;
}

export function MomentReadout({ track }: MomentReadoutProps) {
  const { position } = useScrubState();
  const point = useMemo(() => (position === null ? null : pickAt(track, position)), [position, track]);
  const { formatDistance } = useUnits();

  const distanceText = point
    ? formatDistance(point.distanceM ?? null, 2)
    : '—';
  const timeText = point ? elapsedTime(point.timeS) : '—';

  return (
    <div
      className={`flex items-stretch justify-between gap-3 px-4 py-2 rounded-lg border border-slate-800/60 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-150 ${
        point ? 'opacity-100' : 'opacity-30'
      }`}
      aria-live="polite"
    >
      <DistanceField distance={distanceText} time={timeText} />
      <Field label="Pace" value={paceSecPerKmToMiles(point?.pace ?? null)} accent="emerald" />
      <Field label="Grade" value={gradePct(point?.grade ?? null)} accent="amber" />
      <Field label="HR" value={hrBpm(point?.hr ?? null)} accent="rose" />
      <Field label="Cadence" value={cadenceSpm(point?.cadence ?? null)} accent="sky" />
    </div>
  );
}

function DistanceField({ distance, time }: { distance: string; time: string }) {
  return (
    <div className="flex flex-col items-center min-w-0 flex-1">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">Distance</span>
      <span className="text-sm sm:text-base font-semibold tabular-nums text-slate-100">{distance}</span>
      <span className="text-[10px] tabular-nums text-slate-500">{time}</span>
    </div>
  );
}

function Field({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: 'emerald' | 'amber' | 'rose' | 'sky';
}) {
  const accentClass = {
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    rose: 'text-rose-400',
    sky: 'text-sky-400',
  }[accent];

  return (
    <div className="flex flex-col items-center min-w-0 flex-1">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
      <span className={`text-sm sm:text-base font-semibold tabular-nums ${accentClass}`}>{value}</span>
    </div>
  );
}
