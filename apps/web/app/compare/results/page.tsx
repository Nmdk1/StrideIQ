'use client';

/**
 * Individual Comparison Results Page
 * 
 * The marquee feature - shows 2-10 activities side-by-side with:
 * - Metrics comparison table with best highlighted
 * - Overlay charts for pace and HR
 * - Plain-language insights
 */

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useCompareSelection } from '@/lib/context/CompareContext';
import { useCompareIndividual } from '@/lib/hooks/queries/compare';
import { useUnits } from '@/lib/context/UnitsContext';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import type { IndividualComparisonResult, ActivitySummary, ChartSplitData } from '@/lib/api/services/compare';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

// Colors for each activity in charts and cards
const ACTIVITY_COLORS = [
  '#f97316', // orange-500
  '#3b82f6', // blue-500
  '#22c55e', // green-500
  '#a855f7', // purple-500
  '#ec4899', // pink-500
  '#eab308', // yellow-500
  '#14b8a6', // teal-500
  '#ef4444', // red-500
  '#6366f1', // indigo-500
  '#06b6d4', // cyan-500
];

// Metrics configuration
const METRICS_CONFIG = {
  pace_per_km: { label: 'Pace', lowerIsBetter: true, format: 'pace' },
  efficiency: { label: 'Efficiency', lowerIsBetter: false, format: 'decimal3' },
  avg_hr: { label: 'Avg HR', lowerIsBetter: true, format: 'bpm' },
  distance_m: { label: 'Distance', lowerIsBetter: false, format: 'distance' },
  duration_s: { label: 'Duration', lowerIsBetter: false, format: 'duration' },
  intensity_score: { label: 'Intensity', lowerIsBetter: false, format: 'decimal0' },
  elevation_gain: { label: 'Elevation', lowerIsBetter: false, format: 'elevation' },
  temperature_f: { label: 'Temp', lowerIsBetter: false, format: 'temp' },
};

