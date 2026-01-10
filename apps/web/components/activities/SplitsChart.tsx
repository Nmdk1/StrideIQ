/**
 * Splits Chart Component
 * 
 * Visualizes mile splits with pace and heart rate.
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
    
    // Format pace as mm:ss
    const formatPace = (seconds: number | null): string => {
      if (!seconds) return 'N/A';
      const mins = Math.floor(seconds / 60);
      const secs = Math.round(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, '0')}/mi`;
    };
    
    return {
      split: split.split_number,
      paceSeconds: paceSecondsPerMile,
      paceFormatted: formatPace(paceSecondsPerMile),
      hr: split.average_heartrate || null,
      distance: distance,
    };
  }).filter((d) => d.paceSeconds !== null);

  if (chartData.length === 0) {
    return null;
  }

  return (
    <div className={`bg-gray-800 rounded-lg border border-gray-700 p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4">Splits</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="split" 
            label={{ value: 'Mile', position: 'insideBottom', offset: -5 }}
            stroke="#9CA3AF"
          />
          <YAxis 
            yAxisId="pace"
            label={{ value: 'Pace (seconds)', angle: -90, position: 'insideLeft' }}
            stroke="#9CA3AF"
          />
          <YAxis 
            yAxisId="hr"
            orientation="right"
            label={{ value: 'HR (bpm)', angle: 90, position: 'insideRight' }}
            stroke="#9CA3AF"
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
          />
          <Legend />
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

