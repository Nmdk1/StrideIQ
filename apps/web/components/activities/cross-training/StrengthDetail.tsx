'use client';

import { Dumbbell } from 'lucide-react';
import {
  CrossTrainingActivity,
  ExerciseSet,
  MetricCard,
  WellnessSnapshot,
  TrainingLoadCard,
  SessionTypeBadge,
  formatDuration,
} from './shared';

interface ExerciseGroup {
  pattern: string;
  patternLabel: string;
  muscleGroup: string | null;
  exercises: {
    name: string;
    sets: ExerciseSet[];
  }[];
}

const PATTERN_LABELS: Record<string, string> = {
  hip_hinge: 'Hip Hinge',
  squat: 'Squat',
  lunge: 'Lunge',
  push: 'Push',
  pull: 'Pull',
  core: 'Core',
  plyometric: 'Plyometric',
  carry: 'Carry',
  calf: 'Calf',
  isolation: 'Isolation',
  compound_other: 'Compound',
};

const MUSCLE_LABELS: Record<string, string> = {
  posterior_chain: 'Posterior Chain',
  quadriceps: 'Quads',
  glutes: 'Glutes',
  hip_abductors: 'Hip Abductors',
  chest: 'Chest',
  shoulders: 'Shoulders',
  triceps: 'Triceps',
  lats: 'Lats',
  biceps: 'Biceps',
  upper_back: 'Upper Back',
  rear_delts: 'Rear Delts',
  core_anterior: 'Core',
  core_lateral: 'Core (Lateral)',
  core_rotational: 'Core (Rotational)',
  core_posterior: 'Core (Posterior)',
  lower_body_explosive: 'Explosive',
  full_body: 'Full Body',
  calves: 'Calves',
  hamstrings: 'Hamstrings',
};

function groupExerciseSets(sets: ExerciseSet[]): ExerciseGroup[] {
  const activeSets = sets.filter(s => s.set_type === 'active');
  const byPattern = new Map<string, Map<string, ExerciseSet[]>>();

  for (const s of activeSets) {
    if (!byPattern.has(s.movement_pattern)) {
      byPattern.set(s.movement_pattern, new Map());
    }
    const exercises = byPattern.get(s.movement_pattern)!;
    if (!exercises.has(s.exercise_name)) {
      exercises.set(s.exercise_name, []);
    }
    exercises.get(s.exercise_name)!.push(s);
  }

  const groups: ExerciseGroup[] = [];
  Array.from(byPattern.entries()).forEach(([pattern, exercises]) => {
    const firstSet = Array.from(exercises.values())[0]?.[0];
    groups.push({
      pattern,
      patternLabel: PATTERN_LABELS[pattern] ?? pattern.replace(/_/g, ' '),
      muscleGroup: firstSet?.muscle_group ?? null,
      exercises: Array.from(exercises.entries()).map(([name, sets]) => ({
        name: formatExerciseName(name),
        sets,
      })),
    });
  });

  return groups;
}

function formatExerciseName(raw: string): string {
  return raw
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase());
}

function kgToLbs(kg: number): number {
  return kg * 2.20462;
}

function VolumeSummary({ sets }: { sets: ExerciseSet[] }) {
  const active = sets.filter(s => s.set_type === 'active');
  const totalSets = active.length;
  const totalReps = active.reduce((sum, s) => sum + (s.reps ?? 0), 0);
  const totalVolumeKg = active.reduce((sum, s) => {
    if (s.weight_kg && s.reps) return sum + s.weight_kg * s.reps;
    return sum;
  }, 0);

  const lowerSets = active.filter(s =>
    ['hip_hinge', 'squat', 'lunge', 'calf', 'plyometric'].includes(s.movement_pattern)
  ).length;
  const upperSets = active.filter(s =>
    ['push', 'pull'].includes(s.movement_pattern)
  ).length;
  const coreSets = active.filter(s => s.movement_pattern === 'core').length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <MetricCard label="Total Sets" value={totalSets.toString()} />
      <MetricCard label="Total Reps" value={totalReps.toString()} />
      {totalVolumeKg > 0 && (
        <MetricCard
          label="Volume"
          value={Math.round(kgToLbs(totalVolumeKg)).toLocaleString()}
          unit="lbs"
        />
      )}
      <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg px-4 py-3">
        <p className="text-xs text-slate-400 mb-1">Distribution</p>
        <div className="flex gap-1 h-2 rounded-full overflow-hidden bg-slate-700/50">
          {lowerSets > 0 && (
            <div
              className="bg-emerald-500 rounded-full"
              style={{ flex: lowerSets }}
              title={`Lower body: ${lowerSets} sets`}
            />
          )}
          {upperSets > 0 && (
            <div
              className="bg-blue-500 rounded-full"
              style={{ flex: upperSets }}
              title={`Upper body: ${upperSets} sets`}
            />
          )}
          {coreSets > 0 && (
            <div
              className="bg-amber-500 rounded-full"
              style={{ flex: coreSets }}
              title={`Core: ${coreSets} sets`}
            />
          )}
        </div>
        <div className="flex gap-3 mt-1.5 text-[10px] text-slate-500">
          {lowerSets > 0 && <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Lower {lowerSets}</span>}
          {upperSets > 0 && <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" />Upper {upperSets}</span>}
          {coreSets > 0 && <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />Core {coreSets}</span>}
        </div>
      </div>
    </div>
  );
}

