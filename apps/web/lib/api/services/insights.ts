/**
 * Athlete Insights API Service
 * 
 * Service for athlete self-query and insights endpoints.
 */

import { apiClient } from '../client';

export interface InsightTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  requires_premium: boolean;
  params: string[];
  available: boolean;
}

export interface InsightResult {
  template_id: string;
  template_name: string;
  success: boolean;
  data: any;
  execution_time_ms: number;
}

export interface TemplatesResponse {
  templates: InsightTemplate[];
  is_premium: boolean;
}

export const insightsService = {
  /**
   * Get available insight templates
   */
  async getTemplates(): Promise<TemplatesResponse> {
    return apiClient.get<TemplatesResponse>('/v1/athlete/insights/templates');
  },

  /**
   * Execute an insight template
   */
  async executeInsight(params: {
    templateId: string;
    days?: number;
    weeks?: number;
    limit?: number;
  }): Promise<InsightResult> {
    const queryParams = new URLSearchParams();
    if (params.days) queryParams.append('days', params.days.toString());
    if (params.weeks) queryParams.append('weeks', params.weeks.toString());
    if (params.limit) queryParams.append('limit', params.limit.toString());

    const url = `/v1/athlete/insights/execute/${params.templateId}${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return apiClient.post<InsightResult>(url);
  },
};

export default insightsService;
