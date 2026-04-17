'use client';

/**
 * Comparable Runs Panel — Phase 5 frontend
 *
 * Visual-first comparison view per founder direction:
 *   - NOT generic cards.
 *   - F1-telemetry-inspired: dense info, sparkline pace bars, delta gradients.
 *   - One horizontal "strip" per tier; one row per comparable run.
 *   - Suppressions surface honestly when a tier has no data.
 *
 * Backend: GET /v1/activities/{id}/comparables
 * See `apps/api/services/comparison/comparable_runs.py` for tier rules.
 */

import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { useUnits } from '@/lib/context/UnitsContext';

interface ComparableEntry {
  activity_id: string;
  start_time: string | null;
  distance_m: number | null;
  duration_s: number | null;
  avg_pace_s_per_km: number | null;
  avg_hr: number | null;
  workout_type: string | null;
  name: string | null;
  route_id: string | null;
  route_display_name: string | null;
  temperature_f: number | null;
  dew_point_f: number | null;
  elevation_gain_m: number | null;
  days_ago: number | null;
  in_tolerance_heat: boolean;
  in_tolerance_elevation: boolean;
  delta_pace_s_per_km: number | null;
  delta_hr_bpm: number | null;
  delta_distance_m: number | null;
}

interface ComparableTier {
  kind: string;
  label: string;
  entries: ComparableEntry[];
}

interface ComparablesResponse {
  activity_id: string;
  activity_summary: {
    start_time: string | null;
    distance_m: number | null;
    avg_pace_s_per_km: number | null;
    avg_hr: number | null;
    workout_type: string | null;
    route_display_name: string | null;
    temperature_f: number | null;
    dew_point_f: number | null;
  };
  block_summary: {
    phase: string;
    weeks: number;
    run_count: number;
    quality_pct: number;
    goal_event_name: string | null;
  } | null;
  tiers: ComparableTier[];
  suppressions: { kind: string; reason: string }[];
}

export interface ComparablesPanelProps {
  activityId: string;
}

