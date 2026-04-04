'use client';

import { Mountain } from 'lucide-react';
import { useUnits } from '@/lib/context/UnitsContext';
import {
  CrossTrainingActivity,
  MetricCard,
  WellnessSnapshot,
  TrainingLoadCard,
  formatDuration,
} from './shared';

export function HikingDetail({ activity }: { activity: CrossTrainingActivity }) {
  const { formatDistance, formatElevation } = useUnits();

  const hasDistance = activity.distance_m > 0;
  const hasElevation = activity.total_elevation_gain_m != null && activity.total_elevation_gain_m > 0;

  const avgSpeedMph = activity.distance_m > 0 && activity.moving_time_s > 0
    ? (activity.distance_m / 1609.344) / (activity.moving_time_s / 3600)
    : null;

  return (
    <div className="space-y-4">
      {/* Sport header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-2 rounded-lg bg-emerald-500/15 border border-emerald-500/20">
          <Mountain className="w-5 h-5 text-emerald-400" />
        </div>
        <span className="text-sm font-medium text-emerald-400">Hiking</span>
      </div>

      {/* Elevation hero — the terrain IS the story for hiking */}
      {hasElevation && (
        <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg px-4 py-4">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-3xl font-bold text-white">
              {formatElevation(activity.total_elevation_gain_m)}
            </span>
            <span className="text-sm text-slate-400">elevation gain</span>
          </div>
          {hasDistance && avgSpeedMph != null && (
            <p className="text-xs text-slate-500">
              {formatDistance(activity.distance_m)} in {formatDuration(activity.moving_time_s)}
              {' · '}{avgSpeedMph.toFixed(1)} mph avg
            </p>
          )}
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Duration" value={formatDuration(activity.moving_time_s)} />
        {hasDistance && (
          <MetricCard label="Distance" value={formatDistance(activity.distance_m)} />
        )}
        {avgSpeedMph != null && (
          <MetricCard label="Avg Speed" value={avgSpeedMph.toFixed(1)} unit="mph" />
        )}
        {activity.average_hr != null && (
          <MetricCard label="Avg HR" value={activity.average_hr.toString()} unit="bpm" />
        )}
        {activity.max_hr != null && (
          <MetricCard label="Max HR" value={activity.max_hr.toString()} unit="bpm" />
        )}
      </div>

      {/* Wellness stamps */}
      <WellnessSnapshot activity={activity} />

      {/* Training load */}
      <TrainingLoadCard activity={activity} />
    </div>
  );
}
