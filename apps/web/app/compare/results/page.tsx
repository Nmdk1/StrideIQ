'use client';

/**
 * Multi-Run Comparison Results Page
 * 
 * What the athlete wants:
 * 1. Runs listed vertically with ALL key metrics
 * 2. Overlay charts with toggleable metrics (pace, HR, cadence)
 * 3. Clean "why" presentation
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
  Legend,
} from 'recharts';

// =============================================================================
// DESIGN TOKENS
// =============================================================================

const RUN_COLORS = [
  '#f97316', // Orange (primary/baseline)
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

// =============================================================================
// TYPES
// =============================================================================

interface SplitData {
  split_number: number;
  distance_m: number;
  elapsed_time_s: number;
  pace_per_km?: number;
  avg_hr?: number;
  cadence?: number;
}

interface ComparedRun {
  id: string;
  name: string;
  date: string;
  distance_m?: number;
  distance_km?: number;
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
  workout_type?: string;
}

interface ComparisonResult {
  target_run: ComparedRun;
  similar_runs: ComparedRun[];
  ghost_average?: {
    avg_pace_per_km: number;
    avg_pace_formatted?: string;
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

const COMPARE_STORAGE_KEY = 'strideiq_compare_results';

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

const formatPace = (secondsPerKm: number | null | undefined): string => {
  if (!secondsPerKm || secondsPerKm <= 0) return '—';
  const minutes = Math.floor(secondsPerKm / 60);
  const seconds = Math.round(secondsPerKm % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}/km`;
};

const formatDuration = (seconds: number | null | undefined): string => {
  if (!seconds) return '—';
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const formatDistance = (meters: number | null | undefined): string => {
  if (!meters) return '—';
  return `${(meters / 1000).toFixed(2)} km`;
};

// =============================================================================
// RUN CARD COMPONENT
// =============================================================================

function RunCard({ 
  run, 
  index, 
  isBaseline 
}: { 
  run: ComparedRun; 
  index: number; 
  isBaseline: boolean;
}) {
  const color = RUN_COLORS[index];
  
  return (
    <div 
      className={`rounded-xl border-2 p-5 transition-all ${
        isBaseline 
          ? 'bg-gradient-to-r from-orange-900/20 to-gray-800/60 border-orange-500/50' 
          : 'bg-gray-800/60 border-gray-700 hover:border-gray-600'
      }`}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div 
          className="w-4 h-4 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {isBaseline && (
              <span className="text-xs px-2 py-0.5 bg-orange-600 rounded text-white font-medium">
                BASELINE
              </span>
            )}
            <Link 
              href={`/activities/${run.id}`}
              className="font-semibold text-white hover:text-orange-400 transition-colors truncate"
            >
              {run.name || 'Untitled Run'}
            </Link>
          </div>
          <div className="text-sm text-gray-400">
            {new Date(run.date).toLocaleDateString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
            {run.workout_type && (
              <span className="ml-2 text-gray-500">• {run.workout_type.replace(/_/g, ' ')}</span>
            )}
          </div>
        </div>
      </div>
      
      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Distance</div>
          <div className="text-lg font-bold text-white">
            {formatDistance(run.distance_m || (run.distance_km ? run.distance_km * 1000 : undefined))}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Time</div>
          <div className="text-lg font-bold text-white">{formatDuration(run.duration_s)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Pace</div>
          <div className="text-lg font-bold text-white">{run.pace_formatted || formatPace(run.pace_per_km)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Avg HR</div>
          <div className="text-lg font-bold text-white">
            {run.avg_hr ? `${run.avg_hr} bpm` : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Max HR</div>
          <div className="text-lg font-bold text-white">
            {run.max_hr ? `${run.max_hr} bpm` : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Elevation</div>
          <div className="text-lg font-bold text-white">
            {run.elevation_gain ? `${Math.round(run.elevation_gain)}m` : '—'}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// OVERLAY CHART WITH TOGGLES
// =============================================================================

function OverlayChart({ 
  allRuns 
}: { 
  allRuns: ComparedRun[];
}) {
  const [showPace, setShowPace] = useState(true);
  const [showHR, setShowHR] = useState(true);
  
  // Debug logging
  useEffect(() => {
    console.log('OverlayChart - allRuns:', allRuns);
    allRuns.forEach((run, idx) => {
      console.log(`Run ${idx} (${run.name}):`, {
        hasSplits: !!run.splits,
        splitsLength: run.splits?.length || 0,
        splits: run.splits,
        pace_per_km: run.pace_per_km,
        avg_hr: run.avg_hr,
      });
    });
  }, [allRuns]);
  
  // Build chart data from splits
  const chartData = useMemo(() => {
    if (!allRuns.length) return [];
    
    const maxSplits = Math.max(...allRuns.map(r => r.splits?.length || 0));
    console.log('maxSplits:', maxSplits);
    
    // If no splits, create a simple 2-point chart (start/end) using run averages
    if (maxSplits === 0) {
      // Fallback: Create synthetic points from run-level data
      const runsWithPace = allRuns.filter(r => r.pace_per_km);
      const runsWithHR = allRuns.filter(r => r.avg_hr);
      
      if (runsWithPace.length === 0 && runsWithHR.length === 0) {
        return [];
      }
      
      // Create 2 points per run - this shows flat lines but at least visualizes the comparison
      const data: any[] = [
        { split: 'Start' },
        { split: 'End' },
      ];
      
      allRuns.forEach((run, runIdx) => {
        if (run.pace_per_km) {
          data[0][`pace_${runIdx}`] = run.pace_per_km / 60;
          data[1][`pace_${runIdx}`] = run.pace_per_km / 60;
        }
        if (run.avg_hr) {
          data[0][`hr_${runIdx}`] = run.avg_hr;
          data[1][`hr_${runIdx}`] = run.avg_hr;
        }
      });
      
      console.log('Fallback chart data (no splits):', data);
      return data;
    }
    
    const data: any[] = [];
    for (let i = 0; i < maxSplits; i++) {
      const point: any = { split: i + 1 };
      
      allRuns.forEach((run, runIdx) => {
        const split = run.splits?.[i];
        if (split) {
          if (split.pace_per_km) {
            point[`pace_${runIdx}`] = split.pace_per_km / 60; // Convert to minutes
          }
          if (split.avg_hr) {
            point[`hr_${runIdx}`] = split.avg_hr;
          }
        }
      });
      
      data.push(point);
    }
    console.log('Chart data from splits:', data);
    return data;
  }, [allRuns]);

  const hasPaceData = chartData.some(d => allRuns.some((_, i) => d[`pace_${i}`]));
  const hasHRData = chartData.some(d => allRuns.some((_, i) => d[`hr_${i}`]));
  
  console.log('hasPaceData:', hasPaceData, 'hasHRData:', hasHRData);

  if (chartData.length === 0) {
    return (
      <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-8 text-center">
        <div className="text-4xl mb-4">📊</div>
        <p className="text-gray-400">No pace or heart rate data available for comparison</p>
        <p className="text-xs text-gray-500 mt-2">
          Runs need either split data or average metrics to display charts
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-6">
      {/* Toggle Controls */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">Split-by-Split Comparison</h3>
        <div className="flex items-center gap-4">
          {hasPaceData && (
            <button
              onClick={() => setShowPace(!showPace)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                showPace 
                  ? 'bg-orange-600 text-white' 
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              ⏱️ Pace
            </button>
          )}
          {hasHRData && (
            <button
              onClick={() => setShowHR(!showHR)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                showHR 
                  ? 'bg-rose-600 text-white' 
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              ❤️ Heart Rate
            </button>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4">
        {allRuns.map((run, idx) => (
          <div key={run.id} className="flex items-center gap-2 text-sm">
            <div 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: RUN_COLORS[idx] }}
            />
            <span className="text-gray-300 truncate max-w-[150px]">
              {idx === 0 && '★ '}
              {run.name?.slice(0, 20) || `Run ${idx + 1}`}
            </span>
          </div>
        ))}
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="split" 
            stroke="#9CA3AF"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            label={{ value: 'Split (Mile/Km)', position: 'bottom', fill: '#9CA3AF', offset: 0 }}
          />
          
          {/* Left Y-Axis for Pace */}
          {showPace && (
            <YAxis 
              yAxisId="pace"
              orientation="left"
              stroke="#f97316"
              tick={{ fill: '#f97316', fontSize: 11 }}
              tickFormatter={(v) => formatPace(v * 60)}
              reversed
              domain={['auto', 'auto']}
              label={{ value: 'Pace', angle: -90, position: 'insideLeft', fill: '#f97316', offset: 10 }}
            />
          )}
          
          {/* Right Y-Axis for HR */}
          {showHR && (
            <YAxis 
              yAxisId="hr"
              orientation="right"
              stroke="#ef4444"
              tick={{ fill: '#ef4444', fontSize: 11 }}
              domain={['auto', 'auto']}
              label={{ value: 'HR (bpm)', angle: 90, position: 'insideRight', fill: '#ef4444', offset: 10 }}
            />
          )}
          
          <Tooltip
            contentStyle={{ 
              backgroundColor: '#1F2937', 
              border: '1px solid #374151',
              borderRadius: '8px',
            }}
            labelStyle={{ color: '#F9FAFB' }}
            formatter={(value, name) => {
              if (typeof value !== 'number') return ['-', ''];
              const [metric, idxStr] = String(name).split('_');
              const runIdx = parseInt(idxStr);
              const runName = allRuns[runIdx]?.name?.slice(0, 15) || `Run ${runIdx + 1}`;
              
              if (metric === 'pace') {
                return [formatPace(value * 60), `${runName} Pace`];
              }
              return [`${value} bpm`, `${runName} HR`];
            }}
          />
          
          {/* Pace lines */}
          {showPace && allRuns.map((run, idx) => (
            <Line
              key={`pace_${run.id}`}
              yAxisId="pace"
              type="monotone"
              dataKey={`pace_${idx}`}
              stroke={RUN_COLORS[idx]}
              strokeWidth={idx === 0 ? 3 : 2}
              dot={{ fill: RUN_COLORS[idx], strokeWidth: 1, r: 3 }}
              connectNulls
            />
          ))}
          
          {/* HR lines */}
          {showHR && allRuns.map((run, idx) => (
            <Line
              key={`hr_${run.id}`}
              yAxisId="hr"
              type="monotone"
              dataKey={`hr_${idx}`}
              stroke={RUN_COLORS[idx]}
              strokeWidth={idx === 0 ? 3 : 2}
              strokeDasharray={showPace ? "5 5" : undefined} // Dashed when both shown
              dot={{ fill: RUN_COLORS[idx], strokeWidth: 1, r: 2 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      
      <p className="text-xs text-gray-500 text-center mt-2">
        {showPace && showHR && "Solid lines = Pace (left axis) • Dashed lines = HR (right axis)"}
        {showPace && !showHR && "Lower is faster"}
        {!showPace && showHR && "Heart rate across each split"}
      </p>
    </div>
  );
}

// =============================================================================
// WHY SECTION (KEY DRIVERS)
// =============================================================================

function WhySection({ 
  attribution, 
  isLoading 
}: { 
  attribution: AttributionResult | null; 
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-gradient-to-br from-indigo-900/30 to-purple-900/20 rounded-xl border border-indigo-700/50 p-6">
        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          🔍 Analyzing the WHY...
        </h3>
        <div className="flex justify-center py-8">
          <LoadingSpinner size="md" />
        </div>
      </div>
    );
  }

  if (!attribution || attribution.key_drivers.length === 0) {
    return (
      <div className="bg-gradient-to-br from-gray-800/60 to-gray-900/40 rounded-xl border border-gray-700 p-6">
        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          🔍 The WHY
        </h3>
        <p className="text-gray-400">
          Not enough training input data to determine drivers. 
          Log sleep, check-ins, and body composition to unlock insights.
        </p>
      </div>
    );
  }

  const positiveDrivers = attribution.key_drivers.filter(d => d.direction === 'positive');
  const negativeDrivers = attribution.key_drivers.filter(d => d.direction === 'negative');
  const neutralDrivers = attribution.key_drivers.filter(d => d.direction === 'neutral');

  return (
    <div className="bg-gradient-to-br from-indigo-900/30 to-purple-900/20 rounded-xl border border-indigo-700/50 p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-white flex items-center gap-2">
          🔍 The WHY
        </h3>
        <span className={`text-xs px-3 py-1 rounded-full ${
          attribution.overall_confidence === 'high' 
            ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-700' 
            : attribution.overall_confidence === 'moderate'
              ? 'bg-amber-900/50 text-amber-400 border border-amber-700'
              : 'bg-gray-700 text-gray-400 border border-gray-600'
        }`}>
          {attribution.overall_confidence} confidence
        </span>
      </div>

      {/* Summaries */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {attribution.summary_positive && (
          <div className="bg-emerald-900/30 border border-emerald-700/50 rounded-lg p-4">
            <div className="text-emerald-400 font-bold mb-1">↑ Helped</div>
            <p className="text-gray-200">{attribution.summary_positive}</p>
          </div>
        )}
        {attribution.summary_negative && (
          <div className="bg-rose-900/30 border border-rose-700/50 rounded-lg p-4">
            <div className="text-rose-400 font-bold mb-1">↓ Potential Drags</div>
            <p className="text-gray-200">{attribution.summary_negative}</p>
          </div>
        )}
      </div>

      {/* Driver Pills */}
      <div className="space-y-3">
        {attribution.key_drivers.slice(0, 4).map((driver, idx) => (
          <div 
            key={idx}
            className={`flex items-center gap-4 p-3 rounded-lg ${
              driver.direction === 'positive' 
                ? 'bg-emerald-900/20 border border-emerald-800/50' 
                : driver.direction === 'negative'
                  ? 'bg-rose-900/20 border border-rose-800/50'
                  : 'bg-gray-800/50 border border-gray-700/50'
            }`}
          >
            <span className="text-2xl">{driver.icon}</span>
            <div className="flex-1">
              <div className="font-medium text-white">{driver.name}</div>
              <div className="text-sm text-gray-400">{driver.insight}</div>
            </div>
            <div className={`text-lg font-bold ${
              driver.direction === 'positive' 
                ? 'text-emerald-400' 
                : driver.direction === 'negative'
                  ? 'text-rose-400'
                  : 'text-gray-300'
            }`}>
              {driver.magnitude}
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-500 mt-4">
        Based on {attribution.data_quality_score * 100}% data coverage from trailing 4 weeks
      </p>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

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

  // Combine all runs
  const allRuns = useMemo(() => {
    if (!comparisonData) return [];
    return [comparisonData.target_run, ...comparisonData.similar_runs];
  }, [comparisonData]);

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
        {/* Background */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-500/5 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-4 py-8">
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
                Comparing {allRuns.length} runs
              </p>
            </div>
          </div>

          {/* Quick Stats Bar */}
          {comparisonData.performance_score && (
            <div className="bg-gray-800/60 rounded-xl border border-gray-700 p-4 mb-6 flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div>
                  <div className="text-xs text-gray-500 uppercase">Performance</div>
                  <div className="text-2xl font-bold text-orange-400">
                    {comparisonData.performance_score.score.toFixed(0)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase">vs Baseline</div>
                  <div className={`text-xl font-bold ${
                    comparisonData.performance_score.pace_vs_baseline > 0 
                      ? 'text-emerald-400' 
                      : comparisonData.performance_score.pace_vs_baseline < 0 
                        ? 'text-rose-400' 
                        : 'text-white'
                  }`}>
                    {comparisonData.performance_score.pace_vs_baseline > 0 ? '+' : ''}
                    {comparisonData.performance_score.pace_vs_baseline.toFixed(1)}% pace
                  </div>
                </div>
              </div>
              {comparisonData.headline && (
                <div className="text-right text-gray-300 max-w-md">
                  {comparisonData.headline}
                </div>
              )}
            </div>
          )}

          {/* Section 1: Overlay Chart with Toggles (ABOVE runs) */}
          <section className="mb-8">
            <OverlayChart allRuns={allRuns} />
          </section>

          {/* Section 2: Runs Listed Vertically */}
          <section className="mb-8">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              📋 Runs
            </h2>
            <div className="space-y-3">
              {allRuns.map((run, idx) => (
                <RunCard 
                  key={run.id} 
                  run={run} 
                  index={idx} 
                  isBaseline={idx === 0} 
                />
              ))}
            </div>
          </section>

          {/* Section 3: The WHY */}
          <section className="mb-8">
            <WhySection 
              attribution={attributionData} 
              isLoading={attributionLoading} 
            />
          </section>

          {/* Ghost Average */}
          {comparisonData.ghost_average && (
            <section className="mb-8">
              <div className="bg-gray-800/40 rounded-xl border border-gray-700/50 p-5">
                <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  👻 Ghost Average
                  <span className="text-sm font-normal text-gray-400">
                    (baseline from {comparisonData.ghost_average.num_runs_averaged} runs)
                  </span>
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 uppercase">Avg Pace</div>
                    <div className="text-lg font-bold text-white">
                      {comparisonData.ghost_average.avg_pace_formatted || formatPace(comparisonData.ghost_average.avg_pace_per_km)}
                    </div>
                  </div>
                  {comparisonData.ghost_average.avg_hr && (
                    <div>
                      <div className="text-xs text-gray-500 uppercase">Avg HR</div>
                      <div className="text-lg font-bold text-white">
                        {Math.round(comparisonData.ghost_average.avg_hr)} bpm
                      </div>
                    </div>
                  )}
                  {comparisonData.ghost_average.avg_max_hr && (
                    <div>
                      <div className="text-xs text-gray-500 uppercase">Avg Max HR</div>
                      <div className="text-lg font-bold text-white">
                        {Math.round(comparisonData.ghost_average.avg_max_hr)} bpm
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* Actions */}
          <div className="flex justify-center gap-4">
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
