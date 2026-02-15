'use client';

/**
 * MiniPaceChart — Home hero mini pace chart with effort-colored gradient line
 * and elevation fill.
 *
 * Spec (BUILD_SPEC_HOME_AND_ACTIVITY.md, Change H1):
 *   - 100-120px tall, full-bleed (edge to edge within container)
 *   - Pace line colored by effort intensity via effortToColor()
 *   - Y-axis: pace inverted (faster at top, like the full canvas)
 *   - Elevation fill behind the line (subtle, low opacity)
 *   - No axis labels, no gridlines. Clean.
 *   - Pure SVG — no Recharts dependency for this compact component
 */

import React, { useId, useMemo } from 'react';
import { effortToColor } from '@/components/activities/rsi/utils/effortColor';

interface MiniPaceChartProps {
  paceStream: number[];       // s/km per point
  effortIntensity: number[];  // 0-1 per point
  elevationStream?: number[] | null;
  height?: number;
}

export function MiniPaceChart({
  paceStream,
  effortIntensity,
  elevationStream,
  height = 120,
}: MiniPaceChartProps) {
  const chartData = useMemo(() => {
    const n = paceStream.length;
    if (n === 0) return null;

    // Pace bounds (inverted: min pace = fastest = top of chart)
    // Clamp outliers: anything slower than 15 min/km or faster than 2 min/km
    const paceMin = 120;   // 2:00/km — fastest reasonable
    const paceMax = 900;   // 15:00/km — slowest reasonable
    const clamped = paceStream.map(p => Math.max(paceMin, Math.min(paceMax, p)));
    
    // Find actual range within clamped data for better scaling
    const actualMin = Math.min(...clamped);
    const actualMax = Math.max(...clamped);
    // Add 10% padding
    const range = actualMax - actualMin || 1;
    const padMin = Math.max(paceMin, actualMin - range * 0.1);
    const padMax = Math.min(paceMax, actualMax + range * 0.1);

    // Normalize pace to 0-1 (inverted: 0 = slow/bottom, 1 = fast/top)
    const paceNorm = clamped.map(p => 1 - (p - padMin) / (padMax - padMin || 1));

    // Elevation normalization (if present)
    let elevNorm: number[] | null = null;
    if (elevationStream && elevationStream.length > 0) {
      // Resample elevation to match pace length if different
      const elev = elevationStream.length === n
        ? elevationStream
        : _resample(elevationStream, n);
      const eMin = Math.min(...elev);
      const eMax = Math.max(...elev);
      const eRange = eMax - eMin || 1;
      // Elevation fills the bottom 40% of the chart
      elevNorm = elev.map(e => ((e - eMin) / eRange) * 0.4);
    }

    return { n, paceNorm, elevNorm };
  }, [paceStream, elevationStream]);

  const gradientId = `miniPaceGrad-${useId()}`;

  if (!chartData) return null;

  const { n, paceNorm, elevNorm } = chartData;
  const padding = { top: 4, bottom: 4 };
  const drawHeight = height - padding.top - padding.bottom;

  // Build SVG path points
  const xStep = 100 / (n - 1); // percentage-based for viewBox

  // Pace line points
  const pacePoints = paceNorm.map((py, i) => ({
    x: i * xStep,
    y: padding.top + (1 - py) * drawHeight,
  }));

  const pacePath = pacePoints
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');

  // Elevation fill path (area from bottom up)
  let elevPath: string | null = null;
  if (elevNorm) {
    const elevPoints = elevNorm.map((ey, i) => ({
      x: i * xStep,
      y: height - padding.bottom - ey * drawHeight,
    }));
    elevPath =
      `M 0 ${height} ` +
      elevPoints.map(p => `L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ') +
      ` L 100 ${height} Z`;
  }

  // Effort gradient stops (~30 stops for performance)
  const maxStops = 30;
  const stopStep = Math.max(1, Math.floor(n / maxStops));
  const gradientStops: Array<{ offset: string; color: string }> = [];
  for (let i = 0; i < n; i += stopStep) {
    const effort = effortIntensity[Math.min(i, effortIntensity.length - 1)] ?? 0.5;
    gradientStops.push({
      offset: `${((i / (n - 1)) * 100).toFixed(1)}%`,
      color: effortToColor(effort),
    });
  }
  // Ensure last stop
  const lastEffort = effortIntensity[effortIntensity.length - 1] ?? 0.5;
  if (gradientStops.length === 0 || gradientStops[gradientStops.length - 1].offset !== '100.0%') {
    gradientStops.push({ offset: '100.0%', color: effortToColor(lastEffort) });
  }

  return (
    <svg
      data-testid="mini-pace-chart"
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height, display: 'block' }}
    >
      <defs>
        {/* Effort-colored gradient for the pace line */}
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
          {gradientStops.map((stop, i) => (
            <stop key={i} offset={stop.offset} stopColor={stop.color} />
          ))}
        </linearGradient>
      </defs>

      {/* Elevation fill — subtle, behind everything */}
      {elevPath && (
        <path
          d={elevPath}
          fill="rgba(148, 163, 184, 0.08)"
          data-testid="elevation-fill"
        />
      )}

      {/* Pace line — effort gradient stroke */}
      <path
        d={pacePath}
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth="1.5"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        data-testid="pace-line"
      />
    </svg>
  );
}

/** Resample an array to a target length using linear interpolation. */
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
