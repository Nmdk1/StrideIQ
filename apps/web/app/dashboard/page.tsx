/**
 * Dashboard Page
 * 
 * The core product differentiator - efficiency trends visualization.
 * Shows if athletes are getting fitter or just accumulating work.
 * 
 * Also shows:
 * - Current training plan overview
 * - This week's workouts
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useEfficiencyTrends } from '@/lib/hooks/queries/analytics';
import { useCurrentPlan, useCurrentWeek } from '@/lib/hooks/queries/training-plans';
import { EfficiencyChart } from '@/components/dashboard/EfficiencyChart';
import { LoadResponseChart } from '@/components/dashboard/LoadResponseChart';
import { AgeGradedChart } from '@/components/dashboard/AgeGradedChart';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useUnits } from '@/lib/context/UnitsContext';

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
              <h1 className="text-2xl md:text-3xl font-bold">Efficiency Dashboard</h1>
              <p className="text-gray-400 mt-1 text-sm md:text-base">
                Are you getting fitter or just accumulating work?
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
          
          {/* No plan prompt */}
          {!planLoading && !plan && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6 text-center">
              <h3 className="text-lg font-semibold mb-2">No Training Plan</h3>
              <p className="text-gray-400 mb-4">
                Create a training plan to get structured workouts and track your progress toward your goal race.
              </p>
              <Link 
                href="/plans/create" 
                className="inline-block px-6 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg font-medium transition-colors"
              >
                Create Training Plan
              </Link>
            </div>
          )}

          {/* Summary Stats */}
          {data.summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <p className="text-xs text-gray-400 mb-1">Current Efficiency</p>
                <p className="text-2xl font-semibold">{data.summary.current_efficiency}</p>
                <p className="text-xs text-gray-500 mt-1">Lower is better</p>
              </div>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <p className="text-xs text-gray-400 mb-1">Average Efficiency</p>
                <p className="text-2xl font-semibold">{data.summary.average_efficiency}</p>
                <p className="text-xs text-gray-500 mt-1">Over {days} days</p>
              </div>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <p className="text-xs text-gray-400 mb-1">Best Efficiency</p>
                <p className="text-2xl font-semibold text-green-400">
                  {data.summary.best_efficiency}
                </p>
                <p className="text-xs text-gray-500 mt-1">Most efficient run</p>
              </div>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <p className="text-xs text-gray-400 mb-1">Trend</p>
                <p
                  className={`text-2xl font-semibold capitalize ${
                    data.summary.trend_direction === 'improving'
                      ? 'text-green-400'
                      : data.summary.trend_direction === 'declining'
                      ? 'text-red-400'
                      : 'text-gray-400'
                  }`}
                >
                  {data.summary.trend_direction}
                </p>
                {data.summary.trend_magnitude && (
                  <p className="text-xs text-gray-500 mt-1">
                    Δ {data.summary.trend_magnitude.toFixed(2)}
                  </p>
                )}
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
        </div>
      </div>
    </ProtectedRoute>
  );
}

