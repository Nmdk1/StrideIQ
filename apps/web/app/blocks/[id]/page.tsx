'use client';

/**
 * Block-over-block compare page — Phase 7
 *
 * Side-by-side periodization comparison: focus block vs the most recent
 * prior comparable block. Uses GET /v1/blocks/{id}/compare.
 *
 * Visual treatment:
 *   - Left/right columns, identical structure for direct visual scan.
 *   - Weekly volume bars stacked (same y-scale across both blocks so a
 *     taller bar means more volume regardless of which side).
 *   - Workout-type composition rendered as a horizontal proportion bar.
 *   - Aggregate deltas in a sticky strip up top: emerald = better, amber
 *     = worse, neutral = no opinion.
 *   - Per-workout-type pace deltas inline at the bottom.
 *
 * Suppression: when there is no prior block, the focus is shown solo
 * with an explicit "no previous block to compare yet" notice — never
 * fabricates a comparison.
 */

import React, { useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useUnits } from '@/lib/context/UnitsContext';

interface WeekStat {
  week_index: number;
  iso_week_start: string;
  total_distance_m: number;
  run_count: number;
  quality_count: number;
  easy_count: number;
  longest_run_m: number;
}

interface BlockSide {
  id: string;
  phase: string;
  start_date: string;
  end_date: string;
  weeks: number;
  total_distance_m: number;
  total_duration_s: number;
  run_count: number;
  quality_pct: number;
  peak_week_distance_m: number;
  longest_run_m: number | null;
  dominant_workout_types: string[];
  goal_event_name: string | null;
  week_series: WeekStat[];
}

interface WorkoutTypeCompare {
  workout_type: string;
  a_count: number;
  b_count: number;
  a_total_distance_m: number;
  b_total_distance_m: number;
  a_avg_pace_s_per_km: number | null;
  b_avg_pace_s_per_km: number | null;
  delta_pace_s_per_km: number | null;
  delta_count: number;
}

interface BlockCompareResponse {
  a: BlockSide;
  b: BlockSide;
  same_phase: boolean;
  workout_type_compare: WorkoutTypeCompare[];
  deltas: Record<string, number>;
  suppressions: { kind: string; reason: string }[];
}

const PHASE_BG: Record<string, string> = {
  base: 'bg-sky-500/10 border-sky-500/30',
  build: 'bg-emerald-500/10 border-emerald-500/30',
  peak: 'bg-amber-500/10 border-amber-500/30',
  taper: 'bg-violet-500/10 border-violet-500/30',
  race: 'bg-rose-500/10 border-rose-500/30',
  recovery: 'bg-slate-500/10 border-slate-500/30',
  off: 'bg-slate-700/20 border-slate-600/30',
};

export default function BlockComparePage() {
  return (
    <ProtectedRoute>
      <BlockComparePageInner />
    </ProtectedRoute>
  );
}

