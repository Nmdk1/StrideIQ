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

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAutoCompareSimilar } from '@/lib/hooks/queries/contextual-compare';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useUnits } from '@/lib/context/UnitsContext';
import { UnitToggle } from '@/components/ui/UnitToggle';
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
  MetricHistoryResult,
} from '@/lib/api/services/contextual-compare';
import { getMetricHistory } from '@/lib/api/services/contextual-compare';

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
    bg: 'bg-gradient-to-br from-slate-800/40 to-slate-900/30',
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
            <p className="text-sm text-slate-400 mt-1">
              {new Date(target_run.date).toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-400">Compared to</div>
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
            <div className="text-sm text-slate-400 text-center">out of 100</div>
          </div>
          
          {/* Rating badge */}
          <div className="flex-1">
            <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${style.bg} border ${style.border}`}>
              <span className="text-2xl">{style.icon}</span>
              <span className={`text-lg font-semibold ${style.text}`}>{style.label}</span>
            </div>
            
            {/* Percentile */}
            <div className="mt-3 text-sm text-slate-300">
              Better than <span className="font-bold text-white">{performance_score.percentile.toFixed(0)}%</span> of your similar runs
            </div>
          </div>
        </div>
        
        {/* Headline */}
        <h1 className="text-2xl font-bold text-white mb-3">{headline}</h1>
        
        {/* Key insight (the "BUT" explanation) */}
        <p className="text-lg text-slate-300 leading-relaxed">{key_insight}</p>
        
        {/* Quick stats */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/10">
          <div>
            <div className="text-sm text-slate-400">Pace vs Baseline</div>
            <div className={`text-xl font-bold ${performance_score.pace_vs_baseline > 0 ? 'text-emerald-400' : performance_score.pace_vs_baseline < 0 ? 'text-rose-400' : 'text-white'}`}>
              {performance_score.pace_vs_baseline > 0 ? '+' : ''}{performance_score.pace_vs_baseline.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-sm text-slate-400">Efficiency vs Baseline</div>
            <div className={`text-xl font-bold ${performance_score.efficiency_vs_baseline > 0 ? 'text-emerald-400' : performance_score.efficiency_vs_baseline < 0 ? 'text-rose-400' : 'text-white'}`}>
              {performance_score.efficiency_vs_baseline > 0 ? '+' : ''}{performance_score.efficiency_vs_baseline.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-sm text-slate-400">Age-Graded</div>
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
        <div className="text-xs text-slate-400">This run</div>
        <div className="text-lg font-bold">{factor.this_run_value}</div>
      </div>
      <div className="text-2xl text-slate-500">→</div>
      <div>
        <div className="text-xs text-slate-400">Average</div>
        <div className="text-lg font-medium text-slate-300">{factor.baseline_value}</div>
      </div>
        <div className={`ml-auto px-3 py-1 rounded-full text-sm font-bold ${
          factor.impact === 'positive' ? 'bg-emerald-900/50 text-emerald-300' :
          factor.impact === 'negative' ? 'bg-rose-900/50 text-rose-300' :
          'bg-slate-700/50 text-slate-300'
        }`}>
          {factor.difference}
        </div>
      </div>
      
      <p className="text-sm text-slate-400 leading-relaxed">{factor.explanation}</p>
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
  const { units, distanceUnitShort } = useUnits();
  
  // Conversion factor: pace per km to pace per mile
  const KM_TO_MILES = 0.621371;
  
  const chartData = useMemo(() => {
    if (!target_run.splits || target_run.splits.length === 0) return null;
    
    return target_run.splits.map((split, idx) => {
      const ghostSplit = ghost_average.avg_splits[idx];
      // Convert pace from seconds/km to minutes, adjusting for unit preference
      const paceMultiplier = units === 'imperial' ? (1 / KM_TO_MILES) : 1;
      return {
        split: idx + 1,
        yourPace: split.pace_per_km ? (split.pace_per_km * paceMultiplier) / 60 : null,
        ghostPace: ghostSplit?.avg_pace_per_km ? (ghostSplit.avg_pace_per_km * paceMultiplier) / 60 : null,
        yourHR: split.avg_hr,
        ghostHR: ghostSplit?.avg_hr,
      };
    });
  }, [target_run.splits, ghost_average.avg_splits, units]);
  
  if (!chartData) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-500 bg-slate-800/50 rounded-xl">
        <p>No splits data available</p>
      </div>
    );
  }
  
  // Format pace for display (already in the correct unit)
  const formatPaceValue = (value: number | null): string => {
    if (!value || value <= 0) return '-';
    const minutes = Math.floor(value);
    const seconds = Math.round((value - minutes) * 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
  
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
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
            label={{ value: `${distanceUnitShort === 'mi' ? 'Mile' : 'Km'} Split`, position: 'bottom', fill: '#9CA3AF', offset: -5 }}
          />
          <YAxis 
            stroke="#9CA3AF"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            tickFormatter={(v) => formatPaceValue(v)}
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
              if (name === 'ghostPace') return [formatPaceValue(value), 'Ghost Avg'];
              if (name === 'yourPace') return [formatPaceValue(value), 'Your Pace'];
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
      
      <p className="text-sm text-slate-400 mt-4 text-center">
        The ghost (purple area) represents the average of your {ghost_average.num_runs_averaged} most similar runs
      </p>
    </div>
  );
}

// =============================================================================
// SIMILAR RUNS LIST
// =============================================================================

function SimilarRunCard({ run, rank }: { run: SimilarRun; rank: number }) {
  const { formatDistance, formatPace } = useUnits();
  
  // Format pace from seconds per km (pace_per_km is in seconds)
  // formatPace already includes the unit suffix (/mi or /km)
  const formattedPace = run.pace_per_km 
    ? formatPace(run.pace_per_km)
    : run.pace_formatted || '—';
  
  // formatDistance expects meters, so convert km to meters
  // formatDistance already includes the unit suffix (mi or km)
  const formattedDistance = run.distance_m 
    ? formatDistance(run.distance_m)
    : run.distance_km 
      ? formatDistance(run.distance_km * 1000)
      : '—';
  
  return (
    <Link href={`/activities/${run.id}`}>
      <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4 hover:bg-slate-700/50 hover:border-slate-600 transition-all cursor-pointer">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-sm font-bold text-slate-300">
              {rank}
            </div>
            <div>
              <div className="font-medium text-white truncate max-w-[200px]">{run.name}</div>
              <div className="text-xs text-slate-400">
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
            <span className="text-slate-400">Pace:</span>{' '}
            <span className="text-white">{formattedPace}</span>
          </div>
          <div>
            <span className="text-slate-400">HR:</span>{' '}
            <span className="text-white">{run.avg_hr || '—'}</span>
          </div>
          <div>
            <span className="text-slate-400">Dist:</span>{' '}
            <span className="text-white">{formattedDistance}</span>
          </div>
          {run.temperature_f && (
            <div>
              <span className="text-slate-400">Temp:</span>{' '}
              <span className="text-white">{run.temperature_f}°F</span>
            </div>
          )}
        </div>
        
        {/* Similarity breakdown mini-bars */}
        <div className="mt-3 flex gap-1">
          {Object.entries(run.similarity_breakdown).map(([key, value]) => (
            <div key={key} className="flex-1" title={`${key}: ${(value * 100).toFixed(0)}%`}>
              <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
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

// =============================================================================
// ADVANCED ANALYTICS SECTION
// =============================================================================

function AdvancedAnalyticsSection({ result }: { result: ContextualComparisonResult }) {
  const { formatPace, units } = useUnits();
  const analytics = result.target_run.analytics;
  const ghost = result.ghost_average;
  const [expandedTile, setExpandedTile] = useState<string | null>(null);
  const [metricHistory, setMetricHistory] = useState<MetricHistoryResult | null>(null);
  const [loading, setLoading] = useState(false);

  if (!analytics) {
    return null;
  }

  // Fetch metric history when a tile is expanded
  const handleTileClick = async (tileId: string) => {
    if (expandedTile === tileId) {
      setExpandedTile(null);
      return;
    }
    
    setExpandedTile(tileId);
    
    // Fetch history if not already loaded
    if (!metricHistory) {
      setLoading(true);
      try {
        const history = await getMetricHistory(result.target_run.id);
        setMetricHistory(history);
      } catch (err) {
        console.error('Failed to load metric history:', err);
      } finally {
        setLoading(false);
      }
    }
  };

  // Helper to format efficiency comparison
  const formatEfficiencyDelta = () => {
    if (!result.performance_score.efficiency_vs_baseline) return null;
    const delta = result.performance_score.efficiency_vs_baseline;
    const sign = delta > 0 ? '+' : '';
    return `${sign}${delta.toFixed(1)}%`;
  };
  
  return (
    <div className="mt-8 space-y-6">
      {/* What is Ghost Average - Explanation Box */}
      <div className="bg-gradient-to-r from-indigo-900/30 to-purple-900/20 rounded-xl border border-indigo-700/40 p-5">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-3">
          <span>👻</span> Your &quot;Ghost&quot; Baseline
        </h3>
        <p className="text-slate-300 text-sm leading-relaxed">
          We found <span className="text-indigo-400 font-semibold">{ghost.num_runs_averaged} similar runs</span> in 
          your history—runs with comparable distance, intensity, and conditions. The <span className="text-indigo-400 font-semibold">&quot;Ghost&quot;</span> is 
          the average of those runs. It represents <span className="italic">your typical performance</span> for this type of effort, 
          so you can see if today you ran better, worse, or the same as usual.
        </p>
        {ghost.avg_pace_formatted && ghost.avg_hr && (
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <div className="bg-slate-800/50 rounded px-3 py-1.5">
              <span className="text-slate-400">Ghost Pace:</span>{' '}
              <span className="text-white font-medium">{ghost.avg_pace_formatted}</span>
            </div>
            <div className="bg-slate-800/50 rounded px-3 py-1.5">
              <span className="text-slate-400">Ghost HR:</span>{' '}
              <span className="text-white font-medium">{Math.round(ghost.avg_hr)} bpm</span>
            </div>
            {ghost.avg_efficiency && (
              <div className="bg-slate-800/50 rounded px-3 py-1.5">
                <span className="text-slate-400">Ghost Efficiency:</span>{' '}
                <span className="text-white font-medium">{ghost.avg_efficiency.toFixed(3)}</span>
              </div>
            )}
          </div>
        )}
      </div>
      
      <h3 className="text-lg font-semibold text-white flex items-center gap-2">
        <span>📊</span> How Your Body Performed
      </h3>
      
      {/* Key Metrics Grid - with clear explanations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Efficiency - Expandable */}
        <div 
          className={`bg-slate-800/50 rounded-lg border transition-all cursor-pointer hover:border-purple-500/50 ${expandedTile === 'efficiency' ? 'border-purple-500/70 col-span-1 md:col-span-2' : 'border-slate-700/50'} p-4`}
          onClick={() => handleTileClick('efficiency')}
        >
          <div className="flex justify-between items-start mb-2">
            <div className="text-sm font-medium text-white flex items-center gap-2">
              Running Efficiency
              <span className="text-xs text-slate-500">{expandedTile === 'efficiency' ? '▼' : '▶'}</span>
            </div>
            <div className={`text-lg font-bold ${result.performance_score.efficiency_vs_baseline > 0 ? 'text-emerald-400' : result.performance_score.efficiency_vs_baseline < 0 ? 'text-rose-400' : 'text-white'}`}>
              {formatEfficiencyDelta() || '—'}
            </div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            <span className="text-slate-300">Speed produced per heartbeat.</span> Higher = you&apos;re getting more speed for less cardiac effort.
          </p>
          
          {/* Expanded Content */}
          {expandedTile === 'efficiency' && (
            <div className="mt-4 pt-4 border-t border-slate-700/50" onClick={(e) => e.stopPropagation()}>
              {loading ? (
                <div className="text-center py-4 text-slate-400">Loading history...</div>
              ) : metricHistory ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Your Average</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.statistics.efficiency.avg ? `${metricHistory.statistics.efficiency.avg.toFixed(1)}` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Today</div>
                      <div className={`text-sm font-medium ${result.performance_score.efficiency_vs_baseline > 0 ? 'text-emerald-400' : result.performance_score.efficiency_vs_baseline < 0 ? 'text-rose-400' : 'text-white'}`}>
                        {metricHistory.current.efficiency ? metricHistory.current.efficiency.toFixed(1) : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Best Ever</div>
                      <div className="text-sm font-medium text-purple-400">
                        {metricHistory.statistics.efficiency.best ? `${metricHistory.statistics.efficiency.best.toFixed(1)}` : '—'}
                      </div>
                    </div>
                  </div>
                  {metricHistory.insights.efficiency && (
                    <div className="bg-slate-900/50 rounded p-3 text-xs text-slate-300 leading-relaxed">
                      💡 {metricHistory.insights.efficiency}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-4 text-slate-400">No historical data yet</div>
              )}
            </div>
          )}
        </div>
        
        {/* Cardiac Drift - Expandable */}
        <div 
          className={`bg-slate-800/50 rounded-lg border transition-all cursor-pointer hover:border-purple-500/50 ${expandedTile === 'cardiac' ? 'border-purple-500/70 col-span-1 md:col-span-2' : 'border-slate-700/50'} p-4`}
          onClick={() => handleTileClick('cardiac')}
        >
          <div className="flex justify-between items-start mb-2">
            <div className="text-sm font-medium text-white flex items-center gap-2">
              Cardiac Drift
              <span className="text-xs text-slate-500">{expandedTile === 'cardiac' ? '▼' : '▶'}</span>
            </div>
            <div className={`text-lg font-bold ${analytics.cardiac_drift_pct !== null && analytics.cardiac_drift_pct > 5 ? 'text-amber-400' : analytics.cardiac_drift_pct !== null && analytics.cardiac_drift_pct < 3 ? 'text-emerald-400' : 'text-white'}`}>
              {analytics.cardiac_drift_pct !== null ? `${analytics.cardiac_drift_pct > 0 ? '+' : ''}${analytics.cardiac_drift_pct}%` : '—'}
            </div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            <span className="text-slate-300">How much your heart rate rose during the run.</span> Even at steady pace, HR naturally drifts up.
          </p>
          
          {expandedTile === 'cardiac' && (
            <div className="mt-4 pt-4 border-t border-slate-700/50" onClick={(e) => e.stopPropagation()}>
              {loading ? (
                <div className="text-center py-4 text-slate-400">Loading history...</div>
              ) : metricHistory ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Your Average</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.statistics.cardiac_drift.avg ? `${metricHistory.statistics.cardiac_drift.avg.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Today</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.current.cardiac_drift !== null ? `${metricHistory.current.cardiac_drift.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Best (Lowest)</div>
                      <div className="text-sm font-medium text-emerald-400">
                        {metricHistory.statistics.cardiac_drift.worst !== null ? `${metricHistory.statistics.cardiac_drift.worst.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                  </div>
                  {metricHistory.insights.cardiac_drift && (
                    <div className="bg-slate-900/50 rounded p-3 text-xs text-slate-300 leading-relaxed">
                      💡 {metricHistory.insights.cardiac_drift}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-4 text-slate-400">No historical data yet</div>
              )}
            </div>
          )}
        </div>
        
        {/* Aerobic Decoupling - Expandable */}
        <div 
          className={`bg-slate-800/50 rounded-lg border transition-all cursor-pointer hover:border-purple-500/50 ${expandedTile === 'decoupling' ? 'border-purple-500/70 col-span-1 md:col-span-2' : 'border-slate-700/50'} p-4`}
          onClick={() => handleTileClick('decoupling')}
        >
          <div className="flex justify-between items-start mb-2">
            <div className="text-sm font-medium text-white flex items-center gap-2">
              Aerobic Decoupling
              <span className="text-xs text-slate-500">{expandedTile === 'decoupling' ? '▼' : '▶'}</span>
            </div>
            <div className={`text-lg font-bold ${analytics.aerobic_decoupling_pct !== null && analytics.aerobic_decoupling_pct > 5 ? 'text-amber-400' : analytics.aerobic_decoupling_pct !== null && analytics.aerobic_decoupling_pct < 3 ? 'text-emerald-400' : 'text-white'}`}>
              {analytics.aerobic_decoupling_pct !== null ? `${analytics.aerobic_decoupling_pct}%` : '—'}
            </div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            <span className="text-slate-300">Did your efficiency hold steady or fall apart?</span> First half vs second half comparison.
          </p>
          
          {expandedTile === 'decoupling' && (
            <div className="mt-4 pt-4 border-t border-slate-700/50" onClick={(e) => e.stopPropagation()}>
              {loading ? (
                <div className="text-center py-4 text-slate-400">Loading history...</div>
              ) : metricHistory ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Your Average</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.statistics.aerobic_decoupling.avg ? `${metricHistory.statistics.aerobic_decoupling.avg.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Today</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.current.aerobic_decoupling !== null ? `${metricHistory.current.aerobic_decoupling.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Best (Lowest)</div>
                      <div className="text-sm font-medium text-emerald-400">
                        {metricHistory.statistics.aerobic_decoupling.worst !== null ? `${metricHistory.statistics.aerobic_decoupling.worst.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                  </div>
                  {metricHistory.insights.aerobic_decoupling && (
                    <div className="bg-slate-900/50 rounded p-3 text-xs text-slate-300 leading-relaxed">
                      💡 {metricHistory.insights.aerobic_decoupling}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-4 text-slate-400">No historical data yet</div>
              )}
            </div>
          )}
        </div>
        
        {/* Pace Consistency - Expandable */}
        <div 
          className={`bg-slate-800/50 rounded-lg border transition-all cursor-pointer hover:border-purple-500/50 ${expandedTile === 'pacing' ? 'border-purple-500/70 col-span-1 md:col-span-2' : 'border-slate-700/50'} p-4`}
          onClick={() => handleTileClick('pacing')}
        >
          <div className="flex justify-between items-start mb-2">
            <div className="text-sm font-medium text-white flex items-center gap-2">
              Pace Consistency
              <span className="text-xs text-slate-500">{expandedTile === 'pacing' ? '▼' : '▶'}</span>
            </div>
            <div className={`text-lg font-bold ${analytics.pace_variability_cv !== null && analytics.pace_variability_cv > 5 ? 'text-amber-400' : analytics.pace_variability_cv !== null && analytics.pace_variability_cv < 3 ? 'text-emerald-400' : 'text-white'}`}>
              {analytics.pace_variability_cv !== null ? `${analytics.pace_variability_cv}%` : '—'}
            </div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            <span className="text-slate-300">How evenly you paced the run.</span> Lower = more consistent.
          </p>
          
          {expandedTile === 'pacing' && (
            <div className="mt-4 pt-4 border-t border-slate-700/50" onClick={(e) => e.stopPropagation()}>
              {loading ? (
                <div className="text-center py-4 text-slate-400">Loading history...</div>
              ) : metricHistory ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Your Average</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.statistics.pace_consistency.avg ? `${metricHistory.statistics.pace_consistency.avg.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Today</div>
                      <div className="text-sm font-medium text-white">
                        {metricHistory.current.pace_consistency !== null ? `${metricHistory.current.pace_consistency.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Best (Most Even)</div>
                      <div className="text-sm font-medium text-emerald-400">
                        {metricHistory.statistics.pace_consistency.worst !== null ? `${metricHistory.statistics.pace_consistency.worst.toFixed(1)}%` : '—'}
                      </div>
                    </div>
                  </div>
                  {metricHistory.insights.pace_consistency && (
                    <div className="bg-slate-900/50 rounded p-3 text-xs text-slate-300 leading-relaxed">
                      💡 {metricHistory.insights.pace_consistency}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-4 text-slate-400">No historical data yet</div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* First Half vs Second Half */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
        <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <span>⚖️</span> First Half vs Second Half
          {analytics.split_type && (
            <span className={`ml-2 px-2 py-0.5 rounded text-xs ${
              analytics.split_type === 'negative' ? 'bg-emerald-900/50 text-emerald-400' :
              analytics.split_type === 'positive' ? 'bg-amber-900/50 text-amber-400' :
              'bg-slate-700 text-slate-300'
            }`}>
              {analytics.split_type === 'negative' ? 'Negative Split 🎯' :
               analytics.split_type === 'positive' ? 'Positive Split' :
               'Even Split'}
            </span>
          )}
        </h4>
        <p className="text-xs text-slate-400 mb-4">
          {analytics.split_type === 'negative' 
            ? 'You finished faster than you started—the hallmark of a well-paced run.'
            : analytics.split_type === 'positive'
            ? 'You slowed down in the second half. This is normal for hard efforts or learning to pace.'
            : 'You maintained consistent pace throughout—good discipline.'}
        </p>
        
        <div className="grid grid-cols-2 gap-6">
          {/* First Half */}
          <div className="text-center bg-slate-900/30 rounded-lg p-4">
            <div className="text-xs text-slate-400 uppercase mb-2">First Half</div>
            <div className="text-xl font-bold text-white">
              {analytics.first_half_pace ? formatPace(analytics.first_half_pace) : '—'}
            </div>
            <div className="text-sm text-slate-400 mt-1">
              {analytics.first_half_hr ? `${Math.round(analytics.first_half_hr)} bpm avg` : '—'}
            </div>
          </div>
          
          {/* Second Half */}
          <div className="text-center bg-slate-900/30 rounded-lg p-4">
            <div className="text-xs text-slate-400 uppercase mb-2">Second Half</div>
            <div className="text-xl font-bold text-white">
              {analytics.second_half_pace ? formatPace(analytics.second_half_pace) : '—'}
            </div>
            <div className="text-sm text-slate-400 mt-1">
              {analytics.second_half_hr ? `${Math.round(analytics.second_half_hr)} bpm avg` : '—'}
            </div>
          </div>
        </div>
        
        {/* Change summary */}
        {analytics.fade_pct !== null && (
          <div className="mt-4 pt-4 border-t border-slate-700/50">
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Pace Change:</span>
              <span className={`font-medium ${
                analytics.fade_pct < -2 ? 'text-emerald-400' :
                analytics.fade_pct > 2 ? 'text-amber-400' :
                'text-slate-300'
              }`}>
                {analytics.fade_pct < 0 
                  ? `${Math.abs(analytics.fade_pct)}% faster in 2nd half`
                  : analytics.fade_pct > 0
                  ? `${analytics.fade_pct}% slower in 2nd half`
                  : 'Identical pace'}
              </span>
            </div>
            {analytics.cardiac_drift_pct !== null && (
              <div className="flex justify-between items-center text-sm mt-2">
                <span className="text-slate-400">HR Change:</span>
                <span className={`font-medium ${
                  analytics.cardiac_drift_pct > 5 ? 'text-amber-400' :
                  analytics.cardiac_drift_pct < 3 ? 'text-emerald-400' :
                  'text-slate-300'
                }`}>
                  {analytics.cardiac_drift_pct > 0 
                    ? `+${analytics.cardiac_drift_pct}% (${Math.round((analytics.second_half_hr || 0) - (analytics.first_half_hr || 0))} bpm higher)`
                    : 'Stable'}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// DETAILED SPLITS TABLE
// =============================================================================

function SplitsTable({ result }: { result: ContextualComparisonResult }) {
  const { formatPace, formatDistance, units, distanceUnitShort } = useUnits();
  const splits = result.target_run.splits;
  const ghostSplits = result.ghost_average.avg_splits;
  
  if (!splits || splits.length === 0) {
    return null;
  }
  
  return (
    <div className="mt-8">
      <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
        <span>📈</span> Every {distanceUnitShort === 'mi' ? 'Mile' : 'Kilometer'}, Analyzed
      </h3>
      <p className="text-sm text-slate-400 mb-4">
        Each split compared to your Ghost average. <span className="text-emerald-400">Green = faster than usual</span>, <span className="text-rose-400">Red = slower than usual</span>.
      </p>
      
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-900/50 text-slate-400 text-xs">
                <th className="px-4 py-3 text-left font-medium">{distanceUnitShort === 'mi' ? 'Mile' : 'Km'}</th>
                <th className="px-4 py-3 text-right font-medium">Pace</th>
                <th className="px-4 py-3 text-right font-medium">
                  <span className="flex items-center justify-end gap-1">
                    vs Ghost
                    <span className="text-indigo-400">👻</span>
                  </span>
                </th>
                <th className="px-4 py-3 text-right font-medium">Avg HR</th>
                <th className="px-4 py-3 text-right font-medium">Peak HR</th>
                <th className="px-4 py-3 text-right font-medium">
                  <span title="Steps per minute">Cadence</span>
                </th>
                {splits.some(s => s.gap_per_mile) && (
                  <th className="px-4 py-3 text-right font-medium">
                    <span title="Grade Adjusted Pace - what your pace would be on flat ground">GAP</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/30">
              {splits.map((split, idx) => {
                const ghostSplit = ghostSplits[idx];
                const paceDiff = split.pace_per_km && ghostSplit?.avg_pace_per_km
                  ? ((split.pace_per_km - ghostSplit.avg_pace_per_km) / ghostSplit.avg_pace_per_km) * 100
                  : null;
                
                return (
                  <tr key={split.split_number} className="hover:bg-slate-700/20">
                    <td className="px-4 py-3 font-medium text-white">{split.split_number}</td>
                    <td className="px-4 py-3 text-right text-white font-mono">
                      {split.pace_per_km ? formatPace(split.pace_per_km) : '—'}
                    </td>
                    <td className={`px-4 py-3 text-right font-mono font-medium ${
                      paceDiff !== null && paceDiff < -1 ? 'text-emerald-400' :
                      paceDiff !== null && paceDiff > 1 ? 'text-rose-400' :
                      'text-slate-400'
                    }`}>
                      {paceDiff !== null 
                        ? `${paceDiff < 0 ? '' : '+'}${paceDiff.toFixed(1)}%` 
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {split.avg_hr ? `${Math.round(split.avg_hr)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400">
                      {split.max_hr ? `${Math.round(split.max_hr)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400">
                      {split.cadence ? `${Math.round(split.cadence)} spm` : '—'}
                    </td>
                    {splits.some(s => s.gap_per_mile) && (
                      <td className="px-4 py-3 text-right text-slate-400 font-mono">
                        {split.gap_per_mile ? formatPace(split.gap_per_mile * 0.621371) : '—'}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        
        {/* Legend */}
        <div className="px-4 py-3 bg-slate-900/30 border-t border-slate-700/30 text-xs text-slate-500">
          <span className="font-medium">Legend:</span>{' '}
          HR = Heart Rate (bpm) · 
          Cadence = Steps per minute · 
          {splits.some(s => s.gap_per_mile) && 'GAP = Grade Adjusted Pace (flat equivalent) · '}
          Ghost = Your average from {result.ghost_average.num_runs_averaged} similar runs
        </div>
      </div>
    </div>
  );
}

function SimilarRunsSection({ runs }: { runs: SimilarRun[] }) {
  if (!runs || runs.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400">
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
        <p className="text-sm text-slate-400 mt-4 text-center">
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
      <div className="min-h-screen bg-slate-900 text-slate-100">
        {/* Background accents */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-900/50 via-transparent to-black/50" />
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
        </div>
        
        <div className="relative z-10 max-w-5xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <Link 
                href={activityId ? `/activities/${activityId}` : '/activities'}
                className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors"
              >
                ← Back
              </Link>
              <div>
                <h1 className="text-2xl font-bold">Context Comparison</h1>
                <p className="text-slate-400">How does this run compare to similar efforts?</p>
              </div>
            </div>
            <UnitToggle />
          </div>
          
          {/* Loading */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-20">
              <LoadingSpinner size="lg" />
              <p className="mt-4 text-slate-400">Finding similar runs...</p>
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
                className="inline-block mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm"
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
              
              {/* Advanced Analytics */}
              <AdvancedAnalyticsSection result={result} />
              
              {/* Context Factors */}
              <ContextFactorsSection factors={result.context_factors} />
              
              {/* Ghost Overlay Chart */}
              <div className="mt-8">
                <GhostOverlayChart result={result} />
              </div>
              
              {/* Detailed Splits Table */}
              <SplitsTable result={result} />
              
              {/* Similar Runs */}
              <SimilarRunsSection runs={result.similar_runs} />
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
