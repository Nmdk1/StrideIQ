/**
 * Analytics Page (Research Layer)
 * 
 * Deep analysis for power users, coaches, and scientists:
 * - Efficiency trends over time
 * - Load-response curves
 * - Age-graded trajectory
 * - Stability metrics
 * 
 * This is Layer 3 of the Layered Intelligence architecture.
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useEfficiencyTrends } from '@/lib/hooks/queries/analytics';
import { useCurrentPlan, useCurrentWeek } from '@/lib/hooks/queries/training-plans';
import { EfficiencyChart } from '@/components/dashboard/EfficiencyChart';
import { LoadResponseChart } from '@/components/dashboard/LoadResponseChart';
import { AgeGradedChart } from '@/components/dashboard/AgeGradedChart';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useUnits } from '@/lib/context/UnitsContext';
import { correlationsService, type Correlation } from '@/lib/api/services/correlations';

// Helper to format workout type for display
const workoutTypeColors: Record<string, string> = {
  rest: 'bg-gray-700 text-gray-400',
  easy: 'bg-green-900/50 text-green-400',
  easy_strides: 'bg-green-900/50 text-green-400',
  long: 'bg-blue-900/50 text-blue-400',
  tempo: 'bg-orange-900/50 text-orange-400',
  intervals: 'bg-red-900/50 text-red-400',
  race: 'bg-yellow-900/50 text-yellow-400',
};

export default function DashboardPage() {
  const { formatDistance } = useUnits();
  const [days, setDays] = useState(180); // Default to 180 days to see full training cycles
  const [rollingWindow, setRollingWindow] = useState<'30d' | '60d' | '90d' | '120d' | 'all'>('60d');
  const { data, isLoading, error } = useEfficiencyTrends(days, true, true);
  const { data: plan, isLoading: planLoading } = useCurrentPlan();
  const { data: currentWeek, isLoading: weekLoading } = useCurrentWeek();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center p-4">
          <ErrorMessage error={error} title="Failed to load efficiency trends" />
        </div>
      </ProtectedRoute>
    );
  }

  const dataWithError = data as unknown as { error?: string } | undefined;
  if (!data || dataWithError?.error) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
          <div className="max-w-6xl mx-auto px-4">
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 text-center">
              <p className="text-gray-400">
                {dataWithError?.error ?? 'Insufficient data to calculate efficiency trends'}
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Need at least 3 quality activities with pace and heart rate data.
              </p>
            </div>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-6xl mx-auto px-4">
          <div className="mb-8">
            <div className="mb-4">
              <h1 className="text-2xl md:text-3xl font-bold">Analytics</h1>
              <p className="text-gray-400 mt-1 text-sm md:text-base">
                Efficiency trends, load response, correlations.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <select
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value))}
                className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-base"
              >
                <option value="30">Last 30 days</option>
                <option value="60">Last 60 days</option>
                <option value="90">Last 90 days</option>
                <option value="120">Last 120 days</option>
                <option value="180">Last 6 months</option>
                <option value="365">Last year</option>
              </select>
              <select
                value={rollingWindow}
                onChange={(e) => setRollingWindow(e.target.value as any)}
                className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-base"
              >
                <option value="30d">30-Day Trend</option>
                <option value="60d">60-Day Trend</option>
                <option value="90d">90-Day Trend</option>
                <option value="120d">120-Day Trend</option>
                <option value="all">All Trends</option>
              </select>
            </div>
          </div>

          {/* Training Plan Quick View */}
          {!planLoading && plan && (
            <div className="bg-gradient-to-r from-orange-900/30 to-gray-800 rounded-lg border border-orange-700/50 p-4 mb-6">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h2 className="text-lg font-bold text-white">{plan.name}</h2>
                  <p className="text-sm text-gray-400">
                    {plan.goal_race_name} • {new Date(plan.goal_race_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </p>
                </div>
                <Link 
                  href="/calendar" 
                  className="text-sm text-orange-400 hover:text-orange-300"
                >
                  View Full Plan →
                </Link>
              </div>
              
              {/* Progress bar */}
              <div className="mb-3">
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-orange-500 transition-all"
                    style={{ width: `${plan.progress_percent}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>Week {plan.current_week || 0} of {plan.total_weeks}</span>
                  <span>{plan.progress_percent}%</span>
                </div>
              </div>
              
              {/* This week's workouts */}
              {!weekLoading && currentWeek && (
                <div>
                  <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">
                    This Week • {currentWeek.phase} Phase
                  </p>
                  {/* Desktop: 7 columns */}
                  <div className="hidden md:grid grid-cols-7 gap-1">
                    {currentWeek.workouts.slice(0, 7).map((workout, i) => (
                      <div
                        key={i}
                        className={`text-center py-2 px-1 rounded ${workoutTypeColors[workout.workout_type] || 'bg-gray-800'}`}
                      >
                        <div className="text-[10px] text-gray-400">
                          {new Date(workout.scheduled_date).toLocaleDateString('en-US', { weekday: 'short' })}
                        </div>
                        <div className="text-xs font-medium truncate" title={workout.title}>
                          {workout.workout_type === 'rest' ? 'Rest' : 
                           workout.target_distance_km ? formatDistance(workout.target_distance_km * 1000, 0) : 
                           workout.title.split(' ')[0]}
                        </div>
                        {workout.completed && <span className="text-green-400 text-xs">✓</span>}
                      </div>
                    ))}
                  </div>
                  {/* Mobile: scrollable horizontal row */}
                  <div className="md:hidden flex gap-1 overflow-x-auto pb-2 -mx-1 px-1">
                    {currentWeek.workouts.slice(0, 7).map((workout, i) => (
                      <div
                        key={i}
                        className={`flex-shrink-0 text-center py-2 px-2 rounded min-w-[50px] ${workoutTypeColors[workout.workout_type] || 'bg-gray-800'}`}
                      >
                        <div className="text-[10px] text-gray-400">
                          {new Date(workout.scheduled_date).toLocaleDateString('en-US', { weekday: 'narrow' })}
                        </div>
                        <div className="text-xs font-medium">
                          {workout.workout_type === 'rest' ? 'R' : 
                           workout.target_distance_km ? formatDistance(workout.target_distance_km * 1000, 0) : 
                           workout.title.charAt(0)}
                        </div>
                        {workout.completed && <span className="text-green-400 text-[10px]">✓</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* No plan - subtle prompt */}
          {!planLoading && !plan && (
            <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 p-4 mb-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-400">No active plan.</p>
                <Link 
                  href="/plans/create" 
                  className="text-sm text-orange-400 hover:text-orange-300"
                >
                  Create →
                </Link>
              </div>
            </div>
          )}

          {/* Summary Stats - Sparse, data-driven */}
          {data.summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <div className="bg-gray-800/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">Current EF</p>
                <p className="text-xl font-semibold">{data.summary.current_efficiency}</p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">{days}d Avg</p>
                <p className="text-xl font-semibold">{data.summary.average_efficiency}</p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">Best</p>
                <p className="text-xl font-semibold text-emerald-400">
                  {data.summary.best_efficiency}
                </p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">Trend</p>
                <p className={`text-xl font-semibold ${
                  data.summary.trend_direction === 'improving' ? 'text-emerald-400' :
                  data.summary.trend_direction === 'declining' ? 'text-orange-400' :
                  'text-gray-400'
                }`}>
                  {data.summary.trend_direction === 'improving' ? '↑' :
                   data.summary.trend_direction === 'declining' ? '↓' : '→'}
                  {data.summary.trend_magnitude && ` ${Math.abs(data.summary.trend_magnitude).toFixed(1)}%`}
                </p>
              </div>
            </div>
          )}

          {/* Stability Metrics */}
          {data.stability && data.stability.consistency_score !== null && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-6">
              <h3 className="text-lg font-semibold mb-2">Stability Metrics</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-400">Consistency Score</p>
                  <p className="text-xl font-semibold">
                    {data.stability.consistency_score?.toFixed(1)}/100
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Easy Runs</p>
                  <p className="text-xl font-semibold">{data.stability.easy_runs}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Moderate Runs</p>
                  <p className="text-xl font-semibold">{data.stability.moderate_runs}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Hard Runs</p>
                  <p className="text-xl font-semibold">{data.stability.hard_runs}</p>
                </div>
              </div>
            </div>
          )}

          {/* Efficiency Trend Chart */}
          {data.time_series && data.time_series.length > 0 && (
            <EfficiencyChart
              data={data.time_series}
              rollingWindow={rollingWindow}
              className="mb-6"
            />
          )}

          {/* Age-Graded Trajectory */}
          {data.time_series && data.time_series.length > 0 && (
            <AgeGradedChart data={data.time_series} className="mb-6" />
          )}

          {/* Load-Response Chart */}
          {data.load_response && data.load_response.length > 0 && (
            <LoadResponseChart data={data.load_response} />
          )}
          
          {/* Correlation Explorer */}
          <CorrelationExplorer days={days} />
        </div>
      </div>
    </ProtectedRoute>
  );
}

/**
 * Correlation Explorer Component
 * 
 * Shows "What's Working" and "What's Not Working" from correlation analysis.
 * TONE: Data speaks. No prescriptions.
 */
function CorrelationExplorer({ days }: { days: number }) {
  const { data: whatWorks, isLoading: loadingWorks } = useQuery({
    queryKey: ['what-works', days],
    queryFn: () => correlationsService.whatWorks(days),
    staleTime: 1000 * 60 * 5,
  });
  
  const { data: whatDoesntWork, isLoading: loadingDoesnt } = useQuery({
    queryKey: ['what-doesnt-work', days],
    queryFn: () => correlationsService.whatDoesntWork(days),
    staleTime: 1000 * 60 * 5,
  });
  
  const isLoading = loadingWorks || loadingDoesnt;
  
  if (isLoading) {
    return (
      <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      </div>
    );
  }
  
  const hasData = (whatWorks?.count || 0) > 0 || (whatDoesntWork?.count || 0) > 0;
  
  if (!hasData) {
    return (
      <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-2">Correlation Explorer</h3>
        <p className="text-gray-500 text-sm">
          Not enough data yet. Log more inputs (sleep, nutrition, stress) to discover patterns.
        </p>
      </div>
    );
  }
  
  return (
    <div className="mt-6 grid md:grid-cols-2 gap-4">
      {/* What's Working */}
      <div className="bg-gray-800 rounded-lg border border-emerald-700/30 p-4">
        <h3 className="text-sm font-semibold text-emerald-400 mb-3">
          What Correlates with Better Efficiency
        </h3>
        {whatWorks?.what_works && whatWorks.what_works.length > 0 ? (
          <div className="space-y-2">
            {whatWorks.what_works.slice(0, 5).map((c, i) => (
              <CorrelationItem key={i} correlation={c} positive />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No significant patterns yet.</p>
        )}
      </div>
      
      {/* What's Not Working */}
      <div className="bg-gray-800 rounded-lg border border-orange-700/30 p-4">
        <h3 className="text-sm font-semibold text-orange-400 mb-3">
          What Correlates with Worse Efficiency
        </h3>
        {whatDoesntWork?.what_doesnt_work && whatDoesntWork.what_doesnt_work.length > 0 ? (
          <div className="space-y-2">
            {whatDoesntWork.what_doesnt_work.slice(0, 5).map((c, i) => (
              <CorrelationItem key={i} correlation={c} positive={false} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No significant patterns yet.</p>
        )}
      </div>
    </div>
  );
}

/**
 * Single correlation item display
 */
function CorrelationItem({ correlation, positive }: { correlation: Correlation; positive: boolean }) {
  const strengthLabel = correlation.strength === 'strong' ? '●●●' : 
                        correlation.strength === 'moderate' ? '●●○' : '●○○';
  
  const confidenceText = correlation.is_significant 
    ? `p=${correlation.p_value.toFixed(3)}` 
    : 'not significant';
  
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-700/50 last:border-0">
      <div className="flex-1">
        <div className="text-sm text-white">
          {correlation.input_name.replace(/_/g, ' ')}
        </div>
        <div className="text-xs text-gray-500">
          {correlation.sample_size} samples · {confidenceText}
          {correlation.time_lag_days > 0 && ` · ${correlation.time_lag_days}d lag`}
        </div>
      </div>
      <div className="text-right">
        <div className={`text-xs ${positive ? 'text-emerald-400' : 'text-orange-400'}`}>
          {strengthLabel}
        </div>
        <div className="text-[10px] text-gray-500">
          r={correlation.correlation_coefficient.toFixed(2)}
        </div>
      </div>
    </div>
  );
}

