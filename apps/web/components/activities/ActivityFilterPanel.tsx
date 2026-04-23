/**
 * ActivityFilterPanel — visual-first filter strip for the activities list.
 *
 * Replaces the legacy 4-column dropdown grid with:
 *   - workout-type chip strip (multi-select with live counts)
 *   - brushable distribution histograms for distance, dew point, temp,
 *     elevation gain — each rendered ONLY when the athlete has ≥5 values
 *     in that dimension (suppression rule)
 *
 * The "filter is the histogram" — the athlete sees their distribution and
 * brushes a range directly. They never type a number.
 *
 * Spec: docs/specs/phase1_filters_design.md
 */

'use client';

import { useMemo } from 'react';
import { useFilterDistributions } from '@/lib/hooks/queries/activities';
import { BrushableHistogram, type BrushRange } from './BrushableHistogram';
import { useUnits } from '@/lib/context/UnitsContext';

export interface ActivityFiltersState {
  workout_types: string[]; // empty = all
  distance_m: BrushRange;
  temp_f: BrushRange;
  dew_point_f: BrushRange;
  elev_gain_m: BrushRange;
}

export const EMPTY_FILTERS: ActivityFiltersState = {
  workout_types: [],
  distance_m: { min: null, max: null },
  temp_f: { min: null, max: null },
  dew_point_f: { min: null, max: null },
  elev_gain_m: { min: null, max: null },
};

interface ActivityFilterPanelProps {
  value: ActivityFiltersState;
  onChange: (next: ActivityFiltersState) => void;
}

const WORKOUT_TYPE_LABEL: Record<string, string> = {
  easy_run: 'Easy',
  long_run: 'Long',
  tempo_run: 'Tempo',
  threshold: 'Threshold',
  cruise_intervals: 'Cruise Int.',
  vo2_max_intervals: 'VO2',
  hill_repeats: 'Hill Reps',
  recovery_run: 'Recovery',
  race: 'Race',
  fartlek: 'Fartlek',
  progression_run: 'Progression',
  speed_intervals: 'Speed Int.',
  workout: 'Workout',
};

function prettyWorkoutLabel(value: string): string {
  if (WORKOUT_TYPE_LABEL[value]) return WORKOUT_TYPE_LABEL[value];
  return value
    .split('_')
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' ');
}