function BlockComparePageInner() {
  const params = useParams();
  const blockId = params.id as string;
  const { token } = useAuth();
  const { formatDistance, formatPace } = useUnits();

  const { data, isLoading, error } = useQuery<BlockCompareResponse>({
    queryKey: ['block-compare', blockId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/blocks/${blockId}/compare`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error('Failed to fetch comparison');
      return res.json();
    },
    enabled: !!token && !!blockId,
  });

  // Build a shared y-scale across both blocks' weekly bars.
  const sharedMax = useMemo(() => {
    if (!data) return 0;
    const all = [...data.a.week_series, ...data.b.week_series].map(
      (w) => w.total_distance_m
    );
    return Math.max(0, ...all);
  }, [data]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
        <div className="max-w-6xl mx-auto space-y-4">
          <div className="h-8 bg-slate-800 rounded w-1/3 animate-pulse" />
          <div className="h-64 bg-slate-800/40 rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
        <div className="max-w-3xl mx-auto">
          <div className="px-4 py-6 bg-rose-900/20 border border-rose-700/30 rounded-lg text-sm text-rose-300">
            Could not load block comparison.{' '}
            <Link href="/blocks" className="underline">
              Back to blocks
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const noPrev = data.suppressions.some((s) => s.kind === 'previous_block');

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-4">
          <Link href="/blocks" className="text-xs text-slate-400 hover:text-emerald-300">
            ← All blocks
          </Link>
        </div>

        {noPrev ? (
          <NoPreviousBlock focus={data.b} formatDistance={formatDistance} />
        ) : (
          <>
            <DeltaStrip deltas={data.deltas} samePhase={data.same_phase} a={data.a} b={data.b} formatDistance={formatDistance} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
              <BlockColumn
                side={data.a}
                label="Previous"
                sharedMax={sharedMax}
                formatDistance={formatDistance}
              />
              <BlockColumn
                side={data.b}
                label="This block"
                sharedMax={sharedMax}
                formatDistance={formatDistance}
              />
            </div>

            {data.workout_type_compare.length > 0 && (
              <WorkoutCompare
                rows={data.workout_type_compare}
                formatPace={formatPace}
                formatDistance={formatDistance}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ============================================================ */

function NoPreviousBlock({
  focus,
  formatDistance,
}: {
  focus: BlockSide;
  formatDistance: (m: number) => string;
}) {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">
        {focus.phase[0].toUpperCase() + focus.phase.slice(1)} block
      </h1>
      <p className="text-sm text-slate-400 mt-1">
        {focus.weeks} weeks · {focus.run_count} runs · {formatDistance(focus.total_distance_m)}
      </p>
      <div className="mt-6 px-4 py-6 bg-slate-800/30 border border-slate-700/30 rounded-lg text-sm text-slate-300">
        No previous block detected to compare against. Once you complete another
        full block of training, it will surface here automatically with
        side-by-side periodization.
      </div>
    </div>
  );
}

/* ============================================================ */

function DeltaStrip({
  deltas,
  samePhase,
  a,
  b,
  formatDistance,
}: {
  deltas: Record<string, number>;
  samePhase: boolean;
  a: BlockSide;
  b: BlockSide;
  formatDistance: (m: number) => string;
}) {
  const dist = deltas.total_distance_m ?? 0;
  const peak = deltas.peak_week_distance_m ?? 0;
  const runs = deltas.run_count ?? 0;
  const quality = deltas.quality_pct ?? 0;

  return (
    <header className="border-l-2 border-emerald-500 pl-4">
      <p className="text-[11px] uppercase tracking-wider text-emerald-400">
        Block-over-block
      </p>
      <h1 className="text-2xl font-bold text-white mt-1">
        {b.phase[0].toUpperCase() + b.phase.slice(1)} block
        {b.weeks ? ` · ${b.weeks} weeks` : ''}
      </h1>
      <p className="text-sm text-slate-400 mt-0.5">
        Comparing to {samePhase ? 'previous' : 'last'}{' '}
        <span className="uppercase">{a.phase}</span> block
        {!samePhase && ' (different phase)'}
      </p>

      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        <DeltaTile label="Total volume" delta={dist} formatter={(v) => formatDistance(Math.abs(v))} />
        <DeltaTile label="Peak week" delta={peak} formatter={(v) => formatDistance(Math.abs(v))} />
        <DeltaTile label="Run count" delta={runs} formatter={(v) => `${Math.abs(Math.round(v))} runs`} />
        <DeltaTile
          label="Quality %"
          delta={quality}
          formatter={(v) => `${Math.abs(Math.round(v))} pp`}
        />
      </div>
    </header>
  );
}

function DeltaTile({
  label,
  delta,
  formatter,
}: {
  label: string;
  delta: number;
  formatter: (v: number) => string;
}) {
  const isUp = delta > 0;
  const isDown = delta < 0;
  const arrow = isUp ? '↑' : isDown ? '↓' : '·';
  // For volume / run count: more = neutral-to-positive; we color emerald.
  // For quality %: more = clearly positive; emerald.
  // We don't editorialize that "more is better" for fatigue — just show direction.
  const color = isUp ? 'text-emerald-300' : isDown ? 'text-amber-300' : 'text-slate-400';
  return (
    <div className="px-3 py-2.5 bg-slate-800/40 border border-slate-700/30 rounded-lg">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={`text-base font-bold tabular-nums mt-0.5 ${color}`}>
        {arrow} {formatter(delta)}
      </p>
    </div>
  );
}

/* ============================================================ */

function BlockColumn({
  side,
  label,
  sharedMax,
  formatDistance,
}: {
  side: BlockSide;
  label: string;
  sharedMax: number;
  formatDistance: (m: number) => string;
}) {
  const phaseClass = PHASE_BG[side.phase] || PHASE_BG.off;
  return (
    <section
      className={`rounded-lg border ${phaseClass} overflow-hidden`}
    >
      <header className="px-4 py-3 border-b border-slate-700/30">
        <p className="text-[10px] uppercase tracking-wider text-slate-400">{label}</p>
        <div className="flex items-baseline justify-between gap-3 mt-0.5">
          <h2 className="text-lg font-bold text-white">
            {side.phase[0].toUpperCase() + side.phase.slice(1)}
          </h2>
          <span className="text-[11px] text-slate-400 tabular-nums">
            {side.start_date} → {side.end_date}
          </span>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-slate-300 tabular-nums">
          <span>
            <span className="text-slate-500 block uppercase tracking-wide text-[9px]">Total</span>
            {formatDistance(side.total_distance_m)}
          </span>
          <span>
            <span className="text-slate-500 block uppercase tracking-wide text-[9px]">Peak week</span>
            {formatDistance(side.peak_week_distance_m)}
          </span>
          <span>
            <span className="text-slate-500 block uppercase tracking-wide text-[9px]">Quality</span>
            {side.quality_pct}%
          </span>
        </div>
      </header>

      <div className="p-4">
        <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">
          Weekly volume
        </p>
        <WeeklyBars weeks={side.week_series} sharedMax={sharedMax} formatDistance={formatDistance} />
      </div>
    </section>
  );
}

function WeeklyBars({
  weeks,
  sharedMax,
  formatDistance,
}: {
  weeks: WeekStat[];
  sharedMax: number;
  formatDistance: (m: number) => string;
}) {
  if (weeks.length === 0 || sharedMax === 0) {
    return <div className="text-xs text-slate-500 italic">No weekly data.</div>;
  }
  return (
    <div className="flex items-end gap-1.5 h-32">
      {weeks.map((w) => {
        const pct = (w.total_distance_m / sharedMax) * 100;
        const qualityPct =
          w.run_count > 0 ? (w.quality_count / w.run_count) * 100 : 0;
        return (
          <div
            key={w.week_index}
            className="flex-1 flex flex-col items-center gap-1 group"
            title={`Week of ${w.iso_week_start}: ${formatDistance(w.total_distance_m)} · ${w.run_count} runs (${w.quality_count} quality)`}
          >
            <div className="w-full bg-slate-700/30 rounded-sm flex flex-col-reverse h-full overflow-hidden">
              <div
                className="bg-slate-500 group-hover:bg-slate-400 transition-colors"
                style={{ height: `${pct}%` }}
              >
                {qualityPct > 0 && (
                  <div
                    className="bg-emerald-400/70"
                    style={{ height: `${qualityPct}%` }}
                  />
                )}
              </div>
            </div>
            <span className="text-[9px] text-slate-500 tabular-nums">
              {w.week_index + 1}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ============================================================ */

function WorkoutCompare({
  rows,
  formatPace,
  formatDistance,
}: {
  rows: WorkoutTypeCompare[];
  formatPace: (s: number | null) => string;
  formatDistance: (m: number) => string;
}) {
  return (
    <section className="mt-8 rounded-lg bg-slate-800/30 border border-slate-700/30 overflow-hidden">
      <header className="px-4 py-2.5 border-b border-slate-700/30">
        <h3 className="text-sm font-semibold text-slate-200">Workout type comparison</h3>
      </header>
      <div className="divide-y divide-slate-700/20">
        {rows.map((r) => (
          <WorkoutRow key={r.workout_type} row={r} formatPace={formatPace} formatDistance={formatDistance} />
        ))}
      </div>
    </section>
  );
}

function WorkoutRow({
  row,
  formatPace,
  formatDistance,
}: {
  row: WorkoutTypeCompare;
  formatPace: (s: number | null) => string;
  formatDistance: (m: number) => string;
}) {
  const delta = row.delta_pace_s_per_km;
  const isFaster = delta !== null && delta < 0;
  const isSlower = delta !== null && delta > 0;
  const deltaColor = isFaster ? 'text-emerald-400' : isSlower ? 'text-amber-400' : 'text-slate-400';
  const deltaLabel =
    delta === null
      ? 'no pace data'
      : `${delta > 0 ? '+' : ''}${Math.round(delta)}s/km`;

  return (
    <div className="grid grid-cols-12 items-center gap-3 px-4 py-3">
      <div className="col-span-3">
        <p className="text-sm text-white">{row.workout_type.replace(/_/g, ' ')}</p>
        <p className="text-[10px] text-slate-500 tabular-nums">
          {row.a_count} → {row.b_count} runs
        </p>
      </div>
      <div className="col-span-3 text-xs text-slate-300 tabular-nums">
        <p>
          <span className="text-slate-500">Prev </span>
          {formatPace(row.a_avg_pace_s_per_km)} ·{' '}
          {formatDistance(row.a_total_distance_m)}
        </p>
      </div>
      <div className="col-span-3 text-xs text-slate-300 tabular-nums">
        <p>
          <span className="text-slate-500">This </span>
          {formatPace(row.b_avg_pace_s_per_km)} ·{' '}
          {formatDistance(row.b_total_distance_m)}
        </p>
      </div>
      <div className={`col-span-3 text-right text-sm font-semibold tabular-nums ${deltaColor}`}>
        {deltaLabel}
      </div>
    </div>
  );
}
