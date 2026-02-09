/**
 * Efficiency Trend Chart Component
 * 
 * Visualizes efficiency factor over time with rolling averages.
 * This is the core product differentiator.
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
} from 'recharts';
import type { EfficiencyTrendPoint } from '@/lib/api/services/analytics';

interface EfficiencyChartProps {
  data: EfficiencyTrendPoint[];
  showRollingAverage?: boolean;
  rollingWindow?: '30d' | '60d' | '90d' | '120d' | 'all';
  className?: string;
}

export function EfficiencyChart({
  data,
  showRollingAverage = true,
  rollingWindow = '60d',
  className = '',
}: EfficiencyChartProps) {
  // Format data for Recharts
  const chartData = data.map((point) => ({
    date: new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    fullDate: point.date,
    efficiency: point.efficiency_factor,
    rolling7d: point.rolling_7d_avg,
    rolling30d: point.rolling_30d_avg,
    rolling60d: point.rolling_60d_avg,
    rolling90d: point.rolling_90d_avg,
    rolling120d: point.rolling_120d_avg,
    pace: point.pace_per_mile,
    hr: point.avg_hr,
    annotations: point.annotations || [],
  }));

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-3 shadow-lg">
          <p className="text-sm font-semibold mb-2">{data.date}</p>
          <div className="space-y-1 text-xs">
            <p>
              <span className="text-slate-400">Efficiency:</span>{' '}
              <span className="text-white font-medium">{data.efficiency.toFixed(2)}</span>
            </p>
            {data.rolling30d && (
              <p>
                <span className="text-slate-400">30d Avg:</span>{' '}
                <span className="text-white">{data.rolling30d.toFixed(2)}</span>
              </p>
            )}
            {data.rolling60d && (
              <p>
                <span className="text-slate-400">60d Avg:</span>{' '}
                <span className="text-white">{data.rolling60d.toFixed(2)}</span>
              </p>
            )}
            <p>
              <span className="text-slate-400">Pace:</span>{' '}
              <span className="text-white">
                {Math.floor(data.pace)}:{Math.round((data.pace % 1) * 60)
                  .toString()
                  .padStart(2, '0')}
                /mi
              </span>
            </p>
            <p>
              <span className="text-slate-400">HR:</span>{' '}
              <span className="text-white">{data.hr} bpm</span>
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4">Efficiency Trend</h3>
      <p className="text-sm text-slate-400 mb-4">
        Higher efficiency factor = more efficient (more speed produced at the same heart rate).
        Rolling averages show meaningful fitness trends over training cycles (30-120 days).
      </p>
      <ResponsiveContainer width="100%" height={400}>
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
            label={{ value: 'Efficiency Factor', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="efficiency"
            stroke="#3B82F6"
            strokeWidth={2}
            dot={(props: any) => {
              const { payload } = props;
              // Color code dots based on annotations
              if (payload.annotations?.includes('best_effort')) {
                return <circle {...props} r={5} fill="#10B981" />;
              }
              if (payload.annotations?.includes('regression')) {
                return <circle {...props} r={5} fill="#EF4444" />;
              }
              if (payload.annotations?.includes('plateau')) {
                return <circle {...props} r={5} fill="#F59E0B" />;
              }
              return <circle {...props} r={3} fill="#3B82F6" />;
            }}
            name="Efficiency Factor"
          />
          {showRollingAverage && (
            <>
              {rollingWindow === 'all' || rollingWindow === '30d' ? (
                <Line
                  type="monotone"
                  dataKey="rolling30d"
                  stroke="#10B981"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  name="30-Day Average"
                />
              ) : null}
              {rollingWindow === 'all' || rollingWindow === '60d' ? (
                <Line
                  type="monotone"
                  dataKey="rolling60d"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  name="60-Day Average"
                />
              ) : null}
              {rollingWindow === 'all' || rollingWindow === '90d' ? (
                <Line
                  type="monotone"
                  dataKey="rolling90d"
                  stroke="#F59E0B"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  name="90-Day Average"
                />
              ) : null}
              {rollingWindow === 'all' || rollingWindow === '120d' ? (
                <Line
                  type="monotone"
                  dataKey="rolling120d"
                  stroke="#8B5CF6"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  name="120-Day Average"
                />
              ) : null}
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

