'use client';

/**
 * FeedbackModal — required post-run reflection.
 *
 * Three sections in a single modal:
 *   1. Reflection         (harder / as expected / easier)
 *   2. RPE                (1–10 single-tap scale)
 *   3. Workout type       (confirm auto-classified, or change)
 *
 * Founder-mandated invariants (these are intentional UX choices, not bugs):
 *   - Not skippable.  No X, no backdrop click, no Escape.  The only way out
 *     is to complete all three and click Save.  Athletes who want to dismiss
 *     can navigate away via browser back/home — the modal will reappear on
 *     the next visit until feedback is recorded.
 *   - "Save & Close" is enabled only after every section has a value (or has
 *     been explicitly confirmed for workout type).
 *   - Save fans out to three endpoints in parallel; the modal closes only
 *     after every save resolves successfully.  If any fail, the modal stays
 *     open with an inline error so the athlete can retry — never close
 *     optimistically and lose data.
 *   - Editable later: opening the modal via the Reflect pill pre-fills all
 *     three sections from the backend; sections are pre-confirmed so Save
 *     is immediately available, and only changed values are submitted.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type {
  ReflectionRecord,
  ReflectionValue,
  WorkoutTypeRecord,
} from './useFeedbackCompletion';
import type { ActivityFeedback } from '@/lib/api/types';

interface WorkoutTypeOption {
  value: string;
  label: string;
  zone: string;
  description: string;
}

const REFLECTION_OPTIONS: { value: ReflectionValue; label: string; icon: string }[] = [
  { value: 'harder', label: 'Harder than expected', icon: '▲' },
  { value: 'expected', label: 'As expected', icon: '●' },
  { value: 'easier', label: 'Easier than expected', icon: '▼' },
];

const RPE_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

export interface FeedbackModalProps {
  activityId: string;
  open: boolean;
  /** Pre-fill sources — when null, that section starts blank. */
  existingReflection: ReflectionRecord | null;
  existingFeedback: ActivityFeedback | null;
  existingWorkoutType: WorkoutTypeRecord | null;
  /** Called after a successful save (all three pieces persisted). */
  onSaved: () => void;
}

