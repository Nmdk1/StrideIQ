'use client';

/**
 * CanvasHelpButton — persistent "?" with a popover that documents what
 * each interaction does and what each metric means. Sits in the page
 * header so it's discoverable but never blocks content.
 *
 * Click toggles a popover. Click outside or press Escape to close.
 *
 * The popover ends with "Show the welcome hint again" which clears the
 * `canvasV2:hintsSeen` flag and re-fires the auto-fade hint via the
 * shared callback.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

export interface CanvasHelpButtonProps {
  /** Called when the athlete asks to replay the welcome hint. */
  onReplayHint?: () => void;
}

export function CanvasHelpButton({ onReplayHint }: CanvasHelpButtonProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onClickAway = (e: MouseEvent) => {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('mousedown', onClickAway);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClickAway);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, close]);

  return (
    <div ref={wrapRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center w-7 h-7 rounded-full border border-slate-700/60 bg-slate-900/60 text-slate-300 hover:bg-slate-800/80 hover:text-slate-100 text-sm font-semibold transition-colors"
        aria-label="How to use this view"
        aria-expanded={open}
      >
        ?
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="How to use this view"
          className="absolute right-0 top-9 z-50 w-[320px] rounded-xl border border-slate-700/70 bg-slate-900/95 backdrop-blur-md shadow-2xl p-4 text-sm text-slate-200"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs uppercase tracking-wider text-emerald-400 font-semibold">
              How to use this view
            </h3>
            <button
              type="button"
              onClick={close}
              className="text-slate-500 hover:text-slate-300 text-xs"
              aria-label="Close help"
            >
              ✕
            </button>
          </div>

          <Section title="Charts">
            <li>Hover anywhere to scrub through the run.</li>
            <li>The cards above the map fill with that moment's values.</li>
          </Section>

          <Section title="Map">
            <li>Right-click drag to rotate.</li>
            <li>Scroll to zoom; two-finger drag tilts on touch.</li>
            <li>Click the compass to reset the view.</li>
          </Section>

          <Section title="What you see">
            <li><span className="text-slate-400">Distance</span>: cumulative from start, with elapsed time.</li>
            <li><span className="text-slate-400">Pace</span>: time per mile (or km).</li>
            <li><span className="text-slate-400">Grade</span>: % gradient at that moment.</li>
            <li><span className="text-slate-400">HR / Cadence</span>: bpm and steps per minute.</li>
          </Section>

          {onReplayHint ? (
            <button
              type="button"
              onClick={() => {
                close();
                onReplayHint();
              }}
              className="mt-3 w-full text-left text-xs text-emerald-400 hover:text-emerald-300 underline underline-offset-2"
            >
              Show the welcome hint again
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3 last:mb-0">
      <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">{title}</p>
      <ul className="space-y-0.5 text-[13px] text-slate-200 list-disc list-inside marker:text-slate-600">
        {children}
      </ul>
    </div>
  );
}
