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
    <div className="mb-5 flex flex-wrap items-baseline gap-x-6 gap-y-1.5 border-b border-slate-700/30 pb-4">
      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider w-full sm:w-auto">Going In</span>
      {preRecoveryHrv != null && (
        <span className="text-slate-200">
          <span className="text-slate-400 text-sm">HRV</span>{' '}
          <span className="font-semibold text-lg tabular-nums">{preRecoveryHrv}</span>
          <span className="text-slate-400 text-sm ml-0.5">ms</span>
        </span>
      )}
      {preRestingHr != null && (
        <span className="text-slate-200">
          <span className="text-slate-400 text-sm">RHR</span>{' '}
          <span className="font-semibold text-lg tabular-nums">{preRestingHr}</span>
          <span className="text-slate-400 text-sm ml-0.5">bpm</span>
        </span>
      )}
      {preSleepH != null && (
        <span className="text-slate-200">
          <span className="text-slate-400 text-sm">Sleep</span>{' '}
          <span className="font-semibold text-lg tabular-nums">{preSleepH.toFixed(1)}</span>
          <span className="text-slate-400 text-sm ml-0.5">h</span>
        </span>
      )}
    </div>
  );
}
