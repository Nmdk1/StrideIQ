/**
 * ADR-064 Spike — Option A: Pure Recharts (ReferenceArea gradient)
 *
 * Uses Recharts ReferenceArea components to approximate the effort gradient.
 * Each band covers a time range of similar effort intensity.
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';
import { StreamPoint, effortToColor, formatTime, formatPace, lttbDownsample } from './data';

interface Props {
  data: StreamPoint[];
  onMetrics: (m: { renderMs: number; domNodes: number }) => void;
}

/** Batch consecutive points with similar effort into bands */
function buildEffortBands(data: StreamPoint[], threshold: number = 0.03): Array<{
  x1: number; x2: number; color: string;
}> {
  if (data.length === 0) return [];
  const bands: Array<{ x1: number; x2: number; color: string }> = [];
  let bandStart = data[0].time;
  let bandEffort = data[0].effort;

  for (let i = 1; i < data.length; i++) {
    if (Math.abs(data[i].effort - bandEffort) > threshold || i === data.length - 1) {
      bands.push({
        x1: bandStart,
        x2: data[i].time,
        color: effortToColor(bandEffort),
      });
      bandStart = data[i].time;
      bandEffort = data[i].effort;
    }
  }
  return bands;
}

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

export default function OptionAChart({ data, onMetrics }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [displayData, setDisplayData] = useState<StreamPoint[]>([]);
  const [bands, setBands] = useState<Array<{ x1: number; x2: number; color: string }>>([]);

  useEffect(() => {
    const start = performance.now();

    // Downsample for display
    const sampled = lttbDownsample(data, 500);
    setDisplayData(sampled);

    // Build effort bands from full data (batched)
    const effortBands = buildEffortBands(data, 0.02);
    setBands(effortBands);

    // Measure after next paint
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const renderMs = performance.now() - start;
        const domNodes = containerRef.current
          ? containerRef.current.querySelectorAll('*').length
          : 0;
        onMetrics({ renderMs, domNodes });
      });
    });
  }, [data, onMetrics]);

  const hrDomain = [
    Math.min(...displayData.map(d => d.hr)) - 5,
    Math.max(...displayData.map(d => d.hr)) + 5,
  ];
  const paceDomain = [
    Math.min(...displayData.map(d => d.pace)) - 10,
    Math.max(...displayData.map(d => d.pace)) + 10,
  ];
  const altDomain = [
    Math.min(...displayData.map(d => d.altitude)) - 5,
    Math.max(...displayData.map(d => d.altitude)) + 20,
  ];

  if (displayData.length === 0) return null;

  return (
    <div ref={containerRef}>
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={displayData} margin={{ top: 10, right: 60, left: 0, bottom: 0 }}>
          {/* Effort gradient bands */}
          {bands.map((band, i) => (
            <ReferenceArea
              key={i}
              x1={band.x1}
              x2={band.x2}
              fill={band.color}
              fillOpacity={0.25}
              strokeOpacity={0}
            />
          ))}

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
          <YAxis
            yAxisId="alt"
            domain={altDomain}
            hide
          />
          <Area
            yAxisId="alt"
            dataKey="altitude"
            fill="#334155"
            fillOpacity={0.4}
            stroke="none"
            isAnimationActive={false}
          />

          {/* Pace (left axis, inverted — lower pace = faster) */}
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
            strokeWidth={1.5}
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
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />

          <Tooltip content={<CustomTooltip />} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
