/**
 * ADR-064 Spike — Option B: Canvas 2D gradient + SVG overlay (Hybrid)
 *
 * Renders the effort gradient as a pixel-level Canvas 2D operation.
 * Overlays Recharts SVG for traces, axes, tooltips, and crosshair.
 */

'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { StreamPoint, effortToColor, formatTime, formatPace, lttbDownsample } from './data';

interface Props {
  data: StreamPoint[];
  onMetrics: (m: { renderMs: number; domNodes: number }) => void;
}

// Chart margins must match between Canvas and Recharts
const MARGIN = { top: 10, right: 60, left: 50, bottom: 30 };

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 shadow-lg text-sm">
      <p className="text-slate-400 mb-1">{formatTime(d.time)}</p>
      <p className="text-blue-400">Pace: {formatPace(d.pace)}/km</p>
      <p className="text-red-400">HR: {d.hr} bpm</p>
      <p className="text-slate-300">Alt: {d.altitude}m | Grade: {d.grade}%</p>
      <p className="text-amber-400">Effort: {(d.effort * 100).toFixed(0)}%</p>
    </div>
  );
}

/** Draw the effort gradient directly on a Canvas element */
function drawGradient(
  canvas: HTMLCanvasElement,
  data: StreamPoint[],
  chartWidth: number,
  chartHeight: number,
) {
  const ctx = canvas.getContext('2d');
  if (!ctx || data.length === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const totalWidth = chartWidth + MARGIN.left + MARGIN.right;
  const totalHeight = chartHeight + MARGIN.top + MARGIN.bottom;

  canvas.width = totalWidth * dpr;
  canvas.height = totalHeight * dpr;
  canvas.style.width = `${totalWidth}px`;
  canvas.style.height = `${totalHeight}px`;
  ctx.scale(dpr, dpr);

  // Clear
  ctx.clearRect(0, 0, totalWidth, totalHeight);

  // Map time to x-pixel within the chart area
  const minTime = data[0].time;
  const maxTime = data[data.length - 1].time;
  const timeRange = maxTime - minTime || 1;

  // Draw vertical bands — one per pixel column for smooth gradient
  const pixelCount = Math.ceil(chartWidth);

  for (let px = 0; px < pixelCount; px++) {
    const t = minTime + (px / chartWidth) * timeRange;
    // Find nearest data point
    const idx = Math.min(
      Math.round(((t - minTime) / timeRange) * (data.length - 1)),
      data.length - 1,
    );
    const effort = data[idx].effort;
    const color = effortToColor(effort);

    ctx.fillStyle = color;
    ctx.globalAlpha = 0.3;
    ctx.fillRect(MARGIN.left + px, MARGIN.top, 1, chartHeight);
  }

  ctx.globalAlpha = 1.0;
}

export default function OptionBChart({ data, onMetrics }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [displayData, setDisplayData] = useState<StreamPoint[]>([]);
  const [chartDims, setChartDims] = useState({ width: 800, height: 360 });

  const handleResize = useCallback(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const w = rect.width - MARGIN.left - MARGIN.right;
      const h = 400 - MARGIN.top - MARGIN.bottom;
      setChartDims({ width: Math.max(100, w), height: Math.max(100, h) });
    }
  }, []);

  useEffect(() => {
    const start = performance.now();

    const sampled = lttbDownsample(data, 500);
    setDisplayData(sampled);

    handleResize();
    window.addEventListener('resize', handleResize);

    // Draw gradient on canvas after layout settles
    requestAnimationFrame(() => {
      if (canvasRef.current) {
        drawGradient(canvasRef.current, data, chartDims.width, chartDims.height);
      }
      requestAnimationFrame(() => {
        const renderMs = performance.now() - start;
        const domNodes = containerRef.current
          ? containerRef.current.querySelectorAll('*').length
          : 0;
        onMetrics({ renderMs, domNodes });
      });
    });

    return () => window.removeEventListener('resize', handleResize);
  }, [data, onMetrics, handleResize, chartDims.width, chartDims.height]);

  // Redraw canvas when dimensions change
  useEffect(() => {
    if (canvasRef.current && data.length > 0) {
      drawGradient(canvasRef.current, data, chartDims.width, chartDims.height);
    }
  }, [chartDims, data]);

  const hrDomain: [number, number] = displayData.length > 0
    ? [Math.min(...displayData.map(d => d.hr)) - 5, Math.max(...displayData.map(d => d.hr)) + 5]
    : [90, 190];
  const paceDomain: [number, number] = displayData.length > 0
    ? [Math.min(...displayData.map(d => d.pace)) - 10, Math.max(...displayData.map(d => d.pace)) + 10]
    : [180, 420];
  const altDomain: [number, number] = displayData.length > 0
    ? [Math.min(...displayData.map(d => d.altitude)) - 5, Math.max(...displayData.map(d => d.altitude)) + 20]
    : [80, 160];

  if (displayData.length === 0) return null;

  return (
    <div ref={containerRef} className="relative">
      {/* Canvas layer — effort gradient (behind SVG) */}
      <canvas
        ref={canvasRef}
        className="absolute top-0 left-0 pointer-events-none"
        style={{ zIndex: 0 }}
      />

      {/* SVG layer — Recharts traces, axes, interaction (on top) */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={displayData} margin={MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />

            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={formatTime}
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
            />

            {/* Altitude area (background) */}
            <YAxis yAxisId="alt" domain={altDomain} hide />
            <Area
              yAxisId="alt"
              dataKey="altitude"
              fill="#334155"
              fillOpacity={0.35}
              stroke="none"
              isAnimationActive={false}
            />

            {/* Pace (left axis) */}
            <YAxis
              yAxisId="pace"
              domain={paceDomain}
              reversed
              tickFormatter={(v: number) => formatPace(v)}
              stroke="#64748b"
              tick={{ fill: '#3b82f6', fontSize: 11 }}
              label={{ value: 'Pace', angle: -90, position: 'insideLeft', fill: '#3b82f6', fontSize: 12 }}
            />
            <Line
              yAxisId="pace"
              dataKey="pace"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />

            {/* HR (right axis) */}
            <YAxis
              yAxisId="hr"
              orientation="right"
              domain={hrDomain}
              stroke="#64748b"
              tick={{ fill: '#ef4444', fontSize: 11 }}
              label={{ value: 'HR', angle: 90, position: 'insideRight', fill: '#ef4444', fontSize: 12 }}
            />
            <Line
              yAxisId="hr"
              dataKey="hr"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />

            <Tooltip content={<CustomTooltip />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
