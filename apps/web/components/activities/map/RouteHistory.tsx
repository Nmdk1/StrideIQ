'use client';

import { useState, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Cloud, CloudOff } from 'lucide-react';
import Link from 'next/link';

interface SiblingMeta {
  id: string;
  start_time: string;
  distance_m: number;
  duration_s: number;
  temperature_f: number | null;
  dew_point_f: number | null;
  heat_adjustment_pct: number | null;
  workout_type: string | null;
  avg_hr: number | null;
  name: string | null;
  total_elevation_gain: number | null;
}

interface SplitData {
  split_number: number;
  distance: number | null;
  elapsed_time: number | null;
  moving_time: number | null;
  average_heartrate: number | null;
  gap_seconds_per_mile: number | null;
}

interface Props {
  activityId: string;
  siblings: SiblingMeta[];
  currentDistanceM: number;
  currentDurationS: number;
  currentHeatAdjPct: number | null;
  unitSystem: 'imperial' | 'metric';
}

function paceSecsPerUnit(distM: number, durS: number, unitSystem: 'imperial' | 'metric'): number {
  if (distM <= 0 || durS <= 0) return 0;
  const perKm = durS / (distM / 1000);
  return unitSystem === 'imperial' ? perKm * 1.60934 : perKm;
}

function adjustPace(rawPace: number, heatPct: number | null): number {
  if (!heatPct || heatPct <= 0) return rawPace;
  return rawPace / (1 + heatPct / 100);
}

function formatPace(secsPerUnit: number, unitSystem: 'imperial' | 'metric'): string {
  if (secsPerUnit <= 0) return '-';
  const min = Math.floor(secsPerUnit / 60);
  const sec = Math.round(secsPerUnit % 60);
  const label = unitSystem === 'imperial' ? '/mi' : '/km';
  return `${min}:${sec.toString().padStart(2, '0')}${label}`;
}

