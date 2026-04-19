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
import { useStreamAnalysis, isAnalysisData } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { GarminBadge } from '@/components/integrations/GarminBadge';
import { FeedbackModal } from '@/components/activities/feedback/FeedbackModal';
import { ReflectPill } from '@/components/activities/feedback/ReflectPill';
import { useFeedbackCompletion } from '@/components/activities/feedback/useFeedbackCompletion';
import { useFeedbackTrigger } from '@/components/activities/feedback/useFeedbackTrigger';
import { ShareButton } from '@/components/activities/share/ShareButton';
import { ShareDrawer } from '@/components/activities/share/ShareDrawer';
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
import { RunDetailsGrid } from '@/components/activities/RunDetailsGrid';
import { GarminEffortFallback } from '@/components/activities/GarminEffortFallback';
import dynamic from 'next/dynamic';

// Canvas v2 hero — replaces the in-tab RunShapeCanvas + 2D map combo
// for runs. Lazy-loaded so the ~700kB mapbox-gl chunk doesn't ship in
// the main bundle and so non-run sports never load it at all.
const CanvasV2 = dynamic(
  () => import('@/components/canvas-v2/CanvasV2').then((m) => m.CanvasV2),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-2xl border border-slate-800/60 bg-slate-900/30 h-[520px] flex items-center justify-center text-sm text-slate-500">
        Loading canvas…
      </div>
    ),
  },
);

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

  // FIT-derived activity-level metrics (Phase 1).
  // All nullable: present only when a FIT file landed and the athlete
  // wears a sensor that records the metric.
  total_descent_m: number | null;
  avg_power_w: number | null;
  max_power_w: number | null;
  avg_stride_length_m: number | null;
  avg_ground_contact_ms: number | null;
  avg_ground_contact_balance_pct: number | null;
  avg_vertical_oscillation_cm: number | null;
  avg_vertical_ratio_pct: number | null;
  // Garmin self-evaluation (low-confidence fallback only).
  garmin_feel: string | null;
  garmin_perceived_effort: number | null;

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

