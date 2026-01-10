/**
 * Insight Feedback API Service
 */

import { apiClient } from '../client';

export interface InsightFeedback {
  id: string;
  athlete_id: string;
  insight_type: string;
  insight_id?: string;
  insight_text: string;
  helpful: boolean;
  feedback_text?: string;
  created_at: string;
}

export interface InsightFeedbackCreate {
  insight_type: string;
  insight_id?: string;
  insight_text: string;
  helpful: boolean;
  feedback_text?: string;
}

export interface InsightFeedbackStats {
  total: number;
  helpful: number;
  not_helpful: number;
  helpful_percentage: number;
}

export const insightFeedbackService = {
  /**
   * Create insight feedback
   */
  async createFeedback(feedback: InsightFeedbackCreate): Promise<InsightFeedback> {
    return apiClient.post<InsightFeedback>('/v1/insight-feedback', feedback);
  },

  /**
   * List insight feedback
   */
  async listFeedback(params?: {
    insight_type?: string;
    helpful?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<InsightFeedback[]> {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      });
    }
    const queryString = queryParams.toString();
    return apiClient.get<InsightFeedback[]>(`/v1/insight-feedback${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * Get feedback statistics
   */
  async getStats(): Promise<InsightFeedbackStats> {
    return apiClient.get<InsightFeedbackStats>('/v1/insight-feedback/stats');
  },
} as const;


