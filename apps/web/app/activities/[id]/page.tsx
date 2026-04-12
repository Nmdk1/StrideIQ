'use client';

/**
 * Activity Detail Page — RSI Layer 2
 *
 * Restructured around the Run Shape Canvas as the centerpiece.
 * Spec: docs/specs/RSI_WIRING_SPEC.md (Layer 2)
 *
 * Runs: tabbed layout (Overview default) — see BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md
 */

import React, { useState, useRef, useEffect, useSyncExternalStore } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { API_CONFIG } from '@/lib/api/config';
import { RunShapeCanvas } from '@/components/activities/rsi/RunShapeCanvas';
import { useStreamAnalysis, isAnalysisData } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { ReflectionPrompt } from '@/components/activities/ReflectionPrompt';
import { WorkoutTypeSelector } from '@/components/activities/WorkoutTypeSelector';
import { PerceptionPrompt } from '@/components/activities/PerceptionPrompt';
import { GarminBadge } from '@/components/integrations/GarminBadge';
import { RuntoonCard } from '@/components/activities/RuntoonCard';
import { CyclingDetail, StrengthDetail, HikingDetail, FlexibilityDetail } from '@/components/activities/cross-training';
import type { CrossTrainingActivity } from '@/components/activities/cross-training';
import RouteContext from '@/components/activities/map/RouteContext';
import { StreamHoverProvider } from '@/lib/context/StreamHoverContext';
import { ActivityTabs, type ActivityTabId } from '@/components/activities/ActivityTabs';

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
  dew_point_f: number | null;
  humidity_pct: number | null;
  weather_condition: string | null;
  heat_adjustment_pct: number | null;
  strava_activity_id: string | null;
  provider: string | null;
  device_name: string | null;
  
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

  // Activity Identity
  shape_sentence: string | null;
  athlete_title: string | null;
  resolved_title: string | null;

  // Pre-activity wellness
  pre_sleep_h: number | null;
  pre_sleep_score: number | null;
  pre_resting_hr: number | null;
  pre_recovery_hrv: number | null;
  pre_overnight_hrv: number | null;

  // Cross-training fields (non-run only)
  strength_session_type?: string | null;
  session_detail?: Record<string, unknown> | null;
  tss?: number | null;
  tss_method?: string | null;
  intensity_factor?: number | null;
  weekly_context?: { running_activities: number; cross_training_activities: number } | null;
  exercise_sets?: Array<{
    set_order: number;
    exercise_name: string;
    exercise_category: string;
    movement_pattern: string;
    muscle_group: string | null;
    is_unilateral: boolean;
    set_type: string;
    reps: number | null;
    weight_kg: number | null;
    duration_s: number | null;
    estimated_1rm_kg: number | null;
  }>;

  // Device-level metrics
  steps: number | null;
  active_kcal: number | null;
  avg_cadence_device: number | null;
  max_cadence: number | null;

  // GPS / map
  gps_track: [number, number][] | null;
  start_coords: [number, number] | null;
}

