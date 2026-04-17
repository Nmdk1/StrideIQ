'use client';

/**
 * Activity Detail Page — RSI Layer 2
 *
 * Restructured around the Run Shape Canvas as the centerpiece.
 * Spec: docs/specs/RSI_WIRING_SPEC.md (Layer 2)
 *
 * Runs: tabbed layout (Overview default) — see BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md
 */

import React, { useState, useRef, useEffect } from 'react';
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
import { ActivitySplitsTabPanel } from '@/components/activities/ActivitySplitsTabPanel';
import { GoingInStrip } from '@/components/activities/GoingInStrip';
import { GoingInCard } from '@/components/activities/GoingInCard';
import { FindingsCards } from '@/components/activities/FindingsCards';
import { WhyThisRun } from '@/components/activities/WhyThisRun';
import { RunIntelligence } from '@/components/activities/RunIntelligence';
import { AnalysisTabPanel } from '@/components/activities/AnalysisTabPanel';
import { ComparablesPanel } from '@/components/activities/ComparablesPanel';

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
  const [activeTab, setActiveTab] = useState<ActivityTabId>('overview');
  /** Avoid SSR/client mismatch — first paint matches server (no map), then client mounts. */
  const [clientReady, setClientReady] = useState(false);
  useEffect(() => {
    setClientReady(true);
  }, []);

  const splitTableRowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

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
        {/* ── 1. Header — compact: back + title + date on one row ── */}
        <div className="mb-4">
          <div className="flex items-center gap-3 mb-1">
            <button
              onClick={() => router.back()}
              className="text-slate-400 hover:text-white transition-colors flex-shrink-0"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            {isEditingTitle ? (
              <div className="flex-1 min-w-0">
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
                  className="w-full text-xl font-bold bg-slate-800 text-white border border-slate-600 rounded-lg px-3 py-1 focus:outline-none focus:border-emerald-500"
                />
                <div className="flex items-center gap-2 mt-1.5">
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
              <div className="group flex items-baseline gap-3 flex-1 min-w-0">
                <h1 className="text-xl md:text-2xl font-bold text-white truncate">{displayTitle}</h1>
                <button
                  onClick={handleStartEdit}
                  className="text-slate-500 hover:text-emerald-400 transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100 flex-shrink-0"
                  aria-label="Edit title"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
                <span className="text-slate-500 text-sm whitespace-nowrap flex-shrink-0 hidden md:inline">
                  {formatDate(activity.start_time)} at {formatTime(activity.start_time)}
                </span>
              </div>
            )}
            {activity.provider === 'garmin' && (
              <GarminBadge deviceName={activity.device_name} size="md" className="flex-shrink-0" />
            )}
          </div>
          <p className="text-slate-500 text-sm pl-8 md:hidden">
            {formatDate(activity.start_time)} at {formatTime(activity.start_time)}
          </p>
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
        {/* ── 2. Stats Banner ── */}
        <div className="mb-6 pb-5 border-b border-slate-700/40">
          <div className="grid grid-cols-3 gap-x-6 gap-y-4 md:grid-cols-6 md:gap-x-8">
            <MetricPill label="Distance" value={formatDistance(activity.distance_m)} />
            <MetricPill label="Moving Time" value={formatDuration(activity.moving_time_s)} />
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
            <p className="text-xs text-amber-400/80 mt-3">
              Heat slowed this run ~{activity.heat_adjustment_pct.toFixed(1)}% — your effort was better than the pace shows
            </p>
          )}
        </div>

        <GoingInStrip
          preRecoveryHrv={activity.pre_recovery_hrv}
          preRestingHr={activity.pre_resting_hr}
          preSleepH={activity.pre_sleep_h}
        />

        <ActivityTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          panels={{
            overview: (
              <>
                {/* Hero: RunShapeCanvas full width */}
                <div className="mb-5 -mx-4 sm:mx-0">
                  <RunShapeCanvas
                    activityId={activityId}
                    splits={splits ?? null}
                    intervalSummary={intervalSummary}
                    provider={activity.provider}
                    deviceName={activity.device_name}
                    heatAdjustmentPct={activity.heat_adjustment_pct}
                    temperatureF={activity.temperature_f}
                    splitTableRowRefs={splitTableRowRefs}
                  />
                </div>

                {/* Intelligence card — directly below the chart it describes */}
                <div className="mb-5">
                  <RunIntelligence activityId={activityId} />
                </div>

                {/* Two-column on desktop: splits left, map right. Stacked on mobile. */}
                <div className="flex flex-col md:flex-row md:gap-5 md:items-start mb-5">
                  {/* Splits */}
                  {splits && splits.length > 0 && (
                    <div className="w-full md:w-[55%] min-w-0 mb-4 md:mb-0">
                      <ActivitySplitsTabPanel
                        activityId={activityId}
                        gpsTrack={null}
                        startCoords={activity.start_coords}
                        sportType={activity.sport_type || 'run'}
                        startTime={activity.start_time}
                        distanceM={activity.distance_m}
                        durationS={activity.moving_time_s || activity.elapsed_time_s}
                        temperatureF={activity.temperature_f}
                        weatherCondition={activity.weather_condition}
                        humidityPct={activity.humidity_pct}
                        heatAdjustmentPct={activity.heat_adjustment_pct}
                        splits={splits}
                        intervalSummary={intervalSummary}
                        provider={activity.provider}
                        deviceName={activity.device_name}
                        stream={analysisData?.stream}
                        splitTableRowRefs={splitTableRowRefs}
                        showMap={false}
                      />
                    </div>
                  )}

                  {/* Map */}
                  {activity.gps_track && activity.gps_track.length > 1 && (
                    <div className={`w-full ${splits && splits.length > 0 ? 'md:w-[45%]' : ''} shrink-0`}>
                      {clientReady && (
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
                          mapAspectRatio="4 / 3"
                        />
                      )}
                    </div>
                  )}
                </div>

                <div className="mb-2">
                  <RuntoonCard activityId={activityId} />
                </div>
              </>
            ),
            splits: (
              <>
                <div className="mb-5 -mx-4 sm:mx-0">
                  <RunShapeCanvas
                    activityId={activityId}
                    splits={splits ?? null}
                    intervalSummary={intervalSummary}
                    provider={activity.provider}
                    deviceName={activity.device_name}
                    heatAdjustmentPct={activity.heat_adjustment_pct}
                    temperatureF={activity.temperature_f}
                    splitTableRowRefs={splitTableRowRefs}
                  />
                </div>
                <ActivitySplitsTabPanel
                  activityId={activityId}
                  gpsTrack={activity.gps_track}
                  startCoords={activity.start_coords}
                  sportType={activity.sport_type || 'run'}
                  startTime={activity.start_time}
                  distanceM={activity.distance_m}
                  durationS={activity.moving_time_s || activity.elapsed_time_s}
                  temperatureF={activity.temperature_f}
                  weatherCondition={activity.weather_condition}
                  humidityPct={activity.humidity_pct}
                  heatAdjustmentPct={activity.heat_adjustment_pct}
                  splits={splits}
                  intervalSummary={intervalSummary}
                  provider={activity.provider}
                  deviceName={activity.device_name}
                  stream={analysisData?.stream}
                  splitTableRowRefs={splitTableRowRefs}
                  showMap={clientReady}
                />
              </>
            ),
            analysis: (
              <AnalysisTabPanel
                drift={analysisData?.drift ?? null}
                planComparison={analysisData?.plan_comparison ?? null}
                stream={analysisData?.stream ?? null}
                effortIntensity={analysisData?.effort_intensity ?? null}
                movingTimeS={activity.moving_time_s}
              />
            ),
            compare: <ComparablesPanel activityId={activityId} />,
            context: (
              <div className="space-y-5">
                <GoingInCard
                  preRecoveryHrv={activity.pre_recovery_hrv}
                  preOvernightHrv={activity.pre_overnight_hrv}
                  preRestingHr={activity.pre_resting_hr}
                  preSleepH={activity.pre_sleep_h}
                  preSleepScore={activity.pre_sleep_score}
                />
                <WhyThisRun activityId={activityId} />
                <FindingsCards findings={findings} />
                {activity.narrative && (
                  <div className="px-5 py-4 bg-slate-800/30 border border-slate-700/30 rounded-lg">
                    <p className="text-sm text-slate-400 italic leading-relaxed">
                      &ldquo;{activity.narrative}&rdquo;
                    </p>
                  </div>
                )}
              </div>
            ),
            feedback: (
              <div className="space-y-5">
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


function MetricPill({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="min-w-0">
      <p className="text-2xl md:text-3xl font-bold text-white tabular-nums leading-tight whitespace-nowrap">
        {value}
        {unit && <span className="text-slate-400 text-sm font-normal ml-1">{unit}</span>}
      </p>
      <p className="text-[11px] text-slate-500 uppercase tracking-wide mt-0.5">{label}</p>
    </div>
  );
}

