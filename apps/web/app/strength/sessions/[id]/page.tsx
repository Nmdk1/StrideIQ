'use client';

/**
 * Strength v1 sandbox — single session detail page.
 *
 * Editable surface: athletes can tap any set to edit reps/weight/RPE,
 * append more sets via the picker, or remove a set. All edits and
 * deletes are non-destructive on the backend (supersede pattern); the
 * audit trail is preserved. See routers/strength_v1.py for semantics.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { ExercisePicker } from '@/components/strength/ExercisePicker';
import {
  useAppendStrengthSets,
  useDeleteStrengthSet,
  useStrengthSession,
  useUpdateStrengthSet,
} from '@/lib/hooks/queries/strength';
import type {
  ExercisePickerEntry,
  StrengthSetCreate,
  StrengthSetResponse,
} from '@/lib/api/services/strength';

const KG_TO_LBS = 2.20462262;
const LBS_TO_KG = 0.45359237;

function lbDisplay(kg?: number | null): string {
  if (kg == null) return '—';
  return `${Math.round(kg * KG_TO_LBS).toLocaleString()} lb`;
}

function lbInputValue(kg?: number | null): string {
  if (kg == null) return '';
  return String(Math.round(kg * KG_TO_LBS * 10) / 10);
}

function prettify(slug?: string | null): string {
  if (!slug) return '';
  return slug
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StrengthSessionDetailPage() {
  const params = useParams();
  const id = (params?.id as string) ?? '';
  return (
    <ProtectedRoute>
      <Inner id={id} />
    </ProtectedRoute>
  );
}

function Inner({ id }: { id: string }) {
  const router = useRouter();
  const { data, isLoading, error } = useStrengthSession(id);
  const append = useAppendStrengthSets(id);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busyError, setBusyError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const out = new Map<string, StrengthSetResponse[]>();
    if (!data) return out;
    for (const s of data.sets) {
      const key = s.exercise_name || 'unknown';
      const existing = out.get(key) ?? [];
      existing.push(s);
      out.set(key, existing);
    }
    return out;
  }, [data]);

  const handlePick = async (entry: ExercisePickerEntry) => {
    setPickerOpen(false);
    setBusyError(null);
    try {
      await append.mutateAsync([
        {
          exercise_name: entry.name,
          set_type: 'active',
        } as StrengthSetCreate,
      ]);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message ?? '')
          : '';
      setBusyError(msg || 'Could not add set. Try again.');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-4">
        <p className="text-sm text-slate-500">Loading session…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-4">
        <p className="text-sm text-slate-500">Session not found.</p>
        <Link href="/strength" className="text-sm text-emerald-400 underline">
          Back to strength
        </Link>
      </div>
    );
  }

  const start = new Date(data.start_time);
  const isManual = data.source === 'manual';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-32">
      <header className="px-4 pt-6 pb-4 border-b border-slate-800">
        <button
          type="button"
          onClick={() => router.push('/strength')}
          className="text-xs text-slate-400 hover:text-slate-200"
        >
          ← Strength
        </button>
        <h1 className="text-xl font-bold mt-2">
          {data.name || 'Strength session'}
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {start.toLocaleString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
          })}
        </p>
        <div className="mt-2 flex items-center gap-3 text-[11px] text-slate-500">
          <span>{data.set_count} sets</span>
          <span>·</span>
          <span>{lbDisplay(data.total_volume_kg)} total</span>
          <span>·</span>
          <span className="capitalize">source: {data.source}</span>
        </div>
        {!isManual && (
          <p className="mt-2 text-[11px] text-amber-400/80">
            Garmin-ingested session — edits are disabled to keep future syncs in sync.
          </p>
        )}
      </header>

      <section className="px-4 pt-4 space-y-5">
        {data.sets.length === 0 && (
          <p className="text-sm text-slate-500 italic">
            No sets in this session yet.
          </p>
        )}
        {Array.from(grouped.entries()).map(([name, sets]) => (
          <div
            key={name}
            className="rounded-lg border border-slate-800 bg-slate-900/40 p-3"
          >
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-base font-semibold">{prettify(name) || 'Exercise'}</h2>
              <span className="text-[11px] text-slate-500">
                {prettify(sets[0]?.movement_pattern)}
                {sets[0]?.is_unilateral ? ' · unilateral' : ''}
              </span>
            </div>
            <ul className="mt-2 divide-y divide-slate-800/70">
              {sets.map((s) => (
                <SetRow
                  key={s.id}
                  activityId={id}
                  set={s}
                  editable={isManual}
                />
              ))}
            </ul>
          </div>
        ))}

        {isManual && (
          <button
            type="button"
            onClick={() => {
              setBusyError(null);
              setPickerOpen(true);
            }}
            disabled={append.isPending}
            className="w-full py-3 border border-dashed border-slate-700 rounded-md text-sm text-slate-400 hover:text-slate-200 hover:border-slate-500 disabled:opacity-50"
          >
            {append.isPending ? 'Adding…' : '+ Add set'}
          </button>
        )}

        {busyError && (
          <p className="text-sm text-rose-400" role="alert">
            {busyError}
          </p>
        )}
      </section>

      <ExercisePicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={handlePick}
      />
    </div>
  );
}

interface SetRowProps {
  activityId: string;
  set: StrengthSetResponse;
  editable: boolean;
}

function SetRow({ activityId, set, editable }: SetRowProps) {
  const [editing, setEditing] = useState(false);
  const [reps, setReps] = useState<string>(set.reps != null ? String(set.reps) : '');
  const [lbs, setLbs] = useState<string>(lbInputValue(set.weight_kg));
  const [rpe, setRpe] = useState<string>(set.rpe != null ? String(set.rpe) : '');
  const [rowError, setRowError] = useState<string | null>(null);

  const update = useUpdateStrengthSet(activityId);
  const remove = useDeleteStrengthSet(activityId);

  const cancel = () => {
    setReps(set.reps != null ? String(set.reps) : '');
    setLbs(lbInputValue(set.weight_kg));
    setRpe(set.rpe != null ? String(set.rpe) : '');
    setRowError(null);
    setEditing(false);
  };

  const save = async () => {
    setRowError(null);
    const repsNum = reps.trim() ? Number(reps) : null;
    const lbsNum = lbs.trim() ? Number(lbs) : null;
    const rpeNum = rpe.trim() ? Number(rpe) : null;

    const updates = {
      reps: Number.isFinite(repsNum as number) ? (repsNum as number) : null,
      weight_kg:
        lbsNum != null && Number.isFinite(lbsNum)
          ? Math.round(lbsNum * LBS_TO_KG * 100) / 100
          : null,
      rpe: rpeNum != null && Number.isFinite(rpeNum) ? rpeNum : null,
    };

    try {
      await update.mutateAsync({ setId: set.id, updates });
      setEditing(false);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message ?? '')
          : '';
      setRowError(msg || 'Could not save edit.');
    }
  };

  const handleRemove = async () => {
    if (!window.confirm('Remove this set? It stays in your edit history.')) return;
    setRowError(null);
    try {
      await remove.mutateAsync(set.id);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message ?? '')
          : '';
      setRowError(msg || 'Could not remove set.');
    }
  };

  if (!editing) {
    return (
      <li className="py-2">
        <div className="grid grid-cols-[44px_1fr_auto] gap-2 items-center text-sm">
          <span className="font-mono text-slate-500">
            #{String(set.set_order).padStart(2, '0')}
          </span>
          <span className="text-slate-100">
            {set.reps != null ? `${set.reps} reps` : '—'}
            {set.weight_kg != null ? ` × ${lbDisplay(set.weight_kg)}` : ''}
            {set.duration_s ? ` · ${set.duration_s}s` : ''}
          </span>
          <span className="text-[11px] text-slate-500">
            {set.rpe != null ? `RPE ${set.rpe}` : ''}
            {set.manually_augmented ? ' · edited' : ''}
          </span>
        </div>
        {editable && (
          <div className="flex justify-end gap-3 mt-1">
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="text-[11px] text-slate-400 hover:text-slate-200 px-2 py-1"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={handleRemove}
              disabled={remove.isPending}
              className="text-[11px] text-slate-500 hover:text-rose-400 px-2 py-1 disabled:opacity-50"
            >
              {remove.isPending ? 'Removing…' : 'Remove'}
            </button>
          </div>
        )}
        {rowError && (
          <p className="text-[11px] text-rose-400 mt-1" role="alert">
            {rowError}
          </p>
        )}
      </li>
    );
  }

  return (
    <li className="py-3">
      <div className="grid grid-cols-3 gap-2 items-end">
        <NumField
          label="Reps"
          value={reps}
          onChange={setReps}
          placeholder="—"
          inputMode="numeric"
        />
        <NumField
          label="Weight (lb)"
          value={lbs}
          onChange={setLbs}
          placeholder="—"
          inputMode="decimal"
        />
        <NumField
          label="RPE"
          value={rpe}
          onChange={setRpe}
          placeholder="—"
          inputMode="decimal"
        />
      </div>
      <div className="flex justify-end gap-3 mt-2">
        <button
          type="button"
          onClick={cancel}
          disabled={update.isPending}
          className="text-xs px-3 py-2 rounded-md text-slate-400 hover:text-slate-200 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={save}
          disabled={update.isPending}
          className="text-xs px-3 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold"
        >
          {update.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
      {rowError && (
        <p className="text-[11px] text-rose-400 mt-1" role="alert">
          {rowError}
        </p>
      )}
    </li>
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
