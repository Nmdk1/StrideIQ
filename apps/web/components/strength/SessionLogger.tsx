'use client';

/**
 * SessionLogger — mobile-first manual strength capture.
 *
 * Friction contract (from STRENGTH_V1_SCOPE §6.1):
 *   - Time-to-log a set after selecting an exercise: under three taps.
 *   - "Add same set" is a single tap: weight and reps carry forward.
 *   - All optional fields (RPE, modifier, notes) live behind a "More"
 *     pill and never block save.
 *   - Session save requires only one set with one named exercise.
 *
 * The logger trusts what the athlete typed. It does not silently
 * normalize, round, or "correct" inputs. Garmin reconciliation lives
 * elsewhere; this component is the manual entry surface.
 */

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { useCreateStrengthSession } from '@/lib/hooks/queries/strength';
import type {
  ExercisePickerEntry,
  ImplementType,
  StrengthSetCreate,
} from '@/lib/api/services/strength';

import { ExercisePicker } from './ExercisePicker';

interface DraftSet {
  /** stable id used only for React keys + per-row state */
  localId: string;
  exercise_name: string;
  movement_pattern: string;
  muscle_group?: string | null;
  is_unilateral: boolean;
  reps: string;
  weight_lbs: string;
  duration_s: string;
  rpe: string;
  implement_type: ImplementType | '';
  set_modifier: string;
  tempo: string;
  notes: string;
  expanded: boolean;
}

const LBS_TO_KG = 0.45359237;

let _draftCounter = 0;
function nextDraftId(): string {
  _draftCounter += 1;
  return `draft_${Date.now().toString(36)}_${_draftCounter}`;
}

function makeDraft(seed?: Partial<DraftSet>): DraftSet {
  return {
    localId: nextDraftId(),
    exercise_name: '',
    movement_pattern: 'other',
    muscle_group: null,
    is_unilateral: false,
    reps: '',
    weight_lbs: '',
    duration_s: '',
    rpe: '',
    implement_type: '',
    set_modifier: '',
    tempo: '',
    notes: '',
    expanded: false,
    ...seed,
  };
}

function toServerSet(draft: DraftSet): StrengthSetCreate | null {
  const name = draft.exercise_name.trim();
  if (!name) return null;
  const reps = draft.reps.trim() ? Number(draft.reps) : null;
  const lbs = draft.weight_lbs.trim() ? Number(draft.weight_lbs) : null;
  const duration_s = draft.duration_s.trim() ? Number(draft.duration_s) : null;
  const rpe = draft.rpe.trim() ? Number(draft.rpe) : null;
  return {
    exercise_name: name,
    reps: Number.isFinite(reps as number) ? (reps as number) : null,
    weight_kg:
      lbs != null && Number.isFinite(lbs)
        ? Math.round(lbs * LBS_TO_KG * 100) / 100
        : null,
    duration_s:
      duration_s != null && Number.isFinite(duration_s)
        ? duration_s
        : null,
    rpe: rpe != null && Number.isFinite(rpe) ? rpe : null,
    implement_type: draft.implement_type || null,
    set_modifier: (draft.set_modifier || null) as StrengthSetCreate['set_modifier'],
    tempo: draft.tempo.trim() || null,
    notes: draft.notes.trim() || null,
    set_type: 'active',
  };
}