export function ActivityFilterPanel({ value, onChange }: ActivityFilterPanelProps) {
  const { data, isLoading } = useFilterDistributions();
  const { convertDistance, convertElevation, distanceUnitShort, elevationUnit } = useUnits();

  const formatDistance = useMemo(() => {
    return (lo: number, hi: number) => {
      return `${convertDistance(lo).toFixed(1)}–${convertDistance(hi).toFixed(1)} ${distanceUnitShort}`;
    };
  }, [convertDistance, distanceUnitShort]);

  const formatElev = useMemo(() => {
    return (lo: number, hi: number) => {
      return `${Math.round(convertElevation(lo))}–${Math.round(convertElevation(hi))} ${elevationUnit}`;
    };
  }, [convertElevation, elevationUnit]);

  const formatTemp = (lo: number, hi: number) => `${Math.round(lo)}–${Math.round(hi)} °F`;

  if (isLoading || !data) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-6 text-xs text-slate-500">
        Loading distributions…
      </div>
    );
  }

  // Suppress entire panel if athlete has nothing to filter on
  const hasAnyHistogram =
    data.distance_m.available ||
    data.temp_f.available ||
    data.dew_point_f.available ||
    data.elevation_gain_m.available;
  const hasAnyChips = data.workout_types.length >= 2;

  if (!hasAnyHistogram && !hasAnyChips) {
    return null;
  }

  // ----- chip strip handlers -----
  const toggleWorkoutType = (wt: string) => {
    const isAllOnNow = value.workout_types.length === 0;
    const allTypes = data.workout_types.map((w) => w.value);
    if (isAllOnNow) {
      // From all-on, tapping one chip activates only the OTHER chips' inverse —
      // semantically: "include just this type." So filter down to [wt].
      onChange({ ...value, workout_types: [wt] });
      return;
    }
    const exists = value.workout_types.includes(wt);
    let next: string[];
    if (exists) {
      next = value.workout_types.filter((t) => t !== wt);
    } else {
      next = [...value.workout_types, wt];
    }
    // If the result is "every type selected" we collapse to [] (= no filter).
    if (next.length === allTypes.length) next = [];
    onChange({ ...value, workout_types: next });
  };

  const setRange = (
    field: 'distance_m' | 'temp_f' | 'dew_point_f' | 'elev_gain_m',
    next: BrushRange,
  ) => {
    onChange({ ...value, [field]: next });
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-6">
      {hasAnyChips && (
        <div className="flex items-center gap-2 flex-wrap mb-3">
          {data.workout_types.map((wt) => {
            const isAllOn = value.workout_types.length === 0;
            const isActive = isAllOn || value.workout_types.includes(wt.value);
            return (
              <button
                key={wt.value}
                type="button"
                onClick={() => toggleWorkoutType(wt.value)}
                className={`text-xs px-2.5 py-1 rounded-full transition-colors border ${
                  isActive
                    ? 'bg-orange-500/15 border-orange-500/60 text-orange-200'
                    : 'bg-slate-900/50 border-slate-700 text-slate-500 hover:text-slate-300'
                }`}
                aria-pressed={isActive}
              >
                {prettyWorkoutLabel(wt.value)}
                <span className="ml-1.5 text-[10px] tabular-nums opacity-70">
                  {wt.count}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {hasAnyHistogram && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-5 gap-y-3">
          {data.distance_m.available && data.distance_m.buckets && (
            <BrushableHistogram
              label="Distance"
              buckets={data.distance_m.buckets}
              domainMin={data.distance_m.min!}
              domainMax={data.distance_m.max!}
              value={value.distance_m}
              onChange={(r) => setRange('distance_m', r)}
              formatRange={formatDistance}
            />
          )}
          {data.dew_point_f.available && data.dew_point_f.buckets && (
            <BrushableHistogram
              label="Dew Point"
              buckets={data.dew_point_f.buckets}
              domainMin={data.dew_point_f.min!}
              domainMax={data.dew_point_f.max!}
              value={value.dew_point_f}
              onChange={(r) => setRange('dew_point_f', r)}
              formatRange={formatTemp}
            />
          )}
          {data.temp_f.available && data.temp_f.buckets && (
            <BrushableHistogram
              label="Temperature"
              buckets={data.temp_f.buckets}
              domainMin={data.temp_f.min!}
              domainMax={data.temp_f.max!}
              value={value.temp_f}
              onChange={(r) => setRange('temp_f', r)}
              formatRange={formatTemp}
            />
          )}
          {data.elevation_gain_m.available && data.elevation_gain_m.buckets && (
            <BrushableHistogram
              label="Elevation Gain"
              buckets={data.elevation_gain_m.buckets}
              domainMin={data.elevation_gain_m.min!}
              domainMax={data.elevation_gain_m.max!}
              value={value.elev_gain_m}
              onChange={(r) => setRange('elev_gain_m', r)}
              formatRange={formatElev}
            />
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Convert a `ActivityFiltersState` into the URL query params
 * the backend expects on `/v1/activities`.
 */
export function filtersToParams(state: ActivityFiltersState): Record<string, string | undefined> {
  const out: Record<string, string | undefined> = {};
  if (state.workout_types.length > 0) {
    out.workout_type = state.workout_types.join(',');
  }
  if (state.distance_m.min != null) out.min_distance_m = String(Math.round(state.distance_m.min));
  if (state.distance_m.max != null) out.max_distance_m = String(Math.round(state.distance_m.max));
  if (state.temp_f.min != null) out.temp_min = String(state.temp_f.min);
  if (state.temp_f.max != null) out.temp_max = String(state.temp_f.max);
  if (state.dew_point_f.min != null) out.dew_min = String(state.dew_point_f.min);
  if (state.dew_point_f.max != null) out.dew_max = String(state.dew_point_f.max);
  if (state.elev_gain_m.min != null) out.elev_gain_min = String(state.elev_gain_m.min);
  if (state.elev_gain_m.max != null) out.elev_gain_max = String(state.elev_gain_m.max);
  return out;
}

/**
 * Reverse of `filtersToParams` — used to deserialize URL query params
 * back into an ActivityFiltersState on page load.
 */
export function paramsToFilters(params: URLSearchParams): ActivityFiltersState {
  const num = (key: string) => {
    const v = params.get(key);
    if (v == null || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  return {
    workout_types: (params.get('workout_type') || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    distance_m: { min: num('min_distance_m'), max: num('max_distance_m') },
    temp_f: { min: num('temp_min'), max: num('temp_max') },
    dew_point_f: { min: num('dew_min'), max: num('dew_max') },
    elev_gain_m: { min: num('elev_gain_min'), max: num('elev_gain_max') },
  };
}

export function isFiltersActive(state: ActivityFiltersState): boolean {
  if (state.workout_types.length > 0) return true;
  for (const r of [state.distance_m, state.temp_f, state.dew_point_f, state.elev_gain_m]) {
    if (r.min != null || r.max != null) return true;
  }
  return false;
}
