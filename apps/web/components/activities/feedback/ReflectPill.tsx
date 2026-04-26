'use client';

/**
 * ReflectPill — page-chrome button that:
 *   • shows whether the athlete has filed feedback for this run
 *     (subtle dot indicator when incomplete), and
 *   • opens the FeedbackModal on click for retroactive editing or
 *     completion.
 *
 * The pill is the only intentionally-visible affordance for opening the
 * modal manually.  Auto-open behaviour is handled separately by
 * useFeedbackTrigger inside the page.
 */

import React from 'react';

export interface ReflectPillProps {
  isComplete: boolean;
  isLoading: boolean;
  onClick: () => void;
}

export function ReflectPill({ isComplete, isLoading, onClick }: ReflectPillProps) {
  if (isLoading) {
    return (
      <button
        type="button"
        disabled
        className="inline-flex items-center gap-1.5 px-3 h-8 rounded-full text-xs font-medium bg-slate-800/60 text-slate-500 border border-slate-700/40 cursor-default"
      >
        Reflect
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={isComplete ? 'Edit your reflection' : 'Reflect on this run (incomplete)'}
      className={`inline-flex items-center gap-1.5 px-3 h-8 rounded-full text-xs font-medium border transition-colors ${
        isComplete
          ? 'bg-slate-800/70 text-slate-300 border-slate-700/60 hover:bg-slate-800 hover:text-white'
          : 'bg-emerald-500/15 text-emerald-200 border-emerald-500/40 hover:bg-emerald-500/25'
      }`}
    >
      {isComplete ? (
        <span className="text-emerald-400" aria-hidden="true">
          ✓
        </span>
      ) : (
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" aria-hidden="true" />
      )}
      Reflect
    </button>
  );
}