function maxGradeFromStream(
  stream: { grade: number | null }[] | null | undefined,
): number | null {
  if (!stream || stream.length === 0) return null;
  let max: number | null = null;
  for (const p of stream) {
    if (p.grade !== null && Number.isFinite(p.grade)) {
      if (max === null || p.grade > max) max = p.grade;
    }
  }
  return max;
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
  const [activeTab, setActiveTab] = useState<ActivityTabId>('splits');

  // Feedback modal — required reflection (Phase 3).  Backend completion
  // gates auto-open; localStorage prevents re-pop on refresh after a
  // successful submit; the Reflect pill in the page chrome opens the modal
  // for retroactive editing at any time.
  const feedbackCompletion = useFeedbackCompletion(activityId);
  const { shouldAutoOpen, markShown } = useFeedbackTrigger({
    activityId,
    startTime: activity?.start_time,
    isComplete: feedbackCompletion.isComplete,
    isLoading: feedbackCompletion.isLoading,
  });
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  // Phase 4: share drawer is *only* opened by an explicit chrome click.
  // No auto-open, no nag, no global popup.
  const [shareDrawerOpen, setShareDrawerOpen] = useState(false);
  useEffect(() => {
    if (shouldAutoOpen && !feedbackModalOpen) {
      setFeedbackModalOpen(true);
      markShown();
    }
  }, [shouldAutoOpen, feedbackModalOpen, markShown]);

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
            {activity.sport_type === 'run' && (
              <ReflectPill
                isComplete={feedbackCompletion.isComplete}
                isLoading={feedbackCompletion.isLoading}
                onClick={() => setFeedbackModalOpen(true)}
              />
            )}
            {activity.sport_type === 'run' && (
              <ShareButton onClick={() => setShareDrawerOpen(true)} />
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

        {/* ── Canvas v2 hero — always visible above tabs.
              Replaces the in-tab RunShapeCanvas + 2D map combo for runs.
              Phase 1 leaves the existing 6-tab structure intact; Phase 2
              collapses to 3 tabs (Splits/Coach/Compare). ── */}
        <div className="mb-5 -mx-4 sm:mx-0">
          <CanvasV2
            activityId={activityId}
            chromeless
            title={displayTitle}
            subtitle={`${formatDate(activity.start_time)} at ${formatTime(activity.start_time)}`}
            summary={{
              cardiacDriftPct: analysisData?.drift?.cardiac_pct ?? null,
              avgHrBpm: activity.average_hr ?? null,
              avgCadenceSpm: normalizeCadenceToSpm(activity.average_cadence),
              maxGradePct: maxGradeFromStream(analysisData?.stream),
              totalMovingTimeS: activity.moving_time_s ?? activity.elapsed_time_s ?? null,
            }}
          />
        </div>

        {/* Phase 2 (fit_run_001): self-suppressing FIT cards.  Renders only
            when at least one Garmin running-dynamic / power metric is
            populated. Older Strava-only activities and watch-only setups
            see nothing here — keeps the page clean. */}
        <div className="mb-5">
          <RunDetailsGrid
            avgPowerW={activity.avg_power_w}
            maxPowerW={activity.max_power_w}
            avgStrideLengthM={activity.avg_stride_length_m}
            avgGroundContactMs={activity.avg_ground_contact_ms}
            avgGroundContactBalancePct={activity.avg_ground_contact_balance_pct}
            avgVerticalOscillationCm={activity.avg_vertical_oscillation_cm}
            avgVerticalRatioPct={activity.avg_vertical_ratio_pct}
            totalDescentM={activity.total_descent_m}
          />
        </div>

        <ActivityTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          panels={{
            splits: (
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
                showMap={false}
              />
            ),
            // Coach absorbs the old Overview intelligence card, the Analysis
            // tab, and the Context tab.  Order: brief first (what the coach
            // says), then findings (what the engine found), then context
            // (what was happening before the run), then deep analysis charts.
            coach: (
              <div className="space-y-6">
                <GarminEffortFallback
                  garminPerceivedEffort={activity.garmin_perceived_effort}
                  garminFeel={activity.garmin_feel}
                  athleteRpe={feedbackCompletion.feedback?.perceived_effort ?? null}
                />
                <RunIntelligence activityId={activityId} />
                <FindingsCards findings={findings} />
                <WhyThisRun activityId={activityId} />
                <GoingInCard
                  preRecoveryHrv={activity.pre_recovery_hrv}
                  preOvernightHrv={activity.pre_overnight_hrv}
                  preRestingHr={activity.pre_resting_hr}
                  preSleepH={activity.pre_sleep_h}
                  preSleepScore={activity.pre_sleep_score}
                />
                <AnalysisTabPanel
                  drift={analysisData?.drift ?? null}
                  planComparison={analysisData?.plan_comparison ?? null}
                  stream={analysisData?.stream ?? null}
                  effortIntensity={analysisData?.effort_intensity ?? null}
                  movingTimeS={activity.moving_time_s}
                />
                {activity.narrative && (
                  <div className="px-5 py-4 bg-slate-800/30 border border-slate-700/30 rounded-lg">
                    <p className="text-sm text-slate-400 italic leading-relaxed">
                      &ldquo;{activity.narrative}&rdquo;
                    </p>
                  </div>
                )}
              </div>
            ),
            compare: <ComparablesPanel activityId={activityId} />,
          }}
        />

        {/* Phase 3: required feedback modal — runs only.  Auto-opens on
            first device visit when feedback is incomplete and the activity
            is recent; the Reflect pill in the page header opens it for
            retroactive editing at any time. */}
        <FeedbackModal
          activityId={activityId}
          open={feedbackModalOpen}
          existingReflection={feedbackCompletion.reflection}
          existingFeedback={feedbackCompletion.feedback}
          existingWorkoutType={feedbackCompletion.workoutType}
          onSaved={() => {
            setFeedbackModalOpen(false);
            feedbackCompletion.refetch();
          }}
        />

        {/* Phase 4: share drawer.  Hosts the runtoon (formerly always
            on the page bottom) plus a placeholder for upcoming share
            styles.  Opens only when the athlete taps Share. */}
        <ShareDrawer
          activityId={activityId}
          open={shareDrawerOpen}
          onClose={() => setShareDrawerOpen(false)}
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

