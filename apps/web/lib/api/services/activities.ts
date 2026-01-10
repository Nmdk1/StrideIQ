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
  sort_by?: 'start_time' | 'distance_m' | 'duration_s';
  sort_order?: 'asc' | 'desc';
}

export interface ActivitySummary {
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