function MetricsTable({ 
  activities, 
  comparisonTable,
  bestByMetric,
}: { 
  activities: ActivitySummary[];
  comparisonTable: Record<string, (string | number | null)[]>;
  bestByMetric: Record<string, string>;
}) {
  const { formatDistance, formatPace, formatElevation, units } = useUnits();

  const formatValue = (
    metric: keyof typeof METRICS_CONFIG, 
    value: string | number | null
  ): string => {
    if (value === null || value === undefined) return '—';
    
    const config = METRICS_CONFIG[metric];
    if (!config) return String(value);

    switch (config.format) {
      case 'pace':
        if (typeof value === 'number') {
          return formatPace(value);
        }
        return String(value);
      case 'distance':
        if (typeof value === 'number') {
          return formatDistance(value, 1);
        }
        return String(value);
      case 'duration':
        if (typeof value === 'number') {
          const hours = Math.floor(value / 3600);
          const minutes = Math.floor((value % 3600) / 60);
          const seconds = Math.floor(value % 60);
          if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
          }
          return `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
        return String(value);
      case 'elevation':
        if (typeof value === 'number') {
          return formatElevation(value);
        }
        return String(value);
      case 'decimal3':
        if (typeof value === 'number') {
          return value.toFixed(3);
        }
        return String(value);
      case 'decimal0':
        if (typeof value === 'number') {
          return Math.round(value).toString();
        }
        return String(value);
      case 'bpm':
        return `${value} bpm`;
      case 'temp':
        return `${value}°F`;
      default:
        return String(value);
    }
  };

  const isBest = (metric: string, activityId: string): boolean => {
    return bestByMetric[metric] === activityId;
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-3 px-2 font-medium text-gray-400">Metric</th>
            {activities.map((activity, idx) => (
              <th key={activity.id} className="text-center py-3 px-2">
                <div className="flex items-center justify-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: ACTIVITY_COLORS[idx] }}
                  />
                  <Link href={`/activities/${activity.id}`} className="hover:text-orange-400">
                    <span className="font-medium max-w-[100px] truncate block">
                      {new Date(activity.date).toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric' 
                      })}
                    </span>
                  </Link>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(METRICS_CONFIG).map(([metric, config]) => {
            const values = comparisonTable[metric];
            if (!values || values.every(v => v === null)) return null;
            
            return (
              <tr key={metric} className="border-b border-gray-700/50">
                <td className="py-3 px-2 text-gray-400">{config.label}</td>
                {activities.map((activity, idx) => {
                  const value = values[idx];
                  const best = isBest(metric, activity.id);
                  
                  return (
                    <td 
                      key={activity.id} 
                      className={`text-center py-3 px-2 ${
                        best ? 'text-green-400 font-semibold' : ''
                      }`}
                    >
                      {best && <span className="mr-1">🏆</span>}
                      {formatValue(metric as keyof typeof METRICS_CONFIG, value)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function InsightsPanel({ insights }: { insights: string[] }) {
  if (!insights || insights.length === 0) return null;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <h3 className="font-semibold mb-3">💡 Insights</h3>
      <ul className="space-y-2">
        {insights.map((insight, idx) => (
          <li key={idx} className="text-gray-300 text-sm">
            {insight}
          </li>
        ))}
      </ul>
    </div>
  );
}

// Format pace from seconds/km to MM:SS string
function formatPace(secondsPerKm: number | null): string {
  if (!secondsPerKm || secondsPerKm <= 0) return '-';
  const minutes = Math.floor(secondsPerKm / 60);
  const seconds = Math.round(secondsPerKm % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Format distance for chart labels
function formatDistanceLabel(meters: number, useKm: boolean): string {
  if (useKm) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${(meters / 1609.34).toFixed(1)} mi`;
}

// Chart for pace overlay
function PaceOverlayChart({ activities }: { activities: ActivitySummary[] }) {
  // Build chart data - normalize to cumulative distance
  const chartData = useMemo(() => {
    // Find max splits across all activities
    const maxSplits = Math.max(...activities.map(a => a.splits?.length || 0));
    if (maxSplits === 0) return null;
    
    // Build data points for each split
    const data: any[] = [];
    for (let i = 0; i < maxSplits; i++) {
      const point: any = { split: i + 1 };
      
      activities.forEach((activity, idx) => {
        const split = activity.splits?.[i];
        if (split && split.pace_per_km) {
          // Store pace as minutes for easier reading
          point[`activity_${idx}`] = split.pace_per_km / 60;
          point[`name_${idx}`] = activity.name;
        }
      });
      
      data.push(point);
    }
    
    return data;
  }, [activities]);

  if (!chartData) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No splits data available for chart</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis 
          dataKey="split" 
          stroke="#9CA3AF" 
          label={{ value: 'Split', position: 'bottom', fill: '#9CA3AF' }}
        />
        <YAxis 
          stroke="#9CA3AF"
          tickFormatter={(value) => formatPace(value * 60)}
          reversed // Lower pace is better, show at top
          label={{ value: 'Pace', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
          labelStyle={{ color: '#F9FAFB' }}
          formatter={(value: any, name?: string) => {
            const actIdx = parseInt((name || '').replace('activity_', ''));
            const activityName = activities[actIdx]?.name || `Activity ${actIdx + 1}`;
            return [formatPace(value * 60), activityName];
          }}
        />
        <Legend 
          formatter={(value) => {
            const actIdx = parseInt(value.replace('activity_', ''));
            return activities[actIdx]?.name?.substring(0, 15) || `Activity ${actIdx + 1}`;
          }}
        />
        {activities.map((_, idx) => (
          <Line
            key={idx}
            type="monotone"
            dataKey={`activity_${idx}`}
            stroke={ACTIVITY_COLORS[idx]}
            strokeWidth={2}
            dot={{ fill: ACTIVITY_COLORS[idx], strokeWidth: 2, r: 3 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

// Chart for HR overlay
function HROverlayChart({ activities }: { activities: ActivitySummary[] }) {
  const chartData = useMemo(() => {
    const maxSplits = Math.max(...activities.map(a => a.splits?.length || 0));
    if (maxSplits === 0) return null;
    
    const data: any[] = [];
    for (let i = 0; i < maxSplits; i++) {
      const point: any = { split: i + 1 };
      
      activities.forEach((activity, idx) => {
        const split = activity.splits?.[i];
        if (split && split.avg_hr) {
          point[`activity_${idx}`] = split.avg_hr;
        }
      });
      
      data.push(point);
    }
    
    return data;
  }, [activities]);

  if (!chartData) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500">
        <p>No heart rate splits data available</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis 
          dataKey="split" 
          stroke="#9CA3AF"
          label={{ value: 'Split', position: 'bottom', fill: '#9CA3AF' }}
        />
        <YAxis 
          stroke="#9CA3AF"
          domain={['auto', 'auto']}
          label={{ value: 'HR (bpm)', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
          labelStyle={{ color: '#F9FAFB' }}
          formatter={(value: any, name?: string) => {
            const actIdx = parseInt((name || '').replace('activity_', ''));
            const activityName = activities[actIdx]?.name || `Activity ${actIdx + 1}`;
            return [`${value} bpm`, activityName];
          }}
        />
        <Legend 
          formatter={(value) => {
            const actIdx = parseInt(value.replace('activity_', ''));
            return activities[actIdx]?.name?.substring(0, 15) || `Activity ${actIdx + 1}`;
          }}
        />
        {activities.map((_, idx) => (
          <Line
            key={idx}
            type="monotone"
            dataKey={`activity_${idx}`}
            stroke={ACTIVITY_COLORS[idx]}
            strokeWidth={2}
            dot={{ fill: ACTIVITY_COLORS[idx], strokeWidth: 2, r: 3 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

// Bar chart for metric comparison
function MetricsBarChart({ activities }: { activities: ActivitySummary[] }) {
  const chartData = useMemo(() => {
    return activities.map((a, idx) => ({
      name: a.name?.substring(0, 12) || `Activity ${idx + 1}`,
      distance: a.distance_m / 1000,
      pace: a.pace_per_km ? a.pace_per_km / 60 : 0,
      hr: a.avg_hr || 0,
      efficiency: a.efficiency ? a.efficiency * 100 : 0,
      color: ACTIVITY_COLORS[idx],
    }));
  }, [activities]);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
        <YAxis stroke="#9CA3AF" />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
          labelStyle={{ color: '#F9FAFB' }}
        />
        <Bar 
          dataKey="efficiency" 
          fill="#f97316" 
          name="Efficiency"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ActivityCards({ activities }: { activities: ActivitySummary[] }) {
  const { formatDistance, formatPace } = useUnits();

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
      {activities.map((activity, idx) => (
        <Link key={activity.id} href={`/activities/${activity.id}`}>
          <div 
            className="bg-gray-800 rounded-lg border-2 p-4 hover:bg-gray-750 transition-colors"
            style={{ borderColor: ACTIVITY_COLORS[idx] }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div 
                className="w-4 h-4 rounded-full flex-shrink-0" 
                style={{ backgroundColor: ACTIVITY_COLORS[idx] }}
              />
              <span className="font-medium truncate">{activity.name}</span>
            </div>
            <p className="text-sm text-gray-400">
              {new Date(activity.date).toLocaleDateString('en-US', { 
                weekday: 'short',
                month: 'short', 
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-gray-400">Dist: </span>
                <span className="font-medium">{formatDistance(activity.distance_m, 1)}</span>
              </div>
              <div>
                <span className="text-gray-400">Pace: </span>
                <span className="font-medium">
                  {activity.pace_per_km ? formatPace(activity.pace_per_km) : '—'}
                </span>
              </div>
            </div>
            {activity.workout_type && (
              <div className="mt-2">
                <span className="px-2 py-1 bg-gray-700 rounded text-xs">
                  {activity.workout_type.replace(/_/g, ' ')}
                </span>
              </div>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}

export default function CompareResultsPage() {
  const router = useRouter();
  const { selectedActivities, selectionCount, clearSelection } = useCompareSelection();
  const compareMutation = useCompareIndividual();
  const [result, setResult] = useState<IndividualComparisonResult | null>(null);

  // Run comparison when page loads
  useEffect(() => {
    if (selectionCount >= 2) {
      const ids = selectedActivities.map(a => a.id);
      compareMutation.mutate(ids, {
        onSuccess: (data) => {
          setResult(data);
        },
      });
    }
  }, []);  // Only run on mount

  // Redirect if not enough activities selected
  if (selectionCount < 2) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
          <div className="max-w-6xl mx-auto px-4 text-center">
            <h1 className="text-2xl font-bold mb-4">No Activities Selected</h1>
            <p className="text-gray-400 mb-6">
              Select at least 2 activities from the Activities page to compare them.
            </p>
            <Link
              href="/activities"
              className="px-6 py-3 bg-orange-600 hover:bg-orange-700 rounded-lg font-medium transition-colors inline-block"
            >
              Go to Activities
            </Link>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-7xl mx-auto px-4">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-2xl font-bold">Comparing {selectionCount} Activities</h1>
              <p className="text-gray-400">Side-by-side performance analysis</p>
            </div>
            <div className="flex gap-3">
              <Link
                href="/activities"
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
              >
                ← Add More
              </Link>
              <button
                onClick={() => {
                  clearSelection();
                  router.push('/activities');
                }}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
              >
                Clear & Start Over
              </button>
            </div>
          </div>

          {compareMutation.isPending && (
            <div className="flex justify-center py-12">
              <LoadingSpinner size="lg" />
            </div>
          )}

          {compareMutation.isError && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-center">
              <p className="text-red-400">
                Error comparing activities: {compareMutation.error?.message || 'Unknown error'}
              </p>
            </div>
          )}

          {result && (
            <>
              {/* Activity cards with color coding */}
              <ActivityCards activities={result.activities} />

              {/* Insights */}
              <div className="mb-6">
                <InsightsPanel insights={result.insights} />
              </div>

              {/* Metrics comparison table */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <h3 className="font-semibold mb-4">📊 Metrics Comparison</h3>
                <MetricsTable 
                  activities={result.activities}
                  comparisonTable={result.comparison_table}
                  bestByMetric={result.best_by_metric}
                />
              </div>

              {/* Overlay Charts */}
              <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <h3 className="font-semibold mb-4">📈 Pace Per Split</h3>
                  <PaceOverlayChart activities={result.activities} />
                </div>
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <h3 className="font-semibold mb-4">❤️ Heart Rate Per Split</h3>
                  <HROverlayChart activities={result.activities} />
                </div>
              </div>

              {/* Efficiency Comparison Bar Chart */}
              <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 p-4">
                <h3 className="font-semibold mb-4">⚡ Efficiency Comparison</h3>
                <MetricsBarChart activities={result.activities} />
              </div>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
