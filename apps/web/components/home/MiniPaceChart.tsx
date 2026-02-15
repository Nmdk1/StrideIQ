'use client';

/**
 * MiniPaceChart — Home hero pace chart.
 *
 * NOT clean and minimal. Visually impactful:
 *   - Effort-gradient AREA fill (the main visual mass)
 *   - Bright pace line with glow on top
 *   - Elevation terrain behind
 *   - Interactive hover crosshair with pace tooltip
 */

import React, { useCallback, useId, useMemo, useRef, useState } from 'react';
import { effortToColor } from '@/components/activities/rsi/utils/effortColor';
import { useUnits } from '@/lib/context/UnitsContext';

interface MiniPaceChartProps {
  paceStream: number[];
  effortIntensity: number[];
  elevationStream?: number[] | null;
  height?: number;
}

/** Boost an effortToColor result for hero rendering — increase lightness. */
function effortToHeroColor(effort: number, alpha = 1): string {
  const base = effortToColor(effort);
  // Parse rgb values, boost lightness by blending toward white
  const match = base.match(/rgb\((\d+),(\d+),(\d+)\)/);
  if (!match) return base;
  const [, rs, gs, bs] = match;
  const boost = 1.4; // 40% brighter
  const r = Math.min(255, Math.round(parseInt(rs) * boost));
  const g = Math.min(255, Math.round(parseInt(gs) * boost));
  const b = Math.min(255, Math.round(parseInt(bs) * boost));
  if (alpha < 1) return `rgba(${r},${g},${b},${alpha})`;
  return `rgb(${r},${g},${b})`;
}

