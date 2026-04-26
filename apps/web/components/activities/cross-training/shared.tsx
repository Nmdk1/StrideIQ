'use client';

import { Dumbbell, Bike, Mountain, Footprints, StretchHorizontal } from 'lucide-react';

export interface CrossTrainingActivity {
  id: string;
  name: string;
  sport_type: string;
  start_time: string;
  distance_m: number;
  elapsed_time_s: number;
  moving_time_s: number;
  average_hr: number | null;
  max_hr: number | null;
  total_elevation_gain_m: number | null;
  provider: string | null;
  device_name: string | null;
  resolved_title: string | null;
  athlete_title: string | null;
  shape_sentence: string | null;

  // Wellness stamps
  pre_sleep_h: number | null;
  pre_sleep_score: number | null;
  pre_resting_hr: number | null;
  pre_recovery_hrv: number | null;
  pre_overnight_hrv: number | null;

  // Cross-training fields
  strength_session_type: string | null;
  session_detail: Record<string, unknown> | null;
  tss: number | null;
  tss_method: string | null;
  intensity_factor: number | null;
  weekly_context: {
    running_activities: number;
    cross_training_activities: number;
  } | null;
  exercise_sets?: ExerciseSet[];

  // Device-level metrics
  steps: number | null;
  active_kcal: number | null;
  avg_cadence_device: number | null;
  max_cadence: number | null;

  // GPS / map
  gps_track: [number, number][] | null;
  start_coords: [number, number] | null;
}

export interface ExerciseSet {
  set_order: number;
  exercise_name: string;
  exercise_category: string;
  movement_pattern: string;
  muscle_group: string | null;
  is_unilateral: boolean;
  set_type: string;
  reps: number | null;
  weight_kg: number | null;
  duration_s: number | null;
  estimated_1rm_kg: number | null;
}

export const SPORT_CONFIG: Record<string, { icon: typeof Dumbbell; label: string; color: string }> = {
  strength:    { icon: Dumbbell, label: 'Strength', color: 'text-amber-400' },
  cycling:     { icon: Bike, label: 'Cycling', color: 'text-blue-400' },
  hiking:      { icon: Mountain, label: 'Hiking', color: 'text-emerald-400' },
  walking:     { icon: Footprints, label: 'Walking', color: 'text-teal-400' },
  flexibility: { icon: StretchHorizontal, label: 'Flexibility', color: 'text-purple-400' },
};

export function formatDuration(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.round(seconds % 60);
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function MetricCard({ label, value, unit, className = '' }: {
  label: string;
  value: string;
  unit?: string;
  className?: string;
}) {
  return (
    <div className={`bg-slate-800/50 border border-slate-700/30 rounded-lg px-4 py-3 ${className}`}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-lg font-semibold text-white">
        {value}
        {unit && <span className="text-slate-400 text-sm font-normal ml-1">{unit}</span>}
      </p>
    </div>
  );
}

export function WellnessSnapshot({ activity }: { activity: CrossTrainingActivity }) {
  const hasWellness = activity.pre_recovery_hrv != null
    || activity.pre_resting_hr != null
    || activity.pre_sleep_h != null;

  if (!hasWellness) return null;

  return (
    <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3 mb-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Going In</p>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        {activity.pre_recovery_hrv != null && (
          <span className="text-sm text-slate-300">
            <span className="text-slate-500">Recovery HRV</span>{' '}
            <span className="font-medium">{activity.pre_recovery_hrv}</span>
            <span className="text-slate-500 text-xs ml-0.5">ms</span>
            {activity.pre_overnight_hrv != null && (
              <span className="text-xs text-slate-500 ml-2">(overnight avg {activity.pre_overnight_hrv})</span>
            )}
          </span>
        )}
        {activity.pre_resting_hr != null && (
          <span className="text-sm text-slate-300">
            <span className="text-slate-500">RHR</span>{' '}
            <span className="font-medium">{activity.pre_resting_hr}</span>
            <span className="text-slate-500 text-xs ml-0.5">bpm</span>
          </span>
        )}
        {activity.pre_sleep_h != null && (
          <span className="text-sm text-slate-300">
            <span className="text-slate-500">Sleep</span>{' '}
            <span className="font-medium">{activity.pre_sleep_h.toFixed(1)}</span>
            <span className="text-slate-500 text-xs ml-0.5">h</span>
            {activity.pre_sleep_score != null && (
              <span className="text-xs text-slate-500 ml-1">({activity.pre_sleep_score})</span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}

export function TrainingLoadCard({ activity }: { activity: CrossTrainingActivity }) {
  if (activity.tss == null) return null;

  const sportLabel = SPORT_CONFIG[activity.sport_type]?.label ?? activity.sport_type;

  return (
    <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3 mb-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Training Load</p>
      <div className="flex items-baseline gap-3 mb-1">
        <span className="text-2xl font-bold text-white">{Math.round(activity.tss)}</span>
        <span className="text-sm text-slate-400">TSS</span>
        {activity.intensity_factor != null && (
          <span className="text-xs text-slate-500">IF {activity.intensity_factor.toFixed(2)}</span>
        )}
      </div>
      {activity.weekly_context && (
        <p className="text-xs text-slate-500">
          This week: {activity.weekly_context.running_activities} run{activity.weekly_context.running_activities !== 1 ? 's' : ''}
          {activity.weekly_context.cross_training_activities > 0 && (
            <> + {activity.weekly_context.cross_training_activities} cross-training session{activity.weekly_context.cross_training_activities !== 1 ? 's' : ''}</>
          )}
        </p>
      )}
      {activity.tss_method && (
        <p className="text-[10px] text-slate-600 mt-1">
          {activity.tss_method.startsWith('hrTSS') ? 'Calculated from heart rate' :
           activity.tss_method.startsWith('estimated') ? `Estimated (${sportLabel} default)` :
           activity.tss_method}
        </p>
      )}
    </div>
  );
}

const SESSION_TYPE_LABELS: Record<string, { label: string; description: string }> = {
  maximal: { label: 'Maximal Strength', description: 'Low reps, heavy load' },
  strength_endurance: { label: 'Strength Endurance', description: 'Moderate reps, moderate-heavy load' },
  hypertrophy: { label: 'Hypertrophy', description: 'Moderate reps, moderate load' },
  endurance: { label: 'Muscular Endurance', description: 'High reps, lighter load' },
  power: { label: 'Power', description: 'Explosive with heavy load' },
  mixed: { label: 'Mixed', description: 'Varied session structure' },
};

export function SessionTypeBadge({ type }: { type: string | null }) {
  if (!type) return null;
  const config = SESSION_TYPE_LABELS[type];
  if (!config) return null;

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
      <Dumbbell className="w-3.5 h-3.5 text-amber-400" />
      <span className="text-sm font-medium text-amber-300">{config.label}</span>
      <span className="text-xs text-slate-500">{config.description}</span>
    </div>
  );
}
