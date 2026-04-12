'use client';

import React from 'react';

interface GoingInStripProps {
  preRecoveryHrv: number | null;
  preRestingHr: number | null;
  preSleepH: number | null;
}

export function GoingInStrip({
  preRecoveryHrv,
  preRestingHr,
  preSleepH,
}: GoingInStripProps) {
  if (preRecoveryHrv == null && preRestingHr == null && preSleepH == null) {
    return null;
  }

  return (
    <div className="mb-4 flex flex-wrap items-baseline gap-x-5 gap-y-1 text-sm border-b border-slate-700/30 pb-3">
      <span className="text-xs font-medium text-slate-500 uppercase tracking-wide w-full sm:w-auto">Going In</span>
      {preRecoveryHrv != null && (
        <span className="text-slate-300">
          <span className="text-slate-500">HRV</span>{' '}
          <span className="font-medium tabular-nums">{preRecoveryHrv}</span>
          <span className="text-slate-500 text-xs">ms</span>
        </span>
      )}
      {preRestingHr != null && (
        <span className="text-slate-300">
          <span className="text-slate-500">RHR</span>{' '}
          <span className="font-medium tabular-nums">{preRestingHr}</span>
          <span className="text-slate-500 text-xs">bpm</span>
        </span>
      )}
      {preSleepH != null && (
        <span className="text-slate-300">
          <span className="text-slate-500">Sleep</span>{' '}
          <span className="font-medium tabular-nums">{preSleepH.toFixed(1)}</span>
          <span className="text-slate-500 text-xs">h</span>
        </span>
      )}
    </div>
  );
}
