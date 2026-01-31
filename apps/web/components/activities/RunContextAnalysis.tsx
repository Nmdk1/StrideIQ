'use client';

/**
 * Run Context Analysis Component
 * 
 * Displays the comprehensive analysis of a run including:
 * - Input snapshot (what state you were in before the run)
 * - Historical context (how this compares to your history)
 * - Trend analysis (are you improving or declining?)
 * - Outlier/red flag detection
 * - Root cause hypotheses when trends are detected
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { API_CONFIG } from '@/lib/api/config';

interface RunAnalysisData {
  activity_id: string;
  athlete_id: string;
  analysis_timestamp: string;
  inputs: {
    sleep_last_night: number | null;
    sleep_3_day_avg: number | null;
    sleep_7_day_avg: number | null;
    stress_today: number | null;
    stress_3_day_avg: number | null;
    soreness_today: number | null;
    soreness_3_day_avg: number | null;
    hrv_today: number | null;
    hrv_7_day_avg: number | null;
    resting_hr_today: number | null;
    resting_hr_7_day_avg: number | null;
    days_since_last_run: number | null;
    runs_this_week: number | null;
    volume_this_week_km: number | null;
  };
  context: {
    workout_type: string;
    confidence: number;
    efficiency_score: number | null;
    similar_workouts_count: number;
    percentile_vs_similar: number | null;
    trend_vs_similar: string | null;
    context_this_week: {
      runs_so_far: number;
      volume_km: number;
      avg_efficiency: number | null;
    } | null;
    context_this_month: {
      runs_so_far: number;
      volume_km: number;
      avg_efficiency: number | null;
    } | null;
    context_this_year: {
      runs_so_far: number;
      volume_km: number;
      avg_efficiency: number | null;
    } | null;
  };
  efficiency_trend: {
    metric: string;
    direction: string;
    magnitude: number | null;
    confidence: number;
    data_points: number;
    period_days: number;
    is_significant: boolean;
  };
  volume_trend: {
    metric: string;
    direction: string;
    magnitude: number | null;
    confidence: number;
    data_points: number;
    period_days: number;
    is_significant: boolean;
  };
  is_outlier: boolean;
  outlier_reason: string | null;
  is_red_flag: boolean;
  red_flag_reason: string | null;
  root_cause_hypotheses: Array<{
    factor: string;
    correlation_strength: number;
    direction: string;
    confidence: number;
    explanation: string;
  }>;
  insights: string[];
}

interface RunContextAnalysisProps {
  activityId: string;
}

export default function RunContextAnalysis({ activityId }: RunContextAnalysisProps) {
  const { token } = useAuth();
  const { formatDistance, distanceUnitShort } = useUnits();
  
  const { data: analysis, isLoading, error } = useQuery<RunAnalysisData>({
    queryKey: ['run-analysis', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/run-analysis/${activityId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (!res.ok) throw new Error('Failed to fetch analysis');
      return res.json();
    },
    enabled: !!token && !!activityId,
    staleTime: 60000, // 1 minute
  });

  if (isLoading) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-700 rounded w-1/3"></div>
          <div className="h-4 bg-slate-700 rounded w-full"></div>
          <div className="h-4 bg-slate-700 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-6 text-slate-400">
        Analysis unavailable for this run.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Insights Header */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-lg p-6 border border-slate-700">
        <h3 className="text-xl font-bold text-white mb-4">Run Analysis</h3>
        
        {/* Workout Classification */}
        {/* Only show specific workout type if confidence >= 65%, otherwise show generic "Run" */}
        <div className="flex items-center gap-3 mb-4">
          {analysis.context.confidence >= 0.65 ? (
            <>
              <span className="px-3 py-1 bg-orange-600/20 text-orange-400 rounded-full text-sm font-medium capitalize">
                {analysis.context.workout_type.replace('_', ' ')}
              </span>
              <span className="text-slate-500 text-sm">
                {Math.round(analysis.context.confidence * 100)}% confidence
              </span>
            </>
          ) : (
            <span className="px-3 py-1 bg-slate-700/50 text-slate-300 rounded-full text-sm font-medium">
              Run
            </span>
          )}
        </div>

        {/* Key Insights */}
        {analysis.insights.length > 0 && (
          <div className="space-y-2">
            {analysis.insights.map((insight, i) => (
              <p key={i} className="text-slate-300 text-sm flex items-start gap-2">
                <span className="text-orange-400">→</span>
                {insight}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Flags Row */}
      {(analysis.is_outlier || analysis.is_red_flag) && (
        <div className="flex gap-4">
          {analysis.is_outlier && (
            <div className="flex-1 bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4">
              <div className="flex items-center gap-2 text-yellow-400 mb-1">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="font-medium">Outlier</span>
              </div>
              <p className="text-slate-300 text-sm">{analysis.outlier_reason}</p>
            </div>
          )}
          {analysis.is_red_flag && (
            <div className="flex-1 bg-red-900/20 border border-red-700/50 rounded-lg p-4">
              <div className="flex items-center gap-2 text-red-400 mb-1">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="font-medium">Attention</span>
              </div>
              <p className="text-slate-300 text-sm">{analysis.red_flag_reason}</p>
            </div>
          )}
        </div>
      )}

      {/* Context Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Comparison to Similar */}
        <div className="bg-slate-800/50 rounded-lg p-4">
          <h4 className="text-slate-400 text-sm mb-2">vs. Similar Runs (90 days)</h4>
          {analysis.context.percentile_vs_similar !== null ? (
            <>
              <p className="text-2xl font-bold text-white">
                {Math.round(analysis.context.percentile_vs_similar) >= 50 ? (
                  <>
                    Better than <span className="text-emerald-400">{Math.round(analysis.context.percentile_vs_similar)}%</span>
                  </>
                ) : (
                  <>
                    <span className="text-amber-400">{Math.round(analysis.context.percentile_vs_similar)}th</span>
                    <span className="text-base font-normal text-slate-400 ml-1">percentile</span>
                  </>
                )}
              </p>
              <p className="text-slate-500 text-sm mt-1">
                Out of {analysis.context.similar_workouts_count} similar {analysis.context.workout_type.replace('_', ' ')} runs
              </p>
            </>
          ) : (
            <p className="text-slate-500">Not enough similar runs yet</p>
          )}
        </div>

        {/* This Week Context */}
        {analysis.context.context_this_week && (
          <div className="bg-slate-800/50 rounded-lg p-4">
            <h4 className="text-slate-400 text-sm mb-2">This Week</h4>
            <p className="text-2xl font-bold text-white">
              {analysis.context.context_this_week.runs_so_far}
              <span className="text-base font-normal text-slate-400 ml-1">runs</span>
            </p>
            <p className="text-slate-500 text-sm mt-1">
              {formatDistance(analysis.context.context_this_week.volume_km * 1000, 1)} total
            </p>
          </div>
        )}

        {/* This Month Context */}
        {analysis.context.context_this_month && (
          <div className="bg-slate-800/50 rounded-lg p-4">
            <h4 className="text-slate-400 text-sm mb-2">This Month</h4>
            <p className="text-2xl font-bold text-white">
              {analysis.context.context_this_month.runs_so_far}
              <span className="text-base font-normal text-slate-400 ml-1">runs</span>
            </p>
            <p className="text-slate-500 text-sm mt-1">
              {formatDistance(analysis.context.context_this_month.volume_km * 1000, 1)} total
            </p>
          </div>
        )}
      </div>

      {/* Trend Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Efficiency Trend */}
        <TrendCard
          title="Efficiency Trend"
          trend={analysis.efficiency_trend}
          goodDirection="improving"
          dataPointLabel="runs"
        />
        
        {/* Volume Trend */}
        <TrendCard
          title="Volume Trend"
          trend={analysis.volume_trend}
          goodDirection="stable"
          dataPointLabel="weeks"
        />
      </div>

      {/* Root Cause Analysis */}
      {analysis.root_cause_hypotheses.length > 0 && (
        <div className="bg-slate-800/50 rounded-lg p-6">
          <h4 className="text-white font-medium mb-4">Possible Factors</h4>
          <div className="space-y-3">
            {analysis.root_cause_hypotheses.map((hypothesis, i) => (
              <div key={i} className="flex items-start gap-3">
                <div 
                  className={`w-2 h-2 rounded-full mt-2 ${
                    Math.abs(hypothesis.correlation_strength) > 0.5 
                      ? 'bg-orange-400' 
                      : 'bg-slate-500'
                  }`}
                />
                <div>
                  <p className="text-slate-300">{hypothesis.explanation}</p>
                  <p className="text-slate-500 text-sm mt-1">
                    {Math.round(hypothesis.confidence * 100)}% confidence
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input Snapshot */}
      <details className="bg-slate-800/30 rounded-lg">
        <summary className="p-4 cursor-pointer text-slate-400 hover:text-white transition-colors">
          Pre-Run State Details
        </summary>
        <div className="p-4 pt-0 grid grid-cols-2 md:grid-cols-4 gap-4">
          <InputItem 
            label="Sleep (last night)" 
            value={analysis.inputs.sleep_last_night} 
            unit="h"
            compare={analysis.inputs.sleep_7_day_avg}
          />
          <InputItem 
            label="Stress" 
            value={analysis.inputs.stress_today} 
            unit="/5"
            compare={analysis.inputs.stress_3_day_avg}
            invertComparison
          />
          <InputItem 
            label="Soreness" 
            value={analysis.inputs.soreness_today} 
            unit="/5"
            compare={analysis.inputs.soreness_3_day_avg}
            invertComparison
          />
          <InputItem 
            label="HRV" 
            value={analysis.inputs.hrv_today} 
            unit="ms"
            compare={analysis.inputs.hrv_7_day_avg}
          />
          <InputItem 
            label="Resting HR" 
            value={analysis.inputs.resting_hr_today} 
            unit="bpm"
            compare={analysis.inputs.resting_hr_7_day_avg}
            invertComparison
          />
          <InputItem 
            label="Days Since Last Run" 
            value={analysis.inputs.days_since_last_run} 
            unit="d"
          />
          <InputItem 
            label="Runs This Week" 
            value={analysis.inputs.runs_this_week} 
          />
          <InputItem 
            label="Volume This Week" 
            value={analysis.inputs.volume_this_week_km ? formatDistance(analysis.inputs.volume_this_week_km * 1000, 1) : null}
          />
        </div>
      </details>
    </div>
  );
}


// ============ Sub-Components ============

function TrendCard({ 
  title, 
  trend, 
  goodDirection,
  dataPointLabel,
}: { 
  title: string; 
  trend: RunAnalysisData['efficiency_trend'];
  goodDirection: 'improving' | 'stable';
  dataPointLabel: string;
}) {
  const confidenceLabel = () => {
    // Backend returns a 0-1 scalar; map to human-friendly labels.
    const c = trend.confidence ?? 0;
    if (trend.direction === 'insufficient_data') return 'insufficient';
    if (c >= 0.8) return 'high';
    if (c >= 0.5) return 'moderate';
    if (c >= 0.3) return 'low';
    return 'insufficient';
  };

  const getDirectionColor = () => {
    if (trend.direction === 'insufficient_data') return 'text-slate-500';
    if (trend.direction === 'stable') return 'text-slate-400';
    if (trend.direction === goodDirection) return 'text-green-400';
    if (trend.direction === 'declining') return 'text-orange-400';
    return 'text-slate-400';
  };

  const getArrow = () => {
    if (trend.direction === 'improving') return '↑';
    if (trend.direction === 'declining') return '↓';
    if (trend.direction === 'stable') return '→';
    return '—';
  };

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <h4 className="text-slate-400 text-sm mb-2">{title}</h4>
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-bold ${getDirectionColor()}`}>
          {getArrow()} {trend.direction.replace('_', ' ')}
        </span>
        {trend.is_significant && (
          <span className="text-xs text-orange-400 bg-orange-400/20 px-2 py-0.5 rounded">
            Significant
          </span>
        )}
        <span className="text-xs text-slate-300 bg-slate-700/40 px-2 py-0.5 rounded">
          {confidenceLabel()} confidence
        </span>
      </div>
      <p className="text-slate-500 text-sm mt-1">
        Based on {trend.data_points} {dataPointLabel} in the last {trend.period_days} days.
      </p>
      {trend.magnitude !== null && trend.direction !== 'insufficient_data' && trend.is_significant && (
        <p className="text-slate-500 text-sm mt-1">
          {Math.abs(trend.magnitude).toFixed(1)}% over {trend.period_days} days
        </p>
      )}
      {trend.direction === 'insufficient_data' && (
        <p className="text-slate-500 text-sm mt-1">
          Need more data points ({trend.data_points} available)
        </p>
      )}
    </div>
  );
}


function InputItem({ 
  label, 
  value, 
  unit = '', 
  compare,
  invertComparison = false
}: { 
  label: string; 
  value: number | string | null | undefined;
  unit?: string;
  compare?: number | null;
  invertComparison?: boolean;
}) {
  if (value === null || value === undefined) {
    return (
      <div>
        <p className="text-slate-500 text-xs mb-1">{label}</p>
        <p className="text-slate-600">—</p>
      </div>
    );
  }

  const getComparisonIndicator = () => {
    if (!compare || typeof value !== 'number') return null;
    const diff = value - compare;
    const threshold = compare * 0.1; // 10% threshold
    
    if (Math.abs(diff) < threshold) return null;
    
    const isGood = invertComparison ? diff < 0 : diff > 0;
    
    return (
      <span className={`text-xs ml-1 ${isGood ? 'text-green-500' : 'text-orange-500'}`}>
        {diff > 0 ? '▲' : '▼'}
      </span>
    );
  };

  return (
    <div>
      <p className="text-slate-500 text-xs mb-1">{label}</p>
      <p className="text-slate-200">
        {typeof value === 'number' ? value.toFixed(value % 1 === 0 ? 0 : 1) : value}
        <span className="text-slate-500 text-sm">{unit}</span>
        {getComparisonIndicator()}
      </p>
    </div>
  );
}

