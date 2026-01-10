/**
 * Query Engine API Service
 * 
 * Service for admin query engine endpoints.
 * Admin/owner role required.
 */

import { apiClient } from '../client';

export interface QueryTemplate {
  name: string;
  description: string;
  scope: string;
  params: string[];
}

export interface QueryResult {
  template?: string;
  entity?: string;
  success: boolean;
  data: Record<string, any>[];
  total_count: number;
  execution_time_ms: number;
  metadata: Record<string, any>;
  error: string | null;
}

export interface EntityInfo {
  fields: string[];
  date_field: string | null;
}

export const queryEngineService = {
  /**
   * Get available query templates
   */
  async getTemplates(): Promise<{ templates: QueryTemplate[] }> {
    return apiClient.get<{ templates: QueryTemplate[] }>('/v1/admin/query/templates');
  },

  /**
   * Get queryable entities with their fields
   */
  async getEntities(): Promise<{ entities: Record<string, EntityInfo> }> {
    return apiClient.get<{ entities: Record<string, EntityInfo> }>('/v1/admin/query/entities');
  },

  /**
   * Execute a query template
   */
  async executeTemplate(params: {
    template: string;
    athleteId?: string;
    days?: number;
    workoutType?: string;
    minStrength?: number;
  }): Promise<QueryResult> {
    const queryParams = new URLSearchParams();
    queryParams.append('template', params.template);
    if (params.athleteId) queryParams.append('athlete_id', params.athleteId);
    if (params.days) queryParams.append('days', params.days.toString());
    if (params.workoutType) queryParams.append('workout_type', params.workoutType);
    if (params.minStrength) queryParams.append('min_strength', params.minStrength.toString());

    return apiClient.post<QueryResult>(`/v1/admin/query/execute?${queryParams.toString()}`);
  },

  /**
   * Execute a custom query
   */
  async executeCustom(params: {
    entity: string;
    days?: number;
    athleteId?: string;
    groupBy?: string[];
    aggregations?: Record<string, string>;
    filters?: { field: string; operator: string; value: any }[];
    sortBy?: string;
    limit?: number;
  }): Promise<QueryResult> {
    const queryParams = new URLSearchParams();
    queryParams.append('entity', params.entity);
    if (params.days) queryParams.append('days', params.days.toString());
    if (params.athleteId) queryParams.append('athlete_id', params.athleteId);
    if (params.groupBy?.length) queryParams.append('group_by', params.groupBy.join(','));
    if (params.aggregations) {
      const aggStr = Object.entries(params.aggregations)
        .map(([field, agg]) => `${field}:${agg}`)
        .join(',');
      queryParams.append('aggregations', aggStr);
    }
    if (params.filters?.length) {
      queryParams.append('filters_json', JSON.stringify(params.filters));
    }
    if (params.sortBy) queryParams.append('sort_by', params.sortBy);
    if (params.limit) queryParams.append('limit', params.limit.toString());

    return apiClient.post<QueryResult>(`/v1/admin/query/custom?${queryParams.toString()}`);
  },

  /**
   * Legacy query endpoint
   */
  async legacyQuery(queryType: string, days: number = 180): Promise<any> {
    return apiClient.get<any>(`/v1/admin/query?query_type=${queryType}&days=${days}`);
  },
};

export default queryEngineService;
