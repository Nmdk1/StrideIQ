/**
 * Home API Service
 * 
 * Fetches the "Glance" layer data:
 * - Today's workout with context
 * - Yesterday's insight
 * - Week progress
 */

import { apiClient } from '../client';

// --- Types ---

export interface TodayWorkout {
  has_workout: boolean;
  workout_type?: string;
  title?: string;
  distance_mi?: number;
  pace_guidance?: string;
  why_context?: string;
  why_source?: 'correlation' | 'load' | 'plan';  // ADR-020: Source of context
  week_number?: number;
  phase?: string;
}

export interface YesterdayInsight {
  has_activity: boolean;
  activity_name?: string;
  activity_id?: string;
  distance_mi?: number;
  pace_per_mi?: string;
  insight?: string;
  // Fallback: most recent activity if no yesterday activity
  last_activity_date?: string;
  last_activity_name?: string;
  last_activity_id?: string;
  days_since_last?: number;
}

export interface WeekDay {
  date: string;
  day_abbrev: string;
  workout_type?: string;
  sport?: string;
  distance_mi?: number;
  planned_distance_mi?: number;  // Show both for comparison
  completed: boolean;
  is_today: boolean;
  activity_id?: string;  // For linking to activity
  workout_id?: string;   // For linking to planned workout
}

export interface WeekProgress {
  week_number?: number;
  total_weeks?: number;
  phase?: string;
  completed_mi: number;
  planned_mi: number;
  progress_pct: number;
  days: WeekDay[];
  status: 'on_track' | 'ahead' | 'behind' | 'no_plan';
  trajectory_sentence?: string;
  tsb_context?: 'Fresh' | 'Building' | 'Fatigued';  // ADR-020: Training stress context
  load_trend?: 'up' | 'stable' | 'down';  // ADR-020: Load direction
}

// --- ADR-17 Phase 2 Types ---

export interface CoachNoticed {
  text: string;
  source: 'correlation' | 'signal' | 'insight_feed' | 'narrative';
  ask_coach_query: string;
  finding_id?: string;
}

export interface RaceCountdown {
  race_name?: string;
  race_date: string;
  days_remaining: number;
  goal_time?: string;
  goal_pace?: string;
  predicted_time?: string;
}

export interface StravaStatusDetail {
  connected: boolean;
  last_sync?: string;
  needs_reconnect: boolean;
}

// --- RSI Layer 1 Types ---

export interface LastRunSegment {
  type: string;
  start_time_s: number;
  end_time_s: number;
  duration_s: number;
  avg_pace_s_km?: number | null;
}

export interface LastRun {
  activity_id: string;
  name: string;
  start_time: string;  // ISO datetime
  distance_m?: number | null;
  moving_time_s?: number | null;
  average_hr?: number | null;
  stream_status?: 'success' | 'pending' | 'fetching' | 'unavailable' | null;
  effort_intensity?: number[] | null;  // Only when stream_status === 'success'
  pace_stream?: number[] | null;  // LTTB-downsampled pace (s/km) per point
  elevation_stream?: number[] | null;  // LTTB-downsampled altitude (m) per point
  tier_used?: string | null;
  confidence?: number | null;
  segments?: LastRunSegment[] | null;
  pace_per_km?: number | null;  // Derived from distance/time (s/km)
  provider?: string | null;  // 'strava' | 'garmin' | 'manual'
  device_name?: string | null;  // Garmin device name, e.g. 'forerunner965'
  shape_sentence?: string | null;
  athlete_title?: string | null;
  resolved_title?: string | null;
  heat_adjustment_pct?: number | null;
  workout_classification?: string | null;
}

export interface HomeFinding {
  text: string;
  confidence_tier: string;
  domain: string;
  times_confirmed: number;
  evidence_summary?: string | null;
  implication_summary?: string | null;
}

export type BriefingState = 'fresh' | 'stale' | 'missing' | 'refreshing' | 'consent_required';

export interface HomeData {
  today: TodayWorkout;
  yesterday: YesterdayInsight;
  week: WeekProgress;
  hero_narrative?: string;  // ADR-033: Personalized hero sentence
  strava_connected: boolean;
  garmin_connected: boolean;
  has_any_activities: boolean;
  total_activities: number;
  last_sync?: string;
  ingestion_state?: Record<string, any> | null;
  ingestion_paused?: boolean;
  // ADR-17 Phase 2
  coach_noticed?: CoachNoticed | null;
  race_countdown?: RaceCountdown | null;
  checkin_needed: boolean;
  today_checkin?: {
    readiness_label?: string | null;
    sleep_label?: string | null;
    soreness_label?: string | null;
  } | null;
  strava_status?: StravaStatusDetail | null;
  coach_briefing?: {
    coach_noticed?: string;
    checkin_reaction?: string;
    today_context?: string;
    week_assessment?: string;
    race_assessment?: string;
    // Voice fields — "Give the Data a Voice"
    morning_voice?: string;
    workout_why?: string;
  } | null;
  // RSI Layer 1
  last_run?: LastRun | null;
  // Async briefing state machine — drives polling and pending UI
  briefing_state?: BriefingState | null;
  briefing_is_interim?: boolean;
  briefing_last_updated_at?: string | null;
  briefing_source?: 'llm' | 'deterministic_fallback' | null;
  // Path A surfaces
  finding?: HomeFinding | null;
  has_correlations?: boolean;
  // Daily wellness
  garmin_wellness?: {
    date: string;
    sleep_h?: number;
    sleep_score?: number;
    sleep_score_qualifier?: string;
    recovery_hrv?: number;
    recovery_hrv_status?: 'low' | 'normal' | 'high';
    recovery_hrv_range?: { low: number; high: number };
    overnight_hrv?: number;
    resting_hr?: number;
    resting_hr_status?: 'low' | 'normal' | 'high';
    resting_hr_range?: { low: number; high: number };
    avg_stress?: number;
  } | null;
}

// --- API Functions ---

export async function getHomeData(): Promise<HomeData> {
  return apiClient.get<HomeData>('/v1/home');
}
