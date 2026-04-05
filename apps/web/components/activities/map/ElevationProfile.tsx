'use client';

import { useRef, useMemo, useState } from 'react';
import { useStreamHover } from '@/lib/context/StreamHoverContext';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';

interface Props {
  points: StreamPoint[];
  accentColor?: string;
  height?: number;
  unitSystem?: 'imperial' | 'metric';
}

function formatPace(sPerKm: number, unitSystem: 'imperial' | 'metric'): string {
  const s = unitSystem === 'imperial' ? sPerKm * 1.60934 : sPerKm;
  const min = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  const label = unitSystem === 'imperial' ? '/mi' : '/km';
  return `${min}:${sec.toString().padStart(2, '0')}${label}`;
}

export default function ElevationProfile({
  points,
  accentColor = '#3b82f6',
  height = 56,
  unitSystem = 'imperial',
}: Props) {
  const { hoveredIndex, setHoveredIndex } = useStreamHover();
  const containerRef = useRef<HTMLDivElement>(null);
  const [localHover, setLocalHover] = useState<{ x: number; index: number } | null>(null);

  const altitudes = useMemo(
    () => points.map(p => p.altitude).filter((a): a is number => a != null),
    [points],
  );
  if (altitudes.length < 2) return null;

  const min = Math.min(...altitudes);
  const max = Math.max(...altitudes);
  const range = max - min || 1;
  const svgWidth = 1000;
  const xStep = svgWidth / (altitudes.length - 1);
  const toY = (alt: number) => height - ((alt - min) / range) * (height - 6) - 3;

  const linePath = altitudes
    .map((alt, i) => `${i === 0 ? 'M' : 'L'} ${(i * xStep).toFixed(1)} ${toY(alt).toFixed(1)}`)
    .join(' ');
  const areaPath = `${linePath} L ${((altitudes.length - 1) * xStep).toFixed(1)} ${height} L 0 ${height} Z`;

  const rangeDisplay = unitSystem === 'imperial'
    ? `${Math.round(range * 3.281)} ft`
    : `${Math.round(range)} m`;

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    const index = Math.round(pct * (points.length - 1));
    const clamped = Math.max(0, Math.min(points.length - 1, index));
    setHoveredIndex(clamped);
    setLocalHover({ x, index: clamped });
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
    setLocalHover(null);
  };

  const cursorPct = hoveredIndex != null
    ? (hoveredIndex / (points.length - 1)) * 100
    : null;

  const hovered = localHover != null ? points[localHover.index] : null;

  return (
    <div className="mt-1 px-1" ref={containerRef}>
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[10px] text-slate-500">Elevation</span>
        <span className="text-[10px] text-slate-500">{rangeDisplay} range</span>
      </div>

      <div
        className="relative cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <svg
          viewBox={`0 0 ${svgWidth} ${height}`}
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

        {/* Cursor line from any hover source */}
        {cursorPct != null && (
          <div
            className="absolute top-0 bottom-0 w-px bg-slate-400/50 pointer-events-none"
            style={{ left: `${cursorPct}%` }}
          />
        )}

        {/* Tooltip on direct hover */}
        {localHover != null && hovered && (
          <div
            className="absolute -top-16 px-2 py-1.5 rounded bg-slate-800/95 border border-slate-600/40 text-[10px] leading-tight pointer-events-none z-10 whitespace-nowrap"
            style={{
              left: Math.min(Math.max(localHover.x, 40), (containerRef.current?.offsetWidth ?? 300) - 40),
              transform: 'translateX(-50%)',
            }}
          >
            {hovered.altitude != null && (
              <div className="text-slate-300">
                {unitSystem === 'imperial'
                  ? `${Math.round(hovered.altitude * 3.281)} ft`
                  : `${Math.round(hovered.altitude)} m`}
              </div>
            )}
            {hovered.grade != null && (
              <div className="text-slate-400">
                {hovered.grade > 0 ? '+' : ''}{hovered.grade.toFixed(1)}%
              </div>
            )}
            {hovered.pace != null && (
              <div className="text-slate-400">{formatPace(hovered.pace, unitSystem)}</div>
            )}
            {hovered.hr != null && (
              <div className="text-red-400/80">{hovered.hr} bpm</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
