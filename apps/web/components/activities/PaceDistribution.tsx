'use client';

import React from 'react';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';

interface PaceDistributionProps {
  stream: StreamPoint[];
  effortIntensity: number[];
  movingTimeS: number;
}

const ZONES = [
  { label: 'Z1 · Recovery', max: 0.6, color: 'bg-blue-500' },
  { label: 'Z2 · Easy', max: 0.72, color: 'bg-green-500' },
  { label: 'Z3 · Moderate', max: 0.82, color: 'bg-yellow-500' },
  { label: 'Z4 · Threshold', max: 0.90, color: 'bg-orange-500' },
  { label: 'Z5 · VO2max+', max: 1.01, color: 'bg-red-500' },
] as const;

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, '0')}` : `${s}s`;
}

export function PaceDistribution({ stream, effortIntensity, movingTimeS }: PaceDistributionProps) {
  if (!effortIntensity.length || !stream.length) return null;

  const pointCount = Math.min(stream.length, effortIntensity.length);
  const zoneCounts = new Array(ZONES.length).fill(0);

  for (let i = 0; i < pointCount; i++) {
    const e = effortIntensity[i];
    for (let z = 0; z < ZONES.length; z++) {
      if (e < ZONES[z].max || z === ZONES.length - 1) {
        zoneCounts[z]++;
        break;
      }
    }
  }

  const totalPoints = zoneCounts.reduce((a, b) => a + b, 0);
  if (totalPoints === 0) return null;

  const zonePcts = zoneCounts.map(c => c / totalPoints);
  const maxPct = Math.max(...zonePcts);

  return (
    <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Effort Distribution</p>
      <div className="space-y-2">
        {ZONES.map((zone, i) => {
          const pct = zonePcts[i];
          const durationS = pct * movingTimeS;
          if (pct < 0.005) return null;

          return (
            <div key={zone.label} className="flex items-center gap-3">
              <span className="text-xs text-slate-400 w-28 flex-shrink-0">{zone.label}</span>
              <div className="flex-1 h-5 bg-slate-800/50 rounded overflow-hidden relative">
                <div
                  className={`h-full ${zone.color} rounded transition-all`}
                  style={{ width: `${maxPct > 0 ? (pct / maxPct) * 100 : 0}%` }}
                />
              </div>
              <span className="text-xs text-slate-300 tabular-nums w-14 text-right font-medium">
                {(pct * 100).toFixed(0)}%
              </span>
              <span className="text-xs text-slate-500 tabular-nums w-14 text-right">
                {formatDuration(durationS)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
