/**
 * Training Plans API Service
 * 
 * Provides methods for:
 * - Creating training plans
 * - Fetching current plan and workouts
 * - Calendar view
 */

import { apiClient } from '../client';

export interface CreatePlanRequest {
  goal_race_name: string;
  goal_race_date: string;
  goal_race_distance_m: number;
  goal_time_seconds?: number;
  plan_start_date?: string;
}

export interface PlanSummary {
  id: string;
  name: string;
  status: string;
  goal_race_name: string | null;
  goal_race_date: string;
  goal_race_distance_m: number;
  goal_time_seconds: number | null;
  plan_start_date: string;
  plan_end_date: string;
  total_weeks: number;
  current_week: number | null;
  progress_percent: number;
}

export interface WorkoutSummary {
  id: string;
  scheduled_date: string;
  week_number: number;
  workout_type: string;
  title: string;
  description: string | null;
  phase: string;
  target_duration_minutes: number | null;
  target_distance_km: number | null;
  target_pace_per_km_seconds: number | null;
  completed: boolean;
  skipped: boolean;
  completed_activity_id: string | null;
}

export interface CalendarDay {
  date: string;
  planned_workout: WorkoutSummary | null;
  actual_activities: Array<{
    id: string;
    sport: string;
    distance_km: number | null;
    duration_minutes: number | null;
    pace_per_km: number | null;
  }>;
  day_of_week: number;
  is_today: boolean;
  is_race_day: boolean;
}

export interface CalendarWeek {
  week_number: number;
  phase: string | null;
  days: CalendarDay[];
  planned_volume_km: number;
  actual_volume_km: number;
}

export interface CalendarResponse {
  plan: PlanSummary | null;
  weeks: CalendarWeek[];
  start_date: string;
  end_date: string;
}

export interface WeeklyPlanResponse {
  week_number: number;
  phase: string;
  phase_week: number;
  workouts: WorkoutSummary[];
  total_planned_duration: number;
  total_planned_distance: number;
  completed_workouts: number;
  skipped_workouts: number;
}

export const trainingPlansService = {
  /**
   * Create a new training plan
   */
  async createPlan(request: CreatePlanRequest): Promise<PlanSummary> {
    return apiClient.post<PlanSummary>('/v1/training-plans', request);
  },

  /**
   * Get current active plan
   */
  async getCurrentPlan(): Promise<PlanSummary | null> {
    return apiClient.get<PlanSummary | null>('/v1/training-plans/current');
  },

  /**
   * Get this week's workouts
   */
  async getCurrentWeek(): Promise<WeeklyPlanResponse | null> {
    return apiClient.get<WeeklyPlanResponse | null>('/v1/training-plans/current/week');
  },

  /**
   * Get calendar view
   */
  async getCalendar(startDate?: string, endDate?: string): Promise<CalendarResponse> {
    let url = '/v1/training-plans/calendar';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += `?${params.toString()}`;
    return apiClient.get<CalendarResponse>(url);
  },

  /**
   * Mark workout as completed
   */
  async completeWorkout(planId: string, workoutId: string, activityId?: string): Promise<void> {
    let url = `/v1/training-plans/${planId}/workouts/${workoutId}/complete`;
    if (activityId) url += `?activity_id=${activityId}`;
    await apiClient.post(url, {});
  },

  /**
   * Mark workout as skipped
   */
  async skipWorkout(planId: string, workoutId: string, reason?: string): Promise<void> {
    let url = `/v1/training-plans/${planId}/workouts/${workoutId}/skip`;
    if (reason) url += `?reason=${encodeURIComponent(reason)}`;
    await apiClient.post(url, {});
  },
};
