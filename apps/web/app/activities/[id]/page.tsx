'use client';

/**
 * Activity Detail Page
 * 
 * Shows complete analysis for a single run:
 * - Basic metrics (distance, time, pace, HR)
 * - Splits visualization
 * - Run Context Analysis (the core intelligence)
 * - Perception prompt if applicable
 */

import React from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { API_CONFIG } from '@/lib/api/config';
import RunContextAnalysis from '@/components/activities/RunContextAnalysis';
import { SplitsChart } from '@/components/activities/SplitsChart';
import { PerceptionPrompt } from '@/components/activities/PerceptionPrompt';
import { WorkoutTypeSelector } from '@/components/activities/WorkoutTypeSelector';

interface Activity {
  id: string;
  name: string;
  sport_type: string;
  start_time: string;
  distance_m: number;
  elapsed_time_s: number;
  moving_time_s: number;
  average_hr: number | null;
  max_hr: number | null;
  average_cadence: number | null;
  total_elevation_gain_m: number | null;
  average_temp_c: number | null;
  strava_activity_id: string | null;
  
  // Workout classification
  workout_type: string | null;
  workout_zone: string | null;
  workout_confidence: number | null;
  intensity_score: number | null;
  expected_rpe_range: [number, number] | null;
  
  // Race info
  is_race: boolean | null;
  race_confidence: number | null;
  performance_percentage: number | null;
}

interface Split {
  split_number: number;
  distance: number | null;
  elapsed_time: number | null;
  moving_time: number | null;
  average_heartrate: number | null;
  max_heartrate: number | null;
  average_cadence: number | null;
  gap_seconds_per_mile: number | null;
}

export default function ActivityDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { token, isAuthenticated, isLoading: authLoading } = useAuth();
  const { formatDistance, formatPace, formatElevation, units, distanceUnitShort, paceUnit } = useUnits();
  const activityId = params.id as string;

  const { data: activity, isLoading: activityLoading, error: activityError } = useQuery<Activity>({
    queryKey: ['activity', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Failed to fetch activity');
      return res.json();
    },
    enabled: !authLoading && !!token && !!activityId,
  });

  const { data: splits } = useQuery<Split[]>({
    queryKey: ['activity-splits', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/splits`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !authLoading && !!token && !!activityId,
  });

  // Redirect if not authenticated (after auth loading is done)
  React.useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Show loading while auth is being determined
  if (authLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse space-y-6">
            <div className="h-10 bg-gray-800 rounded w-2/3"></div>
            <div className="h-6 bg-gray-800 rounded w-1/3"></div>
          </div>
        </div>
      </div>
    );
  }

  if (activityLoading) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse space-y-6">
            <div className="h-10 bg-gray-800 rounded w-2/3"></div>
            <div className="h-6 bg-gray-800 rounded w-1/3"></div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-24 bg-gray-800 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (activityError || !activity) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-400 mb-2">Activity Not Found</h2>
            <p className="text-gray-400">This activity could not be loaded.</p>
            <button
              onClick={() => router.push('/dashboard')}
              className="mt-4 px-4 py-2 bg-gray-800 text-white rounded hover:bg-gray-700 transition-colors"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Format helpers
  const formatDuration = (seconds: number): string => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.round(seconds % 60);
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Calculate pace in seconds/km from activity data
  const getPaceSecondsPerKm = (seconds: number, meters: number): number | null => {
    if (!seconds || !meters) return null;
    return seconds / (meters / 1000);
  };

  const formatDate = (dateStr: string): string => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatTime = (dateStr: string): string => {
    return new Date(dateStr).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.back()}
            className="text-gray-400 hover:text-white mb-4 flex items-center gap-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
          
          <h1 className="text-3xl font-bold text-white mb-2">{activity.name}</h1>
          <p className="text-gray-400">
            {formatDate(activity.start_time)} at {formatTime(activity.start_time)}
          </p>
          
          {activity.strava_activity_id && (
            <a
              href={`https://www.strava.com/activities/${activity.strava_activity_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-orange-400 hover:text-orange-300 text-sm mt-2"
            >
              View on Strava
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}
          
          {/* Context Comparison Button - The Differentiator */}
          <div className="mt-4">
            <Link
              href={`/compare/context/${activityId}`}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white font-semibold rounded-lg shadow-lg shadow-orange-500/25 transition-all hover:shadow-orange-500/40 hover:scale-[1.02]"
            >
              <span className="text-lg">👻</span>
              Compare to Similar Runs
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
            <p className="text-xs text-gray-500 mt-1.5">
              See how this run compares to your similar efforts
            </p>
          </div>
        </div>

        {/* Workout Type Classification */}
        <div className="mb-8">
          <WorkoutTypeSelector activityId={activityId} />
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Distance"
            value={formatDistance(activity.distance_m)}
          />
          <MetricCard
            label="Duration"
            value={formatDuration(activity.moving_time_s)}
          />
          <MetricCard
            label="Pace"
            value={formatPace(getPaceSecondsPerKm(activity.moving_time_s, activity.distance_m))}
          />
          <MetricCard
            label="Avg HR"
            value={activity.average_hr?.toString() || '--'}
            unit="bpm"
          />
        </div>

        {/* Secondary Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Max HR"
            value={activity.max_hr?.toString() || '--'}
            unit="bpm"
            secondary
          />
          <MetricCard
            label="Cadence"
            value={activity.average_cadence?.toString() || '--'}
            unit="spm"
            secondary
          />
          <MetricCard
            label="Elevation"
            value={formatElevation(activity.total_elevation_gain_m)}
            secondary
          />
          <MetricCard
            label="Temperature"
            value={activity.average_temp_c?.toFixed(0) || '--'}
            unit="°C"
            secondary
          />
        </div>

        {/* Splits Chart */}
        {splits && splits.length > 0 && (
          <div className="bg-gray-800/50 rounded-lg p-6 mb-8">
            <h2 className="text-xl font-bold text-white mb-4">Splits</h2>
            <SplitsChart splits={splits} />
          </div>
        )}

        {/* Perception Prompt with Expected RPE */}
        <div className="mb-8">
          <PerceptionPrompt 
            activityId={activityId}
            workoutType={activity.workout_type || undefined}
            expectedRpeRange={activity.expected_rpe_range || undefined}
          />
        </div>

        {/* Run Context Analysis - The Core Intelligence */}
        <div className="mb-8">
          <h2 className="text-xl font-bold text-white mb-4">Context Analysis</h2>
          <RunContextAnalysis activityId={activityId} />
        </div>
      </div>
    </div>
  );
}

// ============ Sub-Components ============

function MetricCard({
  label,
  value,
  unit,
  secondary = false,
}: {
  label: string;
  value: string;
  unit?: string;
  secondary?: boolean;
}) {
  return (
    <div className={`rounded-lg p-4 ${secondary ? 'bg-gray-800/30' : 'bg-gray-800/50'}`}>
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className={`font-bold ${secondary ? 'text-xl text-gray-300' : 'text-2xl text-white'}`}>
        {value}
        {unit && <span className="text-gray-500 text-sm font-normal ml-1">{unit}</span>}
      </p>
    </div>
  );
}
