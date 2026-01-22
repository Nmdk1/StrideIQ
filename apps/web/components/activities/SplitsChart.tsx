/**
 * Splits Chart Component
 * 
 * Visualizes mile splits with pace and heart rate.
 * Pace displayed in standard running format: MM:SS/mi
 * Tone: Sparse, data-driven.
 */

'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface Split {
  split_number: number;
  distance: number | null;  // distance in meters
  elapsed_time: number | null;
  moving_time: number | null;
  average_heartrate: number | null;
  max_heartrate: number | null;
  average_cadence: number | null;
  gap_seconds_per_mile: number | null;
}

interface SplitsChartProps {
  splits: Split[];
  className?: string;
}

// Format pace seconds to MM:SS string
function formatPaceToMinSec(seconds: number | null): string {
  if (!seconds || seconds <= 0) return 'N/A';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Custom tooltip for the chart
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;
  
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 shadow-lg">
      <p className="text-slate-300 text-sm font-medium mb-2">Mile {label}</p>
      {payload.map((entry: any, index: number) => {
        if (entry.dataKey === 'paceSeconds') {
          return (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              Pace: {formatPaceToMinSec(entry.value)}/mi
            </p>
          );
        }
        if (entry.dataKey === 'hr') {
          return (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              HR: {entry.value} bpm
            </p>
          );
        }
        return null;
      })}
    </div>
  );
}

export function SplitsChart({ splits, className = '' }: SplitsChartProps) {
  if (!splits || splits.length === 0) {
    return null;
  }

  const chartData = splits.map((split) => {
    // Calculate pace in seconds per mile from distance and moving_time
    const distance = split.distance || 0;
    const time = split.moving_time || split.elapsed_time || 0;
    
    const paceSecondsPerMile = distance > 0 
      ? (time / distance) * 1609.34 
      : null;
    
    return {
      split: split.split_number,
      paceSeconds: paceSecondsPerMile,
      hr: split.average_heartrate || null,
      distance: distance,
    };
  }).filter((d) => d.paceSeconds !== null);

  if (chartData.length === 0) {
    return null;
  }

  // Calculate min/max pace for Y-axis domain (with some padding)
  const paceValues = chartData.map(d => d.paceSeconds).filter(Boolean) as number[];
  const minPace = Math.floor(Math.min(...paceValues) / 60) * 60; // Round down to nearest minute
  const maxPace = Math.ceil(Math.max(...paceValues) / 60) * 60; // Round up to nearest minute

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="split" 
            label={{ value: 'Split', position: 'insideBottom', offset: -5 }}
            stroke="#9CA3AF"
          />
          <YAxis 
            yAxisId="pace"
            domain={[minPace, maxPace]}
            tickFormatter={(value) => formatPaceToMinSec(value)}
            label={{ value: 'Pace (min/mi)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' } }}
            stroke="#9CA3AF"
            width={55}
          />
          <YAxis 
            yAxisId="hr"
            orientation="right"
            label={{ value: 'HR (bpm)', angle: 90, position: 'insideRight' }}
            stroke="#9CA3AF"
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            formatter={(value) => {
              if (value === 'paceSeconds') return 'Pace';
              return value;
            }}
          />
          <Line
            yAxisId="pace"
            type="monotone"
            dataKey="paceSeconds"
            stroke="#3B82F6"
            strokeWidth={2}
            name="Pace"
            dot={{ fill: '#3B82F6', r: 4 }}
          />
          {chartData.some((d) => d.hr !== null) && (
            <Line
              yAxisId="hr"
              type="monotone"
              dataKey="hr"
              stroke="#EF4444"
              strokeWidth={2}
              name="HR"
              dot={{ fill: '#EF4444', r: 4 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