export function SessionLogger() {
  const router = useRouter();
  const create = useCreateStrengthSession();
  const [drafts, setDrafts] = useState<DraftSet[]>(() => [makeDraft()]);
  const [pickerOpenFor, setPickerOpenFor] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
  }, [drafts]);

  const validSetCount = useMemo(
    () => drafts.filter((d) => d.exercise_name.trim()).length,
    [drafts],
  );

  const updateDraft = (localId: string, patch: Partial<DraftSet>) => {
    setDrafts((prev) =>
      prev.map((d) => (d.localId === localId ? { ...d, ...patch } : d)),
    );
  };

  const removeDraft = (localId: string) => {
    setDrafts((prev) => {
      if (prev.length === 1) return [makeDraft()];
      return prev.filter((d) => d.localId !== localId);
    });
  };

  const addBlankSet = () => {
    setDrafts((prev) => [...prev, makeDraft()]);
  };

  const addRepeatSet = (sourceId: string) => {
    setDrafts((prev) => {
      const src = prev.find((d) => d.localId === sourceId);
      if (!src) return prev;
      return [
        ...prev,
        makeDraft({
          exercise_name: src.exercise_name,
          movement_pattern: src.movement_pattern,
          muscle_group: src.muscle_group,
          is_unilateral: src.is_unilateral,
          reps: src.reps,
          weight_lbs: src.weight_lbs,
          implement_type: src.implement_type,
        }),
      ];
    });
  };

  const handlePick = (localId: string, entry: ExercisePickerEntry) => {
    updateDraft(localId, {
      exercise_name: entry.name,
      movement_pattern: entry.movement_pattern,
      muscle_group: entry.muscle_group ?? null,
      is_unilateral: entry.is_unilateral,
    });
  };

  const handleSave = async () => {
    setError(null);
    const sets = drafts
      .map(toServerSet)
      .filter((s): s is StrengthSetCreate => s !== null);
    if (sets.length === 0) {
      setError('Add at least one set with an exercise name.');
      return;
    }
    try {
      const res = await create.mutateAsync({
        sets,
        name: sessionName.trim() || null,
        start_time: new Date().toISOString(),
      });
      router.push(`/strength/sessions/${res.id}`);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message ?? '')
          : '';
      setError(msg || 'Could not save session. Try again.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-32">
      <header className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-sm text-slate-400 hover:text-slate-200 -ml-2 px-2 py-2"
        >
          Cancel
        </button>
        <h1 className="text-base font-semibold">Log strength</h1>
        <span className="text-xs text-slate-500 w-12 text-right">
          {validSetCount} {validSetCount === 1 ? 'set' : 'sets'}
        </span>
      </header>

      <section className="px-4 pt-4">
        <label className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
          Session name (optional)
        </label>
        <input
          type="text"
          value={sessionName}
          onChange={(e) => setSessionName(e.target.value)}
          placeholder="e.g., Push day, Lower body"
          className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-base text-slate-100 placeholder-slate-600 focus:outline-none focus:border-slate-600"
        />
      </section>

      <section className="px-4 pt-6 space-y-3">
        {drafts.map((draft, idx) => (
          <SetCard
            key={draft.localId}
            index={idx + 1}
            draft={draft}
            onPick={() => setPickerOpenFor(draft.localId)}
            onChange={(patch) => updateDraft(draft.localId, patch)}
            onRemove={() => removeDraft(draft.localId)}
            onRepeat={() => addRepeatSet(draft.localId)}
          />
        ))}

        <button
          type="button"
          onClick={addBlankSet}
          className="w-full py-3 border border-dashed border-slate-700 rounded-md text-sm text-slate-400 hover:text-slate-200 hover:border-slate-500"
        >
          + Add set
        </button>
      </section>

      {error && (
        <p className="px-4 mt-4 text-sm text-rose-400" role="alert">
          {error}
        </p>
      )}

      <div className="fixed bottom-0 inset-x-0 bg-slate-950/95 backdrop-blur border-t border-slate-800 px-4 py-3 z-20">
        <button
          type="button"
          disabled={create.isPending || validSetCount === 0}
          onClick={handleSave}
          className="w-full py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-base font-semibold"
        >
          {create.isPending ? 'Saving…' : 'Save session'}
        </button>
        <p className="text-[11px] text-slate-500 text-center mt-2">
          You can edit any set later. Edits keep an audit trail.
        </p>
      </div>

      <ExercisePicker
        open={pickerOpenFor !== null}
        onClose={() => setPickerOpenFor(null)}
        onSelect={(entry) => {
          if (pickerOpenFor) handlePick(pickerOpenFor, entry);
        }}
      />
    </div>
  );
}

interface SetCardProps {
  index: number;
  draft: DraftSet;
  onPick: () => void;
  onChange: (patch: Partial<DraftSet>) => void;
  onRemove: () => void;
  onRepeat: () => void;
}

