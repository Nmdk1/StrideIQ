'use client';

import React from 'react';
import type { DriftAnalysis, PlanComparison } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { useUnits } from '@/lib/context/UnitsContext';

interface AnalysisTabPanelProps {
  drift: DriftAnalysis | null;
  planComparison: PlanComparison | null;
}

export function AnalysisTabPanel({ drift, planComparison }: AnalysisTabPanelProps) {
  const { formatDistance, formatPace, distanceUnitShort } = useUnits();

  const hasDrift = drift && (
    drift.cardiac_pct != null || drift.pace_pct != null || drift.cadence_trend_bpm_per_km != null
  );

  const formatMinutesToDuration = (minutes: number): string => {
    const totalSeconds = Math.round(minutes * 60);
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!hasDrift && !planComparison) {
    return (
      <p className="text-slate-500 text-sm py-10 px-2">
        No analysis data available for this activity.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {hasDrift && drift && (
        <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Drift</p>
          <div className="space-y-1">
            {drift.cardiac_pct != null && (
              <div className="flex justify-between text-sm text-slate-300 bg-slate-800/30 rounded px-2 py-1.5">
                <span className="text-slate-400">Cardiac Drift</span>
                <span className="font-medium tabular-nums">{drift.cardiac_pct.toFixed(1)}%</span>
              </div>
            )}
            {drift.pace_pct != null && (
              <div className="flex justify-between text-sm text-slate-300 bg-slate-800/30 rounded px-2 py-1.5">
                <span className="text-slate-400">Pace Drift</span>
                <span className="font-medium tabular-nums">{drift.pace_pct.toFixed(1)}%</span>
              </div>
            )}
            {drift.cadence_trend_bpm_per_km != null && (
              <div className="flex justify-between text-sm text-slate-300 bg-slate-800/30 rounded px-2 py-1.5">
                <span className="text-slate-400">Cadence Trend</span>
                <span className="font-medium tabular-nums">{drift.cadence_trend_bpm_per_km.toFixed(1)} spm/{distanceUnitShort}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {planComparison && (
        <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Plan vs Actual</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {planComparison.planned_duration_min != null && planComparison.actual_duration_min != null && (
              <PlanCell
                label="Duration"
                planned={formatMinutesToDuration(planComparison.planned_duration_min)}
                actual={formatMinutesToDuration(planComparison.actual_duration_min)}
              />
            )}
            {planComparison.planned_distance_km != null && planComparison.actual_distance_km != null && (
              <PlanCell
                label="Distance"
                planned={formatDistance(planComparison.planned_distance_km * 1000)}
                actual={formatDistance(planComparison.actual_distance_km * 1000)}
              />
            )}
            {planComparison.planned_pace_s_km != null && planComparison.actual_pace_s_km != null && (
              <PlanCell
                label="Pace"
                planned={formatPace(planComparison.planned_pace_s_km)}
                actual={formatPace(planComparison.actual_pace_s_km)}
              />
            )}
            {planComparison.planned_interval_count != null && planComparison.detected_work_count != null && (
              <PlanCell
                label="Intervals"
                planned={String(planComparison.planned_interval_count)}
                actual={String(planComparison.detected_work_count)}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PlanCell({ label, planned, actual }: { label: string; planned: string; actual: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-sm text-white font-medium">{actual}</p>
      <p className="text-xs text-slate-500">planned: {planned}</p>
    </div>
  );
}
