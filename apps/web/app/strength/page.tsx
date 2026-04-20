'use client';

/**
 * Strength v1 sandbox — index page.
 *
 * Lists recent manual + Garmin-ingested strength sessions, with a
 * primary CTA to log a new one. Hidden from athletes whose
 * ``strength.v1`` flag is off via API 404 → empty list state, and
 * the page itself never renders if the API returns 404 to the list
 * call (we treat that as "not in rollout").
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useStrengthSessions } from '@/lib/hooks/queries/strength';
import type { StrengthSessionListItem } from '@/lib/api/services/strength';

const KG_TO_LBS = 2.20462262;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function formatDuration(seconds?: number | null): string {
  if (!seconds) return '—';
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

function formatVolume(kg?: number | null): string {
  if (kg == null) return '—';
  return `${Math.round(kg * KG_TO_LBS).toLocaleString()} lb`;
}

export default function StrengthIndexPage() {
  return (
    <ProtectedRoute>
      <StrengthIndexInner />
    </ProtectedRoute>
  );
}

function StrengthIndexInner() {
  const router = useRouter();
  const { data, isLoading, error } = useStrengthSessions(20);

  const sessions = data ?? [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-24">
      <header className="px-4 pt-6 pb-4 border-b border-slate-800">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">
          Sandbox · Strength v1
        </p>
        <h1 className="text-2xl font-bold mt-1">Strength</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-prose">
          What you actually lift, captured at set-level so the engine can
          eventually learn what helps your running. Nothing in here
          prescribes a workout.
        </p>
      </header>

      <section className="px-4 pt-4 space-y-2">
        <button
          type="button"
          onClick={() => router.push('/strength/log')}
          className="w-full py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-base font-semibold"
        >
          + Log a strength session
        </button>
        <div className="grid grid-cols-2 gap-2">
          <Link
            href="/strength/routines"
            className="block py-2 rounded-md border border-slate-700 text-slate-200 text-center text-xs hover:border-slate-500"
          >
            Routines
          </Link>
          <Link
            href="/strength/goals"
            className="block py-2 rounded-md border border-slate-700 text-slate-200 text-center text-xs hover:border-slate-500"
          >
            Goals
          </Link>
          <Link
            href="/strength/bodyweight"
            className="block py-2 rounded-md border border-slate-700 text-slate-200 text-center text-xs hover:border-slate-500"
          >
            Bodyweight
          </Link>
          <Link
            href="/strength/symptoms"
            className="block py-2 rounded-md border border-slate-700 text-slate-200 text-center text-xs hover:border-slate-500"
          >
            Niggles & aches
          </Link>
        </div>
      </section>

      <section className="px-4 pt-8">
        <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-3">
          Recent sessions
        </h2>

        {isLoading && (
          <p className="text-sm text-slate-500">Loading…</p>
        )}

        {!isLoading && error && (
          <p className="text-sm text-slate-500">
            Strength logging isn&apos;t available on your account yet.
          </p>
        )}

        {!isLoading && !error && sessions.length === 0 && (
          <p className="text-sm text-slate-500">
            No sessions yet. Your first log will live here, plus anything
            your Garmin captures.
          </p>
        )}

        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.id}>
              <SessionRow session={s} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SessionRow({ session }: { session: StrengthSessionListItem }) {
  const patternsLabel = session.movement_patterns
    .filter((p) => p && p !== 'other')
    .slice(0, 4)
    .map((p) => p.replace(/_/g, ' '))
    .join(' · ');

  return (
    <Link
      href={`/strength/sessions/${session.id}`}
      className="block rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900 px-4 py-3"
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-100">
          {session.name || 'Strength session'}
        </p>
        <span className="text-[11px] text-slate-500">
          {formatDate(session.start_time)}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-3 text-[11px] text-slate-500">
        <span>{session.set_count} sets</span>
        <span>·</span>
        <span>{formatDuration(session.duration_s)}</span>
        <span>·</span>
        <span>{formatVolume(session.total_volume_kg)} volume</span>
      </div>
      {patternsLabel && (
        <p className="mt-1 text-[11px] text-slate-500 capitalize">
          {patternsLabel}
        </p>
      )}
    </Link>
  );
}
