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
  baseline_vdot: number | null;
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
                  {plan.baseline_vdot && (
                    <span className="px-2 py-1 bg-orange-600/30 text-orange-300 rounded text-xs">
                      VDOT {plan.baseline_vdot}
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
                                        {dayWorkout.coach_notes && (
                                          <div className="text-xs text-slate-500 mt-1 truncate" title={dayWorkout.coach_notes}>
                                            {dayWorkout.coach_notes}
                                          </div>
                                        )}
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
