'use client';

import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';

interface Props {
  points: StreamPoint[];
  accentColor?: string;
  height?: number;
  unitSystem?: 'imperial' | 'metric';
}

export default function ElevationProfile({
  points,
  accentColor = '#3b82f6',
  height = 48,
  unitSystem = 'imperial',
}: Props) {
  const altitudes = points
    .map(p => p.altitude)
    .filter((a): a is number => a != null);
  if (altitudes.length < 2) return null;

  const min = Math.min(...altitudes);
  const max = Math.max(...altitudes);
  const range = max - min || 1;
  const width = 1000;

  const xStep = width / (altitudes.length - 1);
  const toY = (alt: number) => height - ((alt - min) / range) * (height - 4) - 2;

  const linePath = altitudes
    .map((alt, i) => `${i === 0 ? 'M' : 'L'} ${(i * xStep).toFixed(1)} ${toY(alt).toFixed(1)}`)
    .join(' ');
  const areaPath = `${linePath} L ${((altitudes.length - 1) * xStep).toFixed(1)} ${height} L 0 ${height} Z`;

  const rangeDisplay = unitSystem === 'imperial'
    ? `${Math.round(range * 3.281)} ft`
    : `${Math.round(range)} m`;

  return (
    <div className="mt-1 px-1">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[10px] text-slate-500">Elevation</span>
        <span className="text-[10px] text-slate-500">{rangeDisplay} range</span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="elev-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accentColor} stopOpacity={0.25} />
            <stop offset="100%" stopColor={accentColor} stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#elev-fill)" />
        <path d={linePath} fill="none" stroke={accentColor} strokeWidth="2" opacity="0.5" />
      </svg>
    </div>
  );
}
