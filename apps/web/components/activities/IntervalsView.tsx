'use client';

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import type { Split, IntervalSummary } from '@/lib/types/splits';
import { GarminBadge } from '@/components/integrations/GarminBadge';

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return '—';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.round(seconds % 60);
  if (hrs > 0) return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function paceSecondsPerKm(timeS: number | null | undefined, distanceM: number | null | undefined): number | null {
  if (!timeS || !distanceM || distanceM <= 0) return null;
  return timeS / (distanceM / 1000);
}

const TYPE_LABELS: Record<string, string> = {
  warm_up: 'Warm Up',
  work: 'Run',
  rest: 'Rest',
  cool_down: 'Cool Down',
};

export interface IntervalsViewProps {
  splits: Split[];
  intervalSummary: IntervalSummary;
  provider?: string | null;
  deviceName?: string | null;
}

export function IntervalsView({ splits, intervalSummary, provider, deviceName }: IntervalsViewProps) {
  const { formatDistance, formatPace } = useUnits();

  if (!splits?.length || !intervalSummary?.is_structured) return null;

  const rows = splits
    .map((s) => {
      const splitTime = s.moving_time ?? s.elapsed_time ?? null;
      const paceSecKm = paceSecondsPerKm(splitTime, s.distance);
      return { ...s, splitTime, paceSecKm };
    })
    .filter((r) => r.splitTime !== null && r.distance !== null);

  let totalTime = 0;
  let totalDist = 0;
  for (const r of rows) {
    totalTime += r.splitTime || 0;
    totalDist += r.distance || 0;
  }
  const totalPace = paceSecondsPerKm(totalTime, totalDist);

  return (
    <div className="mt-5">
      {intervalSummary.workout_description && (
        <div className="mb-3 px-1">
          <p className="text-base font-semibold text-white">
            {intervalSummary.workout_description}
          </p>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-700/50">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/40 text-slate-300">
            <tr>
              <th className="w-8 px-2 py-2 text-center font-semibold">#</th>
              <th className="px-3 py-2 text-left font-semibold">Type</th>
              <th className="px-3 py-2 text-right font-semibold">Time</th>
              <th className="px-3 py-2 text-right font-semibold">Dist</th>
              <th className="px-3 py-2 text-right font-semibold">Pace</th>
              <th className="px-3 py-2 text-right font-semibold hidden sm:table-cell">HR</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 bg-slate-950/20">
            {rows.map((r) => {
              const isWork = r.lap_type === 'work';
              const isWarmCool = r.lap_type === 'warm_up' || r.lap_type === 'cool_down';
              const isFastest = isWork && r.interval_number === intervalSummary.fastest_interval;
              const typeLabel = TYPE_LABELS[r.lap_type || ''] || '—';

              return (
                <tr
                  key={r.split_number}
                  className={
                    isWork
                      ? 'text-white'
                      : isWarmCool
                        ? 'text-slate-500'
                        : 'text-slate-400'
                  }
                >
                  <td className="px-2 py-2.5 text-center whitespace-nowrap tabular-nums">
                    {isWork ? (
                      <span className={isFastest ? 'text-amber-400 font-bold' : 'font-semibold'}>
                        {r.interval_number}
                      </span>
                    ) : null}
                  </td>
                  <td className={`px-3 py-2.5 whitespace-nowrap ${isWork ? 'font-semibold' : ''}`}>
                    {typeLabel}
                  </td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap tabular-nums">
                    {formatDuration(r.splitTime)}
                  </td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap tabular-nums">
                    {formatDistance(r.distance, 2)}
                  </td>
                  <td className={`px-3 py-2.5 text-right whitespace-nowrap tabular-nums ${isFastest ? 'text-amber-400 font-bold' : ''}`}>
                    {formatPace(r.paceSecKm)}
                    {isFastest && ' ★'}
                  </td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap tabular-nums hidden sm:table-cell">
                    {r.average_heartrate ?? '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="border-t border-slate-700 bg-slate-900/30">
            <tr className="text-slate-300 font-medium">
              <td className="px-2 py-2.5"></td>
              <td className="px-3 py-2.5">Total</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatDuration(totalTime)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatDistance(totalDist, 2)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatPace(totalPace)}</td>
              <td className="px-3 py-2.5 hidden sm:table-cell"></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="mt-2 text-xs text-slate-500">
        {provider === 'garmin' ? (
          <span className="flex items-center gap-1.5 flex-wrap">
            <GarminBadge deviceName={deviceName} size="sm" />
          </span>
        ) : (
          <span>Intervals detected from lap data.</span>
        )}
      </div>
    </div>
  );
}
