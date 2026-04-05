'use client';

import { useUnits } from '@/lib/context/UnitsContext';
import {
  CrossTrainingActivity,
  MetricCard,
  WellnessSnapshot,
  TrainingLoadCard,
  formatDuration,
  SPORT_CONFIG,
} from './shared';

export function HikingDetail({ activity }: { activity: CrossTrainingActivity }) {
  const { formatDistance, formatElevation } = useUnits();

  const config = SPORT_CONFIG[activity.sport_type] ?? SPORT_CONFIG.hiking;
  const Icon = config.icon;

  const hasDistance = activity.distance_m > 0;
  const hasElevation = activity.total_elevation_gain_m != null && activity.total_elevation_gain_m > 0;
  const isWalking = activity.sport_type === 'walking';

  const avgSpeedMph = activity.distance_m > 0 && activity.moving_time_s > 0
    ? (activity.distance_m / 1609.344) / (activity.moving_time_s / 3600)
    : null;

  return (
    <div className="space-y-4">
      {/* Sport header */}
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-2 rounded-lg ${isWalking ? 'bg-teal-500/15 border border-teal-500/20' : 'bg-emerald-500/15 border border-emerald-500/20'}`}>
          <Icon className={`w-5 h-5 ${config.color}`} />
        </div>
        <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
      </div>

      {/* Walking hero: steps + distance. Hiking hero: elevation gain. */}
      {isWalking && activity.steps != null ? (
        <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg px-4 py-4">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-3xl font-bold text-white">
              {activity.steps.toLocaleString()}
            </span>
            <span className="text-sm text-slate-400">steps</span>
          </div>
          {hasDistance && (
            <p className="text-xs text-slate-500">
              {formatDistance(activity.distance_m)} in {formatDuration(activity.moving_time_s)}
              {avgSpeedMph != null && <>{' · '}{avgSpeedMph.toFixed(1)} mph avg</>}
            </p>
          )}
        </div>
      ) : hasElevation ? (
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
      ) : null}

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
        {!isWalking && activity.steps != null && (
          <MetricCard label="Steps" value={activity.steps.toLocaleString()} />
        )}
        {activity.active_kcal != null && (
          <MetricCard label="Calories" value={activity.active_kcal.toLocaleString()} unit="kcal" />
        )}
        {activity.avg_cadence_device != null && (
          <MetricCard label="Avg Cadence" value={activity.avg_cadence_device.toString()} unit="spm" />
        )}
        {activity.max_cadence != null && (
          <MetricCard label="Max Cadence" value={activity.max_cadence.toString()} unit="spm" />
        )}
      </div>

      {/* Wellness stamps */}
      <WellnessSnapshot activity={activity} />

      {/* Training load */}
      <TrainingLoadCard activity={activity} />
    </div>
  );
}
