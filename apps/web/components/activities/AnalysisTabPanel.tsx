'use client';

import React from 'react';
import type { DriftAnalysis, PlanComparison, StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { useUnits } from '@/lib/context/UnitsContext';
import { PaceDistribution } from '@/components/activities/PaceDistribution';

interface AnalysisTabPanelProps {
  drift: DriftAnalysis | null;
  planComparison: PlanComparison | null;
  stream: StreamPoint[] | null;
  effortIntensity: number[] | null;
  movingTimeS: number;
}

export function AnalysisTabPanel({ drift, planComparison, stream, effortIntensity, movingTimeS }: AnalysisTabPanelProps) {
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

  const hasEffort = stream && stream.length > 0 && effortIntensity && effortIntensity.length > 0;

  if (!hasDrift && !planComparison && !hasEffort) {
    return (
      <p className="text-slate-500 text-sm py-10 px-2">
        No analysis data available for this activity.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {hasDrift && drift && (
        <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Drift</p>
          <div className="space-y-1.5">
            {drift.cardiac_pct != null && (
              <div className="flex justify-between text-sm text-slate-300 bg-slate-800/40 rounded-md px-3 py-2">
                <span className="text-slate-400">Cardiac Drift</span>
                <span className="font-semibold tabular-nums">{drift.cardiac_pct.toFixed(1)}%</span>
              </div>
            )}
            {drift.pace_pct != null && (
              <div className="flex justify-between text-sm text-slate-300 bg-slate-800/40 rounded-md px-3 py-2">
                <span className="text-slate-400">Pace Drift</span>
                <span className="font-semibold tabular-nums">{drift.pace_pct.toFixed(1)}%</span>
              </div>
            )}
            {drift.cadence_trend_bpm_per_km != null && (
              <div className="flex justify-between text-sm text-slate-300 bg-slate-800/40 rounded-md px-3 py-2">
                <span className="text-slate-400">Cadence Trend</span>
                <span className="font-semibold tabular-nums">{drift.cadence_trend_bpm_per_km.toFixed(1)} spm/{distanceUnitShort}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {hasEffort && stream && effortIntensity && (
        <PaceDistribution
          stream={stream}
          effortIntensity={effortIntensity}
          movingTimeS={movingTimeS}
        />
      )}

      {planComparison && (
        <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Plan vs Actual</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
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
