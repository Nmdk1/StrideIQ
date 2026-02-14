'use client';

/**
 * Activity Detail Page — RSI Layer 2
 *
 * Restructured around the Run Shape Canvas as the centerpiece.
 * Spec: docs/specs/RSI_WIRING_SPEC.md (Layer 2)
 *
 * Layout (top to bottom):
 *   1. Header (back + name + date + Strava link)
 *   2. Run Shape Canvas (hero — full width)
 *   3. Coachable Moments (gated: confidence >= 0.8 AND moments.length > 0)
 *   4. Reflection Prompt (3-tap: harder | expected | easier)
 *   5. Metrics Ribbon (compact horizontal strip)
 *   6. Plan Comparison (conditional — from stream analysis)
 *   7. "Why This Run?" (existing component)
 *   8. "Compare to Similar" (existing link)
 *   9. Splits Table (secondary position)
 *  10. Context Analysis (existing component)
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { API_CONFIG } from '@/lib/api/config';
import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';
import { useStreamAnalysis, isAnalysisData } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { CoachableMoments } from '@/components/activities/rsi/CoachableMoments';
import { ReflectionPrompt } from '@/components/activities/ReflectionPrompt';
import RunContextAnalysis from '@/components/activities/RunContextAnalysis';
import { SplitsChart } from '@/components/activities/SplitsChart';
import { SplitsTable } from '@/components/activities/SplitsTable';
import { WorkoutTypeSelector } from '@/components/activities/WorkoutTypeSelector';
import { WhyThisRun } from '@/components/activities/WhyThisRun';

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
  temperature_f: number | null;
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
  
  // ADR-033: Narrative context
  narrative: string | null;
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

function normalizeCadenceToSpm(raw: number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const v = Number(raw);
  if (!isFinite(v) || v <= 0) return null;
  return v < 120 ? v * 2 : v;
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

  // --- Stream analysis data (for coachable moments + plan comparison) ---
  // Must be called before any conditional returns (React hooks rules)
  const streamAnalysis = useStreamAnalysis(activityId);
  const analysisData = isAnalysisData(streamAnalysis.data) ? streamAnalysis.data : null;
  const [showSecondaryMetrics, setShowSecondaryMetrics] = useState(false);

  // Redirect if not authenticated (after auth loading is done)
  React.useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Show loading while auth is being determined
  if (authLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse space-y-6">
            <div className="h-10 bg-slate-800 rounded w-2/3"></div>
            <div className="h-6 bg-slate-800 rounded w-1/3"></div>
          </div>
        </div>
      </div>
    );
  }

  if (activityLoading) {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse space-y-6">
            <div className="h-10 bg-slate-800 rounded w-2/3"></div>
            <div className="h-6 bg-slate-800 rounded w-1/3"></div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-24 bg-slate-800 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (activityError || !activity) {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-400 mb-2">Activity Not Found</h2>
            <p className="text-slate-400">This activity could not be loaded.</p>
            <button
              onClick={() => router.push('/dashboard')}
              className="mt-4 px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 transition-colors"
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

  // Format minutes (from backend PlanComparison) to h:mm:ss display
  const formatMinutesToDuration = (minutes: number): string => {
    const totalSeconds = Math.round(minutes * 60);
    return formatDuration(totalSeconds);
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
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* ── 1. Header ── */}
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="text-slate-400 hover:text-white mb-4 flex items-center gap-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
          
          <h1 className="text-3xl font-bold text-white mb-1">{activity.name}</h1>
          <p className="text-slate-400 text-sm">
            {formatDate(activity.start_time)} at {formatTime(activity.start_time)}
            {activity.strava_activity_id && (
              <>
                {' · '}
                <a
                  href={`https://www.strava.com/activities/${activity.strava_activity_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-orange-400 hover:text-orange-300"
                >
                  Strava ↗
                </a>
              </>
            )}
          </p>
        </div>

        {/* ── 2. Run Shape Canvas (Hero) ── */}
        <div className="mb-6">
          <RunShapeCanvas activityId={activityId} />
        </div>

        {/* ── 3. Coachable Moments (gated: confidence >= 0.8 AND moments.length > 0) ── */}
        {analysisData && (
          <CoachableMoments
            moments={analysisData.moments}
            confidence={analysisData.confidence}
            className="mb-6"
          />
        )}

        {/* ── 4. Reflection Prompt ── */}
        <ReflectionPrompt activityId={activityId} className="mb-6" />

        {/* ── 5. Metrics Ribbon (compact horizontal strip) ── */}
        <div className="mb-6">
          <div className="flex items-center gap-4 overflow-x-auto pb-1">
            <MetricPill label="Distance" value={formatDistance(activity.distance_m)} />
            <MetricPill label="Duration" value={formatDuration(activity.moving_time_s)} />
            <MetricPill
              label="Pace"
              value={formatPace(getPaceSecondsPerKm(activity.moving_time_s, activity.distance_m))}
            />
            <MetricPill
              label="Avg HR"
              value={activity.average_hr?.toString() || '--'}
              unit="bpm"
            />
            <MetricPill
              label="Elevation"
              value={formatElevation(activity.total_elevation_gain_m)}
            />
            <MetricPill
              label="Cadence"
              value={
                normalizeCadenceToSpm(activity.average_cadence) !== null
                  ? Math.round(normalizeCadenceToSpm(activity.average_cadence) as number).toString()
                  : '--'
              }
              unit="spm"
            />
          </div>
          {/* Secondary metrics expand */}
          <button
            onClick={() => setShowSecondaryMetrics(!showSecondaryMetrics)}
            className="text-xs text-slate-500 hover:text-slate-300 mt-2 transition-colors"
          >
            {showSecondaryMetrics ? 'Hide details ▲' : 'More details ▼'}
          </button>
          {showSecondaryMetrics && (
            <div className="flex items-center gap-4 mt-2 overflow-x-auto pb-1">
              <MetricPill label="Max HR" value={activity.max_hr?.toString() || '--'} unit="bpm" secondary />
              <MetricPill label="Temp" value={activity.temperature_f?.toFixed(0) || '--'} unit="°F" secondary />
              <MetricPill label="Workout" value={activity.workout_type?.replace(/_/g, ' ') || '--'} secondary />
            </div>
          )}
        </div>

        {/* ── 6. Plan Comparison (conditional — from stream analysis) ── */}
        {/* Field names match backend PlanComparison dataclass exactly:
            planned_duration_min, actual_duration_min, planned_distance_km,
            actual_distance_km, planned_pace_s_km, actual_pace_s_km,
            planned_interval_count, detected_work_count */}
        {analysisData?.plan_comparison && (
          <div className="mb-6 rounded-lg bg-slate-800/30 border border-slate-700/30 p-4">
            <h3 className="text-sm font-medium text-slate-400 mb-3">Plan vs Actual</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {analysisData.plan_comparison.planned_duration_min != null && analysisData.plan_comparison.actual_duration_min != null && (
                <PlanComparisonCell
                  label="Duration"
                  planned={formatMinutesToDuration(analysisData.plan_comparison.planned_duration_min)}
                  actual={formatMinutesToDuration(analysisData.plan_comparison.actual_duration_min)}
                />
              )}
              {analysisData.plan_comparison.planned_distance_km != null && analysisData.plan_comparison.actual_distance_km != null && (
                <PlanComparisonCell
                  label="Distance"
                  planned={formatDistance(analysisData.plan_comparison.planned_distance_km * 1000)}
                  actual={formatDistance(analysisData.plan_comparison.actual_distance_km * 1000)}
                />
              )}
              {analysisData.plan_comparison.planned_pace_s_km != null && analysisData.plan_comparison.actual_pace_s_km != null && (
                <PlanComparisonCell
                  label="Pace"
                  planned={formatPace(analysisData.plan_comparison.planned_pace_s_km)}
                  actual={formatPace(analysisData.plan_comparison.actual_pace_s_km)}
                />
              )}
              {analysisData.plan_comparison.planned_interval_count != null && analysisData.plan_comparison.detected_work_count != null && (
                <PlanComparisonCell
                  label="Intervals"
                  planned={String(analysisData.plan_comparison.planned_interval_count)}
                  actual={String(analysisData.plan_comparison.detected_work_count)}
                />
              )}
            </div>
          </div>
        )}

        {/* ── 7. Workout Type Classification ── */}
        <div className="mb-6">
          <WorkoutTypeSelector activityId={activityId} />
        </div>

        {/* ── 8. "Why This Run?" + Context Analysis ── */}
        <div className="mb-6">
          <WhyThisRun activityId={activityId} className="mb-4" />
          <RunContextAnalysis activityId={activityId} />
        </div>

        {/* ── 9. "Compare to Similar" ── */}
        <div className="mb-6">
          <Link
            href={`/compare/context/${activityId}`}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white font-semibold rounded-lg shadow-lg shadow-orange-500/25 transition-all hover:shadow-orange-500/40 hover:scale-[1.02]"
          >
            Compare to Similar Runs
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>

        {/* ── 10. Splits (secondary position) ── */}
        {splits && splits.length > 0 && (
          <div className="bg-slate-800/50 rounded-lg p-6 mb-6 border border-slate-700/50">
            <h2 className="text-lg font-bold text-white">Splits / Laps</h2>
            <div className="mt-4">
              <SplitsChart splits={splits} className="mb-4" />
              <SplitsTable splits={splits} />
            </div>
          </div>
        )}

        {/* ── Narrative Context (secondary — canvas is now the hero) ── */}
        {activity.narrative && (
          <div className="mb-6 px-4 py-3 bg-slate-800/30 border border-slate-700/30 rounded-lg">
            <p className="text-sm text-slate-400 italic leading-relaxed">
              &ldquo;{activity.narrative}&rdquo;
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Sub-Components ============

/** Compact metric pill for the horizontal ribbon */
function MetricPill({
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
    <div className="flex-shrink-0">
      <p className={`text-xs ${secondary ? 'text-slate-500' : 'text-slate-400'}`}>{label}</p>
      <p className={`font-semibold whitespace-nowrap ${secondary ? 'text-sm text-slate-400' : 'text-base text-white'}`}>
        {value}
        {unit && <span className="text-slate-500 text-xs font-normal ml-0.5">{unit}</span>}
      </p>
    </div>
  );
}

/** Plan comparison cell (planned vs actual) */
function PlanComparisonCell({
  label,
  planned,
  actual,
}: {
  label: string;
  planned: string;
  actual: string;
}) {
  return (
    <div>
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-sm text-white">{actual}</p>
      <p className="text-xs text-slate-500">planned: {planned}</p>
    </div>
  );
}