export function ComparablesPanel({ activityId }: ComparablesPanelProps) {
  const { token } = useAuth();
  const { formatPace } = useUnits();

  const { data, isLoading, error } = useQuery<ComparablesResponse>({
    queryKey: ['activity-comparables', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/comparables`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error('Failed to fetch comparables');
      return res.json();
    },
    enabled: !!token && !!activityId,
    staleTime: 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <div key={i} className="h-32 bg-slate-800/40 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="text-sm text-slate-500 italic">
        No comparison data available.
      </div>
    );
  }

  const focus = data.activity_summary;
  const hasTiers = data.tiers.length > 0;

  return (
    <div className="space-y-6">
      {/* Focus header — what we're comparing against */}
      <FocusHeader focus={focus} block={data.block_summary} formatPace={formatPace} />

      {hasTiers ? (
        data.tiers.map((tier) => (
          <TierStrip key={tier.kind} tier={tier} focus={focus} formatPace={formatPace} />
        ))
      ) : (
        <div className="text-sm text-slate-400 italic px-4 py-6 bg-slate-800/30 rounded-lg">
          No comparable runs found yet. As more runs are recorded — same route, same workout
          type, similar conditions — they&apos;ll surface here.
        </div>
      )}

      {data.suppressions.length > 0 && (
        <SuppressionList suppressions={data.suppressions} />
      )}
    </div>
  );
}

/* ============================================================ */

function FocusHeader({
  focus,
  block,
  formatPace,
}: {
  focus: ComparablesResponse['activity_summary'];
  block: ComparablesResponse['block_summary'];
  formatPace: (s: number | null) => string;
}) {
  return (
    <div className="border-l-2 border-emerald-500 pl-4">
      <p className="text-[11px] uppercase tracking-wider text-emerald-400 mb-1">
        Comparing this run
      </p>
      <div className="flex items-baseline gap-4 flex-wrap">
        <span className="text-2xl font-bold text-white tabular-nums">
          {formatPace(focus.avg_pace_s_per_km)}
        </span>
        <span className="text-sm text-slate-400">
          {focus.avg_hr ? `${focus.avg_hr} bpm` : '— bpm'} ·{' '}
          {focus.workout_type
            ? focus.workout_type.replace(/_/g, ' ')
            : 'run'}
          {focus.route_display_name && ` · ${focus.route_display_name}`}
        </span>
      </div>
      {block && (
        <p className="text-[11px] text-slate-500 mt-1.5">
          {block.weeks}-week{' '}
          <span className="uppercase tracking-wide">{block.phase}</span> block
          {block.run_count ? ` · ${block.run_count} runs` : ''}
          {block.quality_pct ? ` · ${block.quality_pct}% quality` : ''}
          {block.goal_event_name && ` → ${block.goal_event_name}`}
        </p>
      )}
    </div>
  );
}

/* ============================================================ */

function TierStrip({
  tier,
  focus,
  formatPace,
}: {
  tier: ComparableTier;
  focus: ComparablesResponse['activity_summary'];
  formatPace: (s: number | null) => string;
}) {
  // Build a shared pace scale so all bars in a tier are visually comparable.
  // Domain: ±60s/km from focus, clamped — captures typical training variance
  // without letting one outlier compress everything else.
  const focusPace = focus.avg_pace_s_per_km;
  const paceRange = useMemo(() => {
    const allPaces = tier.entries
      .map((e) => e.avg_pace_s_per_km)
      .filter((p): p is number => p !== null);
    if (focusPace !== null) allPaces.push(focusPace);
    if (allPaces.length === 0) return { min: 0, max: 0 };
    const min = Math.min(...allPaces);
    const max = Math.max(...allPaces);
    // Pad by 10% so the focus bar never sits at the absolute edge.
    const span = max - min || 30;
    return { min: min - span * 0.1, max: max + span * 0.1 };
  }, [tier.entries, focusPace]);

  return (
    <section className="rounded-lg bg-slate-800/30 border border-slate-700/30 overflow-hidden">
      <header className="px-4 py-2.5 border-b border-slate-700/30 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">{tier.label}</h3>
        <span className="text-[11px] text-slate-500 tabular-nums">
          {tier.entries.length} {tier.entries.length === 1 ? 'run' : 'runs'}
        </span>
      </header>
      <div className="divide-y divide-slate-700/20">
        {tier.entries.map((entry) => (
          <ComparableRow
            key={entry.activity_id}
            entry={entry}
            focusPace={focusPace}
            paceRange={paceRange}
            formatPace={formatPace}
          />
        ))}
      </div>
    </section>
  );
}

/* ============================================================ */

function ComparableRow({
  entry,
  focusPace,
  paceRange,
  formatPace,
}: {
  entry: ComparableEntry;
  focusPace: number | null;
  paceRange: { min: number; max: number };
  formatPace: (s: number | null) => string;
}) {
  const dateLabel = formatRelativeDate(entry.start_time, entry.days_ago);
  const distanceKm = entry.distance_m ? entry.distance_m / 1000 : null;
  const delta = entry.delta_pace_s_per_km;
  const isFaster = delta !== null && delta < 0;
  const isSlower = delta !== null && delta > 0;
  const deltaColor = isFaster
    ? 'text-emerald-400'
    : isSlower
    ? 'text-amber-400'
    : 'text-slate-400';
  const deltaSign = delta !== null && delta > 0 ? '+' : '';

  return (
    <Link
      href={`/activities/${entry.activity_id}`}
      className="grid grid-cols-12 gap-2 items-center px-4 py-3 hover:bg-slate-800/50 transition-colors"
    >
      {/* Date / days ago */}
      <div className="col-span-3 md:col-span-2 min-w-0">
        <p className="text-xs text-slate-300 tabular-nums truncate">{dateLabel.primary}</p>
        <p className="text-[10px] text-slate-500 uppercase tracking-wide">
          {dateLabel.secondary}
        </p>
      </div>

      {/* Pace bar — visual telemetry strip */}
      <div className="col-span-6 md:col-span-7">
        <PaceBar
          pace={entry.avg_pace_s_per_km}
          focusPace={focusPace}
          range={paceRange}
        />
        <div className="flex items-baseline gap-3 mt-1">
          <span className="text-sm font-semibold text-white tabular-nums">
            {formatPace(entry.avg_pace_s_per_km)}
          </span>
          {delta !== null && (
            <span className={`text-[11px] font-medium ${deltaColor} tabular-nums`}>
              {deltaSign}
              {Math.abs(Math.round(delta))}s/km
            </span>
          )}
          {entry.avg_hr !== null && (
            <span className="text-[11px] text-slate-500 tabular-nums">
              {entry.avg_hr} bpm
              {entry.delta_hr_bpm !== null && entry.delta_hr_bpm !== 0 && (
                <span
                  className={
                    entry.delta_hr_bpm < 0 ? 'text-emerald-400/70 ml-1' : 'text-amber-400/70 ml-1'
                  }
                >
                  ({entry.delta_hr_bpm > 0 ? '+' : ''}
                  {entry.delta_hr_bpm})
                </span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Distance + conditions */}
      <div className="col-span-3 md:col-span-3 text-right">
        <p className="text-xs text-slate-300 tabular-nums">
          {distanceKm !== null ? `${distanceKm.toFixed(2)} km` : '—'}
        </p>
        <ConditionsRow entry={entry} />
      </div>
    </Link>
  );
}

function PaceBar({
  pace,
  focusPace,
  range,
}: {
  pace: number | null;
  focusPace: number | null;
  range: { min: number; max: number };
}) {
  if (pace === null || range.max === range.min) {
    return <div className="h-1 bg-slate-700/40 rounded-full" />;
  }
  const span = range.max - range.min;
  const pct = ((pace - range.min) / span) * 100;
  const focusPct = focusPace !== null ? ((focusPace - range.min) / span) * 100 : null;
  // Lower pace s/km = faster; we paint a bar that fills from 0 to pct.
  // Focus baseline marker is rendered as a vertical tick.
  const isFaster = focusPace !== null && pace < focusPace;
  const barColor = isFaster ? 'bg-emerald-400/70' : 'bg-amber-400/60';

  return (
    <div className="relative h-1.5 bg-slate-700/40 rounded-full overflow-hidden">
      <div className={`absolute inset-y-0 left-0 ${barColor}`} style={{ width: `${pct}%` }} />
      {focusPct !== null && (
        <div
          className="absolute inset-y-0 w-px bg-emerald-300"
          style={{ left: `${focusPct}%` }}
          title="this run"
        />
      )}
    </div>
  );
}

function ConditionsRow({ entry }: { entry: ComparableEntry }) {
  const parts: string[] = [];
  if (entry.temperature_f !== null) {
    parts.push(`${Math.round(entry.temperature_f)}°F`);
    if (entry.dew_point_f !== null) {
      parts.push(`dew ${Math.round(entry.dew_point_f)}`);
    }
  }
  if (entry.elevation_gain_m !== null) {
    parts.push(`${Math.round(entry.elevation_gain_m)}m ↑`);
  }
  if (parts.length === 0) return null;
  return (
    <p className="text-[10px] text-slate-500 mt-0.5 tabular-nums">{parts.join(' · ')}</p>
  );
}

function SuppressionList({
  suppressions,
}: {
  suppressions: { kind: string; reason: string }[];
}) {
  return (
    <div className="text-[11px] text-slate-500 space-y-1 px-1">
      <p className="text-slate-400 font-medium uppercase tracking-wider mb-1">
        Not shown
      </p>
      {suppressions.map((s) => (
        <p key={s.kind}>
          <span className="text-slate-400">{labelFor(s.kind)}:</span> {s.reason}
        </p>
      ))}
    </div>
  );
}

/* ============================================================ */
/*                            Helpers                           */
/* ============================================================ */

function formatRelativeDate(
  isoTime: string | null,
  daysAgo: number | null
): { primary: string; secondary: string } {
  if (!isoTime) return { primary: '—', secondary: '' };
  const d = new Date(isoTime);
  const primary = d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
  if (daysAgo === null) return { primary, secondary: '' };
  if (daysAgo === 0) return { primary, secondary: 'today' };
  if (daysAgo === 1) return { primary, secondary: 'yesterday' };
  if (daysAgo < 14) return { primary, secondary: `${daysAgo}d ago` };
  if (daysAgo < 60) return { primary, secondary: `${Math.round(daysAgo / 7)}w ago` };
  if (daysAgo < 365) return { primary, secondary: `${Math.round(daysAgo / 30)}mo ago` };
  const years = daysAgo / 365;
  return { primary, secondary: `${years.toFixed(1)}y ago` };
}

function labelFor(kind: string): string {
  switch (kind) {
    case 'same_route_anniversary':
      return 'Same route, year ago';
    case 'same_route_recent':
      return 'Same route, recent';
    case 'same_type_current_block':
      return 'Same workout, this block';
    case 'same_type_similar_cond':
      return 'Same workout, similar conditions';
    default:
      return kind;
  }
}
