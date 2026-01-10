'use client';

/**
 * Contextual Comparison Page
 * 
 * The differentiator: "Context vs Context" comparison.
 * Shows how a run performs against similar runs with full context.
 * 
 * Design Philosophy:
 * - Performance score is the hero
 * - Ghost average provides the baseline
 * - Context factors explain the "why"
 * - Beautiful, distinctive aesthetic
 */

import React, { useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAutoCompareSimilar } from '@/lib/hooks/queries/contextual-compare';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from 'recharts';
import type { 
  ContextualComparisonResult, 
  ContextFactor, 
  SimilarRun,
  GhostAverage,
} from '@/lib/api/services/contextual-compare';

// =============================================================================
// DESIGN TOKENS
// =============================================================================

const RATING_STYLES = {
  exceptional: {
    bg: 'bg-gradient-to-br from-amber-900/40 to-orange-900/30',
    border: 'border-amber-500/50',
    text: 'text-amber-400',
    glow: 'shadow-amber-500/20',
    icon: '🏆',
    label: 'Exceptional',
  },
  strong: {
    bg: 'bg-gradient-to-br from-emerald-900/40 to-green-900/30',
    border: 'border-emerald-500/50',
    text: 'text-emerald-400',
    glow: 'shadow-emerald-500/20',
    icon: '💪',
    label: 'Strong',
  },
  solid: {
    bg: 'bg-gradient-to-br from-blue-900/40 to-cyan-900/30',
    border: 'border-blue-500/50',
    text: 'text-blue-400',
    glow: 'shadow-blue-500/20',
    icon: '✅',
    label: 'Solid',
  },
  average: {
    bg: 'bg-gradient-to-br from-slate-800/40 to-gray-900/30',
    border: 'border-slate-500/50',
    text: 'text-slate-300',
    glow: 'shadow-slate-500/10',
    icon: '📊',
    label: 'On Par',
  },
  below: {
    bg: 'bg-gradient-to-br from-orange-900/30 to-red-900/20',
    border: 'border-orange-500/40',
    text: 'text-orange-400',
    glow: 'shadow-orange-500/10',
    icon: '📉',
    label: 'Below Average',
  },
  struggling: {
    bg: 'bg-gradient-to-br from-red-900/30 to-rose-900/20',
    border: 'border-red-500/40',
    text: 'text-red-400',
    glow: 'shadow-red-500/10',
    icon: '⚠️',
    label: 'Tough Day',
  },
};

const IMPACT_COLORS = {
  positive: 'text-emerald-400 bg-emerald-900/30 border-emerald-700/50',
  negative: 'text-rose-400 bg-rose-900/30 border-rose-700/50',
  neutral: 'text-slate-300 bg-slate-800/30 border-slate-700/50',
};

// =============================================================================
// PERFORMANCE SCORE HERO
// =============================================================================

