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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { BarChart3, TrendingUp, TrendingDown, Minus, Target, Calendar, ArrowRight, Activity, Zap, AlertTriangle, Info } from 'lucide-react';
import { WhyThisTrend } from '@/components/analytics/WhyThisTrend';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

// Helper to format workout type for display
const workoutTypeColors: Record<string, string> = {
  rest: 'bg-slate-700 text-slate-400',
  easy: 'bg-green-900/50 text-green-400',
  easy_strides: 'bg-green-900/50 text-green-400',
  long: 'bg-blue-900/50 text-blue-400',
  tempo: 'bg-orange-900/50 text-orange-400',
  intervals: 'bg-red-900/50 text-red-400',
  race: 'bg-yellow-900/50 text-yellow-400',
};

function InfoTooltip({ content }: { content: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Metric info"
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-400 transition-colors"
        >
          <Info className="w-3.5 h-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">
        <p className="text-xs leading-relaxed">{content}</p>
      </TooltipContent>
    </Tooltip>
  );
}

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
        <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
          <div className="max-w-6xl mx-auto px-4">
            <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 text-center">
              <p className="text-slate-400">
                {dataWithError?.error ?? 'Insufficient data to calculate efficiency trends'}
              </p>
              <p className="text-sm text-slate-500 mt-2">
                Need at least 3 quality activities with pace and heart rate data.
              </p>
            </div>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const currentEfTooltip = `Current EF: ${data.summary?.current_efficiency}. Efficiency Factor (EF) is a simple pace-per-heart-rate signal; higher usually means you can run faster at the same effort.`;
  const avgEfTooltip = `${days}d Avg EF: ${data.summary?.average_efficiency}. A smoothed view of efficiency over the selected window.`;
  const bestEfTooltip = `Best EF: ${data.summary?.best_efficiency}. Your highest observed efficiency — useful for tracking fitness peaks.`;
  const trendTooltip = `Trend: ${data.summary?.trend_direction ?? 'stable'}. Improving means EF is rising over time; declining means EF is falling.`;
  const consistencyScoreTooltip = `Consistency Score: ${data.stability?.consistency_score?.toFixed(1)}/100. Summarizes training regularity and intensity balance.`;
  const easyRunsTooltip = `Easy Runs: ${data.stability?.easy_runs}. Lower-intensity sessions (recovery / aerobic base).`;
  const moderateRunsTooltip = `Moderate Runs: ${data.stability?.moderate_runs}. Steady aerobic work (not easy, not hard).`;
  const hardRunsTooltip = `Hard Runs: ${data.stability?.hard_runs}. Higher-intensity sessions (threshold / VO₂ / hard workouts).`;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
        <div className="max-w-6xl mx-auto px-4">
          <TooltipProvider>
          <div className="mb-8">
            <div className="mb-4">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                  <BarChart3 className="w-6 h-6 text-orange-500" />
                </div>
                <h1 className="text-2xl md:text-3xl font-bold">Analytics</h1>
              </div>
              <p className="text-slate-400 text-sm md:text-base">
                Efficiency trends, load response, correlations.
              </p>
            </div>
            <Card className="bg-slate-800 border-slate-700">
              <CardContent className="py-4">
                <div className="flex flex-col sm:flex-row gap-3">
                  <select
                    value={days}
                    onChange={(e) => setDays(parseInt(e.target.value))}
                    className="flex-1 px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white text-base focus:border-orange-500 focus:outline-none"
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
                    onChange={(e) => setRollingWindow(e.target.value as '30d' | '60d' | '90d' | '120d' | 'all')}
                    className="flex-1 px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white text-base focus:border-orange-500 focus:outline-none"
                  >
                    <option value="30d">30-Day Trend</option>
                    <option value="60d">60-Day Trend</option>
                    <option value="90d">90-Day Trend</option>
                    <option value="120d">120-Day Trend</option>
                    <option value="all">All Trends</option>
                  </select>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Training Plan Quick View */}
          {!planLoading && plan && (
            <Card className="bg-gradient-to-r from-orange-900/30 to-slate-800 border-orange-700/50 mb-6">
              <CardContent className="pt-5 pb-5">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-orange-500/20 ring-1 ring-orange-500/30">
                      <Target className="w-5 h-5 text-orange-500" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-white">{plan.name}</h2>
                      <p className="text-sm text-slate-400 flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        {plan.goal_race_name} • {new Date(plan.goal_race_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </p>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" asChild className="text-orange-400 hover:text-orange-300">
                    <Link href="/calendar">
                      View Plan <ArrowRight className="w-4 h-4 ml-1" />
                    </Link>
                  </Button>
                </div>
              
                {/* Progress bar */}
                <div className="mb-3">
                  <Progress value={plan.progress_percent} className="h-2" indicatorClassName="bg-orange-500" />
                  <div className="flex justify-between text-xs text-slate-400 mt-1">
                    <span>Week {plan.current_week || 0} of {plan.total_weeks}</span>
                    <Badge variant="outline" className="text-orange-400 border-orange-500/30">{plan.progress_percent}%</Badge>
                  </div>
                </div>
              
              {/* This week's workouts */}
              {!weekLoading && currentWeek && (
                <div>
                  <p className="text-xs text-slate-400 mb-2 uppercase tracking-wide">
                    This Week • {currentWeek.phase} Phase
                  </p>
                  {/* Desktop: 7 columns */}
                  <div className="hidden md:grid grid-cols-7 gap-1">
                    {currentWeek.workouts.slice(0, 7).map((workout, i) => {
                      const linkHref = workout.completed && workout.completed_activity_id 
                        ? `/activities/${workout.completed_activity_id}`
                        : `/calendar?date=${workout.scheduled_date}`;
                      return (
                        <Link
                          key={i}
                          href={linkHref}
                          className={`text-center py-2 px-1 rounded transition-all hover:scale-105 cursor-pointer ${workoutTypeColors[workout.workout_type] || 'bg-slate-800'}`}
                        >
                          <div className="text-[10px] text-slate-400">
                            {new Date(workout.scheduled_date).toLocaleDateString('en-US', { weekday: 'short' })}
                          </div>
                          <div className="text-xs font-medium truncate">
                            {workout.workout_type === 'rest' ? 'Rest' : 
                             workout.target_distance_km ? formatDistance(workout.target_distance_km * 1000, 0) : 
                             workout.title.split(' ')[0]}
                          </div>
                          {workout.completed && <span className="text-green-400 text-xs">✓</span>}
                        </Link>
                      );
                    })}
                  </div>
                  {/* Mobile: scrollable horizontal row */}
                  <div className="md:hidden flex gap-1 overflow-x-auto pb-2 -mx-1 px-1">
                    {currentWeek.workouts.slice(0, 7).map((workout, i) => {
                      const linkHref = workout.completed && workout.completed_activity_id 
                        ? `/activities/${workout.completed_activity_id}`
                        : `/calendar?date=${workout.scheduled_date}`;
                      return (
                        <Link
                          key={i}
                          href={linkHref}
                          className={`flex-shrink-0 text-center py-2 px-2 rounded min-w-[50px] transition-all hover:scale-105 cursor-pointer ${workoutTypeColors[workout.workout_type] || 'bg-slate-800'}`}
                        >
                          <div className="text-[10px] text-slate-400">
                            {new Date(workout.scheduled_date).toLocaleDateString('en-US', { weekday: 'narrow' })}
                          </div>
                          <div className="text-xs font-medium">
                            {workout.workout_type === 'rest' ? 'R' : 
                             workout.target_distance_km ? formatDistance(workout.target_distance_km * 1000, 0) : 
                             workout.title.charAt(0)}
                          </div>
                          {workout.completed && <span className="text-green-400 text-[10px]">✓</span>}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              )}
              </CardContent>
            </Card>
          )}
          
          {/* No plan - subtle prompt */}
          {!planLoading && !plan && (
            <Card className="bg-slate-800/50 border-slate-700/50 mb-6">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    No active plan.
                  </p>
                  <Button variant="ghost" size="sm" asChild className="text-orange-400 hover:text-orange-300">
                    <Link href="/plans/create">
                      Create <ArrowRight className="w-4 h-4 ml-1" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Summary Stats - Sparse, data-driven */}
          {data.summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <Card
                className="bg-slate-800 border-slate-700 transition-colors hover:border-slate-600"
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-slate-500">Current EF</p>
                    <InfoTooltip content={currentEfTooltip} />
                  </div>
                  <p className="text-xl font-semibold">{data.summary.current_efficiency}</p>
                </CardContent>
              </Card>
              <Card
                className="bg-slate-800 border-slate-700 transition-colors hover:border-slate-600"
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-slate-500">{days}d Avg</p>
                    <InfoTooltip content={avgEfTooltip} />
                  </div>
                  <p className="text-xl font-semibold">{data.summary.average_efficiency}</p>
                </CardContent>
              </Card>
              <Card
                className="bg-slate-800 border-slate-700 transition-colors hover:border-slate-600"
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-slate-500">Best</p>
                    <InfoTooltip content={bestEfTooltip} />
                  </div>
                  <p className="text-xl font-semibold text-emerald-400">
                    {data.summary.best_efficiency}
                  </p>
                </CardContent>
              </Card>
              <Card
                className="bg-slate-800 border-slate-700 transition-colors hover:border-slate-600"
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-slate-500">Trend</p>
                    <InfoTooltip content={trendTooltip} />
                  </div>
                  <p className={`text-xl font-semibold flex items-center gap-1 ${
                    data.summary.trend_direction === 'improving' ? 'text-emerald-400' :
                    data.summary.trend_direction === 'declining' ? 'text-orange-400' :
                    'text-slate-400'
                  }`}>
                    {data.summary.trend_direction === 'improving' ? <TrendingUp className="w-5 h-5" /> :
                     data.summary.trend_direction === 'declining' ? <TrendingDown className="w-5 h-5" /> : <Minus className="w-5 h-5" />}
                    {data.summary.trend_magnitude && ` ${Math.abs(data.summary.trend_magnitude).toFixed(1)}%`}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Stability Metrics */}
          {data.stability && data.stability.consistency_score !== null && (
            <Card className="bg-slate-800 border-slate-700 mb-6">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="w-5 h-5 text-orange-500" />
                  Stability Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div
                    className="rounded-lg border border-slate-700 bg-slate-900/20 p-3 transition-colors hover:border-slate-600"
                  >
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-slate-400">Consistency Score</p>
                      <InfoTooltip content={consistencyScoreTooltip} />
                    </div>
                    <p className="text-xl font-semibold">
                      {data.stability.consistency_score?.toFixed(1)}/100
                    </p>
                  </div>
                  <div
                    className="rounded-lg border border-slate-700 bg-slate-900/20 p-3 transition-colors hover:border-slate-600"
                  >
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-slate-400">Easy Runs</p>
                      <InfoTooltip content={easyRunsTooltip} />
                    </div>
                    <p className="text-xl font-semibold text-emerald-400">{data.stability.easy_runs}</p>
                  </div>
                  <div
                    className="rounded-lg border border-slate-700 bg-slate-900/20 p-3 transition-colors hover:border-slate-600"
                  >
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-slate-400">Moderate Runs</p>
                      <InfoTooltip content={moderateRunsTooltip} />
                    </div>
                    <p className="text-xl font-semibold text-blue-400">{data.stability.moderate_runs}</p>
                  </div>
                  <div
                    className="rounded-lg border border-slate-700 bg-slate-900/20 p-3 transition-colors hover:border-slate-600"
                  >
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-slate-400">Hard Runs</p>
                      <InfoTooltip content={hardRunsTooltip} />
                    </div>
                    <p className="text-xl font-semibold text-orange-400">{data.stability.hard_runs}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Efficiency Trend Chart */}
          {data.time_series && data.time_series.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-slate-200">Efficiency Trend</h2>
                <WhyThisTrend metric="efficiency" days={days} />
              </div>
              <EfficiencyChart
                data={data.time_series}
                rollingWindow={rollingWindow}
              />
            </div>
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
          </TooltipProvider>
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
      <Card className="mt-6 bg-slate-800 border-slate-700">
        <CardContent className="py-8">
          <div className="flex justify-center">
            <LoadingSpinner />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const hasData = (whatWorks?.count || 0) > 0 || (whatDoesntWork?.count || 0) > 0;
  
  if (!hasData) {
    return (
      <Card className="mt-6 bg-slate-800 border-slate-700">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Zap className="w-5 h-5 text-orange-500" />
            Correlation Explorer
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="text-slate-400 text-sm">
            Log check-ins and nutrition to discover what habits correlate with your best runs.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link href="/checkin">
              <Button variant="outline" size="sm">
                Log Check-in
              </Button>
            </Link>
            <Link href="/nutrition">
              <Button variant="outline" size="sm">
                Log Nutrition
              </Button>
            </Link>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            ~10 entries needed to surface meaningful correlations.
          </p>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <div className="mt-6 grid md:grid-cols-2 gap-4">
      {/* What's Working */}
      <Card className="bg-slate-800 border-emerald-700/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-emerald-400 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            What Correlates with Better Efficiency
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {whatWorks?.what_works && whatWorks.what_works.length > 0 ? (
            <div className="space-y-2">
              {whatWorks.what_works.slice(0, 5).map((c, i) => (
                <CorrelationItem key={i} correlation={c} positive />
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No significant patterns yet.</p>
          )}
        </CardContent>
      </Card>
      
      {/* What's Not Working */}
      <Card className="bg-slate-800 border-orange-700/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-orange-400 flex items-center gap-2">
            <TrendingDown className="w-4 h-4" />
            What Correlates with Worse Efficiency
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {whatDoesntWork?.what_doesnt_work && whatDoesntWork.what_doesnt_work.length > 0 ? (
            <div className="space-y-2">
              {whatDoesntWork.what_doesnt_work.slice(0, 5).map((c, i) => (
                <CorrelationItem key={i} correlation={c} positive={false} />
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No significant patterns yet.</p>
          )}
        </CardContent>
      </Card>
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
    <div className="flex items-center justify-between py-2 border-b border-slate-700/50 last:border-0">
      <div className="flex-1">
        <div className="text-sm text-white">
          {correlation.input_name.replace(/_/g, ' ')}
        </div>
        <div className="text-xs text-slate-500">
          {correlation.sample_size} samples · {confidenceText}
          {correlation.time_lag_days > 0 && ` · ${correlation.time_lag_days}d lag`}
        </div>
      </div>
      <div className="text-right">
        <div className={`text-xs ${positive ? 'text-emerald-400' : 'text-orange-400'}`}>
          {strengthLabel}
        </div>
        <div className="text-[10px] text-slate-500">
          r={correlation.correlation_coefficient.toFixed(2)}
        </div>
      </div>
    </div>
  );
}
