'use client';

/**
 * Strength v1 sandbox — single session detail page.
 *
 * Read-only for now. Edits land via the inline set list; this page
 * exists so a saved session has a stable URL for sharing/inspecting.
 */

import { use, useMemo } from 'react';
import Link from 'next/link';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useStrengthSession } from '@/lib/hooks/queries/strength';
import type { StrengthSetResponse } from '@/lib/api/services/strength';

const KG_TO_LBS = 2.20462262;

function lb(kg?: number | null): string {
  if (kg == null) return '—';
  return `${Math.round(kg * KG_TO_LBS).toLocaleString()} lb`;
}

export default function StrengthSessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <ProtectedRoute>
      <Inner id={id} />
    </ProtectedRoute>
  );
}

function Inner({ id }: { id: string }) {
  const { data, isLoading, error } = useStrengthSession(id);

  const grouped = useMemo(() => {
    const out = new Map<string, StrengthSetResponse[]>();
    if (!data) return out;
    for (const s of data.sets) {
      const key = s.exercise_name;
      const existing = out.get(key) ?? [];
      existing.push(s);
      out.set(key, existing);
    }
    return out;
  }, [data]);

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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-16">
      <header className="px-4 pt-6 pb-4 border-b border-slate-800">
        <Link
          href="/strength"
          className="text-xs text-slate-400 hover:text-slate-200"
        >
          ← Strength
        </Link>
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
          <span>{lb(data.total_volume_kg)} total</span>
          <span>·</span>
          <span className="capitalize">source: {data.source}</span>
        </div>
      </header>

      <section className="px-4 pt-4 space-y-5">
        {Array.from(grouped.entries()).map(([name, sets]) => (
          <div key={name} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
            <div className="flex items-baseline justify-between">
              <h2 className="text-base font-semibold capitalize">{name}</h2>
              <span className="text-[11px] text-slate-500 capitalize">
                {sets[0].movement_pattern.replace(/_/g, ' ')}
                {sets[0].is_unilateral ? ' · unilateral' : ''}
              </span>
            </div>
            <ul className="mt-2 divide-y divide-slate-800/70">
              {sets.map((s) => (
                <li
                  key={s.id}
                  className="py-2 grid grid-cols-[60px_1fr_auto] gap-2 items-center text-sm"
                >
                  <span className="font-mono text-slate-500">
                    #{String(s.set_order).padStart(2, '0')}
                  </span>
                  <span className="text-slate-100">
                    {s.reps != null ? `${s.reps} reps` : '—'}
                    {s.weight_kg != null ? ` × ${lb(s.weight_kg)}` : ''}
                    {s.duration_s ? ` · ${s.duration_s}s` : ''}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {s.rpe != null ? `RPE ${s.rpe}` : ''}
                    {s.manually_augmented ? ' · edited' : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}
