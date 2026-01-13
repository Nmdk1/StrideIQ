'use client';

/**
 * Home Page - The Glance Layer
 * 
 * What athletes see when they log in:
 * - Today's workout + why it matters
 * - Yesterday's insight (one key takeaway)
 * - Week progress at a glance
 * 
 * TONE: Sparse, direct, data-driven. No prescriptiveness.
 * EMPTY STATES: Helpful, action-oriented, no guilt.
 */

import React from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useHomeData } from '@/lib/hooks/queries/home';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

// Workout type colors - minimal palette
const WORKOUT_COLORS: Record<string, string> = {
  rest: 'text-gray-500',
  recovery: 'text-gray-400',
  easy: 'text-emerald-400',
  easy_strides: 'text-emerald-400',
  strides: 'text-emerald-400',
  medium_long: 'text-blue-400',
  long: 'text-blue-400',
  long_mp: 'text-blue-400',
  threshold: 'text-orange-400',
  tempo: 'text-orange-400',
  intervals: 'text-red-400',
  vo2max: 'text-red-400',
  race: 'text-pink-400',
};

function getWorkoutColor(type?: string): string {
  if (!type) return 'text-gray-400';
  return WORKOUT_COLORS[type] || 'text-gray-400';
}

function formatWorkoutType(type?: string): string {
  if (!type) return '';
  const labels: Record<string, string> = {
    easy: 'Easy',
    easy_strides: 'Easy + Strides',
    strides: 'Strides',
    medium_long: 'Medium Long',
    long: 'Long Run',
    long_mp: 'Long + MP',
    threshold: 'Threshold',
    tempo: 'Tempo',
    intervals: 'Intervals',
    vo2max: 'VO2max',
    rest: 'Rest',
    recovery: 'Recovery',
    race: 'Race',
  };
  return labels[type] || type.replace(/_/g, ' ');
}

