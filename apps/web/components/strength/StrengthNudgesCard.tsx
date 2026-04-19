'use client';

/**
 * Home-page card for Garmin strength sessions that look incomplete.
 *
 * Surfaces only when:
 *   - Athlete has the client-side strength_v1 flag enabled
 *     (server already gates /v1/strength/nudges by strength.v1)
 *   - At least one Garmin-ingested strength session in the last 7d
 *     has < 3 active sets and hasn't been touched manually
 *
 * Dismissal is per-activity, persisted in localStorage. The next
 * server sweep will resurface a session only if it is still sparse.
 *
 * Voice: never accusatory ("you forgot…"), never prescriptive
 * ("you should…"). Just observation + offer.
 */

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { isFeatureEnabled } from '@/lib/featureFlags';
import { useStrengthNudges } from '@/lib/hooks/queries/strength';
import type { StrengthNudge } from '@/lib/api/services/strength';

const DISMISS_KEY = 'strideiq.strength_nudge_dismissed_v1';

function readDismissed(): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = window.localStorage.getItem(DISMISS_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(arr);
  } catch {
    return new Set();
  }
}

function writeDismissed(ids: Set<string>) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(DISMISS_KEY, JSON.stringify(Array.from(ids)));
  } catch {
    // ignore
  }
}

function formatDay(iso: string | null): string {
  if (!iso) return 'recently';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { weekday: 'long' });
}

export function StrengthNudgesCard() {
  const flagOn = isFeatureEnabled('strength_v1');
  const { data, isLoading } = useStrengthNudges();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    setDismissed(readDismissed());
  }, []);

  if (!flagOn) return null;
  if (isLoading) return null;
  const nudges = (data?.nudges ?? []).filter(
    (n) => !dismissed.has(n.activity_id),
  );
  if (nudges.length === 0) return null;

  // Show only the most recent (single card, not a list of nags).
  const top = nudges[0];

  function dismiss(id: string) {
    const next = new Set(dismissed);
    next.add(id);
    setDismissed(next);
    writeDismissed(next);
  }

  return (
    <section
      aria-label="Strength session reconciliation"
      className="rounded-xl border border-amber-700/30 bg-amber-500/5 px-4 py-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-wide text-amber-400/80">
            Strength · Garmin saw something
          </p>
          <p className="mt-1 text-sm text-slate-100">
            {NudgeMessage(top)}
          </p>
        </div>
        <button
          type="button"
          aria-label="Dismiss"
          onClick={() => dismiss(top.activity_id)}
          className="text-slate-500 hover:text-slate-200 text-sm leading-none"
        >
          ×
        </button>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Link
          href={`/strength/sessions/${top.activity_id}`}
          className="inline-flex items-center px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold"
        >
          Fill in details
        </Link>
        <button
          type="button"
          onClick={() => dismiss(top.activity_id)}
          className="text-[11px] text-slate-400 hover:text-slate-200 px-2 py-1"
        >
          Not now
        </button>
      </div>
    </section>
  );
}

function NudgeMessage(n: StrengthNudge): string {
  const day = formatDay(n.start_time);
  if (n.current_set_count === 0) {
    return `Garmin recorded a strength session on ${day} but no sets came through. Want to fill in what you did?`;
  }
  return `Garmin recorded a strength session on ${day} with only ${n.current_set_count} set${
    n.current_set_count === 1 ? '' : 's'
  }. Want to add the rest?`;
}
