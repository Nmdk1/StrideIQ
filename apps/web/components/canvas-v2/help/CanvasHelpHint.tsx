'use client';

/**
 * CanvasHelpHint — the "first visit" toast.
 *
 * Renders a small floating card at the top of the page with two short
 * pointers (hover charts, rotate map). Auto-dismisses on whichever
 * comes first:
 *   - 8 second timer
 *   - first user interaction (mousemove, click, touchstart, keydown)
 *
 * After dismissal we set the localStorage flag so it never appears again
 * until the athlete clicks "Show me the welcome hint again" inside the
 * persistent help popover.
 *
 * Accepts an `open` prop so the help popover can re-trigger the tour.
 */

import React, { useEffect, useState } from 'react';
import { useHintsSeen } from './useHintsSeen';

export interface CanvasHelpHintProps {
  /** When true, force-show the hint even if it's already been seen. */
  force?: boolean;
  /** Called when the hint dismisses (auto or via interaction). */
  onDismiss?: () => void;
}

const AUTO_DISMISS_MS = 8000;

export function CanvasHelpHint({ force = false, onDismiss }: CanvasHelpHintProps) {
  const { seen, markSeen } = useHintsSeen();
  const [visible, setVisible] = useState(false);
  const [fadingOut, setFadingOut] = useState(false);

  useEffect(() => {
    if (seen === null) return;
    if (!force && seen) return;
    setFadingOut(false);
    setVisible(true);
  }, [seen, force]);

  useEffect(() => {
    if (!visible) return;

    let timer: ReturnType<typeof setTimeout> | null = null;
    let fadeTimer: ReturnType<typeof setTimeout> | null = null;

    const dismiss = () => {
      if (fadeTimer) return;
      setFadingOut(true);
      fadeTimer = setTimeout(() => {
        setVisible(false);
        markSeen();
        onDismiss?.();
      }, 250);
    };

    timer = setTimeout(dismiss, AUTO_DISMISS_MS);

    const onInteract = () => dismiss();
    window.addEventListener('mousemove', onInteract, { once: true });
    window.addEventListener('click', onInteract, { once: true });
    window.addEventListener('touchstart', onInteract, { once: true });
    window.addEventListener('keydown', onInteract, { once: true });

    return () => {
      if (timer) clearTimeout(timer);
      if (fadeTimer) clearTimeout(fadeTimer);
      window.removeEventListener('mousemove', onInteract);
      window.removeEventListener('click', onInteract);
      window.removeEventListener('touchstart', onInteract);
      window.removeEventListener('keydown', onInteract);
    };
  }, [visible, markSeen, onDismiss]);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`pointer-events-none fixed top-6 left-1/2 -translate-x-1/2 z-40 transition-opacity duration-200 ${
        fadingOut ? 'opacity-0' : 'opacity-100'
      }`}
    >
      <div className="pointer-events-auto rounded-xl border border-slate-700/70 bg-slate-900/90 backdrop-blur-md shadow-2xl px-4 py-3 max-w-md">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 text-emerald-400 text-xs uppercase tracking-wider font-semibold">
            Quick tour
          </div>
          <button
            type="button"
            onClick={() => {
              setFadingOut(true);
              setTimeout(() => {
                setVisible(false);
                markSeen();
                onDismiss?.();
              }, 200);
            }}
            className="ml-auto text-slate-500 hover:text-slate-300 text-xs"
            aria-label="Dismiss tour"
          >
            ✕
          </button>
        </div>
        <ul className="mt-1 space-y-1 text-sm text-slate-200">
          <li>
            <span className="text-slate-400">Hover any chart</span> to see the moment under your cursor.
          </li>
          <li>
            <span className="text-slate-400">Right-click drag the map</span> to rotate the terrain.
          </li>
        </ul>
        <p className="mt-2 text-[11px] text-slate-500">
          This hint will go away on its own.
        </p>
      </div>
    </div>
  );
}
