'use client';

/**
 * Strength goals — index + create.
 *
 * Athlete-set targets only. The system never suggests, recommends, or
 * picks a target. Goal types here are scaffolds the athlete fills in.
 *
 * "coupled_running_metric" is a free-text reminder so the athlete can
 * note why this target matters in the context of their running (e.g.
 * "maintain deadlift while losing 10 lb before goal race"). It is
 * *not* an automatic correlation — that lives in the engine when
 * enough data exists.
 */

import Link from 'next/link';
import { useState } from 'react';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import {
  useCreateStrengthGoal,
  useDeleteStrengthGoal,
  useStrengthGoals,
  useUpdateStrengthGoal,
} from '@/lib/hooks/queries/routinesGoals';
import type {
  GoalType,
  StrengthGoalResponse,
} from '@/lib/api/services/routinesGoals';

const GOAL_TYPE_LABEL: Record<GoalType, string> = {
  e1rm_target: 'Hit a target estimated 1RM',
  e1rm_maintain: 'Maintain estimated 1RM',
  bodyweight_target: 'Bodyweight target',
  volume_target: 'Weekly volume target',
  strength_to_bodyweight_ratio: 'Strength-to-bodyweight ratio',
  freeform: 'Freeform note',
};

export default function GoalsPage() {
  return (
    <ProtectedRoute>
      <GoalsInner />
    </ProtectedRoute>
  );
}

function GoalsInner() {
  const { data, isLoading, error } = useStrengthGoals();
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-24">
      <header className="px-4 pt-6 pb-4 border-b border-slate-800">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">
          Sandbox · Strength v1
        </p>
        <h1 className="text-2xl font-bold mt-1">Goals</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-prose">
          What you&apos;re working toward, in your own words. Targets
          you set, not targets we set for you.
        </p>
      </header>

      <section className="px-4 pt-4 space-y-2">
        <button
          type="button"
          onClick={() => setShowNew((v) => !v)}
          className="w-full py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-base font-semibold"
        >
          {showNew ? 'Cancel' : '+ New goal'}
        </button>
        <Link
          href="/strength"
          className="block w-full py-2 rounded-md border border-slate-700 text-slate-300 text-center text-sm hover:border-slate-500"
        >
          Back to Strength
        </Link>
      </section>

      {showNew && (
        <section className="px-4 pt-4">
          <NewGoalForm onDone={() => setShowNew(false)} />
        </section>
      )}

      <section className="px-4 pt-8">
        <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-3">
          Active goals
        </h2>

        {isLoading && <p className="text-sm text-slate-500">Loading…</p>}

        {!isLoading && error && (
          <p className="text-sm text-slate-500">
            Strength goals aren&apos;t available on your account yet.
          </p>
        )}

        {!isLoading && !error && (data?.length ?? 0) === 0 && (
          <p className="text-sm text-slate-500">
            No active goals. Add one above when you&apos;ve decided what
            you&apos;re chasing.
          </p>
        )}

        <ul className="space-y-2">
          {(data ?? []).map((g) => (
            <li key={g.id}>
              <GoalRow goal={g} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function GoalRow({ goal }: { goal: StrengthGoalResponse }) {
  const update = useUpdateStrengthGoal();
  const remove = useDeleteStrengthGoal();

  const targetLine =
    goal.target_value != null
      ? `${goal.target_value}${goal.target_unit ? ' ' + goal.target_unit : ''}`
      : null;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-slate-100">
          {goal.exercise_name || GOAL_TYPE_LABEL[goal.goal_type] || goal.goal_type}
        </p>
        {targetLine && (
          <span className="text-[11px] text-emerald-400 font-mono">
            {targetLine}
          </span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-500">
        {GOAL_TYPE_LABEL[goal.goal_type] || goal.goal_type}
        {goal.target_date ? ` · by ${goal.target_date}` : ''}
      </p>
      {goal.coupled_running_metric && (
        <p className="mt-1 text-[11px] text-slate-400 italic">
          “{goal.coupled_running_metric}”
        </p>
      )}
      {goal.notes && (
        <p className="mt-1 text-[11px] text-slate-500">{goal.notes}</p>
      )}
      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() =>
            update.mutate({ goalId: goal.id, payload: { is_active: false } })
          }
          className="text-[11px] text-slate-500 hover:text-slate-200"
          disabled={update.isPending}
        >
          Mark done
        </button>
        <button
          type="button"
          onClick={() => {
            if (confirm('Delete this goal?')) remove.mutate(goal.id);
          }}
          className="text-[11px] text-slate-500 hover:text-rose-300"
          disabled={remove.isPending}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function NewGoalForm({ onDone }: { onDone: () => void }) {
  const create = useCreateStrengthGoal();
  const [goalType, setGoalType] = useState<GoalType>('e1rm_target');
  const [exerciseName, setExerciseName] = useState('');
  const [targetValue, setTargetValue] = useState('');
  const [targetUnit, setTargetUnit] = useState('lbs');
  const [coupledMetric, setCoupledMetric] = useState('');
  const [notes, setNotes] = useState('');

  function handleSubmit() {
    create.mutate(
      {
        goal_type: goalType,
        exercise_name: exerciseName.trim() || null,
        target_value: targetValue.trim() ? Number(targetValue) : null,
        target_unit: targetUnit.trim() || null,
        coupled_running_metric: coupledMetric.trim() || null,
        notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          setExerciseName('');
          setTargetValue('');
          setCoupledMetric('');
          setNotes('');
          onDone();
        },
      },
    );
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 space-y-3">
      <div>
        <label className="text-[11px] uppercase text-slate-500 mb-1 block">
          Goal type
        </label>
        <select
          value={goalType}
          onChange={(e) => setGoalType(e.target.value as GoalType)}
          className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
        >
          {Object.entries(GOAL_TYPE_LABEL).map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-[11px] uppercase text-slate-500 mb-1 block">
          Exercise (optional)
        </label>
        <input
          type="text"
          value={exerciseName}
          onChange={(e) => setExerciseName(e.target.value)}
          placeholder="deadlift, back squat, bench…"
          className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[11px] uppercase text-slate-500 mb-1 block">
            Target value
          </label>
          <input
            type="number"
            inputMode="decimal"
            value={targetValue}
            onChange={(e) => setTargetValue(e.target.value)}
            placeholder="405"
            className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-[11px] uppercase text-slate-500 mb-1 block">
            Unit
          </label>
          <input
            type="text"
            value={targetUnit}
            onChange={(e) => setTargetUnit(e.target.value)}
            placeholder="lbs / kg / reps"
            className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="text-[11px] uppercase text-slate-500 mb-1 block">
          Why this matters for your running (optional)
        </label>
        <input
          type="text"
          value={coupledMetric}
          onChange={(e) => setCoupledMetric(e.target.value)}
          placeholder="e.g. maintain deadlift while losing 10 lb before goal race"
          className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="text-[11px] uppercase text-slate-500 mb-1 block">
          Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
        />
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={create.isPending}
        className="w-full py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold"
      >
        {create.isPending ? 'Saving…' : 'Save goal'}
      </button>
    </div>
  );
}
