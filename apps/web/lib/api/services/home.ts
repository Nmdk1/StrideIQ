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
}

export interface HomeData {
  today: TodayWorkout;
  yesterday: YesterdayInsight;
  week: WeekProgress;
}

// --- API Functions ---

export async function getHomeData(): Promise<HomeData> {
  return apiClient.get<HomeData>('/home');
}
