'use client';

/**
 * StreamsStack — three stacked SVG bands (HR, Pace, Elevation) sharing one
 * x-axis. Order is HR → Pace → Elevation so elevation sits closest to the
 * terrain panel directly below it.
 *
 * Visual treatment matches the splits-tab ElevationProfile (gradient fill,
 * thicker stroke at lower opacity, compressed band height) so peaks read as
 * climbs instead of spikes.
 *
 * Coordinated scrub: pointermove computes t in [0, 1] and writes to
 * ScrubProvider. The terrain panel reads the same context and moves its
 * marker; the moment readout reads it for instantaneous values.
 *
 * Plain SVG (no recharts) — full control over scrub interaction, no library
 * coupling, and the stream is already LTTB-downsampled to ≤500 pts so a
 * single SVG path renders fast.
 */

import React, { useId, useMemo, useRef } from 'react';
import { useScrubState } from './hooks/useScrubState';
import type { TrackPoint } from './hooks/useResampledTrack';

// Visual treatment matches the splits-tab ElevationProfile (gentler peaks):
// shorter bands, gradient fill, thicker stroke at lower opacity. The
// vertical compression is what makes climbs read as climbs instead of spikes.
const CHART_HEIGHT = 64;
const CHART_PADDING_TOP = 6;
const CHART_PADDING_BOTTOM = 6;
const PLOT_HEIGHT = CHART_HEIGHT - CHART_PADDING_TOP - CHART_PADDING_BOTTOM;

export interface SeriesPoint {
  t: number;
  v: number;
}

function buildSeries(track: TrackPoint[], pick: (p: TrackPoint) => number | null): SeriesPoint[] {
  const out: SeriesPoint[] = [];
  for (const p of track) {
    const v = pick(p);
    if (v !== null && Number.isFinite(v)) {
      out.push({ t: p.t, v });
    }
  }
  return out;
}

/**
 * Percentile-based domain. Returns the value at the given quantile (0..1) of
 * a numerically-sorted copy of the series.
 *
 * Why: raw stream pace = 1000/velocity. A momentary GPS skip producing
 * 0.1 m/s yields 10,000 s/km, collapsing every real pace value into a
 * flat band at one edge of the chart. Same risk for HR sensor dropouts
 * and barometric altitude glitches. Clipping the y-axis domain to the
 * 2nd/98th percentile makes 96% of the data fill the band properly;
 * outliers still pass through but get drawn clamped to the edge.
 */
