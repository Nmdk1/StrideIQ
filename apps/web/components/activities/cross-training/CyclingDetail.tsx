'use client';

import { Bike } from 'lucide-react';
import { useUnits } from '@/lib/context/UnitsContext';
import {
  CrossTrainingActivity,
  MetricCard,
  WellnessSnapshot,
  TrainingLoadCard,
  formatDuration,
} from './shared';

export function CyclingDetail({ activity }: { activity: CrossTrainingActivity }) {
  const { formatDistance, formatElevation, units } = useUnits();

  const hasDistance = activity.distance_m > 0;
  const hasElevation = activity.total_elevation_gain_m != null && activity.total_elevation_gain_m > 0;
  const hasHR = activity.average_hr != null;

  const avgSpeed = activity.distance_m > 0 && activity.moving_time_s > 0
    ? (units === 'imperial'
        ? (activity.distance_m / 1609.344) / (activity.moving_time_s / 3600)
        : (activity.distance_m / 1000) / (activity.moving_time_s / 3600))
    : null;
  const speedUnit = units === 'imperial' ? 'mph' : 'km/h';

  return (
    <div className="space-y-4">
      {/* Sport header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-2 rounded-lg bg-blue-500/15 border border-blue-500/20">
          <Bike className="w-5 h-5 text-blue-400" />
        </div>
        <span className="text-sm font-medium text-blue-400">Cycling</span>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Duration" value={formatDuration(activity.moving_time_s)} />
        {hasDistance && (
          <MetricCard label="Distance" value={formatDistance(activity.distance_m)} />
        )}
        {avgSpeed != null && (
          <MetricCard label="Avg Speed" value={avgSpeed.toFixed(1)} unit={speedUnit} />
        )}
        {hasElevation && (
          <MetricCard label="Elevation" value={formatElevation(activity.total_elevation_gain_m)} />
        )}
        {hasHR && (
          <MetricCard label="Avg HR" value={activity.average_hr!.toString()} unit="bpm" />
        )}
        {activity.max_hr != null && (
          <MetricCard label="Max HR" value={activity.max_hr.toString()} unit="bpm" />
        )}
        {activity.active_kcal != null && (
          <MetricCard label="Calories" value={activity.active_kcal.toLocaleString()} unit="kcal" />
        )}
        {activity.avg_cadence_device != null && (
          <MetricCard label="Avg Cadence" value={activity.avg_cadence_device.toString()} unit="rpm" />
        )}
      </div>

      {/* Wellness stamps */}
      <WellnessSnapshot activity={activity} />

      {/* Training load */}
      <TrainingLoadCard activity={activity} />
    </div>
  );
}