import type { Split, SplitsResponse } from '@/lib/types/splits';

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

  const { data: splitsResponse } = useQuery<SplitsResponse>({
    queryKey: ['activity-splits', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/splits`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) return { splits: [], interval_summary: null };
      return res.json();
    },
    enabled: !authLoading && !!token && !!activityId,
  });

  const splits = splitsResponse?.splits ?? null;
  const intervalSummary = splitsResponse?.interval_summary ?? null;

  const { data: findings } = useQuery<{ text: string; domain: string; confidence_tier: string; evidence_summary?: string | null }[]>({
    queryKey: ['activity-findings', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/findings`,
        { headers: { Authorization: `Bearer ${token}` } }
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
  const [showDetails, setShowDetails] = useState(false);
  const [activeTab, setActiveTab] = useState<ActivityTabId>('overview');
  /** Mobile: user toggles map; desktop (md+): always show — do not mount Leaflet while `display:none` (zero-size fit). */
  const [routeMapOpen, setRouteMapOpen] = useState(false);
  /** Avoid SSR/client mismatch from matchMedia; first paint matches server (no map), then client commits. */
  const [clientReady, setClientReady] = useState(false);
  useEffect(() => {
    setClientReady(true);
  }, []);
  const isMdUp = useSyncExternalStore(
    onStoreChange => {
      if (typeof window === 'undefined') return () => {};
      const mq = window.matchMedia('(min-width: 768px)');
      mq.addEventListener('change', onStoreChange);
      return () => mq.removeEventListener('change', onStoreChange);
    },
    () => window.matchMedia('(min-width: 768px)').matches,
    () => false,
  );
  const showRouteMap = clientReady && (isMdUp || routeMapOpen);

  // Title editing
  const queryClient = useQueryClient();
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState('');
  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [isEditingTitle]);

  const titleMutation = useMutation({
    mutationFn: async (newTitle: string | null) => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/title`,
        {
          method: 'PUT',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ title: newTitle }),
        }
      );
      if (!res.ok) throw new Error('Failed to update title');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activity', activityId] });
      queryClient.invalidateQueries({ queryKey: ['activities'] });
      queryClient.invalidateQueries({ queryKey: ['home'] });
      setIsEditingTitle(false);
    },
  });

  const displayTitle = activity?.resolved_title ?? activity?.name ?? 'Run';

  const handleStartEdit = () => {
    setEditTitleValue(displayTitle);
    setIsEditingTitle(true);
  };

  const handleSaveTitle = () => {
    const trimmed = editTitleValue.trim();
    titleMutation.mutate(trimmed || null);
  };

  const handleCancelEdit = () => {
    setIsEditingTitle(false);
  };

  const handleResetTitle = () => {
    titleMutation.mutate(null);
  };

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
              onClick={() => router.push('/home')}
              className="mt-4 px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 transition-colors"
            >
              Back to Home
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
      <div className="max-w-7xl mx-auto px-4 py-8">
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
          
          {isEditingTitle ? (
            <div className="mb-1">
              <input
                ref={titleInputRef}
                type="text"
                value={editTitleValue}
                onChange={(e) => setEditTitleValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveTitle();
                  if (e.key === 'Escape') handleCancelEdit();
                }}
                maxLength={200}
                className="w-full text-2xl font-bold bg-slate-800 text-white border border-slate-600 rounded-lg px-3 py-1.5 focus:outline-none focus:border-emerald-500"
              />
              <div className="flex items-center gap-2 mt-2">
                <button
                  onClick={handleSaveTitle}
                  disabled={titleMutation.isPending}
                  className="px-3 py-1 text-sm bg-emerald-600 hover:bg-emerald-700 text-white rounded-md transition-colors disabled:opacity-50"
                >
                  Save
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="px-3 py-1 text-sm text-slate-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                {activity.athlete_title && activity.shape_sentence && (
                  <button
                    onClick={handleResetTitle}
                    className="px-3 py-1 text-sm text-slate-500 hover:text-emerald-400 transition-colors ml-auto"
                  >
                    Reset to auto-detected
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="group flex items-center gap-2 mb-1">
              <h1 className="text-3xl font-bold text-white">{displayTitle}</h1>
              <button
                onClick={handleStartEdit}
                className="text-slate-500 hover:text-emerald-400 transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100"
                aria-label="Edit title"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
            </div>
          )}
          <p className="text-slate-400 text-sm">
            {formatDate(activity.start_time)} at {formatTime(activity.start_time)}
          </p>
          {activity.provider === 'garmin' && (
            <GarminBadge deviceName={activity.device_name} size="md" className="mt-2" />
          )}
        </div>

        {/* ── Sport branching: non-run activities get dedicated layouts ── */}
        {activity.sport_type && activity.sport_type !== 'run' ? (
          <div className="mb-6">
            {/* Map as hero for outdoor non-run sports */}
            {activity.gps_track && activity.gps_track.length > 1 && (
              <div className="mb-4">
                <RouteContext
                  activityId={activityId}
                  track={activity.gps_track}
                  startCoords={activity.start_coords}
                  sportType={activity.sport_type}
                  startTime={activity.start_time}
                  accentColor={
                    activity.sport_type === 'cycling' ? '#60a5fa' :
                    activity.sport_type === 'walking' ? '#2dd4bf' :
                    '#34d399'
                  }
                  weather={{
                    temperature_f: activity.temperature_f,
                    weather_condition: activity.weather_condition,
                    humidity_pct: activity.humidity_pct,
                    heat_adjustment_pct: activity.heat_adjustment_pct,
                  }}
                  distanceM={activity.distance_m}
                  durationS={activity.moving_time_s || activity.elapsed_time_s}
                  heatAdjustmentPct={activity.heat_adjustment_pct}
                />
              </div>
            )}
            {activity.sport_type === 'cycling' && <CyclingDetail activity={activity as unknown as CrossTrainingActivity} />}
            {activity.sport_type === 'strength' && <StrengthDetail activity={activity as unknown as CrossTrainingActivity} />}
            {(activity.sport_type === 'hiking' || activity.sport_type === 'walking') && <HikingDetail activity={activity as unknown as CrossTrainingActivity} />}
            {activity.sport_type === 'flexibility' && <FlexibilityDetail activity={activity as unknown as CrossTrainingActivity} />}
          </div>
        ) : (
        <StreamHoverProvider>
        {/* ── 2. Stats Banner — persistent header ── */}
        <div className="mb-3">
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
          {activity.heat_adjustment_pct != null && activity.heat_adjustment_pct > 3 && (
            <p className="text-xs text-amber-400/80 mt-1.5">
              🌡️ Heat slowed this run ~{activity.heat_adjustment_pct.toFixed(1)}% — your effort was better than the pace shows
            </p>
          )}
        </div>

        <GoingInCompactStrip activity={activity} />

        <ActivityTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          panels={{
            overview: (
              <>
                <div className="mb-4 -mx-4 sm:mx-0">
                  <RunShapeCanvas
                    activityId={activityId}
                    splits={splits ?? null}
                    intervalSummary={intervalSummary}
                    provider={activity.provider}
                    deviceName={activity.device_name}
                    heatAdjustmentPct={activity.heat_adjustment_pct}
                    temperatureF={activity.temperature_f}
                  />
                </div>
                <div
                  className="min-h-[88px] rounded-lg border border-dashed border-slate-600/40 bg-slate-800/20 mb-4 px-4 py-3"
                  aria-label="Insights for this chart"
                />
                {activity.gps_track && activity.gps_track.length > 1 && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between md:hidden mb-2 px-0">
                      <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Route</span>
                      <button
                        type="button"
                        onClick={() => setRouteMapOpen((v) => !v)}
                        className="text-sm text-orange-400/90 hover:text-orange-300"
                      >
                        {routeMapOpen ? 'Hide map' : 'Show map'}
                      </button>
                    </div>
                    {showRouteMap && (
                      <RouteContext
                        activityId={activityId}
                        track={activity.gps_track}
                        startCoords={activity.start_coords}
                        sportType={activity.sport_type || 'run'}
                        startTime={activity.start_time}
                        streamPoints={analysisData?.stream}
                        weather={{
                          temperature_f: activity.temperature_f,
                          weather_condition: activity.weather_condition,
                          humidity_pct: activity.humidity_pct,
                          heat_adjustment_pct: activity.heat_adjustment_pct,
                        }}
                        distanceM={activity.distance_m}
                        durationS={activity.moving_time_s || activity.elapsed_time_s}
                        heatAdjustmentPct={activity.heat_adjustment_pct}
                        mapAspectRatio="16 / 9"
                      />
                    )}
                  </div>
                )}
                <div className="mb-2">
                  <RuntoonCard activityId={activityId} />
                </div>
              </>
            ),
            splits: (
              <p className="text-slate-500 text-sm py-10 px-2 rounded-lg border border-dashed border-slate-700/40 bg-slate-800/10">
                Splits and elevation — Step 2.
              </p>
            ),
            analysis: (
              <p className="text-slate-500 text-sm py-10 px-2 rounded-lg border border-dashed border-slate-700/40 bg-slate-800/10">
                Drift, pace distribution, and plan vs actual — Step 4–5.
              </p>
            ),
            context: (
              <div className="space-y-4">
                {(activity.pre_recovery_hrv != null || activity.pre_resting_hr != null || activity.pre_sleep_h != null) && (
                  <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Going In</p>
                    <div className="flex flex-wrap gap-x-6 gap-y-1">
                      {activity.pre_recovery_hrv != null && (
                        <span className="text-sm text-slate-300">
                          <span className="text-slate-500">Recovery HRV</span>{' '}
                          <span className="font-medium">{activity.pre_recovery_hrv}</span>
                          <span className="text-slate-500 text-xs ml-0.5">ms</span>
                          {activity.pre_overnight_hrv != null && (
                            <span className="text-xs text-slate-500 ml-2">(overnight avg {activity.pre_overnight_hrv})</span>
                          )}
                        </span>
                      )}
                      {activity.pre_resting_hr != null && (
                        <span className="text-sm text-slate-300">
                          <span className="text-slate-500">RHR</span>{' '}
                          <span className="font-medium">{activity.pre_resting_hr}</span>
                          <span className="text-slate-500 text-xs ml-0.5">bpm</span>
                        </span>
                      )}
                      {activity.pre_sleep_h != null && (
                        <span className="text-sm text-slate-300">
                          <span className="text-slate-500">Sleep</span>{' '}
                          <span className="font-medium">{activity.pre_sleep_h.toFixed(1)}</span>
                          <span className="text-slate-500 text-xs ml-0.5">h</span>
                          {activity.pre_sleep_score != null && (
                            <span className="text-xs text-slate-500 ml-1">({activity.pre_sleep_score})</span>
                          )}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                {findings && findings.length > 0 && (
                  <div className="space-y-2">
                    {findings.map((f, i) => (
                      <div key={i} className="rounded-lg border border-slate-700/30 bg-slate-800/20 px-4 py-3">
                        <div className="flex items-start gap-2">
                          <span className="text-sm flex-shrink-0">🔬</span>
                          <div>
                            <p className="text-sm text-slate-300">{f.text}</p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {f.confidence_tier === 'strong' ? 'Strong' : 'Confirmed'} · {f.domain.replace(/_/g, ' ')}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {activity.narrative && (
                  <div className="px-4 py-3 bg-slate-800/30 border border-slate-700/30 rounded-lg">
                    <p className="text-sm text-slate-400 italic leading-relaxed">
                      &ldquo;{activity.narrative}&rdquo;
                    </p>
                  </div>
                )}
              </div>
            ),
            feedback: (
              <div className="space-y-4">
                <ReflectionPrompt activityId={activityId} />
                <PerceptionPrompt
                  activityId={activityId}
                  workoutType={activity.workout_type ?? undefined}
                  expectedRpeRange={activity.expected_rpe_range ?? undefined}
                />
                <WorkoutTypeSelector activityId={activityId} compact />
              </div>
            ),
          }}
        />

        {/* ── Plan vs actual (stays until Analysis tab consolidation in Step 4) ── */}
        <div className="mb-6 mt-8">
          <button
            onClick={() => setShowDetails((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
            data-testid="show-details-toggle"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform ${showDetails ? 'rotate-90' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {showDetails ? 'Hide details' : 'Show details'}
          </button>
        </div>

        {showDetails && analysisData?.plan_comparison && (
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
        </StreamHoverProvider>
        )}
      </div>
    </div>
  );
}

// ============ Helpers ============

function formatDeviceName(raw: string): string {
  return raw
    .replace(/([a-z])(\d)/g, '$1 $2')
    .replace(/(\d)([a-z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============ Sub-Components ============

/** One-line Going In summary below stats (full card lives on Context tab). */
function GoingInCompactStrip({ activity }: { activity: Activity }) {
  if (
    activity.pre_recovery_hrv == null &&
    activity.pre_resting_hr == null &&
    activity.pre_sleep_h == null
  ) {
    return null;
  }
  return (
    <div className="mb-4 flex flex-wrap items-baseline gap-x-5 gap-y-1 text-sm border-b border-slate-700/30 pb-3">
      <span className="text-xs font-medium text-slate-500 uppercase tracking-wide w-full sm:w-auto">Going In</span>
      {activity.pre_recovery_hrv != null && (
        <span className="text-slate-300">
          <span className="text-slate-500">HRV</span>{' '}
          <span className="font-medium tabular-nums">{activity.pre_recovery_hrv}</span>
          <span className="text-slate-500 text-xs">ms</span>
        </span>
      )}
      {activity.pre_resting_hr != null && (
        <span className="text-slate-300">
          <span className="text-slate-500">RHR</span>{' '}
          <span className="font-medium tabular-nums">{activity.pre_resting_hr}</span>
          <span className="text-slate-500 text-xs">bpm</span>
        </span>
      )}
      {activity.pre_sleep_h != null && (
        <span className="text-slate-300">
          <span className="text-slate-500">Sleep</span>{' '}
          <span className="font-medium tabular-nums">{activity.pre_sleep_h.toFixed(1)}</span>
          <span className="text-slate-500 text-xs">h</span>
        </span>
      )}
    </div>
  );
}

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
