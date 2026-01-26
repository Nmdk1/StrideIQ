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
  distance_mi?: number;
  completed: boolean;
  is_today: boolean;
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

export interface HomeData {
  today: TodayWorkout;
  yesterday: YesterdayInsight;
  week: WeekProgress;
  hero_narrative?: string;  // ADR-033: Personalized hero sentence
  strava_connected: boolean;
  has_any_activities: boolean;
  total_activities: number;
  last_sync?: string;
  ingestion_state?: Record<string, any> | null;
  ingestion_paused?: boolean;
}

// --- API Functions ---

export async function getHomeData(): Promise<HomeData> {
  return apiClient.get<HomeData>('/v1/home');
}