export function MiniPaceChart({
  paceStream,
  effortIntensity,
  elevationStream,
  height = 140,
}: MiniPaceChartProps) {
  const { formatPace } = useUnits();
  const containerRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ x: number; idx: number } | null>(null);

  const chartData = useMemo(() => {
    const n = paceStream.length;
    if (n === 0) return null;

    const paceMin = 120;
    const paceMax = 900;
    const clamped = paceStream.map(p => Math.max(paceMin, Math.min(paceMax, p)));

    const actualMin = Math.min(...clamped);
    const actualMax = Math.max(...clamped);
    const range = actualMax - actualMin || 1;
    const padMin = Math.max(paceMin, actualMin - range * 0.1);
    const padMax = Math.min(paceMax, actualMax + range * 0.1);

    // 0 = slow/bottom, 1 = fast/top
    const paceNorm = clamped.map(p => 1 - (p - padMin) / (padMax - padMin || 1));

    let elevNorm: number[] | null = null;
    if (elevationStream && elevationStream.length > 0) {
      const elev = elevationStream.length === n
        ? elevationStream
        : _resample(elevationStream, n);
      const eMin = Math.min(...elev);
      const eMax = Math.max(...elev);
      const eRange = eMax - eMin || 1;
      elevNorm = elev.map(e => ((e - eMin) / eRange) * 0.35);
    }

    return { n, paceNorm, elevNorm, padMin, padMax };
  }, [paceStream, elevationStream]);

  const lineGradientId = `paceLineGrad-${useId()}`;
  const areaGradientId = `paceAreaGrad-${useId()}`;
  const glowFilterId = `paceGlow-${useId()}`;

  const updateHover = useCallback((clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect || !chartData) return;
    const relX = (clientX - rect.left) / rect.width;
    const idx = Math.round(relX * (chartData.n - 1));
    const clampedIdx = Math.max(0, Math.min(chartData.n - 1, idx));
    setHover({ x: relX * 100, idx: clampedIdx });
  }, [chartData]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    updateHover(e.clientX);
  }, [updateHover]);

  const handleTouchMove = useCallback((e: React.TouchEvent<HTMLDivElement>) => {
    if (e.touches.length > 0) {
      e.preventDefault(); // prevent scroll while scrubbing
      updateHover(e.touches[0].clientX);
    }
  }, [updateHover]);

  const handleLeave = useCallback(() => setHover(null), []);

  if (!chartData) return null;

  const { n, paceNorm, elevNorm } = chartData;
  const pad = { top: 8, bottom: 8 };
  const drawH = height - pad.top - pad.bottom;
  const xStep = 100 / (n - 1);

  // Pace line points
  const pacePoints = paceNorm.map((py, i) => ({
    x: i * xStep,
    y: pad.top + (1 - py) * drawH,
  }));

  // Pace LINE path
  const pacePath = pacePoints
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');

  // Pace AREA path (line + close to bottom)
  const areaPath = pacePath +
    ` L ${pacePoints[pacePoints.length - 1].x.toFixed(2)} ${height}` +
    ` L ${pacePoints[0].x.toFixed(2)} ${height} Z`;

  // Elevation fill path
  let elevPath: string | null = null;
  if (elevNorm) {
    const elevPoints = elevNorm.map((ey, i) => ({
      x: i * xStep,
      y: height - pad.bottom - ey * drawH,
    }));
    elevPath =
      `M 0 ${height} ` +
      elevPoints.map(p => `L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ') +
      ` L 100 ${height} Z`;
  }

  // Gradient stops — brighter for hero
  const maxStops = 40;
  const stopStep = Math.max(1, Math.floor(n / maxStops));
  const lineStops: Array<{ offset: string; color: string }> = [];
  const areaStops: Array<{ offset: string; color: string }> = [];
  for (let i = 0; i < n; i += stopStep) {
    const effort = effortIntensity[Math.min(i, effortIntensity.length - 1)] ?? 0.5;
    const off = `${((i / (n - 1)) * 100).toFixed(1)}%`;
    lineStops.push({ offset: off, color: effortToHeroColor(effort) });
    areaStops.push({ offset: off, color: effortToHeroColor(effort, 0.25) });
  }
  // Ensure last stop
  const lastE = effortIntensity[effortIntensity.length - 1] ?? 0.5;
  if (!lineStops.length || lineStops[lineStops.length - 1].offset !== '100.0%') {
    lineStops.push({ offset: '100.0%', color: effortToHeroColor(lastE) });
    areaStops.push({ offset: '100.0%', color: effortToHeroColor(lastE, 0.25) });
  }

  // Hover data
  const hoverPace = hover ? paceStream[hover.idx] : null;
  const hoverEffort = hover ? (effortIntensity[hover.idx] ?? 0.5) : null;
  const hoverY = hover ? pacePoints[hover.idx]?.y : null;

  return (
    <div
      ref={containerRef}
      className="relative cursor-crosshair"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleLeave}
      onTouchStart={handleTouchMove}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleLeave}
      style={{ height }}
      data-testid="mini-pace-chart-container"
    >
      <svg
        data-testid="mini-pace-chart"
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        className="w-full absolute inset-0"
        style={{ height, display: 'block' }}
      >
        <defs>
          {/* Line gradient — boosted colors */}
          <linearGradient id={lineGradientId} x1="0" y1="0" x2="1" y2="0">
            {lineStops.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} />
            ))}
          </linearGradient>
          {/* Area gradient — same colors at 25% alpha */}
          <linearGradient id={areaGradientId} x1="0" y1="0" x2="1" y2="0">
            {areaStops.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} />
            ))}
          </linearGradient>
          {/* Glow filter for the pace line */}
          <filter id={glowFilterId} x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Elevation terrain — visible, slate-tinted */}
        {elevPath && (
          <path
            d={elevPath}
            fill="rgba(148, 163, 184, 0.15)"
            data-testid="elevation-fill"
          />
        )}

        {/* Area fill under the pace line — this is the main visual mass */}
        <path
          d={areaPath}
          fill={`url(#${areaGradientId})`}
          data-testid="pace-area"
        />

        {/* Pace line — thick, glowing, effort-colored */}
        <path
          d={pacePath}
          fill="none"
          stroke={`url(#${lineGradientId})`}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          filter={`url(#${glowFilterId})`}
          data-testid="pace-line"
        />

        {/* Hover crosshair */}
        {hover && (
          <line
            x1={hover.x}
            y1={0}
            x2={hover.x}
            y2={height}
            stroke="rgba(255,255,255,0.4)"
            strokeWidth="0.3"
            vectorEffect="non-scaling-stroke"
          />
        )}

        {/* Hover dot on the line */}
        {hover && hoverY != null && (
          <circle
            cx={hover.x}
            cy={hoverY}
            r="1"
            fill="white"
            vectorEffect="non-scaling-stroke"
            style={{ filter: 'drop-shadow(0 0 2px rgba(255,255,255,0.8))' }}
          />
        )}
      </svg>

      {/* Hover tooltip — positioned above the chart */}
      {hover && hoverPace != null && hoverEffort != null && (
        <div
          className="absolute top-1 pointer-events-none"
          style={{
            left: `${Math.max(5, Math.min(85, hover.x))}%`,
            transform: 'translateX(-50%)',
          }}
        >
          <div className="bg-slate-800/90 backdrop-blur-sm border border-slate-600/50 rounded px-2 py-0.5 text-xs whitespace-nowrap">
            <span className="font-semibold text-white">{formatPace(hoverPace)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function _resample(arr: number[], targetLen: number): number[] {
  if (arr.length === targetLen) return arr;
  const result: number[] = [];
  for (let i = 0; i < targetLen; i++) {
    const srcIdx = (i / (targetLen - 1)) * (arr.length - 1);
    const lo = Math.floor(srcIdx);
    const hi = Math.min(lo + 1, arr.length - 1);
    const frac = srcIdx - lo;
    result.push(arr[lo] + (arr[hi] - arr[lo]) * frac);
  }
  return result;
}
