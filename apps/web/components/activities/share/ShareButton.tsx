'use client';

/**
 * ShareButton — page-chrome pill that opens the Share drawer for an
 * activity.  Sibling to ReflectPill in the activity header.
 *
 * Phase 4 placement is deliberate: sharing is a *pull* action — when an
 * athlete wants to share, they hunt for it.  Nothing about this run
 * shares itself or pops up uninvited.  The auto-popup runtoon prompt
 * has been removed from the global layout in the same change.
 */

import React from 'react';
import { Share2 } from 'lucide-react';

export interface ShareButtonProps {
  onClick: () => void;
}

export function ShareButton({ onClick }: ShareButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Share this run"
      className="inline-flex items-center gap-1.5 px-3 h-8 rounded-full text-xs font-medium border border-slate-700/60 bg-slate-800/70 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
    >
      <Share2 className="w-3.5 h-3.5" aria-hidden="true" />
      Share
    </button>
  );
}