function formatDelta(deltaSecs: number): string {
  const abs = Math.abs(Math.round(deltaSecs));
  const sign = deltaSecs < 0 ? '-' : '+';
  if (abs >= 60) {
    const m = Math.floor(abs / 60);
    const s = abs % 60;
    return `${sign}${m}:${s.toString().padStart(2, '0')}`;
  }
  return `${sign}${abs}s`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const CHART_COLORS = [
  '#3b82f6', // current - blue (bold)
  '#94a3b8', // sibling 1
  '#64748b', // sibling 2
  '#6366f1', // sibling 3
  '#8b5cf6', // sibling 4
  '#a78bfa', // sibling 5
];

export default function RouteHistory({
  activityId,
  siblings,
  currentDistanceM,
  currentDurationS,
  currentHeatAdjPct,
  unitSystem,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [weatherAdj, setWeatherAdj] = useState(false);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  const recent5 = useMemo(() => {
    return [...siblings]
      .sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime())
      .slice(0, 5);
  }, [siblings]);

  const siblingIds = useMemo(() => recent5.map(s => s.id), [recent5]);

  const { data: splitsData, isLoading: splitsLoading } = useQuery<{ splits_by_activity: Record<string, SplitData[]> }>({
    queryKey: ['route-sibling-splits', activityId, siblingIds.join(',')],
    queryFn: async () => {
      const res = await fetch(
        `/v1/activities/${activityId}/route-siblings/splits?sibling_ids=${siblingIds.join(',')}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } },
      );
      if (!res.ok) return { splits_by_activity: {} };
      return res.json();
    },
    enabled: expanded && siblingIds.length > 0,
    staleTime: 10 * 60 * 1000,
  });

  const summary = useMemo(() => {
    const allPaces = [
      paceSecsPerUnit(currentDistanceM, currentDurationS, unitSystem),
      ...siblings.map(s => paceSecsPerUnit(s.distance_m, s.duration_s, unitSystem)),
    ].filter(p => p > 0);

    const currentPace = allPaces[0] || 0;
    const avgPace = allPaces.reduce((a, b) => a + b, 0) / allPaces.length;
    const delta = currentPace - avgPace;

    const sorted = [...siblings].sort((a, b) =>
      new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );
    let trendDelta = 0;
    if (sorted.length >= 4) {
      const firstPaces = sorted.slice(0, 3).map(s => paceSecsPerUnit(s.distance_m, s.duration_s, unitSystem));
      const lastPaces = sorted.slice(-3).map(s => paceSecsPerUnit(s.distance_m, s.duration_s, unitSystem));
      const firstAvg = firstPaces.reduce((a, b) => a + b, 0) / firstPaces.length;
      const lastAvg = lastPaces.reduce((a, b) => a + b, 0) / lastPaces.length;
      trendDelta = firstAvg - lastAvg;
    }

    return { currentPace, avgPace, delta, trendDelta, totalRuns: siblings.length + 1 };
  }, [siblings, currentDistanceM, currentDurationS, unitSystem]);

  const chartData = useMemo(() => {
    if (!splitsData?.splits_by_activity) return null;

    const allSplits = splitsData.splits_by_activity;
    const entries: { id: string; splits: SplitData[]; heatPct: number | null; color: string; label: string; isCurrent: boolean }[] = [];

    const currentSplits = allSplits[activityId];
    if (currentSplits?.length) {
      entries.push({
        id: activityId,
        splits: currentSplits,
        heatPct: currentHeatAdjPct,
        color: CHART_COLORS[0],
        label: 'This run',
        isCurrent: true,
      });
    }

    recent5.forEach((sib, i) => {
      const sibSplits = allSplits[sib.id];
      if (sibSplits?.length) {
        entries.push({
          id: sib.id,
          splits: sibSplits,
          heatPct: sib.heat_adjustment_pct,
          color: CHART_COLORS[i + 1] || '#475569',
          label: formatDate(sib.start_time),
          isCurrent: false,
        });
      }
    });

    if (entries.length < 2) return null;

    const maxSplits = Math.max(...entries.map(e => e.splits.length));

    const avgByMile: number[] = [];
    for (let mi = 0; mi < maxSplits; mi++) {
      const paces: number[] = [];
      for (const e of entries) {
        const split = e.splits[mi];
        if (split?.elapsed_time && split?.distance) {
          let pace = paceSecsPerUnit(split.distance, split.elapsed_time, unitSystem);
          if (weatherAdj) pace = adjustPace(pace, e.heatPct);
          paces.push(pace);
        }
      }
      avgByMile.push(paces.length > 0 ? paces.reduce((a, b) => a + b, 0) / paces.length : 0);
    }

    return { entries, maxSplits, avgByMile };
  }, [splitsData, activityId, recent5, currentHeatAdjPct, weatherAdj, unitSystem]);

  const toggleExpand = useCallback(() => setExpanded(prev => !prev), []);

  const trendStr = summary.trendDelta > 3
    ? `Trending ${formatDelta(summary.trendDelta)} faster`
    : summary.trendDelta < -3
    ? `Trending ${formatDelta(Math.abs(summary.trendDelta))} slower`
    : null;

  const deltaColor = summary.delta < -1 ? 'text-emerald-400' : summary.delta > 1 ? 'text-amber-400' : 'text-slate-400';

  return (
    <div className="mt-2">
      {/* Summary line — always visible, tappable */}
      <button
        onClick={toggleExpand}
        className="w-full text-left text-xs text-slate-300 hover:text-slate-100 transition-colors py-1.5 px-1 -mx-1 rounded"
      >
        <span className="text-slate-400">{summary.totalRuns} runs on this route</span>
        {trendStr && (
          <span className="text-emerald-400"> · {trendStr}</span>
        )}
        <span> · This run: </span>
        <span className={deltaColor}>{formatDelta(summary.delta)}{unitSystem === 'imperial' ? '/mi' : '/km'} vs avg</span>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="mt-2 rounded-lg bg-slate-800/30 border border-slate-700/30 p-3 space-y-3">
          {/* Weather toggle */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Pace over distance</span>
            <button
              onClick={() => setWeatherAdj(!weatherAdj)}
              className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full transition-colors ${
                weatherAdj
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-700/30 text-slate-500 border border-slate-700/30 hover:text-slate-300'
              }`}
            >
              {weatherAdj ? <Cloud className="w-3 h-3" /> : <CloudOff className="w-3 h-3" />}
              {weatherAdj ? 'Weather-adjusted' : 'Adjust for weather'}
            </button>
          </div>

          {/* Pace-over-distance chart */}
          {splitsLoading && (
            <div className="flex items-center justify-center py-6">
              <div className="w-4 h-4 border-2 border-slate-600 border-t-blue-400 rounded-full animate-spin" />
            </div>
          )}

          {chartData && (
            <PaceOverDistanceChart
              entries={chartData.entries}
              maxSplits={chartData.maxSplits}
              avgByMile={chartData.avgByMile}
              unitSystem={unitSystem}
              weatherAdj={weatherAdj}
              highlightedId={highlightedId}
            />
          )}

          {chartData && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px]">
              {chartData.entries.map(e => (
                <span key={e.id} className="flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: e.color, opacity: e.isCurrent ? 1 : 0.7 }} />
                  <span className={e.isCurrent ? 'text-slate-200 font-medium' : 'text-slate-500'}>{e.label}</span>
                </span>
              ))}
              <span className="flex items-center gap-1">
                <span className="inline-block w-4 border-t border-dashed border-slate-500" />
                <span className="text-slate-500">avg</span>
              </span>
            </div>
          )}

          {/* Compact table */}
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] text-slate-300">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700/30">
                  <th className="text-left py-1 pr-2 font-normal">Date</th>
                  <th className="text-right py-1 pr-2 font-normal">Pace</th>
                  <th className="text-right py-1 pr-2 font-normal">vs Avg</th>
                  <th className="text-right py-1 pr-2 font-normal">HR</th>
                  <th className="text-right py-1 font-normal">Temp</th>
                </tr>
              </thead>
              <tbody>
                {/* Current run */}
                <tr
                  className="border-b border-slate-700/10 bg-blue-500/5"
                  onMouseEnter={() => setHighlightedId(activityId)}
                  onMouseLeave={() => setHighlightedId(null)}
                >
                  <td className="py-1 pr-2 font-medium text-blue-400">Today</td>
                  <td className="py-1 pr-2 text-right font-medium">
                    {formatPace(
                      weatherAdj
                        ? adjustPace(paceSecsPerUnit(currentDistanceM, currentDurationS, unitSystem), currentHeatAdjPct)
                        : paceSecsPerUnit(currentDistanceM, currentDurationS, unitSystem),
                      unitSystem,
                    )}
                  </td>
                  <td className={`py-1 pr-2 text-right ${deltaColor}`}>
                    {formatDelta(summary.delta)}
                  </td>
                  <td className="py-1 pr-2 text-right text-slate-500">-</td>
                  <td className="py-1 text-right text-slate-500">-</td>
                </tr>
                {/* Siblings sorted most recent first */}
                {[...siblings]
                  .sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime())
                  .map(s => {
                    let pace = paceSecsPerUnit(s.distance_m, s.duration_s, unitSystem);
                    if (weatherAdj) pace = adjustPace(pace, s.heat_adjustment_pct);
                    const d = pace - summary.avgPace;
                    const dc = d < -1 ? 'text-emerald-400' : d > 1 ? 'text-amber-400' : 'text-slate-400';
                    return (
                      <tr
                        key={s.id}
                        className={`border-b border-slate-700/10 hover:bg-slate-700/10 transition-colors ${highlightedId === s.id ? 'bg-slate-700/20' : ''}`}
                        onMouseEnter={() => setHighlightedId(s.id)}
                        onMouseLeave={() => setHighlightedId(null)}
                      >
                        <td className="py-1 pr-2">
                          <Link href={`/activities/${s.id}`} className="hover:text-blue-400 transition-colors">
                            {formatDate(s.start_time)}
                          </Link>
                        </td>
                        <td className="py-1 pr-2 text-right font-medium">{formatPace(pace, unitSystem)}</td>
                        <td className={`py-1 pr-2 text-right ${dc}`}>{formatDelta(d)}</td>
                        <td className="py-1 pr-2 text-right text-slate-400">{s.avg_hr ?? '-'}</td>
                        <td className="py-1 text-right text-slate-400">
                          {s.temperature_f != null ? `${Math.round(s.temperature_f)}°` : '-'}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>

          {weatherAdj && (
            <p className="text-[10px] text-slate-600 italic">
              Weather-adjusted paces use dew point heat model. Hotter conditions → faster adjusted pace.
            </p>
          )}
        </div>
      )}
    </div>
  );
}


interface PaceChartProps {
  entries: { id: string; splits: SplitData[]; heatPct: number | null; color: string; isCurrent: boolean }[];
  maxSplits: number;
  avgByMile: number[];
  unitSystem: 'imperial' | 'metric';
  weatherAdj: boolean;
  highlightedId: string | null;
}

function PaceOverDistanceChart({ entries, maxSplits, avgByMile, unitSystem, weatherAdj, highlightedId }: PaceChartProps) {
  const svgW = 400;
  const svgH = 120;
  const padL = 40;
  const padR = 8;
  const padT = 8;
  const padB = 20;
  const plotW = svgW - padL - padR;
  const plotH = svgH - padT - padB;

  const { allPaces, minP, maxP } = useMemo(() => {
    const all: number[] = [];
    for (const e of entries) {
      for (const s of e.splits) {
        if (s.elapsed_time && s.distance) {
          let p = paceSecsPerUnit(s.distance, s.elapsed_time, unitSystem);
          if (weatherAdj) p = adjustPace(p, e.heatPct);
          all.push(p);
        }
      }
    }
    all.push(...avgByMile.filter(p => p > 0));
    const sorted = [...all].sort((a, b) => a - b);
    const p5 = sorted[Math.floor(sorted.length * 0.05)] || 0;
    const p95 = sorted[Math.floor(sorted.length * 0.95)] || 1;
    const margin = (p95 - p5) * 0.1;
    return { allPaces: all, minP: p5 - margin, maxP: p95 + margin };
  }, [entries, avgByMile, weatherAdj, unitSystem]);

  const yTicks = useMemo(() => {
    const range = maxP - minP;
    const step = range <= 60 ? 15 : range <= 120 ? 30 : 60;
    const ticks: number[] = [];
    let v = Math.ceil(minP / step) * step;
    while (v <= maxP) {
      ticks.push(v);
      v += step;
    }
    return ticks;
  }, [minP, maxP]);

  if (maxSplits < 2 || allPaces.length === 0) return null;

  const xStep = plotW / (maxSplits - 1);
  const toX = (mi: number) => padL + mi * xStep;
  const toY = (pace: number) => {
    const t = Math.max(0, Math.min(1, (pace - minP) / ((maxP - minP) || 1)));
    return padT + t * plotH;
  };

  const unitLabel = unitSystem === 'imperial' ? '/mi' : '/km';

  return (
    <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
      {yTicks.map(v => (
        <g key={v}>
          <line x1={padL} y1={toY(v)} x2={svgW - padR} y2={toY(v)} stroke="#334155" strokeWidth="0.5" />
          <text x={padL - 4} y={toY(v) + 3} textAnchor="end" fill="#64748b" fontSize="8">
            {Math.floor(v / 60)}:{(Math.round(v) % 60).toString().padStart(2, '0')}
          </text>
        </g>
      ))}

      {/* X axis labels */}
      {Array.from({ length: maxSplits }, (_, i) => {
        const show = maxSplits <= 8 || i === 0 || i === maxSplits - 1 || (i + 1) % Math.ceil(maxSplits / 6) === 0;
        if (!show) return null;
        return (
          <text key={i} x={toX(i)} y={svgH - 4} textAnchor="middle" fill="#64748b" fontSize="8">
            {i + 1}{unitLabel}
          </text>
        );
      })}

      {/* Average dashed line */}
      {avgByMile.length >= 2 && (
        <polyline
          fill="none"
          stroke="#475569"
          strokeWidth="1"
          strokeDasharray="4,3"
          points={avgByMile.map((p, i) => `${toX(i)},${toY(p)}`).join(' ')}
        />
      )}

      {/* Sibling lines (behind current) */}
      {entries.filter(e => !e.isCurrent).map(e => {
        const pts = e.splits
          .filter(s => s.elapsed_time && s.distance)
          .map(s => {
            let p = paceSecsPerUnit(s.distance!, s.elapsed_time!, unitSystem);
            if (weatherAdj) p = adjustPace(p, e.heatPct);
            return { mi: s.split_number - 1, pace: p };
          });
        if (pts.length < 2) return null;
        const isHighlighted = highlightedId === e.id;
        return (
          <polyline
            key={e.id}
            fill="none"
            stroke={e.color}
            strokeWidth={isHighlighted ? 2 : 1.2}
            opacity={isHighlighted ? 0.9 : 0.4}
            points={pts.map(p => `${toX(p.mi)},${toY(p.pace)}`).join(' ')}
          />
        );
      })}

      {/* Current run line (bold, on top) */}
      {entries.filter(e => e.isCurrent).map(e => {
        const pts = e.splits
          .filter(s => s.elapsed_time && s.distance)
          .map(s => {
            let p = paceSecsPerUnit(s.distance!, s.elapsed_time!, unitSystem);
            if (weatherAdj) p = adjustPace(p, e.heatPct);
            return { mi: s.split_number - 1, pace: p };
          });
        if (pts.length < 2) return null;
        return (
          <g key={e.id}>
            <polyline
              fill="none"
              stroke={e.color}
              strokeWidth="2.5"
              opacity={1}
              points={pts.map(p => `${toX(p.mi)},${toY(p.pace)}`).join(' ')}
            />
            {pts.map((p, i) => (
              <circle key={i} cx={toX(p.mi)} cy={toY(p.pace)} r={2} fill={e.color} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
