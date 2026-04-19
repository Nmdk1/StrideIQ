'use client';

/**
 * Bodyweight quick-entry — Strength v1 sandbox.
 *
 * Surface for athletes who don't have a smart scale, or who want to
 * log weight in the same place they're already logging strength. The
 * page reuses the existing /v1/body-composition table — no new
 * schema. Today's entry is upserted (POST → 400 → PUT).
 *
 * Strength-to-bodyweight ratio appears once we have both a weight
 * AND an active strength goal of type strength_to_bodyweight_ratio
 * with a target_value set. We never compute it implicitly.
 */

import Link from 'next/link';
import { useState } from 'react';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import {
  KG_TO_LBS,
  type BodyCompEntry,
} from '@/lib/api/services/bodyweight';
import {
  useBodyweightHistory,
  useUpsertBodyweightToday,
} from '@/lib/hooks/queries/bodyweight';

export default function BodyweightPage() {
  return (
    <ProtectedRoute>
      <BodyweightInner />
    </ProtectedRoute>
  );
}

function BodyweightInner() {
  const { user } = useAuth();
  const { data, isLoading } = useBodyweightHistory(90);
  const upsert = useUpsertBodyweightToday();

  const [weightLbs, setWeightLbs] = useState('');
  const [bodyFat, setBodyFat] = useState('');
  const [notes, setNotes] = useState('');
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const sorted = (data ?? []).slice().sort((a, b) => (a.date < b.date ? 1 : -1));
  const todayKey = new Date().toISOString().slice(0, 10);
  const todayEntry = sorted.find((e) => e.date === todayKey);

  function handleSave() {
    const w = Number(weightLbs);
    if (!user || !Number.isFinite(w) || w <= 0) return;
    upsert.mutate(
      {
        athleteId: user.id,
        weightLbs: w,
        bodyFatPct: bodyFat.trim() ? Number(bodyFat) : null,
        notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString());
          setNotes('');
        },
      },
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-24">
      <header className="px-4 pt-6 pb-4 border-b border-slate-800">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">
          Sandbox · Strength v1
        </p>
        <h1 className="text-2xl font-bold mt-1">Bodyweight</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-prose">
          Log today&apos;s weight in 5 seconds. The system never sets a
          target weight; that&apos;s a goal you create yourself if you
          want one.
        </p>
      </header>

      <section className="px-4 pt-4 space-y-3">
        <div>
          <label className="text-[11px] uppercase text-slate-500 mb-1 block">
            Weight (lb)
          </label>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={weightLbs}
            onChange={(e) => setWeightLbs(e.target.value)}
            placeholder={
              todayEntry?.weight_kg
                ? `Today: ${(Number(todayEntry.weight_kg) * KG_TO_LBS).toFixed(1)}`
                : '175.4'
            }
            className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-3 text-2xl font-mono text-center"
          />
        </div>
        <div>
          <label className="text-[11px] uppercase text-slate-500 mb-1 block">
            Body fat % (optional)
          </label>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={bodyFat}
            onChange={(e) => setBodyFat(e.target.value)}
            placeholder="14.5"
            className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-[11px] uppercase text-slate-500 mb-1 block">
            Notes (optional)
          </label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="post-workout, dehydrated, fasted…"
            className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={upsert.isPending || !weightLbs}
          className="w-full py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-base font-semibold"
        >
          {upsert.isPending
            ? 'Saving…'
            : todayEntry
            ? 'Update today'
            : 'Save weight'}
        </button>
        {savedAt && (
          <p className="text-[11px] text-emerald-400 text-center">
            Saved at {savedAt}
          </p>
        )}
        <Link
          href="/strength"
          className="block w-full py-2 rounded-md border border-slate-700 text-slate-300 text-center text-sm hover:border-slate-500"
        >
          Back to Strength
        </Link>
      </section>

      <section className="px-4 pt-8">
        <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-3">
          Last 90 days
        </h2>
        {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {!isLoading && sorted.length === 0 && (
          <p className="text-sm text-slate-500">
            No entries yet. Log today&apos;s weight above.
          </p>
        )}
        <ul className="space-y-1">
          {sorted.slice(0, 30).map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between border-b border-slate-800 py-2 text-sm"
            >
              <span className="text-slate-400">{formatDate(e.date)}</span>
              <span className="font-mono text-slate-100">
                {formatWeight(e)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function formatWeight(entry: BodyCompEntry): string {
  if (entry.weight_kg == null) return '—';
  const lbs = Number(entry.weight_kg) * KG_TO_LBS;
  const bf = entry.body_fat_pct
    ? ` · ${Number(entry.body_fat_pct).toFixed(1)}% bf`
    : '';
  return `${lbs.toFixed(1)} lb${bf}`;
}
