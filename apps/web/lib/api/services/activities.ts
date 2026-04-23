/**
 * Activities API Service
 * 
 * Type-safe service layer for activity-related API calls.
 * Each service is isolated and can be swapped/refactored independently.
 */

import { apiClient } from '../client';
import type {
  Activity,
  ActivityAnalysis,
  RunDelivery,
  ActivityFeedback,
  ActivityFeedbackCreate,
} from '../types';

export interface ActivityListParams {
  limit?: number;
  offset?: number;
  start_date?: string;
  end_date?: string;
  min_distance_m?: number;
  max_distance_m?: number;
  sport?: string;
  is_race?: boolean;
  // Phase 1 — comparison product family
  workout_type?: string; // comma-separated CSV (e.g., "long_run,threshold")
  temp_min?: number;
  temp_max?: number;
  dew_min?: number;
  dew_max?: number;
  elev_gain_min?: number;
  elev_gain_max?: number;
  sort_by?: 'start_time' | 'distance_m' | 'duration_s';
  sort_order?: 'asc' | 'desc';
}

export interface FilterHistogramBucket {
  lo: number;
  hi: number;
  count: number;
}

export interface FilterHistogram {
  available: boolean;
  min?: number;
  max?: number;
  buckets?: FilterHistogramBucket[];
}

export interface FilterDistributions {
  workout_types: { value: string; count: number }[];
  distance_m: FilterHistogram;
  temp_f: FilterHistogram;
  dew_point_f: FilterHistogram;
  elevation_gain_m: FilterHistogram;
}

/** A single sport-bucket inside an ActivitySummary. */
export interface ActivitySummaryBucket {
  total_activities: number;
  total_distance_km: number;
  total_distance_miles: number;
  total_duration_hours: number;
  average_pace_per_mile?: number | null;
  race_count?: number;
}

export interface ActivitySummaryOtherBucket extends ActivitySummaryBucket {
  by_sport: Record<string, ActivitySummaryBucket>;
}

export interface ActivitySummary {
  // Sport-aware buckets — running is the canonical metric.
  running: ActivitySummaryBucket;
  other: ActivitySummaryOtherBucket;
  combined: ActivitySummaryBucket;

  // Backwards-compatible top-level (mirrors `running`).
  total_activities: number;
  total_distance_km: number;
  total_distance_miles: number;
  total_duration_hours: number;
  average_pace_per_mile: number | null;
  activities_by_sport: Record<string, number>;
  race_count: number;
  period_days: number;
}

export const activitiesService = {
  /**
   * List activities with filtering and pagination
   */
  async listActivities(params?: ActivityListParams): Promise<Activity[]> {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      });
    }
    const queryString = queryParams.toString();
    return apiClient.get<Activity[]>(`/v1/activities${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * Get activity summary statistics
   */
  async getSummary(days: number = 30): Promise<ActivitySummary> {
    return apiClient.get<ActivitySummary>(`/v1/activities/summary?days=${days}`);
  },

  /**
   * Per-dimension distributions powering the brushable filter histograms.
   *
   * The backend marks each dimension `available: false` when there are
   * fewer than 5 activities with values — the frontend uses this to
   * suppress that histogram entirely (suppression > placeholder).
   */
  async getFilterDistributions(): Promise<FilterDistributions> {
    return apiClient.get<FilterDistributions>('/v1/activities/filter-distributions');
  },

  /**
   * Get activity by ID
   */
  async getActivity(activityId: string): Promise<Activity> {
    return apiClient.get<Activity>(`/v1/activities/${activityId}`);
  },

  /**
   * Get activity analysis (efficiency insights)
   */
  async getActivityAnalysis(activityId: string): Promise<ActivityAnalysis> {
    return apiClient.get<ActivityAnalysis>(`/v1/activities/${activityId}/analysis`);
  },

  /**
   * Get complete run delivery (analysis + perception prompts)
   */
  async getRunDelivery(activityId: string): Promise<RunDelivery> {
    return apiClient.get<RunDelivery>(`/v1/activities/${activityId}/delivery`);
  },

  /**
   * Create activity feedback
   */
  async createFeedback(feedback: ActivityFeedbackCreate): Promise<ActivityFeedback> {
    return apiClient.post<ActivityFeedback>('/v1/activity-feedback', feedback);
  },

  /**
   * Get feedback for activity
   */
  async getFeedback(activityId: string): Promise<ActivityFeedback> {
    return apiClient.get<ActivityFeedback>(`/v1/activity-feedback/activity/${activityId}`);
  },

  /**
   * Update feedback
   */
  async updateFeedback(
    feedbackId: string,
    updates: Partial<ActivityFeedbackCreate>
  ): Promise<ActivityFeedback> {
    return apiClient.put<ActivityFeedback>(`/v1/activity-feedback/${feedbackId}`, updates);
  },

  /**
   * Delete feedback
   */
  async deleteFeedback(feedbackId: string): Promise<void> {
    return apiClient.delete<void>(`/v1/activity-feedback/${feedbackId}`);
  },

  /**
   * Get pending feedback prompts
   */
  async getPendingPrompts(limit: number = 10): Promise<Array<{
    should_prompt: boolean;
    prompt_text: string | null;
    required_fields: string[];
    optional_fields: string[];
    activity_id: string;
    run_type: string | null;
  }>> {
    return apiClient.get(`/v1/activity-feedback/pending?limit=${limit}`);
  },
} as const;

