/**
 * Age-Graded Trajectory Chart Component
 * 
 * Shows age-graded performance percentage over time.
 * Answers: "Am I adapting or just aging?"
 */

'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { EfficiencyTrendPoint } from '@/lib/api/services/analytics';

interface AgeGradedChartProps {
  data: EfficiencyTrendPoint[];
  className?: string;
}

export function AgeGradedChart({ data, className = '' }: AgeGradedChartProps) {
  // Filter to only points with age-graded data
  const chartData = data
    .filter((point) => point.performance_percentage !== null && point.performance_percentage !== undefined)
    .map((point) => ({
      date: new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      fullDate: point.date,
      ageGraded: point.performance_percentage!,
      efficiency: point.efficiency_factor,
      pace: point.pace_per_mile,
    }));

  if (chartData.length === 0) {
    return (
      <div className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className}`}>
        <h3 className="text-lg font-semibold mb-4">Age-Graded Trajectory</h3>
        <p className="text-slate-400 text-sm">
          Age-graded data not available. Age-grading requires race activities with distance and time.
        </p>
      </div>
    );
  }

  // Calculate trend
  const firstHalf = chartData.slice(0, Math.floor(chartData.length / 2));
  const secondHalf = chartData.slice(Math.floor(chartData.length / 2));
  const earlyAvg = firstHalf.reduce((sum, p) => sum + p.ageGraded, 0) / firstHalf.length;
  const recentAvg = secondHalf.reduce((sum, p) => sum + p.ageGraded, 0) / secondHalf.length;
  const trend = recentAvg > earlyAvg ? 'improving' : recentAvg < earlyAvg ? 'declining' : 'stable';

  // World-class threshold (typically 90%+)
  const worldClassThreshold = 90;
  const eliteThreshold = 80;
  const competitiveThreshold = 70;

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-3 shadow-lg">
          <p className="text-sm font-semibold mb-2">{data.date}</p>
          <div className="space-y-1 text-xs">
            <p>
              <span className="text-slate-400">Age-Graded:</span>{' '}
              <span className="text-white font-medium">{data.ageGraded.toFixed(1)}%</span>
            </p>
            <p>
              <span className="text-slate-400">Efficiency:</span>{' '}
              <span className="text-white">{data.efficiency.toFixed(2)}</span>
            </p>
            <p>
              <span className="text-slate-400">Pace:</span>{' '}
              <span className="text-white">
                {Math.floor(data.pace)}:{Math.round((data.pace % 1) * 60)
                  .toString()
                  .padStart(2, '0')}
                /mi
              </span>
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className}`}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">Age-Graded Trajectory</h3>
          <p className="text-sm text-slate-400 mt-1">
            Personal slope: Are you adapting or just aging?
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-400">Trend</p>
          <p
            className={`text-lg font-semibold capitalize ${
              trend === 'improving'
                ? 'text-green-400'
                : trend === 'declining'
                ? 'text-red-400'
                : 'text-slate-400'
            }`}
          >
            {trend}
          </p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            domain={[0, 100]}
            label={{ value: 'Age-Graded %', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          {/* Reference lines for performance levels */}
          <ReferenceLine
            y={worldClassThreshold}
            stroke="#F59E0B"
            strokeDasharray="3 3"
            label={{ value: 'World-Class (90%)', position: 'right' }}
          />
          <ReferenceLine
            y={eliteThreshold}
            stroke="#6B7280"
            strokeDasharray="3 3"
            label={{ value: 'Elite (80%)', position: 'right' }}
          />
          <ReferenceLine
            y={competitiveThreshold}
            stroke="#4B5563"
            strokeDasharray="3 3"
            label={{ value: 'Competitive (70%)', position: 'right' }}
          />
          <Line
            type="monotone"
            dataKey="ageGraded"
            stroke="#8B5CF6"
            strokeWidth={2}
            dot={{ r: 4, fill: '#8B5CF6' }}
            name="Age-Graded %"
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="mt-4 text-xs text-slate-400">
        <p>
          Current: {chartData[chartData.length - 1]?.ageGraded.toFixed(1)}% | Average:{' '}
          {(chartData.reduce((sum, p) => sum + p.ageGraded, 0) / chartData.length).toFixed(1)}%
        </p>
      </div>
    </div>
  );
}


