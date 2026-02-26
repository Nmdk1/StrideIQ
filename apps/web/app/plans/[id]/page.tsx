'use client';

/**
 * Plan Overview Page
 *
 * Full view of a training plan showing:
 * - All weeks at a glance
 * - Phase progression
 * - Volume chart
 * - Workout details per week
 *
 * DESIGN: Users need to see their entire plan to understand the journey
 */

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

/** Workout types that carry pace targets and should show the locked-pace UI. */
const QUALITY_TYPES = new Set(['threshold', 'tempo', 'intervals', 'long_mp']);

interface PlannedWorkout {
  id: string;
  date: string | null;
  day_of_week: number;
  workout_type: string;
  title: string;
  description: string | null;
  phase: string;
  target_distance_km: number | null;
  target_duration_minutes: number | null;
  coach_notes: string | null;
  completed: boolean;
  skipped: boolean;
}

interface PlanDetail {
  id: string;
  name: string;
  status: string;
  goal_race_name: string | null;
  goal_race_date: string | null;
  total_weeks: number;
  start_date: string | null;
  end_date: string | null;
  baseline_rpi: number | null;
  paces_locked: boolean;
  weeks: Record<string, PlannedWorkout[]>;
}

// Workout type styling
const workoutStyles: Record<string, { bg: string; text: string }> = {
  rest: { bg: 'bg-slate-800', text: 'text-slate-500' },
  easy: { bg: 'bg-emerald-900/40', text: 'text-emerald-400' },
  easy_strides: { bg: 'bg-emerald-900/40', text: 'text-emerald-400' },
  easy_hills: { bg: 'bg-emerald-900/40', text: 'text-emerald-400' },
  recovery: { bg: 'bg-slate-800', text: 'text-slate-400' },
  medium_long: { bg: 'bg-sky-900/40', text: 'text-sky-400' },
  long: { bg: 'bg-blue-900/40', text: 'text-blue-400' },
  long_mp: { bg: 'bg-pink-900/40', text: 'text-pink-400' },
  progression: { bg: 'bg-blue-900/40', text: 'text-blue-300' },
  threshold: { bg: 'bg-orange-900/40', text: 'text-orange-400' },
  tempo: { bg: 'bg-orange-900/40', text: 'text-orange-400' },
  intervals: { bg: 'bg-red-900/40', text: 'text-red-400' },
  race: { bg: 'bg-gradient-to-r from-pink-600 to-orange-600', text: 'text-white' },
};

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function PlanOverviewPage() {
  const params = useParams();
  const router = useRouter();
  const { token, isAuthenticated, isLoading: authLoading } = useAuth();
  const planId = params.id as string;
  
  const [expandedWeek, setExpandedWeek] = useState<number | null>(null);
  const [unlocking, setUnlocking] = useState(false);

  /** Initiate the $5 one-time plan unlock via Stripe Checkout. */
  const unlockPaces = async () => {
    if (!plan || !token || unlocking) return;
    setUnlocking(true);
    try {
      const res = await fetch(`${API_CONFIG.baseURL}/v1/billing/checkout/plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan_snapshot_id: plan.id }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail ?? 'Could not start checkout. Please try again.');
        return;
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch {
      alert('Network error. Please check your connection and try again.');
    } finally {
      setUnlocking(false);
    }
  };

  const { data: plan, isLoading, error } = useQuery<PlanDetail>({
    queryKey: ['plan', planId],
    queryFn: async () => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${planId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to fetch plan');
      return res.json();
    },
    enabled: !authLoading && !!token && !!planId,
  });
  
  // Redirect if not authenticated
  React.useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Post-unlock success: clean URL and show confirmation
  const [unlockSuccess, setUnlockSuccess] = React.useState(false);
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('unlocked') === '1') {
      setUnlockSuccess(true);
      // Remove the query param without adding a history entry
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);
  
  // Calculate week volume
  const getWeekVolume = (workouts: PlannedWorkout[]): number => {
    return workouts.reduce((sum, w) => sum + (w.target_distance_km || 0), 0);
  };
  
  // Get phase color
  const getPhaseColor = (phase: string): string => {
    const phases: Record<string, string> = {
      base: 'text-emerald-400',
      build: 'text-orange-400',
      peak: 'text-pink-400',
      taper: 'text-blue-400',
      race: 'text-white',
    };
    return phases[phase.toLowerCase()] || 'text-slate-400';
  };
  
  // Format date
  const formatDate = (dateStr: string): string => {
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-6xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="mb-8">
            <button
              onClick={() => router.push('/calendar')}
              className="text-slate-400 hover:text-white mb-4 flex items-center gap-2 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to Calendar
            </button>
            
            {isLoading ? (
              <div className="animate-pulse">
                <div className="h-10 bg-slate-800 rounded w-2/3 mb-4"></div>
                <div className="h-6 bg-slate-800 rounded w-1/3"></div>
              </div>
            ) : plan ? (
              <>
                <h1 className="text-3xl font-bold text-white mb-2">{plan.name}</h1>
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  {plan.goal_race_name && plan.goal_race_date && (
                    <span className="text-slate-400">
                      🏁 {plan.goal_race_name} • {formatDate(plan.goal_race_date)}
                    </span>
                  )}
                  <span className="px-2 py-1 bg-blue-600/30 text-blue-300 rounded text-xs">
                    {plan.total_weeks} weeks
                  </span>
                  {plan.baseline_rpi && (
                    <span className="px-2 py-1 bg-orange-600/30 text-orange-300 rounded text-xs">
                      Fitness Index {plan.baseline_rpi}
                    </span>
                  )}
                    <span className={`px-2 py-1 rounded text-xs ${
                    plan.status === 'active' ? 'bg-emerald-600/30 text-emerald-300' :
                    plan.status === 'paused' ? 'bg-amber-600/30 text-amber-300' :
                    'bg-slate-600/30 text-slate-300'
                  }`}>
                    {plan.status}
                  </span>
                </div>
              </>
            ) : null}
          </div>
          
          {error && (
            <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-6">
              <h2 className="text-xl font-bold text-red-400 mb-2">Plan Not Found</h2>
              <p className="text-slate-400">This plan could not be loaded.</p>
            </div>
          )}
          
          {plan && (
            <>
              {/* Post-unlock success confirmation */}
              {unlockSuccess && (
                <div className="mb-4 flex items-center gap-3 rounded-xl border border-emerald-700/40 bg-emerald-900/20 px-5 py-3">
                  <svg className="w-5 h-5 text-emerald-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm text-emerald-300">
                    Paces unlocked — your full training prescriptions are now visible.
                  </span>
                </div>
              )}

              {/* Locked-pace banner — only shown when paces are gated */}
              {plan.paces_locked && (
                <div className="mb-6 flex items-center justify-between gap-4 rounded-xl border border-orange-700/40 bg-gradient-to-r from-orange-900/20 to-slate-800 px-5 py-4">
                  <div>
                    <p className="text-sm font-semibold text-orange-300">Paces locked</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Unlock calculated training paces for this plan — one-time, $5.
                    </p>
                  </div>
                  <button
                    onClick={unlockPaces}
                    disabled={unlocking}
                    className="shrink-0 rounded-lg bg-gradient-to-r from-orange-500 to-pink-600 px-4 py-2 text-sm font-semibold text-white shadow hover:from-orange-600 hover:to-pink-700 disabled:opacity-60 transition-all"
                  >
                    {unlocking ? 'Redirecting…' : 'Unlock — $5'}
                  </button>
                </div>
              )}

              {/* Week Overview Grid */}
              <div className="space-y-4">
                {Object.entries(plan.weeks)
                  .sort(([a], [b]) => parseInt(a) - parseInt(b))
                  .map(([weekNum, workouts]) => {
                    const weekNumber = parseInt(weekNum);
                    const isExpanded = expandedWeek === weekNumber;
                    const volume = getWeekVolume(workouts);
                    const volumeMiles = (volume * 0.621371).toFixed(0);
                    const phase = workouts[0]?.phase || 'base';
                    const qualitySessions = workouts.filter(w => 
                      ['threshold', 'tempo', 'intervals', 'long_mp'].includes(w.workout_type)
                    ).length;
                    const completedCount = workouts.filter(w => w.completed).length;
                    const isCurrentWeek = workouts.some(w => {
                      if (!w.date) return false;
                      const today = new Date();
                      const workoutDate = new Date(w.date);
                      return workoutDate <= today && 
                        workoutDate >= new Date(today.setDate(today.getDate() - 7));
                    });
                    
                    return (
                      <div 
                        key={weekNum}
                        className={`bg-slate-800/50 rounded-lg border ${
                          isCurrentWeek ? 'border-blue-500' : 'border-slate-700/50'
                        }`}
                      >
                        {/* Week Header - Clickable */}
                        <button
                          onClick={() => setExpandedWeek(isExpanded ? null : weekNumber)}
                          className="w-full p-4 flex items-center justify-between hover:bg-slate-800/70 transition-colors rounded-lg"
                        >
                          <div className="flex items-center gap-4">
                            <div className="text-lg font-bold text-white">
                              Week {weekNumber}
                            </div>
                            <span className={`text-sm font-medium ${getPhaseColor(phase)}`}>
                              {phase}
                            </span>
                            {isCurrentWeek && (
                              <span className="px-2 py-0.5 bg-blue-600 text-white text-xs rounded">
                                Current
                              </span>
                            )}
                          </div>
                          
                          <div className="flex items-center gap-6">
                            <div className="text-right">
                              <div className="text-white font-semibold">{volumeMiles} mi</div>
                              <div className="text-xs text-slate-500">
                                {qualitySessions} quality • {completedCount}/{workouts.length} done
                              </div>
                            </div>
                            
                            {/* Workout dots preview */}
                            <div className="hidden sm:flex gap-1">
                              {workouts.slice(0, 7).map((w, i) => {
                                const style = workoutStyles[w.workout_type] || workoutStyles.easy;
                                return (
                                  <div
                                    key={i}
                                    className={`w-3 h-3 rounded-full ${style.bg} ${
                                      w.completed ? 'ring-1 ring-emerald-500' : 
                                      w.skipped ? 'opacity-30' : ''
                                    }`}
                                    title={w.title}
                                  />
                                );
                              })}
                            </div>
                            
                            <svg 
                              className={`w-5 h-5 text-slate-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                              fill="none" viewBox="0 0 24 24" stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </button>
                        
                        {/* Expanded Week Detail */}
                        {isExpanded && (
                          <div className="px-4 pb-4 border-t border-slate-700/50 mt-2 pt-4">
                            <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
                              {DAY_NAMES.map((dayName, dayIndex) => {
                                const dayWorkout = workouts.find(w => w.day_of_week === dayIndex);
                                const style = dayWorkout 
                                  ? (workoutStyles[dayWorkout.workout_type] || workoutStyles.easy)
                                  : workoutStyles.rest;
                                
                                return (
                                  <div 
                                    key={dayIndex}
                                    className={`p-3 rounded-lg border border-slate-700/50 ${style.bg} ${
                                      dayWorkout?.completed ? 'ring-1 ring-emerald-500' :
                                      dayWorkout?.skipped ? 'opacity-50' : ''
                                    }`}
                                  >
                                    <div className="text-xs text-slate-500 mb-1">
                                      {dayName}
                                      {dayWorkout?.date && (
                                        <span className="ml-1">{formatDate(dayWorkout.date)}</span>
                                      )}
                                    </div>
                                    
                                    {dayWorkout ? (
                                      <>
                                        <div className={`font-semibold text-sm ${style.text}`}>
                                          {dayWorkout.title}
                                        </div>
                                        {dayWorkout.target_distance_km && (
                                          <div className="text-xs text-slate-400 mt-1">
                                            {(dayWorkout.target_distance_km * 0.621371).toFixed(1)} mi
                                          </div>
                                        )}
                                        {dayWorkout.coach_notes ? (
                                          <div className="text-xs text-slate-500 mt-1 truncate" title={dayWorkout.coach_notes}>
                                            {dayWorkout.coach_notes}
                                          </div>
                                        ) : plan.paces_locked && QUALITY_TYPES.has(dayWorkout.workout_type) ? (
                                          <button
                                            onClick={unlockPaces}
                                            disabled={unlocking}
                                            className="mt-1 flex items-center gap-1 rounded bg-orange-900/30 px-1.5 py-0.5 text-xs text-orange-400 hover:bg-orange-900/50 transition-colors disabled:opacity-60"
                                            title="Unlock calculated paces — $5"
                                          >
                                            <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
                                              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                                            </svg>
                                            {unlocking ? '…' : 'Unlock paces'}
                                          </button>
                                        ) : null}
                                        {dayWorkout.completed && (
                                          <div className="text-xs text-emerald-400 mt-1">✓ Completed</div>
                                        )}
                                        {dayWorkout.skipped && (
                                          <div className="text-xs text-slate-500 mt-1">Skipped</div>
                                        )}
                                      </>
                                    ) : (
                                      <div className="text-slate-600 text-sm">Rest</div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
              
              {/* Legend */}
              <div className="mt-8 p-4 bg-slate-800/30 rounded-lg">
                <h3 className="text-sm font-semibold text-slate-400 mb-3">Workout Types</h3>
                <div className="flex flex-wrap gap-3">
                  {[
                    { type: 'easy', label: 'Easy' },
                    { type: 'long', label: 'Long Run' },
                    { type: 'threshold', label: 'Threshold' },
                    { type: 'intervals', label: 'Intervals' },
                    { type: 'long_mp', label: 'MP Work' },
                    { type: 'race', label: 'Race' },
                  ].map(({ type, label }) => {
                    const style = workoutStyles[type];
                    return (
                      <div key={type} className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${style.bg}`} />
                        <span className={`text-xs ${style.text}`}>{label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
