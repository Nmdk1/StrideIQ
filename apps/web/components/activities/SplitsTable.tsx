'use client';

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';

type Split = {
  split_number: number;
  distance: number | null; // meters
  elapsed_time: number | null; // seconds
  moving_time: number | null; // seconds
  average_heartrate: number | null;
  max_heartrate: number | null;
  average_cadence: number | null;
  gap_seconds_per_mile: number | null;
};

const MILES_TO_KM = 1.60934;

function normalizeCadenceToSpm(raw: number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const v = Number(raw);
  if (!isFinite(v) || v <= 0) return null;
  // Strava running cadence often comes through as "strides/min" (~85-100).
  // Most athletes think in steps/min (~170-200), so convert if it looks like half-cadence.
  return v < 120 ? v * 2 : v;
}

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

function gapSecondsPerKmFromPerMile(gapSecondsPerMile: number | null | undefined): number | null {
  if (!gapSecondsPerMile || gapSecondsPerMile <= 0) return null;
  return gapSecondsPerMile / MILES_TO_KM;
}

export function SplitsTable({ splits }: { splits: Split[] }) {
  const { formatDistance, formatPace } = useUnits();

  if (!splits?.length) return null;

  const rows = splits
    .map((s) => {
      const time = s.moving_time ?? s.elapsed_time ?? null;
      const paceSecKm = paceSecondsPerKm(time, s.distance);
      const gapSecKm = gapSecondsPerKmFromPerMile(s.gap_seconds_per_mile);
      const cadenceSpm = normalizeCadenceToSpm(s.average_cadence);
      return {
        ...s,
        time,
        paceSecKm,
        gapSecKm,
        cadenceSpm,
      };
    })
    .filter((r) => r.time !== null && r.distance !== null);

  const bestPace = rows
    .map((r) => r.paceSecKm)
    .filter((v): v is number => typeof v === 'number' && isFinite(v))
    .reduce((min, v) => (v < min ? v : min), Number.POSITIVE_INFINITY);

  return (
    <div className="mt-5">
      <div className="overflow-x-auto rounded-lg border border-slate-700/50">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/40 text-slate-300">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Split</th>
              <th className="px-3 py-2 text-left font-semibold">Dist</th>
              <th className="px-3 py-2 text-left font-semibold">Time</th>
              <th className="px-3 py-2 text-left font-semibold">Pace</th>
              <th className="px-3 py-2 text-left font-semibold">GAP</th>
              <th className="px-3 py-2 text-left font-semibold">Avg HR</th>
              <th className="px-3 py-2 text-left font-semibold">Cadence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-950/20">
            {rows.map((r) => {
              const isBest = typeof r.paceSecKm === 'number' && isFinite(r.paceSecKm) && r.paceSecKm === bestPace;
              return (
                <tr key={r.split_number} className="text-slate-200">
                  <td className="px-3 py-2 whitespace-nowrap">{r.split_number}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDistance(r.distance, 2)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatDuration(r.time)}</td>
                  <td className={`px-3 py-2 whitespace-nowrap ${isBest ? 'font-semibold text-white' : ''}`}>
                    {formatPace(r.paceSecKm)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{r.gapSecKm ? formatPace(r.gapSecKm) : '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{r.average_heartrate ?? '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.cadenceSpm !== null && r.cadenceSpm !== undefined ? Math.round(r.cadenceSpm) : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Splits are sourced from Strava laps (auto-laps or manual laps/intervals). Pace is computed from split distance/time.
      </p>
    </div>
  );
}