export default function HomePage() {
  const { data, isLoading, error } = useHomeData();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-gray-900">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-900 text-gray-100 p-4">
          <div className="max-w-2xl mx-auto pt-12">
            <p className="text-gray-400">Could not load data. Try again.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const { today, yesterday, week } = data;
  const hasAnyData = yesterday.has_activity || week.completed_mi > 0;
  const isNewUser = !hasAnyData && !today.has_workout;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <div className="max-w-2xl mx-auto px-4 py-6 md:py-10">
          
          {/* New User Onboarding Banner */}
          {isNewUser && (
            <section className="mb-8">
              <div className="bg-gradient-to-r from-orange-900/30 to-orange-800/20 border border-orange-700/30 rounded-lg p-5">
                <h2 className="text-lg font-medium text-orange-300 mb-2">
                  Welcome to StrideIQ
                </h2>
                <p className="text-sm text-gray-300 mb-4 leading-relaxed">
                  Connect your Strava account to import your runs. We&apos;ll analyze your data and show you what&apos;s actually working.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link 
                    href="/settings"
                    className="inline-flex items-center px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Connect Strava
                  </Link>
                  <Link 
                    href="/calendar"
                    className="inline-flex items-center px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors"
                  >
                    Create Training Plan
                  </Link>
                </div>
              </div>
            </section>
          )}
          
          {/* Today's Workout - Hero Section */}
          <section className="mb-8">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">
              {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
            </p>
            
            {today.has_workout ? (
              <div className="bg-gray-800 border border-gray-700 rounded-lg p-5">
                {/* Workout Header */}
                <div className="mb-4">
                  <h1 className={`text-2xl md:text-3xl font-semibold ${getWorkoutColor(today.workout_type)}`}>
                    {today.title || formatWorkoutType(today.workout_type)}
                  </h1>
                  <p className="text-gray-400 text-base mt-2">
                    {today.distance_mi && `${today.distance_mi} mi`}
                    {today.distance_mi && today.pace_guidance && ' · '}
                    {today.pace_guidance}
                  </p>
                </div>
                
                {/* Why This Workout */}
                {today.why_context && (
                  <div className="bg-gray-900/50 rounded-lg p-4 mb-4">
                    <p className="text-sm text-gray-300 leading-relaxed">{today.why_context}</p>
                  </div>
                )}
                
                {/* Week/Phase Context */}
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  {today.week_number && (
                    <span>Week {today.week_number}</span>
                  )}
                  {today.phase && (
                    <span className="text-orange-400/70">{today.phase}</span>
                  )}
                </div>
                
                {/* Action */}
                <div className="mt-4 pt-4 border-t border-gray-700/50">
                  <Link 
                    href="/calendar"
                    className="text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    View in Calendar →
                  </Link>
                </div>
              </div>
            ) : (
              <div className="bg-gray-800 border border-gray-700 rounded-lg p-5">
                <h1 className="text-xl md:text-2xl font-medium text-gray-300 mb-2">
                  No workout scheduled
                </h1>
                <p className="text-gray-500 text-sm mb-4">
                  {hasAnyData 
                    ? "Good day for easy recovery or complete rest. Your call."
                    : "Connect Strava or create a plan to see workouts here."
                  }
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link 
                    href="/calendar"
                    className="text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    View Calendar →
                  </Link>
                  {!hasAnyData && (
                    <Link 
                      href="/settings"
                      className="text-sm text-orange-400 hover:text-orange-300 transition-colors"
                    >
                      Connect Strava →
                    </Link>
                  )}
                </div>
              </div>
            )}
          </section>
          
          {/* Yesterday's Insight */}
          <section className="mb-8">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Yesterday</p>
            
            {yesterday.has_activity ? (
              <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-base font-medium text-white">
                      {yesterday.activity_name}
                    </p>
                    <p className="text-sm text-gray-500">
                      {yesterday.distance_mi && `${yesterday.distance_mi} mi`}
                      {yesterday.distance_mi && yesterday.pace_per_mi && ' · '}
                      {yesterday.pace_per_mi}
                    </p>
                  </div>
                  {yesterday.activity_id && (
                    <Link 
                      href={`/activities/${yesterday.activity_id}`}
                      className="text-sm text-gray-500 hover:text-white transition-colors"
                    >
                      Details →
                    </Link>
                  )}
                </div>
                
                {yesterday.insight && (
                  <p className="text-sm text-gray-300 mt-3 leading-relaxed">{yesterday.insight}</p>
                )}
              </div>
            ) : (
              <div className="bg-gray-800/30 border border-gray-700/30 rounded-lg p-4">
                <p className="text-base text-gray-400 mb-2">No activity yesterday</p>
                <p className="text-sm text-gray-500">
                  {hasAnyData 
                    ? "Rest day. Cool."
                    : "Sync an activity to see insights here."
                  }
                </p>
              </div>
            )}
          </section>
          
          {/* Week Progress */}
          <section className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-gray-500 uppercase tracking-wider">This Week</p>
              {week.week_number && week.total_weeks && (
                <p className="text-xs text-gray-500">
                  Week {week.week_number}/{week.total_weeks}
                  {week.phase && <span className="text-orange-400/70 ml-2">{week.phase}</span>}
                </p>
              )}
            </div>
            
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
              {/* Day Pills - larger touch targets for mobile */}
              <div className="flex justify-between gap-1 mb-4">
                {week.days.map((day) => (
                  <div 
                    key={day.date}
                    className={`
                      flex-1 text-center py-3 px-1 rounded-lg
                      ${day.is_today ? 'bg-blue-900/40 ring-2 ring-blue-500/50' : ''}
                      ${day.completed ? 'bg-emerald-900/30' : 'bg-gray-800/50'}
                    `}
                  >
                    <div className="text-xs text-gray-500 mb-1">{day.day_abbrev}</div>
                    <div className={`text-sm font-medium ${day.completed ? 'text-emerald-400' : getWorkoutColor(day.workout_type)}`}>
                      {day.completed && day.distance_mi ? (
                        <span>✓ {day.distance_mi}</span>
                      ) : day.workout_type === 'rest' ? (
                        <span className="text-gray-600">—</span>
                      ) : day.distance_mi ? (
                        <span>{day.distance_mi}</span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              
              {week.status === 'no_plan' ? (
                /* Empty state for no plan */
                <div className="text-center py-2">
                  <p className="text-sm text-gray-400 mb-2">No training plan active</p>
                  <p className="text-xs text-gray-500 mb-3">
                    {week.completed_mi > 0 
                      ? `${week.completed_mi} mi logged this week. Data accruing.`
                      : "Connect Strava to track activities, or create a plan."
                    }
                  </p>
                  <div className="flex justify-center gap-4">
                    <Link 
                      href="/calendar"
                      className="text-xs text-gray-400 hover:text-white transition-colors"
                    >
                      Create Plan →
                    </Link>
                    {week.completed_mi === 0 && (
                      <Link 
                        href="/settings"
                        className="text-xs text-orange-400 hover:text-orange-300 transition-colors"
                      >
                        Connect Strava →
                      </Link>
                    )}
                  </div>
                </div>
              ) : (
                <>
                  {/* Progress Bar */}
                  {week.planned_mi > 0 && (
                    <div className="mb-3">
                      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full transition-all ${
                            week.status === 'ahead' ? 'bg-emerald-500' :
                            week.status === 'on_track' ? 'bg-blue-500' :
                            week.status === 'behind' ? 'bg-orange-500' : 'bg-gray-600'
                          }`}
                          style={{ width: `${Math.min(100, week.progress_pct)}%` }}
                        />
                      </div>
                    </div>
                  )}
                  
                  {/* Stats */}
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">
                      {week.completed_mi} / {week.planned_mi} mi
                    </span>
                    <span className={`text-sm font-medium ${
                      week.status === 'ahead' ? 'text-emerald-400' :
                      week.status === 'on_track' ? 'text-blue-400' :
                      week.status === 'behind' ? 'text-orange-400' :
                      'text-gray-500'
                    }`}>
                      {week.status === 'ahead' && 'Ahead'}
                      {week.status === 'on_track' && 'On track'}
                      {week.status === 'behind' && 'Behind'}
                    </span>
                  </div>
                  
                  {/* Trajectory sentence */}
                  {week.trajectory_sentence && (
                    <p className="text-sm text-gray-400 mt-3">{week.trajectory_sentence}</p>
                  )}
                </>
              )}
            </div>
            
            {/* Calendar Link */}
            <div className="mt-3 text-right">
              <Link 
                href="/calendar"
                className="text-sm text-gray-500 hover:text-white transition-colors"
              >
                Full Calendar →
              </Link>
            </div>
          </section>
          
          {/* Quick Links - larger touch targets */}
          <section className="grid grid-cols-2 gap-3">
            <Link 
              href="/analytics"
              className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-5 hover:bg-gray-800 transition-colors active:bg-gray-700"
            >
              <p className="text-base font-medium text-white">Analytics</p>
              <p className="text-sm text-gray-500 mt-1">Trends & correlations</p>
            </Link>
            <Link 
              href="/coach"
              className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-5 hover:bg-gray-800 transition-colors active:bg-gray-700"
            >
              <p className="text-base font-medium text-white">Coach</p>
              <p className="text-sm text-gray-500 mt-1">Ask questions</p>
            </Link>
          </section>
          
        </div>
      </div>
    </ProtectedRoute>
  );
}
