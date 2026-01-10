/**
 * Activity Comparison API Service
 * 
 * Enables comparison of workouts by type, conditions, time periods.
 * Key differentiator from Garmin/Strava.
 */

import { apiClient } from '../client';

export interface ChartSplitData {
  split_number: number;
  distance_m: number;
  elapsed_time_s: number;
  pace_per_km: number | null;
  avg_hr: number | null;
  cumulative_distance_m: number;
}

export interface ActivitySummary {
  id: string;
  date: string;
  name: string;
  workout_type: string | null;
  distance_m: number;
  distance_km: number;
  duration_s: number;
  avg_hr: number | null;
  pace_per_km: number | null;
  pace_formatted: string | null;
  efficiency: number | null;
  intensity_score: number | null;
  elevation_gain: number | null;
  temperature_f: number | null;
  splits: ChartSplitData[];
}

export interface ComparisonResult {
  workout_type: string;
  total_activities: number;
  date_range_start: string | null;
  date_range_end: string | null;
  avg_pace_per_km: number | null;
  avg_pace_formatted: string | null;
  avg_efficiency: number | null;
  avg_hr: number | null;
  total_distance_km: number;
  efficiency_trend: 'improving' | 'declining' | 'stable' | null;
  efficiency_change_pct: number | null;
  pace_trend: 'improving' | 'declining' | 'stable' | null;
  pace_change_pct: number | null;
  best_activity: ActivitySummary | null;
  worst_activity: ActivitySummary | null;
  most_recent: ActivitySummary | null;
  activities: ActivitySummary[];
}

export interface WorkoutTypeSummary {
  workout_types: Record<string, number>;
  total: number;
}

export interface ActivityWithComparison {
  id: string;
  date: string;
  workout_type: string | null;
  workout_zone: string | null;
  distance_m: number;
  duration_s: number;
  avg_hr: number | null;
  max_hr: number | null;
  elevation_gain: number | null;
  pace_per_km: number | null;
  efficiency: number | null;
  intensity_score: number | null;
  temperature_f: number | null;
  splits: SplitData[];
  comparison: {
    similar_count: number;
    percentile_vs_similar: number | null;
    avg_similar_efficiency: number | null;
    similar_activities: Array<{
      id: string;
      date: string;
      distance_m: number;
      pace_per_km: number | null;
      avg_hr: number | null;
      efficiency: number | null;
    }>;
  } | null;
}

export interface SplitData {
  split_number: number;
  distance: number | null;
  elapsed_time: number | null;
  moving_time: number | null;
  average_heartrate: number | null;
  max_heartrate: number | null;
  average_cadence: number | null;
  gap_seconds_per_mile: number | null;
}

export interface ClassifyResult {
  classified: number;
  total_unclassified_before: number;
  message: string;
}

export interface IndividualComparisonResult {
  activities: ActivitySummary[];
  comparison_table: Record<string, (string | number | null)[]>;
  best_by_metric: Record<string, string>;
  insights: string[];
  count: number;
}

export const compareService = {
  /**
   * Get summary of activities by workout type
   */
  async getWorkoutTypeSummary(): Promise<WorkoutTypeSummary> {
    return apiClient.get<WorkoutTypeSummary>('/v1/compare/workout-types');
  },

  /**
   * Compare activities by workout type
   */
  async compareByType(workoutType: string, days: number = 180): Promise<ComparisonResult> {
    return apiClient.get<ComparisonResult>(`/v1/compare/by-type/${workoutType}?days=${days}`);
  },

  /**
   * Compare activities by conditions
   */
  async compareByConditions(params: {
    workout_type?: string;
    temp_min?: number;
    temp_max?: number;
    days?: number;
  }): Promise<ComparisonResult> {
    const searchParams = new URLSearchParams();
    if (params.workout_type) searchParams.set('workout_type', params.workout_type);
    if (params.temp_min !== undefined) searchParams.set('temp_min', params.temp_min.toString());
    if (params.temp_max !== undefined) searchParams.set('temp_max', params.temp_max.toString());
    if (params.days) searchParams.set('days', params.days.toString());
    
    return apiClient.get<ComparisonResult>(`/v1/compare/by-conditions?${searchParams}`);
  },

  /**
   * Get activity with comparison to similar workouts
   */
  async getActivityWithComparison(activityId: string): Promise<ActivityWithComparison> {
    return apiClient.get<ActivityWithComparison>(`/v1/compare/activity/${activityId}`);
  },

  /**
   * Classify all unclassified activities
   */
  async classifyAll(): Promise<ClassifyResult> {
    return apiClient.post<ClassifyResult>('/v1/compare/classify-all');
  },

  /**
   * Compare 2-10 specific activities side-by-side
   * This is the marquee feature
   */
  async compareIndividual(activityIds: string[]): Promise<IndividualComparisonResult> {
    return apiClient.post<IndividualComparisonResult>('/v1/compare/individual', {
      activity_ids: activityIds,
    });
  },
};
