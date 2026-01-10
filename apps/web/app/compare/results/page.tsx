'use client';

/**
 * Multi-Run Comparison Results Page
 * 
 * Shows detailed comparison of 2-10 user-selected runs:
 * - Pace overlay chart (all runs on same chart)
 * - HR overlay chart (all runs on same chart)
 * - Metrics comparison table
 * - Performance insights
 */

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useAnalyzeAttribution } from '@/lib/hooks/queries/attribution';
import type { PerformanceDriver, AttributionResult } from '@/lib/api/services/attribution';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

// Color palette for runs
const RUN_COLORS = [
  '#f97316', // Orange (baseline)
  '#3b82f6', // Blue
  '#10b981', // Emerald
  '#8b5cf6', // Violet
  '#ec4899', // Pink
  '#06b6d4', // Cyan
  '#f59e0b', // Amber
  '#6366f1', // Indigo
  '#84cc16', // Lime
  '#ef4444', // Red
];

// Types for comparison data
interface SplitData {
  split: number;
  distance_km: number;
  pace_per_km?: number;
  avg_hr?: number;
}

interface ComparedRun {
  id: string;
  name: string;
  date: string;
  distance_km: number;
  duration_s: number;
  pace_per_km?: number;
  pace_formatted?: string;
  avg_hr?: number;
  max_hr?: number;
  intensity_score?: number;
  elevation_gain?: number;
  temperature_f?: number;
  similarity_score?: number;
  splits?: SplitData[];
}

interface ComparisonResult {
  target_run: ComparedRun;
  similar_runs: ComparedRun[];
  ghost_average?: {
    avg_pace_per_km: number;
    avg_hr?: number;
    avg_max_hr?: number;
    num_runs_averaged: number;
  };
  performance_score?: {
    score: number;
    rating: string;
    pace_vs_baseline: number;
    efficiency_vs_baseline: number;
  };
  headline?: string;
  key_insight?: string;
}

// Storage key for comparison results
const COMPARE_STORAGE_KEY = 'strideiq_compare_results';