function ExerciseGroupCard({ group }: { group: ExerciseGroup }) {
  return (
    <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg overflow-hidden">
      <div className="px-4 py-2.5 border-b border-slate-700/20 bg-slate-800/50">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-slate-300">{group.patternLabel}</span>
          {group.muscleGroup && (
            <span className="text-xs text-slate-500">
              {MUSCLE_LABELS[group.muscleGroup] ?? group.muscleGroup}
            </span>
          )}
        </div>
      </div>
      <div className="divide-y divide-slate-700/20">
        {group.exercises.map((exercise) => (
          <div key={exercise.name} className="px-4 py-2.5">
            <p className="text-sm text-white mb-1.5">{exercise.name}</p>
            <div className="flex flex-wrap gap-2">
              {exercise.sets.map((set, i) => (
                <div
                  key={i}
                  className="text-xs text-slate-400 bg-slate-700/30 rounded px-2 py-1"
                >
                  {set.reps != null && set.weight_kg != null ? (
                    <span>
                      {set.reps} &times; {Math.round(kgToLbs(set.weight_kg))} lbs
                      {set.estimated_1rm_kg != null && (
                        <span className="text-slate-600 ml-1">
                          (e1RM {Math.round(kgToLbs(set.estimated_1rm_kg))})
                        </span>
                      )}
                    </span>
                  ) : set.reps != null ? (
                    <span>{set.reps} reps</span>
                  ) : set.duration_s != null ? (
                    <span>{Math.round(set.duration_s)}s</span>
                  ) : (
                    <span>Set {i + 1}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StrengthDetail({ activity }: { activity: CrossTrainingActivity }) {
  const hasSets = activity.exercise_sets && activity.exercise_sets.length > 0;
  const groups = hasSets ? groupExerciseSets(activity.exercise_sets!) : [];

  return (
    <div className="space-y-4">
      {/* Sport header + session type */}
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-amber-500/15 border border-amber-500/20">
            <Dumbbell className="w-5 h-5 text-amber-400" />
          </div>
          <span className="text-sm font-medium text-amber-400">Strength</span>
        </div>
        <SessionTypeBadge type={activity.strength_session_type} />
      </div>

      {/* Basic metrics (always shown) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Duration" value={formatDuration(activity.moving_time_s)} />
        {activity.average_hr != null && (
          <MetricCard label="Avg HR" value={activity.average_hr.toString()} unit="bpm" />
        )}
        {activity.max_hr != null && (
          <MetricCard label="Max HR" value={activity.max_hr.toString()} unit="bpm" />
        )}
      </div>

      {/* Exercise sets — rich state */}
      {hasSets && (
        <>
          <VolumeSummary sets={activity.exercise_sets!} />
          <div className="space-y-3">
            {groups.map((group) => (
              <ExerciseGroupCard key={group.pattern} group={group} />
            ))}
          </div>
        </>
      )}

      {/* Exercise sets — placeholder state */}
      {!hasSets && (
        <div className="rounded-lg border border-slate-700/30 bg-slate-800/20 px-4 py-6 text-center">
          <Dumbbell className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-400">Detailed exercise data not available for this session.</p>
          <p className="text-xs text-slate-600 mt-1">
            Exercise tracking requires a compatible Garmin watch with strength workout mode.
          </p>
        </div>
      )}

      {/* Wellness stamps */}
      <WellnessSnapshot activity={activity} />

      {/* Training load */}
      <TrainingLoadCard activity={activity} />
    </div>
  );
}
