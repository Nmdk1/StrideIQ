/**
 * Plan Generation API Service
 * 
 * Provides access to the plan generation system.
 */

import { apiClient } from '../client';

// =============================================================================
// TYPES
// =============================================================================

export interface PlanPhase {
  name: string;
  phase_type: string;
  weeks: number[];
  focus: string;
}

export interface WorkoutSegment {
  name: string;
  distance_miles?: number;
  duration_minutes?: number;
  pace_description: string;
}

export interface GeneratedWorkout {
  week: number;
  day: number;
  day_name: string;
  date?: string;
  workout_type: string;
  title: string;
  description: string;
  phase: string;
  phase_name: string;
  distance_miles: number;
  duration_minutes: number;
  pace_description: string;
  segments?: WorkoutSegment[];
  option: 'A' | 'B';
  has_option_b: boolean;
}

export interface GeneratedPlan {
  plan_tier: 'standard' | 'semi_custom' | 'custom';
  distance: string;
  duration_weeks: number;
  volume_tier: string;
  days_per_week: number;
  vdot?: number;
  start_date?: string;
  end_date?: string;
  race_date?: string;
  phases: PlanPhase[];
  workouts: GeneratedWorkout[];
  weekly_volumes: number[];
  peak_volume: number;
  total_miles: number;
  total_quality_sessions: number;
}

export interface PlanOptions {
  distances: string[];
  durations: number[];
  volume_tiers: { value: string; label: string; range: string }[];
  days_options: number[];
}

export interface StandardPlanRequest {
  distance: string;
  duration_weeks: number;
  days_per_week: number;
  volume_tier: string;
  start_date?: string;
}

export interface SemiCustomPlanRequest extends StandardPlanRequest {
  recent_race_distance?: string;
  recent_race_time?: string;
  race_date?: string;
  race_name?: string;
}

// =============================================================================
// API METHODS
// =============================================================================

export const planService = {
  /**
   * Get available plan options
   */
  async getOptions(): Promise<PlanOptions> {
    return apiClient.get<PlanOptions>('/v2/plans/options');
  },

  /**
   * Get volume tier classification for current weekly miles
   */
  async classifyTier(weeklyMiles: number, distance: string = 'marathon') {
    return apiClient.get<{ tier: string; label: string; range: string }>(
      `/v2/plans/classify-tier?weekly_miles=${weeklyMiles}&distance=${distance}`
    );
  },

  /**
   * Preview a standard plan (without creating it)
   */
  async previewStandard(request: StandardPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/standard/preview', request);
  },

  /**
   * Create a standard (free) plan
   */
  async createStandard(request: StandardPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/standard', request);
  },

  /**
   * Create a semi-custom plan ($5)
   */
  async createSemiCustom(request: SemiCustomPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/semi-custom', request);
  },
};