// Key Drivers Component
function KeyDriversSection({ 
  attribution, 
  isLoading 
}: { 
  attribution: AttributionResult | null; 
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6 mb-8">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>🔍</span> Analyzing Key Drivers...
        </h3>
        <div className="flex justify-center py-8">
          <LoadingSpinner size="md" />
        </div>
      </div>
    );
  }

  if (!attribution || attribution.key_drivers.length === 0) {
    return (
      <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6 mb-8">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>🔍</span> Key Drivers
        </h3>
        <p className="text-gray-400 text-center py-4">
          Not enough input data (sleep, weight, etc.) to identify drivers yet.
          Keep logging to unlock the &quot;why&quot; behind your performance.
        </p>
      </div>
    );
  }

  const positiveDrivers = attribution.key_drivers.filter(d => d.direction === 'positive');
  const negativeDrivers = attribution.key_drivers.filter(d => d.direction === 'negative');

  return (
    <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <span>🔍</span> Why This Performance?
        </h3>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-1 rounded-full ${
            attribution.overall_confidence === 'high' 
              ? 'bg-emerald-900/50 text-emerald-400' 
              : attribution.overall_confidence === 'moderate'
                ? 'bg-amber-900/50 text-amber-400'
                : 'bg-gray-700 text-gray-400'
          }`}>
            {attribution.overall_confidence} confidence
          </span>
          <span className="text-xs text-gray-500">
            {Math.round(attribution.data_quality_score * 100)}% data coverage
          </span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {attribution.summary_positive && (
          <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-4">
            <div className="flex items-center gap-2 text-emerald-400 font-medium mb-2">
              <span>↑</span> Helped
            </div>
            <p className="text-sm text-gray-300">{attribution.summary_positive}</p>
          </div>
        )}
        {attribution.summary_negative && (
          <div className="bg-rose-900/20 border border-rose-700/50 rounded-lg p-4">
            <div className="flex items-center gap-2 text-rose-400 font-medium mb-2">
              <span>↓</span> Potential Drags
            </div>
            <p className="text-sm text-gray-300">{attribution.summary_negative}</p>
          </div>
        )}
      </div>

      {/* Driver Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {attribution.key_drivers.map((driver, idx) => (
          <div 
            key={idx}
            className={`rounded-lg p-4 border ${
              driver.direction === 'positive' 
                ? 'bg-emerald-900/10 border-emerald-700/30' 
                : driver.direction === 'negative'
                  ? 'bg-rose-900/10 border-rose-700/30'
                  : 'bg-gray-800/50 border-gray-700/50'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xl">{driver.icon}</span>
              <span className="font-medium text-white">{driver.name}</span>
              <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                driver.confidence === 'high' 
                  ? 'bg-emerald-900/50 text-emerald-400' 
                  : driver.confidence === 'moderate'
                    ? 'bg-amber-900/50 text-amber-400'
                    : 'bg-gray-700 text-gray-400'
              }`}>
                {driver.confidence}
              </span>
            </div>
            
            <div className={`text-lg font-bold mb-1 ${
              driver.direction === 'positive' 
                ? 'text-emerald-400' 
                : driver.direction === 'negative'
                  ? 'text-rose-400'
                  : 'text-gray-300'
            }`}>
              {driver.magnitude}
            </div>
            
            <p className="text-xs text-gray-400">{driver.insight}</p>
            
            {/* Contribution bar */}
            <div className="mt-2">
              <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${
                    driver.direction === 'positive' 
                      ? 'bg-emerald-500' 
                      : driver.direction === 'negative'
                        ? 'bg-rose-500'
                        : 'bg-gray-500'
                  }`}
                  style={{ width: `${driver.contribution_score * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CompareResultsPage() {
  const router = useRouter();
  const [comparisonData, setComparisonData] = useState<ComparisonResult | null>(null);
  const [attributionData, setAttributionData] = useState<AttributionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [attributionLoading, setAttributionLoading] = useState(false);
  
  const analyzeAttributionMutation = useAnalyzeAttribution();

  // Load comparison data from sessionStorage
  useEffect(() => {
    const storedData = sessionStorage.getItem(COMPARE_STORAGE_KEY);
    if (storedData) {
      try {
        setComparisonData(JSON.parse(storedData));
      } catch (e) {
        console.error('Failed to parse comparison data:', e);
      }
    }
    setLoading(false);
  }, []);

  // Fetch attribution once comparison data is loaded
  useEffect(() => {
    if (!comparisonData) return;
    
    const fetchAttribution = async () => {
      setAttributionLoading(true);
      try {
        const result = await analyzeAttributionMutation.mutateAsync({
          currentActivityId: comparisonData.target_run.id,
          baselineActivityIds: comparisonData.similar_runs.map(r => r.id),
          performanceDelta: comparisonData.performance_score?.pace_vs_baseline,
        });
        if (result.success && result.data) {
          setAttributionData(result.data);
        }
      } catch (e) {
        console.error('Failed to fetch attribution:', e);
      } finally {
        setAttributionLoading(false);
      }
    };
    
    fetchAttribution();
  }, [comparisonData]); // eslint-disable-line react-hooks/exhaustive-deps

  // Combine all runs for comparison
  const allRuns = useMemo(() => {
    if (!comparisonData) return [];
    return [comparisonData.target_run, ...comparisonData.similar_runs];
  }, [comparisonData]);

  // Build pace overlay chart data
  const paceChartData = useMemo(() => {
    if (!allRuns.length) return [];
    
    // Find max number of splits
    const maxSplits = Math.max(...allRuns.map(r => r.splits?.length || 0));
    if (maxSplits === 0) return [];
    
    const data: any[] = [];
    for (let i = 0; i < maxSplits; i++) {
      const point: any = { split: i + 1 };
      allRuns.forEach((run, runIdx) => {
        const split = run.splits?.[i];
        if (split?.pace_per_km) {
          // Convert to minutes for display
          point[`run_${runIdx}`] = split.pace_per_km / 60;
        }
      });
      data.push(point);
    }
    return data;
  }, [allRuns]);

  // Build HR overlay chart data
  const hrChartData = useMemo(() => {
    if (!allRuns.length) return [];
    
    const maxSplits = Math.max(...allRuns.map(r => r.splits?.length || 0));
    if (maxSplits === 0) return [];
    
    const data: any[] = [];
    for (let i = 0; i < maxSplits; i++) {
      const point: any = { split: i + 1 };
      allRuns.forEach((run, runIdx) => {
        const split = run.splits?.[i];
        if (split?.avg_hr) {
          point[`run_${runIdx}`] = split.avg_hr;
        }
      });
      data.push(point);
    }
    return data;
  }, [allRuns]);

  // Format pace for tooltip
  const formatPaceValue = (value: number | null): string => {
    if (!value || value <= 0) return '-';
    const minutes = Math.floor(value);
    const seconds = Math.round((value - minutes) * 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}/km`;
  };

  // Format duration
  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-900 flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (!comparisonData) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-900 text-gray-100 py-12">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <div className="text-6xl mb-6">📊</div>
            <h1 className="text-2xl font-bold mb-4">No Comparison Data</h1>
            <p className="text-gray-400 mb-8">
              Select runs from the Compare page to see detailed comparison.
            </p>
            <Link
              href="/compare"
              className="inline-block px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-lg transition-colors"
            >
              Go to Compare
            </Link>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-900 to-gray-950 text-gray-100">
        {/* Background accents */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 max-w-6xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <Link 
              href="/compare"
              className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
            >
              ← Back
            </Link>
            <div>
              <h1 className="text-2xl font-bold">Run Comparison</h1>
              <p className="text-gray-400">
                Comparing {allRuns.length} runs side by side
              </p>
            </div>
          </div>

          {/* Summary Cards */}
          {comparisonData.performance_score && (
            <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6 mb-8">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="text-center">
                  <div className="text-4xl font-bold text-orange-400">
                    {comparisonData.performance_score.score.toFixed(0)}
                  </div>
                  <div className="text-sm text-gray-400">Performance Score</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${
                    comparisonData.performance_score.pace_vs_baseline > 0 
                      ? 'text-emerald-400' 
                      : comparisonData.performance_score.pace_vs_baseline < 0 
                        ? 'text-rose-400' 
                        : 'text-white'
                  }`}>
                    {comparisonData.performance_score.pace_vs_baseline > 0 ? '+' : ''}
                    {comparisonData.performance_score.pace_vs_baseline.toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-400">vs Baseline Pace</div>
                </div>
                <div className="col-span-2">
                  {comparisonData.headline && (
                    <p className="text-lg font-medium text-white">{comparisonData.headline}</p>
                  )}
                  {comparisonData.key_insight && (
                    <p className="text-sm text-gray-400 mt-1">{comparisonData.key_insight}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Legend - Run Colors */}
          <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-4 mb-6">
            <div className="flex flex-wrap gap-4">
              {allRuns.map((run, idx) => (
                <div key={run.id} className="flex items-center gap-2">
                  <div 
                    className="w-4 h-4 rounded-full" 
                    style={{ backgroundColor: RUN_COLORS[idx] }}
                  />
                  <span className="text-sm">
                    {idx === 0 && '★ '}
                    {run.name?.slice(0, 30) || `Run ${idx + 1}`}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(run.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">★ = Baseline run</p>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Pace Overlay Chart */}
            <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>⏱️</span> Pace Comparison
              </h3>
              {paceChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={paceChartData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis 
                      dataKey="split" 
                      stroke="#9CA3AF"
                      tick={{ fill: '#9CA3AF', fontSize: 11 }}
                      label={{ value: 'Split', position: 'bottom', fill: '#9CA3AF', offset: 0 }}
                    />
                    <YAxis 
                      stroke="#9CA3AF"
                      tick={{ fill: '#9CA3AF', fontSize: 11 }}
                      tickFormatter={(v) => formatPaceValue(v)}
                      reversed
                      domain={['auto', 'auto']}
                    />
                    <Tooltip
                      contentStyle={{ 
                        backgroundColor: '#1F2937', 
                        border: '1px solid #374151',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: '#F9FAFB' }}
                      formatter={(value, name) => {
                        if (typeof value !== 'number') return ['-', name || ''];
                        const runIdx = parseInt(String(name).split('_')[1]);
                        const runName = allRuns[runIdx]?.name?.slice(0, 20) || `Run ${runIdx + 1}`;
                        return [formatPaceValue(value), runName];
                      }}
                    />
                    {allRuns.map((run, idx) => (
                      <Line
                        key={run.id}
                        type="monotone"
                        dataKey={`run_${idx}`}
                        stroke={RUN_COLORS[idx]}
                        strokeWidth={idx === 0 ? 3 : 2}
                        dot={{ fill: RUN_COLORS[idx], strokeWidth: 1, r: 3 }}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  No splits data available
                </div>
              )}
            </div>

            {/* HR Overlay Chart */}
            <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>❤️</span> Heart Rate Comparison
              </h3>
              {hrChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={hrChartData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis 
                      dataKey="split" 
                      stroke="#9CA3AF"
                      tick={{ fill: '#9CA3AF', fontSize: 11 }}
                      label={{ value: 'Split', position: 'bottom', fill: '#9CA3AF', offset: 0 }}
                    />
                    <YAxis 
                      stroke="#9CA3AF"
                      tick={{ fill: '#9CA3AF', fontSize: 11 }}
                      domain={['auto', 'auto']}
                      label={{ value: 'BPM', angle: -90, position: 'insideLeft', fill: '#9CA3AF', offset: 10 }}
                    />
                    <Tooltip
                      contentStyle={{ 
                        backgroundColor: '#1F2937', 
                        border: '1px solid #374151',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: '#F9FAFB' }}
                      formatter={(value, name) => {
                        if (typeof value !== 'number') return ['-', name || ''];
                        const runIdx = parseInt(String(name).split('_')[1]);
                        const runName = allRuns[runIdx]?.name?.slice(0, 20) || `Run ${runIdx + 1}`;
                        return [`${value} bpm`, runName];
                      }}
                    />
                    {allRuns.map((run, idx) => (
                      <Line
                        key={run.id}
                        type="monotone"
                        dataKey={`run_${idx}`}
                        stroke={RUN_COLORS[idx]}
                        strokeWidth={idx === 0 ? 3 : 2}
                        dot={{ fill: RUN_COLORS[idx], strokeWidth: 1, r: 3 }}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  No heart rate data available
                </div>
              )}
            </div>
          </div>

          {/* Key Drivers Section - THE WHY */}
          <KeyDriversSection 
            attribution={attributionData} 
            isLoading={attributionLoading} 
          />

          {/* Comparison Table */}
          <div className="bg-gray-800/60 rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-4 border-b border-gray-700">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span>📊</span> Metrics Comparison
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">Run</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-400">Date</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">Distance</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">Duration</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">Pace</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">Avg HR</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">Max HR</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-400">Elevation</th>
                  </tr>
                </thead>
                <tbody>
                  {allRuns.map((run, idx) => (
                    <tr 
                      key={run.id} 
                      className={`border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors ${
                        idx === 0 ? 'bg-orange-900/10' : ''
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3 rounded-full flex-shrink-0" 
                            style={{ backgroundColor: RUN_COLORS[idx] }}
                          />
                          <Link 
                            href={`/activities/${run.id}`}
                            className="text-white hover:text-orange-400 transition-colors truncate max-w-[200px]"
                          >
                            {idx === 0 && <span className="text-orange-400">★ </span>}
                            {run.name?.slice(0, 30) || `Run ${idx + 1}`}
                          </Link>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {new Date(run.date).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {run.distance_km?.toFixed(2)} km
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {formatDuration(run.duration_s)}
                      </td>
                      <td className="px-4 py-3 text-right text-white font-medium">
                        {run.pace_formatted || '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {run.avg_hr ? `${run.avg_hr} bpm` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {run.max_hr ? `${run.max_hr} bpm` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {run.elevation_gain ? `${Math.round(run.elevation_gain)}m` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Ghost Average Stats */}
          {comparisonData.ghost_average && (
            <div className="mt-8 bg-indigo-900/20 rounded-xl border border-indigo-700/50 p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>👻</span> Ghost Average (Baseline from {comparisonData.ghost_average.num_runs_averaged} runs)
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-gray-400">Avg Pace</div>
                  <div className="text-xl font-bold text-white">
                    {formatPaceValue(comparisonData.ghost_average.avg_pace_per_km / 60)}
                  </div>
                </div>
                {comparisonData.ghost_average.avg_hr && (
                  <div>
                    <div className="text-sm text-gray-400">Avg HR</div>
                    <div className="text-xl font-bold text-white">
                      {Math.round(comparisonData.ghost_average.avg_hr)} bpm
                    </div>
                  </div>
                )}
                {comparisonData.ghost_average.avg_max_hr && (
                  <div>
                    <div className="text-sm text-gray-400">Avg Max HR</div>
                    <div className="text-xl font-bold text-white">
                      {Math.round(comparisonData.ghost_average.avg_max_hr)} bpm
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="mt-8 flex justify-center gap-4">
            <Link
              href="/compare"
              className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition-colors"
            >
              Compare Different Runs
            </Link>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
