'use client';

import React from 'react';

interface GoingInCardProps {
  preRecoveryHrv: number | null;
  preOvernightHrv: number | null;
  preRestingHr: number | null;
  preSleepH: number | null;
  preSleepScore: number | null;
}

export function GoingInCard({
  preRecoveryHrv,
  preOvernightHrv,
  preRestingHr,
  preSleepH,
  preSleepScore,
}: GoingInCardProps) {
  if (preRecoveryHrv == null && preRestingHr == null && preSleepH == null) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Going In</p>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        {preRecoveryHrv != null && (
          <span className="text-sm text-slate-300">
            <span className="text-slate-500">Recovery HRV</span>{' '}
            <span className="font-medium">{preRecoveryHrv}</span>
            <span className="text-slate-500 text-xs ml-0.5">ms</span>
            {preOvernightHrv != null && (
              <span className="text-xs text-slate-500 ml-2">(overnight avg {preOvernightHrv})</span>
            )}
          </span>
        )}
        {preRestingHr != null && (
          <span className="text-sm text-slate-300">
            <span className="text-slate-500">RHR</span>{' '}
            <span className="font-medium">{preRestingHr}</span>
            <span className="text-slate-500 text-xs ml-0.5">bpm</span>
          </span>
        )}
        {preSleepH != null && (
          <span className="text-sm text-slate-300">
            <span className="text-slate-500">Sleep</span>{' '}
            <span className="font-medium">{preSleepH.toFixed(1)}</span>
            <span className="text-slate-500 text-xs ml-0.5">h</span>
            {preSleepScore != null && (
              <span className="text-xs text-slate-500 ml-1">({preSleepScore})</span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}