function PerformanceScoreHero({ 
  result 
}: { 
  result: ContextualComparisonResult 
}) {
  const { performance_score, headline, key_insight, target_run } = result;
  const style = RATING_STYLES[performance_score.rating] || RATING_STYLES.average;
  
  // Calculate score arc (for circular progress)
  const scoreAngle = (performance_score.score / 100) * 180;
  
  return (
    <div className={`relative overflow-hidden rounded-2xl border-2 ${style.border} ${style.bg} p-8 ${style.glow} shadow-xl`}>
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle at 20% 80%, rgba(255,255,255,0.1) 0%, transparent 50%),
                           radial-gradient(circle at 80% 20%, rgba(255,255,255,0.1) 0%, transparent 50%)`,
        }} />
      </div>
      
      <div className="relative z-10">
        {/* Top row: Activity info */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link href={`/activities/${target_run.id}`} className="hover:opacity-80 transition-opacity">
              <h2 className="text-xl font-semibold text-white">{target_run.name}</h2>
            </Link>
            <p className="text-sm text-gray-400 mt-1">
              {new Date(target_run.date).toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Compared to</div>
            <div className="text-lg font-medium text-white">
              {result.ghost_average.num_runs_averaged} similar runs
            </div>
          </div>
        </div>
        
        {/* Score display */}
        <div className="flex items-center gap-8 mb-6">
          {/* Large score */}
          <div className="relative">
            <div className={`text-7xl font-black ${style.text} tracking-tight`}>
              {performance_score.score.toFixed(0)}
            </div>
            <div className="text-sm text-gray-400 text-center">out of 100</div>
          </div>
          
          {/* Rating badge */}
          <div className="flex-1">
            <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${style.bg} border ${style.border}`}>
              <span className="text-2xl">{style.icon}</span>
              <span className={`text-lg font-semibold ${style.text}`}>{style.label}</span>
            </div>
            
            {/* Percentile */}
            <div className="mt-3 text-sm text-gray-300">
              Better than <span className="font-bold text-white">{performance_score.percentile.toFixed(0)}%</span> of your similar runs
            </div>
          </div>
        </div>
        
        {/* Headline */}
        <h1 className="text-2xl font-bold text-white mb-3">{headline}</h1>
        
        {/* Key insight (the "BUT" explanation) */}
        <p className="text-lg text-gray-300 leading-relaxed">{key_insight}</p>
        
        {/* Quick stats */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/10">
          <div>
            <div className="text-sm text-gray-400">Pace vs Baseline</div>
            <div className={`text-xl font-bold ${performance_score.pace_vs_baseline > 0 ? 'text-emerald-400' : performance_score.pace_vs_baseline < 0 ? 'text-rose-400' : 'text-white'}`}>
              {performance_score.pace_vs_baseline > 0 ? '+' : ''}{performance_score.pace_vs_baseline.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Efficiency vs Baseline</div>
            <div className={`text-xl font-bold ${performance_score.efficiency_vs_baseline > 0 ? 'text-emerald-400' : performance_score.efficiency_vs_baseline < 0 ? 'text-rose-400' : 'text-white'}`}>
              {performance_score.efficiency_vs_baseline > 0 ? '+' : ''}{performance_score.efficiency_vs_baseline.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Age-Graded</div>
            <div className="text-xl font-bold text-white">
              {performance_score.age_graded_performance 
                ? `${performance_score.age_graded_performance.toFixed(1)}%` 
                : '—'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// CONTEXT FACTORS
// =============================================================================

function ContextFactorCard({ factor }: { factor: ContextFactor }) {
  return (
    <div className={`rounded-xl border p-4 ${IMPACT_COLORS[factor.impact]}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{factor.icon}</span>
        <span className="font-semibold">{factor.name}</span>
      </div>
      
      <div className="flex items-center gap-4 mb-3">
        <div>
          <div className="text-xs text-gray-400">This run</div>
          <div className="text-lg font-bold">{factor.this_run_value}</div>
        </div>
        <div className="text-2xl text-gray-500">→</div>
        <div>
          <div className="text-xs text-gray-400">Average</div>
          <div className="text-lg font-medium text-gray-300">{factor.baseline_value}</div>
        </div>
        <div className={`ml-auto px-3 py-1 rounded-full text-sm font-bold ${
          factor.impact === 'positive' ? 'bg-emerald-900/50 text-emerald-300' :
          factor.impact === 'negative' ? 'bg-rose-900/50 text-rose-300' :
          'bg-slate-700/50 text-slate-300'
        }`}>
          {factor.difference}
        </div>
      </div>
      
      <p className="text-sm text-gray-400 leading-relaxed">{factor.explanation}</p>
    </div>
  );
}

function ContextFactorsSection({ factors }: { factors: ContextFactor[] }) {
  if (!factors || factors.length === 0) {
    return null;
  }
  
  return (
    <div className="mt-8">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <span>🔍</span> What Affected Your Performance
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {factors.map((factor, idx) => (
          <ContextFactorCard key={idx} factor={factor} />
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// GHOST OVERLAY CHART
// =============================================================================

function GhostOverlayChart({ 
  result 
}: { 
  result: ContextualComparisonResult 
}) {
  const { target_run, ghost_average } = result;
  
  const chartData = useMemo(() => {
    if (!target_run.splits || target_run.splits.length === 0) return null;
    
    return target_run.splits.map((split, idx) => {
      const ghostSplit = ghost_average.avg_splits[idx];
      return {
        split: idx + 1,
        yourPace: split.pace_per_km ? split.pace_per_km / 60 : null,
        ghostPace: ghostSplit?.avg_pace_per_km ? ghostSplit.avg_pace_per_km / 60 : null,
        yourHR: split.avg_hr,
        ghostHR: ghostSplit?.avg_hr,
      };
    });
  }, [target_run.splits, ghost_average.avg_splits]);
  
  if (!chartData) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 bg-gray-800/50 rounded-xl">
        <p>No splits data available</p>
      </div>
    );
  }
  
  // Format pace for display
  const formatPace = (value: number | null): string => {
    if (!value || value <= 0) return '-';
    const minutes = Math.floor(value);
    const seconds = Math.round((value - minutes) * 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
  
  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/50 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <span>👻</span> Your Run vs Ghost Average
      </h3>
      
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
          <defs>
            <linearGradient id="ghostArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="split" 
            stroke="#9CA3AF"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            label={{ value: 'Mile/Km Split', position: 'bottom', fill: '#9CA3AF', offset: -5 }}
          />
          <YAxis 
            stroke="#9CA3AF"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            tickFormatter={(v) => formatPace(v)}
            reversed // Lower pace is better
            domain={['auto', 'auto']}
            label={{ value: 'Pace', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
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
            if (name === 'ghostPace') return [formatPace(value), 'Ghost Avg'];
            if (name === 'yourPace') return [formatPace(value), 'Your Pace'];
            return [value, name || ''];
          }}
        />
          <Legend 
            formatter={(value) => {
              if (value === 'ghostPace') return 'Ghost Average';
              if (value === 'yourPace') return 'Your Run';
              return value;
            }}
          />
          
          {/* Ghost average area */}
          <Area
            type="monotone"
            dataKey="ghostPace"
            stroke="#6366f1"
            strokeWidth={2}
            strokeDasharray="5 5"
            fill="url(#ghostArea)"
            connectNulls
          />
          
          {/* Your run line */}
          <Line
            type="monotone"
            dataKey="yourPace"
            stroke="#f97316"
            strokeWidth={3}
            dot={{ fill: '#f97316', strokeWidth: 2, r: 4 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
      
      <p className="text-sm text-gray-400 mt-4 text-center">
        The ghost (purple area) represents the average of your {ghost_average.num_runs_averaged} most similar runs
      </p>
    </div>
  );
}

// =============================================================================
// SIMILAR RUNS LIST
// =============================================================================

function SimilarRunCard({ run, rank }: { run: SimilarRun; rank: number }) {
  return (
    <Link href={`/activities/${run.id}`}>
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 p-4 hover:bg-gray-700/50 hover:border-gray-600 transition-all cursor-pointer">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm font-bold text-gray-300">
              {rank}
            </div>
            <div>
              <div className="font-medium text-white truncate max-w-[200px]">{run.name}</div>
              <div className="text-xs text-gray-400">
                {new Date(run.date).toLocaleDateString('en-US', { 
                  month: 'short', 
                  day: 'numeric',
                  year: 'numeric',
                })}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-semibold text-amber-400">
              {(run.similarity_score * 100).toFixed(0)}% match
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-4 text-sm">
          <div>
            <span className="text-gray-400">Pace:</span>{' '}
            <span className="text-white">{run.pace_formatted || '—'}</span>
          </div>
          <div>
            <span className="text-gray-400">HR:</span>{' '}
            <span className="text-white">{run.avg_hr || '—'}</span>
          </div>
          <div>
            <span className="text-gray-400">Dist:</span>{' '}
            <span className="text-white">{run.distance_km.toFixed(1)} km</span>
          </div>
          {run.temperature_f && (
            <div>
              <span className="text-gray-400">Temp:</span>{' '}
              <span className="text-white">{run.temperature_f}°F</span>
            </div>
          )}
        </div>
        
        {/* Similarity breakdown mini-bars */}
        <div className="mt-3 flex gap-1">
          {Object.entries(run.similarity_breakdown).map(([key, value]) => (
            <div key={key} className="flex-1" title={`${key}: ${(value * 100).toFixed(0)}%`}>
              <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-amber-500/70 rounded-full"
                  style={{ width: `${value * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </Link>
  );
}

function SimilarRunsSection({ runs }: { runs: SimilarRun[] }) {
  if (!runs || runs.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No similar runs found. Keep training to build your comparison base!
      </div>
    );
  }
  
  return (
    <div className="mt-8">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <span>🏃</span> Similar Runs Used for Comparison
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {runs.slice(0, 6).map((run, idx) => (
          <SimilarRunCard key={run.id} run={run} rank={idx + 1} />
        ))}
      </div>
      {runs.length > 6 && (
        <p className="text-sm text-gray-400 mt-4 text-center">
          + {runs.length - 6} more similar runs
        </p>
      )}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function ContextualComparisonPage() {
  const params = useParams();
  const activityId = params?.activityId as string;
  
  const { data: result, isLoading, error } = useAutoCompareSimilar(activityId || null);
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-900 to-gray-950 text-gray-100">
        {/* Background accents */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
        </div>
        
        <div className="relative z-10 max-w-5xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <Link 
              href={activityId ? `/activities/${activityId}` : '/activities'}
              className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
            >
              ← Back
            </Link>
            <div>
              <h1 className="text-2xl font-bold">Context Comparison</h1>
              <p className="text-gray-400">How does this run compare to similar efforts?</p>
            </div>
          </div>
          
          {/* Loading */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-20">
              <LoadingSpinner size="lg" />
              <p className="mt-4 text-gray-400">Finding similar runs...</p>
            </div>
          )}
          
          {/* Error */}
          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-6 text-center">
              <p className="text-red-400">
                Unable to find similar runs. You may need more training history for comparison.
              </p>
              <Link
                href="/activities"
                className="inline-block mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
              >
                Back to Activities
              </Link>
            </div>
          )}
          
          {/* Results */}
          {result && (
            <>
              {/* Performance Score Hero */}
              <PerformanceScoreHero result={result} />
              
              {/* Context Factors */}
              <ContextFactorsSection factors={result.context_factors} />
              
              {/* Ghost Overlay Chart */}
              <div className="mt-8">
                <GhostOverlayChart result={result} />
              </div>
              
              {/* Similar Runs */}
              <SimilarRunsSection runs={result.similar_runs} />
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
