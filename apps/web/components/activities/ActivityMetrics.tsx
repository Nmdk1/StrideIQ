/**
 * Activity Metrics Component
 * 
 * Displays key activity metrics in a clean grid.
 * Tone: Sparse, direct, data-driven.
 */

'use client';

import type { Activity } from '@/lib/api/types';
import { useUnits } from '@/lib/context/UnitsContext';

interface ActivityMetricsProps {
  activity: Activity;
  className?: string;
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

export function ActivityMetrics({ activity, className = '' }: ActivityMetricsProps) {
  const { formatDistance, formatElevation, formatPace, units, paceUnit } = useUnits();
  return (
    <div className={`bg-gray-800 rounded-lg border border-gray-700 p-6 ${className}`}>
      <h2 className="text-xl font-semibold mb-4">Metrics</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {activity.distance && (
          <div>
            <p className="text-sm text-gray-400">Distance</p>
            <p className="text-lg font-semibold">{formatDistance(activity.distance, 2)}</p>
          </div>
        )}
        {activity.moving_time && (
          <div>
            <p className="text-sm text-gray-400">Duration</p>
            <p className="text-lg font-semibold">{formatDuration(activity.moving_time)}</p>
          </div>
        )}
        {activity.pace_per_mile && (
          <div>
            <p className="text-sm text-gray-400">Pace</p>
            <p className="text-lg font-semibold">{activity.pace_per_mile}</p>
          </div>
        )}
        {activity.average_heartrate && (
          <div>
            <p className="text-sm text-gray-400">Avg HR</p>
            <p className="text-lg font-semibold">{activity.average_heartrate} bpm</p>
          </div>
        )}
        {activity.max_hr && (
          <div>
            <p className="text-sm text-gray-400">Max HR</p>
            <p className="text-lg font-semibold">{activity.max_hr} bpm</p>
          </div>
        )}
        {activity.total_elevation_gain && (
          <div>
            <p className="text-sm text-gray-400">Elevation</p>
            <p className="text-lg font-semibold">
              {formatElevation(activity.total_elevation_gain)}
            </p>
          </div>
        )}
        {activity.average_cadence && (
          <div>
            <p className="text-sm text-gray-400">Cadence</p>
            <p className="text-lg font-semibold">
              {Math.round(activity.average_cadence)} spm
            </p>
          </div>
        )}
        {activity.performance_percentage && (
          <div>
            <p className="text-sm text-gray-400">Age-Graded</p>
            <p className="text-lg font-semibold">
              {(activity.performance_percentage * 100).toFixed(1)}%
            </p>
          </div>
        )}
      </div>
    </div>
  );
}


