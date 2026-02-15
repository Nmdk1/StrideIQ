/**
 * RSI Layer 2 — Coachable Moments
 *
 * Renders moment markers from stream analysis.
 * Gated: only renders when confidence >= 0.8 AND moments.length > 0.
 * Section hidden entirely when gate fails — no placeholders.
 *
 * Spec: docs/specs/RSI_WIRING_SPEC.md (Layer 2, item 2)
 */

'use client';

import type { Moment } from './hooks/useStreamAnalysis';

interface CoachableMomentsProps {
  moments: Moment[];
  confidence: number;
  className?: string;
}

const MOMENT_ICONS: Record<string, string> = {
  'cardiac_drift': '♥',
  'pace_surge': '⚡',
  'cadence_drop': '🦶',
  'hr_spike': '📈',
  'recovery_window': '🔄',
  'negative_split': '📉',
  'effort_spike': '🔥',
};

function formatTimeS(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function CoachableMoments({ moments, confidence, className = '' }: CoachableMomentsProps) {
  // Gate: confidence >= 0.8 AND moments.length > 0
  if (confidence < 0.8 || moments.length === 0) {
    return null;
  }

  return (
    <div className={`${className}`} data-testid="coachable-moments">
      <h3 className="text-sm font-medium text-slate-400 mb-3">Key Moments</h3>
      <div className="space-y-2">
        {moments.map((moment, i) => (
          <div
            key={`${moment.type}-${moment.time_s}-${i}`}
            className="flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-800/30 border border-slate-700/30"
            data-testid={`moment-${moment.type}`}
          >
            <span className="text-base flex-shrink-0" aria-hidden="true">
              {MOMENT_ICONS[moment.type] || '●'}
            </span>
            <span className="text-xs text-slate-500 font-mono flex-shrink-0 w-12">
              {formatTimeS(moment.time_s)}
            </span>
            <span className="text-sm text-slate-300 flex-1" data-testid={`moment-text-${i}`}>
              {moment.narrative || moment.context || formatMomentType(moment.type)}
            </span>
            {/* Show metric value only when narrative is absent (fallback mode) */}
            {!moment.narrative && moment.value != null && (
              <span className="text-xs text-slate-500 flex-shrink-0">
                {moment.value.toFixed(1)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatMomentType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