export function quantile(sortedAsc: number[], q: number): number {
  if (sortedAsc.length === 0) return 0;
  if (sortedAsc.length === 1) return sortedAsc[0];
  const pos = (sortedAsc.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  if (lo === hi) return sortedAsc[lo];
  return sortedAsc[lo] + (sortedAsc[hi] - sortedAsc[lo]) * (pos - lo);
}

export function robustDomain(series: SeriesPoint[]): { vMin: number; vMax: number } {
  if (series.length === 0) return { vMin: 0, vMax: 1 };
  const sorted = series.map((p) => p.v).sort((a, b) => a - b);
  let vMin = quantile(sorted, 0.02);
  let vMax = quantile(sorted, 0.98);
  if (!Number.isFinite(vMin) || !Number.isFinite(vMax) || vMin === vMax) {
    vMin = sorted[0];
    vMax = sorted[sorted.length - 1];
    if (vMin === vMax) {
      vMin -= 1;
      vMax += 1;
    }
  }
  return { vMin, vMax };
}

function buildSmoothPath(series: SeriesPoint[], width: number, vMin: number, vMax: number, invertY: boolean): string {
  if (series.length < 2) return '';
  const range = vMax - vMin || 1;
  const yFor = (v: number) => {
    // Clamp to [vMin, vMax] so percentile-clipped outliers draw at the
    // edge of the band instead of blowing out of the SVG box.
    const clamped = v < vMin ? vMin : v > vMax ? vMax : v;
    const norm = (clamped - vMin) / range;
    // SVG y is top-down: y=0 is the top of the chart.
    // Default (invertY=false): higher data value → drawn higher on screen
    //   (HR, Elevation: peaks read as peaks).
    // invertY=true: higher data value → drawn lower on screen
    //   (Pace where lower = faster: a fast moment reads as a peak).
    const fractionFromTop = invertY ? norm : 1 - norm;
    return CHART_PADDING_TOP + fractionFromTop * PLOT_HEIGHT;
  };
  const xFor = (t: number) => t * width;

  let d = `M ${xFor(series[0].t).toFixed(2)} ${yFor(series[0].v).toFixed(2)}`;
  for (let i = 1; i < series.length; i++) {
    d += ` L ${xFor(series[i].t).toFixed(2)} ${yFor(series[i].v).toFixed(2)}`;
  }
  return d;
}

function buildAreaPath(series: SeriesPoint[], width: number, vMin: number, vMax: number, invertY: boolean): string {
  const linePath = buildSmoothPath(series, width, vMin, vMax, invertY);
  if (!linePath) return '';
  const lastX = (series[series.length - 1].t * width).toFixed(2);
  const firstX = (series[0].t * width).toFixed(2);
  const baseY = CHART_PADDING_TOP + PLOT_HEIGHT;
  return `${linePath} L ${lastX} ${baseY} L ${firstX} ${baseY} Z`;
}

function paceSecondsToMinSec(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/**
 * Internal: one stacked band. Renders title + path + scrub vertical line.
 */
interface BandProps {
  title: string;
  unit: string;
  series: SeriesPoint[];
  width: number;
  /** Color of the line/area (Tailwind text colors mapped to currentColor). */
  colorClass: string;
  /** Pace is "lower is better" → invert so lower pace draws as higher peaks. */
  invertY?: boolean;
  /** Format the value for the inline scrub label. */
  formatValue: (v: number) => string;
  scrubT: number | null;
}

function Band({ title, unit, series, width, colorClass, invertY = false, formatValue, scrubT }: BandProps) {
  const gradientId = useId();
  const { line, area, scrubValue } = useMemo(() => {
    if (series.length === 0) {
      return { line: '', area: '', scrubValue: null as number | null };
    }
    const { vMin: lo, vMax: hi } = robustDomain(series);
    let scrubV: number | null = null;
    if (scrubT !== null) {
      // Binary search for nearest t.
      let lo2 = 0;
      let hi2 = series.length - 1;
      while (lo2 < hi2) {
        const mid = (lo2 + hi2) >> 1;
        if (series[mid].t < scrubT) lo2 = mid + 1;
        else hi2 = mid;
      }
      scrubV = series[lo2].v;
    }
    return {
      line: buildSmoothPath(series, width, lo, hi, invertY),
      area: buildAreaPath(series, width, lo, hi, invertY),
      scrubValue: scrubV,
    };
  }, [series, width, invertY, scrubT]);

  return (
    <div className="relative">
      <div className="absolute top-1.5 left-2 z-10 text-[10px] uppercase tracking-wider text-slate-500 pointer-events-none">
        {title}
      </div>
      {scrubT !== null && scrubValue !== null && (
        <div
          className="absolute top-1.5 right-2 z-10 text-xs tabular-nums text-slate-300 pointer-events-none"
        >
          {formatValue(scrubValue)} <span className="text-slate-500">{unit}</span>
        </div>
      )}
      <svg
        width={width}
        height={CHART_HEIGHT}
        viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
        className={`block ${colorClass}`}
        role="img"
        aria-label={title}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity={0.25} />
            <stop offset="100%" stopColor="currentColor" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#${gradientId})`} />
        <path d={line} stroke="currentColor" strokeWidth={2} opacity={0.55} fill="none" />
        {scrubT !== null && (
          <line
            x1={scrubT * width}
            x2={scrubT * width}
            y1={CHART_PADDING_TOP - 2}
            y2={CHART_HEIGHT - CHART_PADDING_BOTTOM + 2}
            stroke="rgba(255,255,255,0.45)"
            strokeWidth={1}
          />
        )}
      </svg>
    </div>
  );
}

export interface StreamsStackProps {
  track: TrackPoint[];
  /** Container width in CSS pixels. Caller must measure (responsive). */
  width: number;
}

export function StreamsStack({ track, width }: StreamsStackProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { position, setPosition, clear } = useScrubState();

  const paceSeries = useMemo(() => buildSeries(track, (p) => p.pace), [track]);
  const hrSeries = useMemo(() => buildSeries(track, (p) => p.hr), [track]);
  const elevationSeries = useMemo(() => buildSeries(track, (p) => p.altitude), [track]);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width <= 0) return;
    const x = e.clientX - rect.left;
    setPosition(x / rect.width);
  };

  if (track.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800/60 bg-slate-900/30 p-6 text-sm text-slate-500">
        No stream data available for this activity.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerLeave={clear}
      className="relative rounded-xl overflow-hidden border border-slate-800/60 bg-slate-900/30 cursor-crosshair select-none touch-none"
      style={{ touchAction: 'none' }}
    >
      <Band
        title="Heart Rate"
        unit="bpm"
        series={hrSeries}
        width={width}
        colorClass="text-rose-400"
        formatValue={(v) => Math.round(v).toString()}
        scrubT={position}
      />
      <div className="h-px bg-slate-800/50" />
      <Band
        title="Pace"
        unit="/mi"
        series={paceSeries}
        width={width}
        colorClass="text-emerald-400"
        invertY
        formatValue={(secPerKm) => paceSecondsToMinSec(secPerKm * 1.609344)}
        scrubT={position}
      />
      <div className="h-px bg-slate-800/50" />
      <Band
        title="Elevation"
        unit="ft"
        series={elevationSeries}
        width={width}
        colorClass="text-amber-400"
        formatValue={(meters) => Math.round(meters * 3.28084).toString()}
        scrubT={position}
      />
    </div>
  );
}
