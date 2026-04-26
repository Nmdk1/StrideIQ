'use client';

/**
 * ShareDrawer — bottom sheet on mobile, side-anchored modal on desktop,
 * that hosts every share-style for an activity.  Phase 4 ships with one
 * style (Runtoon) but the layout intentionally leaves room for the
 * follow-on share styles the founder called out: photo overlays,
 * customizable stats, modern backgrounds, race photos, flyovers.
 *
 * The Runtoon used to live in three loud places: an auto-popup bottom
 * sheet on every recent run (mobile), a card bolted onto the activity
 * page bottom, and the runtoon prompt poll firing every 10 seconds.
 * In Phase 4 the runtoon retreats inside this drawer.  It is reachable
 * exclusively via the Share button in the page chrome.
 *
 * Dismiss surface, in order of priority:
 *   1. Close button (top-right)
 *   2. Escape key
 *   3. Backdrop click
 *
 * The drawer is *not* coupled to the FeedbackModal — feedback and
 * sharing are independent flows.  An athlete can share without filing
 * feedback (the Reflect pill keeps nagging until they do).
 */

import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { RuntoonCard } from '@/components/activities/RuntoonCard';

export interface ShareDrawerProps {
  activityId: string;
  open: boolean;
  onClose: () => void;
}

export function ShareDrawer({ activityId, open, onClose }: ShareDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Share this run"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6 bg-slate-950/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full sm:max-w-lg max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-slate-700/60 bg-slate-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/80 sticky top-0 bg-slate-900 z-10">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Share this run</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Pick a look. More styles coming.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close share drawer"
            className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5">
          {/* Style 1: Runtoon (existing) */}
          <section>
            <header className="mb-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Runtoon
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                AI caricature of you on this run. Best for stories.
              </p>
            </header>
            <RuntoonCard activityId={activityId} />
          </section>

          {/* Style 2: roadmap placeholder.  Kept visible (not dev-only)
              so athletes know more is coming and so the drawer never
              feels like a one-trick room. */}
          <section className="rounded-lg border border-dashed border-slate-700/50 bg-slate-800/20 p-4 text-center">
            <p className="text-xs font-medium text-slate-300">
              More share styles are on the way
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Photo overlays, custom stat cards, flyover videos, race
              moments. Tell us what you want to see first.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