function SetCard({
  index,
  draft,
  onPick,
  onChange,
  onRemove,
  onRepeat,
}: SetCardProps) {
  const hasName = !!draft.exercise_name.trim();
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-mono text-slate-500">
          SET {String(index).padStart(2, '0')}
        </span>
        <button
          type="button"
          onClick={onRemove}
          className="text-[11px] text-slate-500 hover:text-rose-400"
          aria-label={`Remove set ${index}`}
        >
          Remove
        </button>
      </div>

      <button
        type="button"
        onClick={onPick}
        className={`w-full text-left px-3 py-3 rounded-md border ${
          hasName
            ? 'border-slate-700 bg-slate-900 text-slate-100'
            : 'border-dashed border-slate-700 bg-transparent text-slate-500'
        }`}
      >
        <span className="text-base capitalize">
          {hasName ? draft.exercise_name : 'Pick exercise'}
        </span>
        {hasName && draft.movement_pattern !== 'other' && (
          <span className="ml-2 text-[11px] uppercase tracking-wide text-slate-500">
            {draft.movement_pattern.replace(/_/g, ' ')}
          </span>
        )}
      </button>

      <div className="grid grid-cols-2 gap-2 mt-3">
        <NumField
          label="Reps"
          value={draft.reps}
          onChange={(v) => onChange({ reps: v })}
          placeholder="—"
          inputMode="numeric"
        />
        <NumField
          label="Weight (lb)"
          value={draft.weight_lbs}
          onChange={(v) => onChange({ weight_lbs: v })}
          placeholder="—"
          inputMode="decimal"
        />
      </div>

      {!draft.expanded ? (
        <div className="flex items-center justify-between mt-3">
          <button
            type="button"
            onClick={() => onChange({ expanded: true })}
            className="text-[11px] text-slate-400 hover:text-slate-200"
          >
            + RPE / notes / modifier
          </button>
          <button
            type="button"
            onClick={onRepeat}
            disabled={!hasName}
            className="text-xs px-3 py-2 rounded-md bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-100"
          >
            Repeat set
          </button>
        </div>
      ) : (
        <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
          <div className="grid grid-cols-2 gap-2">
            <NumField
              label="RPE (1–10)"
              value={draft.rpe}
              onChange={(v) => onChange({ rpe: v })}
              placeholder="—"
              inputMode="decimal"
            />
            <SelectField
              label="Implement"
              value={draft.implement_type}
              onChange={(v) =>
                onChange({ implement_type: v as DraftSet['implement_type'] })
              }
              options={[
                ['', '—'],
                ['barbell', 'Barbell'],
                ['dumbbell_each', 'Dumbbell (each)'],
                ['dumbbell_total', 'Dumbbell (total)'],
                ['kettlebell_each', 'Kettlebell (each)'],
                ['kettlebell_total', 'Kettlebell (total)'],
                ['plate_per_side', 'Plate (per side)'],
                ['machine', 'Machine'],
                ['cable', 'Cable'],
                ['bodyweight', 'Bodyweight'],
                ['band', 'Band'],
                ['other', 'Other'],
              ]}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <SelectField
              label="Modifier"
              value={draft.set_modifier}
              onChange={(v) => onChange({ set_modifier: v })}
              options={[
                ['', '—'],
                ['straight', 'Straight'],
                ['warmup', 'Warm-up'],
                ['drop', 'Drop'],
                ['failure', 'To failure'],
                ['amrap', 'AMRAP'],
                ['paused', 'Paused'],
                ['tempo', 'Tempo'],
              ]}
            />
            <NumField
              label="Duration (s)"
              value={draft.duration_s}
              onChange={(v) => onChange({ duration_s: v })}
              placeholder="hold/timed"
              inputMode="numeric"
            />
          </div>
          <label className="block text-[11px] uppercase tracking-wide text-slate-500 mt-1">
            Notes
          </label>
          <textarea
            value={draft.notes}
            onChange={(e) => onChange({ notes: e.target.value })}
            placeholder="Anything worth remembering"
            rows={2}
            className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-slate-600"
          />
          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              onClick={() => onChange({ expanded: false })}
              className="text-[11px] text-slate-500 hover:text-slate-300"
            >
              Hide details
            </button>
            <button
              type="button"
              onClick={onRepeat}
              disabled={!hasName}
              className="text-xs px-3 py-2 rounded-md bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-100"
            >
              Repeat set
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function NumField({
  label,
  value,
  onChange,
  placeholder,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  inputMode?: 'numeric' | 'decimal';
}) {
  return (
    <label className="block">
      <span className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
        {label}
      </span>
      <input
        type="text"
        inputMode={inputMode ?? 'decimal'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-base text-slate-100 placeholder-slate-600 focus:outline-none focus:border-slate-600"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: ReadonlyArray<readonly [string, string]>;
}) {
  return (
    <label className="block">
      <span className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-base text-slate-100 focus:outline-none focus:border-slate-600"
      >
        {options.map(([v, lbl]) => (
          <option key={v} value={v}>
            {lbl}
          </option>
        ))}
      </select>
    </label>
  );
}
