'use client';

import { StretchHorizontal } from 'lucide-react';
import {
  CrossTrainingActivity,
  MetricCard,
  WellnessSnapshot,
  TrainingLoadCard,
  formatDuration,
} from './shared';

export function FlexibilityDetail({ activity }: { activity: CrossTrainingActivity }) {
  return (
    <div className="space-y-4">
      {/* Sport header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-2 rounded-lg bg-purple-500/15 border border-purple-500/20">
          <StretchHorizontal className="w-5 h-5 text-purple-400" />
        </div>
        <span className="text-sm font-medium text-purple-400">Flexibility</span>
      </div>

      {/* Metrics — intentionally minimal */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard label="Duration" value={formatDuration(activity.moving_time_s)} />
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
