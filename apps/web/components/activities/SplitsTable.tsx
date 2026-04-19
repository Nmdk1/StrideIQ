'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import type { Split } from '@/lib/types/splits';
import { GarminBadge } from '@/components/integrations/GarminBadge';

const MILES_TO_KM = 1.60934;
const M_TO_FT = 3.28084;

const COLUMN_PREFS_KEY = 'splits:columnPrefs:v1';

export function normalizeCadenceToSpm(raw: number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const v = Number(raw);
  if (!isFinite(v) || v <= 0) return null;
  // Strava running cadence often comes through as "strides/min" (~85-100).
  // Most athletes think in steps/min (~170-200), so convert if it looks like half-cadence.
  return v < 120 ? v * 2 : v;
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return '—';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.round(seconds % 60);
  if (hrs > 0) return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function paceSecondsPerKm(timeS: number | null | undefined, distanceM: number | null | undefined): number | null {
  if (!timeS || !distanceM || distanceM <= 0) return null;
  return timeS / (distanceM / 1000);
}

function gapSecondsPerKmFromPerMile(gapSecondsPerMile: number | null | undefined): number | null {
  if (!gapSecondsPerMile || gapSecondsPerMile <= 0) return null;
  return gapSecondsPerMile / MILES_TO_KM;
}

function fmt(v: number | null | undefined, digits = 0, suffix = ''): string {
  if (v === null || v === undefined || !isFinite(v)) return '—';
  return `${v.toFixed(digits)}${suffix}`;
}

// --- Optional columns: keys, labels, predicate (any split has data) ---

type OptionalColumnKey =
  | 'maxHr'
  | 'ascent'
  | 'descent'
  | 'power'
  | 'stride'
  | 'gct'
  | 'vo'
  | 'vr';

const OPTIONAL_COLUMNS: ReadonlyArray<{
  key: OptionalColumnKey;
  label: string;
  has: (s: Split) => boolean;
}> = [
  { key: 'maxHr',   label: 'Max HR',     has: (s) => s.max_heartrate != null },
  { key: 'ascent',  label: 'Ascent',     has: (s) => s.total_ascent_m != null },
  { key: 'descent', label: 'Descent',    has: (s) => s.total_descent_m != null },
  { key: 'power',   label: 'Power',      has: (s) => s.avg_power_w != null },
  { key: 'stride',  label: 'Stride',     has: (s) => s.avg_stride_length_m != null },
  { key: 'gct',     label: 'GCT',        has: (s) => s.avg_ground_contact_ms != null },
  { key: 'vo',      label: 'Vert Osc',   has: (s) => s.avg_vertical_oscillation_cm != null },
  { key: 'vr',      label: 'Vert Ratio', has: (s) => s.avg_vertical_ratio_pct != null },
];

export interface SplitsTableProps {
  splits: Split[];
  /** Data source: 'garmin' | 'strava' | null */
  provider?: string | null;
  /** Device model for Garmin attribution (e.g. "forerunner165"). Optional — logo alone is shown if absent. */
  deviceName?: string | null;
  /** Optional: callback when mouse enters a split row (index into splits array) */
  onRowHover?: (index: number | null) => void;
  /** Optional: ref map for direct DOM manipulation of row highlights */
  rowRefs?: React.MutableRefObject<Map<number, HTMLTableRowElement>>;
}

export function SplitsTable({ splits, provider, deviceName, onRowHover, rowRefs }: SplitsTableProps) {
  const { formatDistance, formatPace, units } = useUnits();
  const isImperial = units === 'imperial';

  const availableOptional = useMemo(
    () => OPTIONAL_COLUMNS.filter((c) => splits.some((s) => c.has(s))),
    [splits],
  );

  const [enabled, setEnabled] = useState<Set<OptionalColumnKey>>(() => new Set());
  const [pickerOpen, setPickerOpen] = useState(false);

  // Restore prefs once on mount.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(COLUMN_PREFS_KEY);
      if (raw) setEnabled(new Set(JSON.parse(raw) as OptionalColumnKey[]));
    } catch {
      // localStorage may be unavailable (private mode); fall back to none.
    }
  }, []);

  // Persist prefs whenever they change.
  useEffect(() => {
    try {
      window.localStorage.setItem(COLUMN_PREFS_KEY, JSON.stringify(Array.from(enabled)));
    } catch {
      // no-op
    }
  }, [enabled]);

  if (!splits?.length) return null;

  const toggleCol = (k: OptionalColumnKey) => {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k); else next.add(k);
      return next;
    });
  };

  let cumulativeTime = 0;
  const rows = splits
    .map((s) => {
      const splitTime = s.moving_time ?? s.elapsed_time ?? null;
      if (splitTime) cumulativeTime += splitTime;
      const paceSecKm = paceSecondsPerKm(splitTime, s.distance);
      const gapSecKm = gapSecondsPerKmFromPerMile(s.gap_seconds_per_mile);
      const cadenceSpm = normalizeCadenceToSpm(s.average_cadence);
      return {
        ...s,
        splitTime,
        cumulativeTime: splitTime ? cumulativeTime : null,
        paceSecKm,
        gapSecKm,
        cadenceSpm,
      };
    })
    .filter((r) => r.splitTime !== null && r.distance !== null);

  const bestPace = rows
    .map((r) => r.paceSecKm)
    .filter((v): v is number => typeof v === 'number' && isFinite(v))
    .reduce((min, v) => (v < min ? v : min), Number.POSITIVE_INFINITY);

  const showCol = (k: OptionalColumnKey) => enabled.has(k);

  return (
    <div className="mt-5">
      {availableOptional.length > 0 && (
        <div className="mb-2 flex items-center justify-end gap-2 relative">
          <button
            type="button"
            onClick={() => setPickerOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-700/60 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800/60 transition"
            aria-haspopup="menu"
            aria-expanded={pickerOpen}
          >
            <span aria-hidden>⚙</span>
            <span>Columns</span>
            {enabled.size > 0 && (
              <span className="ml-0.5 inline-flex items-center justify-center min-w-[1.25rem] rounded-full bg-emerald-500/30 px-1.5 text-[0.65rem] text-emerald-200">
                +{enabled.size}
              </span>
            )}
          </button>
          {pickerOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg border border-slate-700/60 bg-slate-900/95 p-2 shadow-xl backdrop-blur"
            >
              <p className="mb-1.5 px-1 text-[0.65rem] uppercase tracking-wider text-slate-500">
                Show columns
              </p>
              {availableOptional.map((c) => (
                <label
                  key={c.key}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-slate-200 hover:bg-slate-800/60"
                >
                  <input
                    type="checkbox"
                    checked={enabled.has(c.key)}
                    onChange={() => toggleCol(c.key)}
                    className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500/50"
                  />
                  <span>{c.label}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-700/50">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/40 text-slate-300">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Split</th>
              <th className="px-3 py-2 text-left font-semibold">Dist</th>
              <th className="px-3 py-2 text-left font-semibold">Time</th>
              <th className="px-3 py-2 text-left font-semibold">Pace</th>
              <th className="px-3 py-2 text-left font-semibold">GAP</th>
              <th className="px-3 py-2 text-left font-semibold">Avg HR</th>
              <th className="px-3 py-2 text-left font-semibold">Cadence</th>
              {showCol('maxHr')   && <th className="px-3 py-2 text-left font-semibold">Max HR</th>}
              {showCol('ascent')  && <th className="px-3 py-2 text-left font-semibold">{isImperial ? 'Ascent (ft)' : 'Ascent (m)'}</th>}
              {showCol('descent') && <th className="px-3 py-2 text-left font-semibold">{isImperial ? 'Descent (ft)' : 'Descent (m)'}</th>}
              {showCol('power')   && <th className="px-3 py-2 text-left font-semibold">Power (W)</th>}
              {showCol('stride')  && <th className="px-3 py-2 text-left font-semibold">Stride (m)</th>}
              {showCol('gct')     && <th className="px-3 py-2 text-left font-semibold">GCT (ms)</th>}
              {showCol('vo')      && <th className="px-3 py-2 text-left font-semibold">Vert Osc (cm)</th>}
              {showCol('vr')      && <th className="px-3 py-2 text-left font-semibold">Vert Ratio (%)</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-950/20">
            {rows.map((r) => {
              const isBest = typeof r.paceSecKm === 'number' && isFinite(r.paceSecKm) && r.paceSecKm === bestPace;
              return (
                <tr
                  key={r.split_number}
                  className="text-slate-200 transition-colors duration-75"
                  ref={(el) => { if (el && rowRefs) rowRefs.current.set(r.split_number - 1, el); }}
                  onMouseEnter={() => onRowHover?.(r.split_number - 1)}
                  onMouseLeave={() => onRowHover?.(null)}
                >
                  <td className="px-3 py-2 whitespace-nowrap">{r.split_number}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDistance(r.distance, 2)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDuration(r.cumulativeTime)}</td>
                  <td className={`px-3 py-2 whitespace-nowrap ${isBest ? 'font-semibold text-white' : ''}`}>
                    {formatPace(r.paceSecKm)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{r.gapSecKm ? formatPace(r.gapSecKm) : '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{r.average_heartrate ?? '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.cadenceSpm !== null && r.cadenceSpm !== undefined ? Math.round(r.cadenceSpm) : '—'}
                  </td>
                  {showCol('maxHr')   && <td className="px-3 py-2 whitespace-nowrap">{r.max_heartrate ?? '—'}</td>}
                  {showCol('ascent')  && <td className="px-3 py-2 whitespace-nowrap">{r.total_ascent_m == null ? '—' : isImperial ? fmt(r.total_ascent_m * M_TO_FT, 0) : fmt(r.total_ascent_m, 0)}</td>}
                  {showCol('descent') && <td className="px-3 py-2 whitespace-nowrap">{r.total_descent_m == null ? '—' : isImperial ? fmt(r.total_descent_m * M_TO_FT, 0) : fmt(r.total_descent_m, 0)}</td>}
                  {showCol('power')   && <td className="px-3 py-2 whitespace-nowrap">{r.avg_power_w ?? '—'}</td>}
                  {showCol('stride')  && <td className="px-3 py-2 whitespace-nowrap">{fmt(r.avg_stride_length_m, 2)}</td>}
                  {showCol('gct')     && <td className="px-3 py-2 whitespace-nowrap">{fmt(r.avg_ground_contact_ms, 0)}</td>}
                  {showCol('vo')      && <td className="px-3 py-2 whitespace-nowrap">{fmt(r.avg_vertical_oscillation_cm, 1)}</td>}
                  {showCol('vr')      && <td className="px-3 py-2 whitespace-nowrap">{fmt(r.avg_vertical_ratio_pct, 1)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-xs text-slate-500">
        {provider === 'garmin' ? (
          <span className="flex items-center gap-1.5 flex-wrap">
            <GarminBadge deviceName={deviceName} size="sm" />
            <span>· Pace is computed from split distance/time.</span>
          </span>
        ) : (
          <span>
            Splits are sourced from Strava laps (auto-laps or manual laps/intervals). Pace is computed from split distance/time.
          </span>
        )}
      </div>
    </div>
  );
}
