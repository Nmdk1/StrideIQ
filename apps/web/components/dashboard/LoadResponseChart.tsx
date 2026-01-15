/**
 * Load-Response Chart Component
 * 
 * Shows weekly load vs efficiency delta to identify productive vs wasted vs harmful load.
 */

'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { EfficiencyTrendsResponse } from '@/lib/api/services/analytics';
import { useUnits } from '@/lib/context/UnitsContext';

interface LoadResponseChartProps {
  data: EfficiencyTrendsResponse['load_response'];
  className?: string;
}

const LOAD_TYPE_COLORS = {
  productive: '#10B981', // green
  neutral: '#6B7280', // gray
  wasted: '#F59E0B', // yellow
  harmful: '#EF4444', // red
};

export function LoadResponseChart({ data, className = '' }: LoadResponseChartProps) {
  const { formatDistance, units } = useUnits();
  
  if (!data || data.length === 0) {
    return null;
  }

  const chartData = data.map((week) => ({
    week: new Date(week.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    // API returns miles, convert to meters for formatDistance
    distanceMeters: week.total_distance_miles * 1609.34,
    efficiencyDelta: week.efficiency_delta || 0,
    loadType: week.load_type,
    activityCount: week.activity_count,
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-3 shadow-lg">
          <p className="text-sm font-semibold mb-2">{data.week}</p>
          <div className="space-y-1 text-xs">
            <p>
              <span className="text-slate-400">Distance:</span>{' '}
              <span className="text-white">{formatDistance(data.distanceMeters, 1)}</span>
            </p>
            <p>
              <span className="text-slate-400">Efficiency Δ:</span>{' '}
              <span
                className={
                  data.efficiencyDelta < 0
                    ? 'text-green-400'
                    : data.efficiencyDelta > 0
                    ? 'text-red-400'
                    : 'text-slate-400'
                }
              >
                {data.efficiencyDelta > 0 ? '+' : ''}
                {data.efficiencyDelta.toFixed(2)}
              </span>
            </p>
            <p>
              <span className="text-slate-400">Load Type:</span>{' '}
              <span
                className="text-white capitalize"
                style={{ color: LOAD_TYPE_COLORS[data.loadType as keyof typeof LOAD_TYPE_COLORS] }}
              >
                {data.loadType}
              </span>
            </p>
            <p>
              <span className="text-slate-400">Activities:</span>{' '}
              <span className="text-white">{data.activityCount}</span>
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4">Load → Response</h3>
      <p className="text-sm text-slate-400 mb-4">
        Weekly distance vs efficiency change. Negative delta = improvement (more efficient).
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="week"
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            label={{ value: 'Efficiency Δ', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Bar dataKey="efficiencyDelta" name="Efficiency Change">
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={LOAD_TYPE_COLORS[entry.loadType as keyof typeof LOAD_TYPE_COLORS]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-4 flex gap-4 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: LOAD_TYPE_COLORS.productive }} />
          <span className="text-slate-400">Productive</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: LOAD_TYPE_COLORS.neutral }} />
          <span className="text-slate-400">Neutral</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: LOAD_TYPE_COLORS.wasted }} />
          <span className="text-slate-400">Wasted</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded" style={{ backgroundColor: LOAD_TYPE_COLORS.harmful }} />
          <span className="text-slate-400">Harmful</span>
        </div>
      </div>
    </div>
  );
}