export function FeedbackModal({
  activityId,
  open,
  existingReflection,
  existingFeedback,
  existingWorkoutType,
  onSaved,
}: FeedbackModalProps) {
  const queryClient = useQueryClient();
  const titleId = `feedback-modal-title-${activityId}`;

  const [reflection, setReflection] = useState<ReflectionValue | null>(null);
  const [rpe, setRpe] = useState<number | null>(null);
  const [workoutType, setWorkoutType] = useState<string | null>(null);
  const [workoutTypeAcked, setWorkoutTypeAcked] = useState(false);
  const [showTypePicker, setShowTypePicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-fill state when the modal opens.  We deliberately re-run on every
  // open so that an athlete editing via the Reflect pill always sees the
  // current backend values — not whatever stale local state was left from
  // the previous session.
  //
  // Workout-type acking nuance: a value the athlete previously chose
  // themselves (`is_user_override`) counts as acked so editing only
  // reflection or RPE doesn't force them to re-confirm a classification
  // they already approved.  An auto-classification, however, must be
  // explicitly confirmed (or changed) — that's the whole point of putting
  // it in the modal: make the athlete look at the engine's guess.
  useEffect(() => {
    if (!open) return;
    setReflection(existingReflection?.response ?? null);
    setRpe(existingFeedback?.perceived_effort ?? null);
    setWorkoutType(existingWorkoutType?.workout_type ?? null);
    setWorkoutTypeAcked(!!existingWorkoutType?.is_user_override);
    setShowTypePicker(!existingWorkoutType?.workout_type);
    setSaving(false);
    setError(null);
  }, [open, existingReflection, existingFeedback, existingWorkoutType]);

  const optionsQuery = useQuery<{ options: WorkoutTypeOption[] }>({
    queryKey: ['workout-type-options'],
    queryFn: () => apiClient.get('/v1/activities/workout-types/options'),
    enabled: open,
    staleTime: Infinity,
  });
  const options = optionsQuery.data?.options ?? [];
  const currentTypeOption = useMemo(
    () => options.find((o) => o.value === workoutType) ?? null,
    [options, workoutType],
  );

  const reflectionDirty = reflection !== (existingReflection?.response ?? null);
  const rpeDirty = rpe !== (existingFeedback?.perceived_effort ?? null);
  const typeDirty = workoutType !== (existingWorkoutType?.workout_type ?? null);

  const canSave =
    !!reflection && !!rpe && workoutTypeAcked && !!workoutType && !saving;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    setError(null);
    try {
      const tasks: Promise<unknown>[] = [];
      if (reflectionDirty && reflection) {
        tasks.push(
          apiClient.post(`/v1/activities/${activityId}/reflection`, {
            response: reflection,
          }),
        );
      }
      if (rpeDirty && rpe) {
        if (existingFeedback?.id) {
          tasks.push(
            apiClient.put(`/v1/activity-feedback/${existingFeedback.id}`, {
              perceived_effort: rpe,
            }),
          );
        } else {
          tasks.push(
            apiClient.post('/v1/activity-feedback', {
              activity_id: activityId,
              perceived_effort: rpe,
            }),
          );
        }
      }
      if (typeDirty && workoutType) {
        tasks.push(
          apiClient.put(`/v1/activities/${activityId}/workout-type`, {
            workout_type: workoutType,
          }),
        );
      }
      await Promise.all(tasks);

      // Refresh everything that depends on these three artifacts before we
      // close — guarantees the page chrome's Reflect pill, the next
      // useFeedbackCompletion check, and any downstream consumers see the
      // new state immediately.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['feedback-modal', 'reflection', activityId] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-modal', 'feedback', activityId] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-modal', 'workout-type', activityId] }),
        queryClient.invalidateQueries({ queryKey: ['reflection', activityId] }),
        queryClient.invalidateQueries({ queryKey: ['activity-workout-type', activityId] }),
        queryClient.invalidateQueries({ queryKey: ['activities', activityId] }),
      ]);
      onSaved();
    } catch (e) {
      setSaving(false);
      const msg = e instanceof Error ? e.message : 'Save failed';
      setError(msg);
      // Intentionally do NOT close — athlete must retry.  Their selections
      // remain on screen so nothing is lost.
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6 bg-slate-950/80 backdrop-blur-sm"
    >
      <div className="w-full sm:max-w-lg max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-slate-700/60 bg-slate-900 shadow-2xl">
        {/* Header */}
        <div className="px-5 pt-5 pb-3 border-b border-slate-800">
          <h2 id={titleId} className="text-base font-semibold text-slate-100">
            How did this run feel?
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Three quick taps. Your reflection sharpens every brief and finding the engine writes for you.
          </p>
        </div>

        <div className="px-5 py-5 space-y-6">
          {/* ── Section 1: Reflection ───────────────────────────────── */}
          <Section index={1} title="Compared to what you expected">
            <div className="grid grid-cols-3 gap-2">
              {REFLECTION_OPTIONS.map((opt) => {
                const selected = reflection === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setReflection(opt.value)}
                    disabled={saving}
                    aria-pressed={selected}
                    className={`px-3 py-3 rounded-lg text-xs font-medium transition-all border ${
                      selected
                        ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/60 ring-1 ring-emerald-500/40'
                        : 'bg-slate-800/50 text-slate-300 border-slate-700/60 hover:bg-slate-800'
                    } disabled:opacity-50`}
                  >
                    <span className="block text-base mb-1">{opt.icon}</span>
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </Section>

          {/* ── Section 2: RPE ───────────────────────────────────────── */}
          <Section index={2} title="How hard did it feel? (1 easy → 10 max)">
            <div className="flex items-center justify-between gap-1">
              {RPE_VALUES.map((v) => {
                const selected = rpe === v;
                return (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setRpe(v)}
                    disabled={saving}
                    aria-pressed={selected}
                    className={`w-8 h-8 sm:w-9 sm:h-9 rounded-full text-sm font-medium transition-colors ${
                      selected
                        ? 'bg-emerald-500 text-white ring-2 ring-emerald-400 ring-offset-2 ring-offset-slate-900'
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    } disabled:opacity-50`}
                  >
                    {v}
                  </button>
                );
              })}
            </div>
            <div className="flex justify-between text-[10px] text-slate-500 mt-1.5 px-0.5">
              <span>Very easy</span>
              <span>Threshold</span>
              <span>All-out</span>
            </div>
          </Section>

          {/* ── Section 3: Workout type ──────────────────────────────── */}
          <Section index={3} title="Workout type">
            {!showTypePicker ? (
              <div className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg border border-slate-700/60 bg-slate-800/50">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-100 truncate">
                    {currentTypeOption?.label ??
                      (workoutType ? prettifyType(workoutType) : 'Not classified yet')}
                  </p>
                  {currentTypeOption?.description ? (
                    <p className="text-xs text-slate-400 truncate">
                      {currentTypeOption.description}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setWorkoutTypeAcked(true);
                    }}
                    disabled={saving || !workoutType}
                    aria-pressed={workoutTypeAcked && !typeDirty}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                      workoutTypeAcked && !typeDirty
                        ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/40'
                        : 'bg-emerald-500 text-white hover:bg-emerald-400'
                    } disabled:opacity-50`}
                  >
                    {workoutTypeAcked && !typeDirty ? 'Confirmed' : 'Looks right'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowTypePicker(true)}
                    disabled={saving}
                    className="text-xs text-slate-300 hover:text-white underline underline-offset-2 disabled:opacity-50"
                  >
                    Change
                  </button>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-slate-700/60 bg-slate-800/40 p-3 max-h-56 overflow-y-auto">
                {options.length === 0 ? (
                  <p className="text-xs text-slate-500">Loading types…</p>
                ) : (
                  <div className="grid grid-cols-2 gap-1.5">
                    {options.map((opt) => {
                      const selected = workoutType === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => {
                            setWorkoutType(opt.value);
                            setWorkoutTypeAcked(true);
                            setShowTypePicker(false);
                          }}
                          disabled={saving}
                          className={`text-left px-2.5 py-2 rounded text-xs transition-colors ${
                            selected
                              ? 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/50'
                              : 'bg-slate-900/40 border border-transparent text-slate-300 hover:bg-slate-700/50'
                          } disabled:opacity-50`}
                        >
                          <div className="font-medium">{opt.label}</div>
                          <div className="text-[10px] text-slate-500 truncate">
                            {opt.description}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </Section>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-800 bg-slate-900/95 sticky bottom-0">
          {error ? (
            <p className="text-xs text-rose-400 mb-2" role="alert">
              Save failed: {error}. Your selections are preserved — try again.
            </p>
          ) : null}
          <button
            type="button"
            onClick={handleSave}
            disabled={!canSave}
            className="w-full px-4 py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-semibold hover:bg-emerald-400 transition-colors disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving…' : 'Save & Close'}
          </button>
          <p className="text-[11px] text-slate-500 text-center mt-2">
            You can edit any of this later from the Reflect button.
          </p>
        </div>
      </div>
    </div>
  );
}

function Section({
  index,
  title,
  children,
}: {
  index: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
        <span className="text-slate-600">{index}.</span> {title}
      </p>
      {children}
    </div>
  );
}

function prettifyType(raw: string): string {
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
