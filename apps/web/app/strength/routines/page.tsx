'use client';

/**
 * Strength routines — index + create.
 *
 * Athlete-saved patterns only. The system never seeds, suggests, or
 * recommends a routine. This page lists what the athlete has saved
 * themselves, lets them create a new one, rename, or archive.
 *
 * Items are intentionally light: exercise name + optional defaults.
 * The point is two-tap repeat in SessionLogger, not a coaching
 * blueprint. Future: "Start session from this routine" CTA pre-fills
 * SessionLogger drafts.
 */

import Link from 'next/link';
import { useState } from 'react';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import {
  useArchiveStrengthRoutine,
  useCreateStrengthRoutine,
  useStrengthRoutines,
} from '@/lib/hooks/queries/routinesGoals';
import type { StrengthRoutineResponse, RoutineItem } from '@/lib/api/services/routinesGoals';

export default function RoutinesPage() {
  return (
    <ProtectedRoute>
      <RoutinesInner />
    </ProtectedRoute>
  );
}

function RoutinesInner() {
  const { data, isLoading, error } = useStrengthRoutines();
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-24">
      <header className="px-4 pt-6 pb-4 border-b border-slate-800">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">
          Sandbox · Strength v1
        </p>
        <h1 className="text-2xl font-bold mt-1">Routines</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-prose">
          Save the patterns you actually run, so logging the next one
          takes two taps. Nothing here is prescribed; you write what you
          do.
        </p>
      </header>

      <section className="px-4 pt-4 space-y-2">
        <button
          type="button"
          onClick={() => setShowNew((v) => !v)}
          className="w-full py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-base font-semibold"
        >
          {showNew ? 'Cancel' : '+ New routine'}
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
          <NewRoutineForm onDone={() => setShowNew(false)} />
        </section>
      )}

      <section className="px-4 pt-8">
        <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-3">
          Saved routines
        </h2>

        {isLoading && <p className="text-sm text-slate-500">Loading…</p>}

        {!isLoading && error && (
          <p className="text-sm text-slate-500">
            Strength routines aren&apos;t available on your account yet.
          </p>
        )}

        {!isLoading && !error && (data?.length ?? 0) === 0 && (
          <p className="text-sm text-slate-500">
            No routines saved. Create one above to make repeat logging
            easier.
          </p>
        )}

        <ul className="space-y-2">
          {(data ?? []).map((r) => (
            <li key={r.id}>
              <RoutineRow routine={r} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function RoutineRow({ routine }: { routine: StrengthRoutineResponse }) {
  const archive = useArchiveStrengthRoutine();
  const items = (routine.items as RoutineItem[]) ?? [];
  const summary = items
    .slice(0, 4)
    .map((it) => it.exercise_name)
    .join(' · ');

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-slate-100">{routine.name}</p>
        <span className="text-[11px] text-slate-500">
          used {routine.times_used}×
        </span>
      </div>
      {summary && (
        <p className="mt-1 text-[11px] text-slate-500 capitalize">{summary}</p>
      )}
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            if (confirm(`Archive "${routine.name}"?`)) {
              archive.mutate(routine.id);
            }
          }}
          className="text-[11px] text-slate-500 hover:text-rose-300"
          disabled={archive.isPending}
        >
          Archive
        </button>
      </div>
    </div>
  );
}

function NewRoutineForm({ onDone }: { onDone: () => void }) {
  const create = useCreateStrengthRoutine();
  const [name, setName] = useState('');
  const [itemsText, setItemsText] = useState('');

  function handleSubmit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    const items: RoutineItem[] = itemsText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => ({ exercise_name: line }));

    create.mutate(
      { name: trimmed, items },
      {
        onSuccess: () => {
          setName('');
          setItemsText('');
          onDone();
        },
      },
    );
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 space-y-3">
      <div>
        <label className="text-[11px] uppercase text-slate-500 mb-1 block">
          Name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Pull day, leg day, AMRAP Tuesdays…"
          className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="text-[11px] uppercase text-slate-500 mb-1 block">
          Exercises (one per line)
        </label>
        <textarea
          value={itemsText}
          onChange={(e) => setItemsText(e.target.value)}
          rows={5}
          placeholder={'deadlift\npull up\nbarbell row'}
          className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm font-mono"
        />
        <p className="mt-1 text-[10px] text-slate-500">
          Just names for now. Sets / reps / weight stay in the logger
          where you can adjust them per session.
        </p>
      </div>
      <button
        type="button"
        disabled={!name.trim() || create.isPending}
        onClick={handleSubmit}
        className="w-full py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold"
      >
        {create.isPending ? 'Saving…' : 'Save routine'}
      </button>
    </div>
  );
}
