'use client';

/**
 * GarminEffortFallback
 *
 * Surfaces Garmin's self-evaluation (perceived effort 1-10 and "feel"
 * label) ONLY when the athlete has not provided their own RPE via the
 * StrideIQ FeedbackModal. The athlete's own subjective score always
 * takes full weight (founder rule); this card is a low-confidence
 * fallback so we don't lose information when the watch happened to
 * capture a self-eval but the athlete hasn't reflected yet.
 *
 * No template language. We say "from your watch" and show the raw
 * number/word. Interpretation belongs in the coach brief, not here.
 */

import React from 'react';

const FEEL_LABELS: Record<string, string> = {
  very_strong: 'Very strong',
  strong: 'Strong',
  normal: 'Normal',
  weak: 'Weak',
  very_weak: 'Very weak',
};

export interface GarminEffortFallbackProps {
  /** Garmin's self-evaluation effort (1-10). */
  garminPerceivedEffort?: number | null;
  /** Garmin's self-evaluation "feel" enum, e.g. "normal". */
  garminFeel?: string | null;
  /** Athlete's own RPE (from ActivityFeedback). When present, this card hides. */
  athleteRpe?: number | null;
}

export function GarminEffortFallback({
  garminPerceivedEffort,
  garminFeel,
  athleteRpe,
}: GarminEffortFallbackProps): React.ReactElement | null {
  // Athlete's score wins outright — never show this when they've reflected.
  if (typeof athleteRpe === 'number' && athleteRpe > 0) return null;

  const hasEffort = typeof garminPerceivedEffort === 'number' && garminPerceivedEffort > 0;
  const hasFeel = typeof garminFeel === 'string' && garminFeel.length > 0;
  if (!hasEffort && !hasFeel) return null;

  const feelLabel = hasFeel ? FEEL_LABELS[garminFeel as string] ?? garminFeel : null;

  return (
    <div
      role="note"
      aria-label="Self-evaluation captured on your watch"
      className="rounded-lg border border-slate-700/40 bg-slate-900/30 px-4 py-3 text-sm text-slate-300"
    >
      <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
        From your watch · self-evaluation
      </p>
      <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {hasEffort && (
          <span>
            <span className="text-white font-semibold tabular-nums">
              {garminPerceivedEffort}
            </span>
            <span className="text-slate-400 text-xs ml-1">/ 10</span>
          </span>
        )}
        {feelLabel && (
          <span className="text-slate-200">{feelLabel}</span>
        )}
        <span className="text-xs text-slate-500">
          Reflect on this run to log your own — yours always takes precedence.
        </span>
      </p>
    </div>
  );
}
