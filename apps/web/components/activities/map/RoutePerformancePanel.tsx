'use client';

import { useState, useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import Link from 'next/link';

interface SiblingEntry {
  id: string;
  start_time: string;
  distance_m: number;
  duration_s: number;
  temperature_f: number | null;
  dew_point_f: number | null;
  workout_type: string | null;
  avg_hr: number | null;
  name: string | null;
  total_elevation_gain: number | null;
}

interface Props {
  siblings: SiblingEntry[];
  currentActivityId: string;
  currentDistanceM: number;
  currentDurationS: number;
  sportType: string;
  unitSystem: 'imperial' | 'metric';
}

function formatSpeed(distM: number, durS: number, sport: string, unitSystem: 'imperial' | 'metric'): string {
  if (durS <= 0) return '-';
  if (sport === 'run') {
    const perKm = durS / (distM / 1000);
    const perUnit = unitSystem === 'imperial' ? perKm * 1.60934 : perKm;
    const min = Math.floor(perUnit / 60);
    const sec = Math.round(perUnit % 60);
    const label = unitSystem === 'imperial' ? '/mi' : '/km';
    return `${min}:${sec.toString().padStart(2, '0')}${label}`;
  }
  const mps = distM / durS;
  const factor = unitSystem === 'imperial' ? 2.23694 : 3.6;
  const label = unitSystem === 'imperial' ? ' mph' : ' km/h';
  return `${(mps * factor).toFixed(1)}${label}`;
}

function speedValue(distM: number, durS: number, sport: string): number {
  if (durS <= 0) return 0;
  if (sport === 'run') return durS / (distM / 1000);
  return distM / durS;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function weatherIcon(condition: string | null): string {
  if (!condition) return '';
  const c = condition.toLowerCase();
  if (c.includes('clear')) return '☀️';
  if (c.includes('cloud') || c.includes('overcast')) return '☁️';
  if (c.includes('rain')) return '🌧️';
  return '';
}

export default function RoutePerformancePanel({
  siblings,
  currentActivityId,
  currentDistanceM,
  currentDurationS,
  sportType,
  unitSystem,
}: Props) {
  const [showTable, setShowTable] = useState(false);

  const analysis = useMemo(() => {
    const all = [
      { id: currentActivityId, distance_m: currentDistanceM, duration_s: currentDurationS, start_time: new Date().toISOString(), isCurrent: true },
      ...siblings.map(s => ({ ...s, isCurrent: false })),
    ];

    const speeds = all.map(a => speedValue(a.distance_m, a.duration_s, sportType));
    const avgSpeed = speeds.reduce((a, b) => a + b, 0) / speeds.length;
    const currentSpeed = speeds[0];

    const isRun = sportType === 'run';
    let bestIdx = 0, worstIdx = 0;
    speeds.forEach((s, i) => {
      if (isRun ? s < speeds[bestIdx] : s > speeds[bestIdx]) bestIdx = i;
      if (isRun ? s > speeds[worstIdx] : s < speeds[worstIdx]) worstIdx = i;
    });

    const sorted = [...all].sort((a, b) =>
      new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );
    const sortedSpeeds = sorted.map(a => speedValue(a.distance_m, a.duration_s, sportType));

    let trendLabel = 'flat';
    if (sortedSpeeds.length >= 5) {
      const firstAvg = sortedSpeeds.slice(0, 3).reduce((a, b) => a + b, 0) / 3;
      const lastAvg = sortedSpeeds.slice(-3).reduce((a, b) => a + b, 0) / 3;
      const diff = lastAvg - firstAvg;
      const threshold = Math.abs(firstAvg) * 0.02;
      if (isRun) {
        trendLabel = diff < -threshold ? 'up' : diff > threshold ? 'down' : 'flat';
      } else {
        trendLabel = diff > threshold ? 'up' : diff < -threshold ? 'down' : 'flat';
      }
    }

    return { all, speeds, avgSpeed, currentSpeed, bestIdx, worstIdx, sorted, sortedSpeeds, trendLabel };
  }, [siblings, currentActivityId, currentDistanceM, currentDurationS, sportType]);

  const { all, speeds, avgSpeed, currentSpeed, bestIdx, sorted, sortedSpeeds, trendLabel } = analysis;

  const delta = currentSpeed - avgSpeed;
  const isRun = sportType === 'run';
  const deltaStr = isRun
    ? `${delta < 0 ? '-' : '+'}${Math.abs(Math.round(delta))}s`
    : `${delta > 0 ? '+' : ''}${delta.toFixed(1)}`;
  const deltaColor = isRun
    ? (delta < 0 ? 'text-emerald-400' : delta > 0 ? 'text-red-400' : 'text-slate-400')
    : (delta > 0 ? 'text-emerald-400' : delta < 0 ? 'text-red-400' : 'text-slate-400');

  const svgW = 400, svgH = 52;

  return (
    <div className="mt-2 rounded-lg bg-slate-800/30 border border-slate-700/30 p-3 space-y-3">
      {/* Summary line */}
      <div className="text-xs text-slate-300 space-y-0.5">
        <div>
          <span className="text-slate-400">This route:</span>{' '}
          <span className="font-medium">{all.length} efforts</span>
          {trendLabel !== 'flat' && (
            <span className={trendLabel === 'up' ? 'text-emerald-400' : 'text-red-400'}>
              {' '}· trending {trendLabel}
            </span>
          )}
        </div>
        <div>
          <span className="text-slate-400">Today:</span>{' '}
          <span className="font-medium">{formatSpeed(currentDistanceM, currentDurationS, sportType, unitSystem)}</span>
          <span className={`ml-1 ${deltaColor}`}>{deltaStr} vs avg</span>
        </div>
        <div className="text-slate-500">
          Best: {formatSpeed(all[bestIdx].distance_m, all[bestIdx].duration_s, sportType, unitSystem)}
          {' · '}Avg: {formatSpeed(currentDistanceM, avgSpeed > 0 ? (isRun ? currentDistanceM / 1000 * avgSpeed : currentDistanceM / avgSpeed) : 1, sportType, unitSystem)}
        </div>
      </div>

      {/* Trend chart */}
      {sortedSpeeds.length >= 2 && (
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full" style={{ height: svgH }} preserveAspectRatio="none">
          {(() => {
            const min = Math.min(...sortedSpeeds);
            const max = Math.max(...sortedSpeeds);
            const range = max - min || 1;
            const xStep = svgW / (sortedSpeeds.length - 1);
            const toY = (v: number) => svgH - 4 - ((v - min) / range) * (svgH - 8);

            return (
              <>
                <line x1="0" y1={toY(avgSpeed)} x2={svgW} y2={toY(avgSpeed)} stroke="#475569" strokeWidth="1" strokeDasharray="4,3" />
                <polyline
                  fill="none"
                  stroke="#64748b"
                  strokeWidth="1.5"
                  points={sortedSpeeds.map((s, i) => `${i * xStep},${toY(s)}`).join(' ')}
                />
                {sorted.map((a, i) => {
                  const isCurrent = 'isCurrent' in a && (a as { isCurrent?: boolean }).isCurrent;
                  return (
                    <circle
                      key={i}
                      cx={i * xStep}
                      cy={toY(sortedSpeeds[i])}
                      r={isCurrent ? 4 : 2.5}
                      fill={isCurrent ? '#3b82f6' : '#94a3b8'}
                      stroke={isCurrent ? '#fff' : 'none'}
                      strokeWidth={isCurrent ? 1.5 : 0}
                    />
                  );
                })}
              </>
            );
          })()}
        </svg>
      )}

      {/* Comparison table toggle */}
      <button
        onClick={() => setShowTable(!showTable)}
        className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
      >
        <ChevronDown className={`w-3 h-3 transition-transform ${showTable ? 'rotate-180' : ''}`} />
        {showTable ? 'Hide details' : 'Show all efforts'}
      </button>

      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] text-slate-300">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700/30">
                <th className="text-left py-1 pr-2 font-normal">Date</th>
                <th className="text-left py-1 pr-2 font-normal">Name</th>
                <th className="text-right py-1 pr-2 font-normal">{isRun ? 'Pace' : 'Speed'}</th>
                <th className="text-right py-1 pr-2 font-normal">+/- Avg</th>
                <th className="text-right py-1 font-normal">Conditions</th>
              </tr>
            </thead>
            <tbody>
              {siblings
                .sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime())
                .map((s) => {
                  const spd = speedValue(s.distance_m, s.duration_s, sportType);
                  const d = spd - avgSpeed;
                  const dStr = isRun
                    ? `${d < 0 ? '-' : '+'}${Math.abs(Math.round(d))}s`
                    : `${d > 0 ? '+' : ''}${d.toFixed(1)}`;
                  const dColor = isRun
                    ? (d < 0 ? 'text-emerald-400' : d > 0 ? 'text-red-400' : '')
                    : (d > 0 ? 'text-emerald-400' : d < 0 ? 'text-red-400' : '');
                  return (
                    <tr key={s.id} className="border-b border-slate-700/10 hover:bg-slate-700/10">
                      <td className="py-1 pr-2">
                        <Link href={`/activities/${s.id}`} className="hover:text-blue-400 transition-colors">
                          {formatDate(s.start_time)}
                        </Link>
                      </td>
                      <td className="py-1 pr-2 text-slate-400 truncate max-w-[120px]">{s.name || '-'}</td>
                      <td className="py-1 pr-2 text-right font-medium">{formatSpeed(s.distance_m, s.duration_s, sportType, unitSystem)}</td>
                      <td className={`py-1 pr-2 text-right ${dColor}`}>{dStr}</td>
                      <td className="py-1 text-right">
                        {s.temperature_f != null ? `${Math.round(s.temperature_f)}°F` : ''}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
