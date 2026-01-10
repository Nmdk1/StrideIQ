/**
 * Analytics API Service
 * 
 * Service for efficiency trends and analytics endpoints.
 */

import { apiClient } from '../client';

export interface EfficiencyTrendPoint {
  date: string;
  efficiency_factor: number;
  pace_per_mile: number;
  avg_hr: number;
  distance_m?: number;
  duration_s?: number;
  performance_percentage?: number;
  activity_id: string;
  rolling_7d_avg?: number;
  rolling_30d_avg?: number;
  rolling_60d_avg?: number;
  rolling_90d_avg?: number;
  rolling_120d_avg?: number;
  annotations?: string[];
  // Decoupling metrics
  decoupling_percent?: number;
  decoupling_status?: 'green' | 'yellow' | 'red';
  first_half_ef?: number;
  second_half_ef?: number;
}

export interface EfficiencyTrendsResponse {
  time_series: EfficiencyTrendPoint[];
  summary: {
    total_activities: number;
    date_range: {
      start: string;
      end: string;
    };
    current_efficiency: number;
    average_efficiency: number;
    best_efficiency: number;
    worst_efficiency: number;
    trend_direction: 'improving' | 'declining' | 'stable' | 'insufficient_data';
    trend_magnitude?: number;
  };
  stability?: {
    consistency_score?: number;
    variance?: number;
    sample_size: number;
    easy_runs: number;
    moderate_runs: number;
    hard_runs: number;
  };
  load_response?: Array<{
    week_start: string;
    total_distance_km: number;
    total_distance_miles: number;
    total_duration_hours: number;
    activity_count: number;
    avg_efficiency?: number;
    efficiency_delta?: number;
    load_type: 'productive' | 'wasted' | 'harmful' | 'neutral';
  }>;
}

export const analyticsService = {
  /**
   * Get efficiency trends over time
   */
  async getEfficiencyTrends(
    days: number = 90,
    include_stability: boolean = true,
    include_load_response: boolean = true,
    include_annotations: boolean = true
  ): Promise<EfficiencyTrendsResponse> {
    const params = new URLSearchParams({
      days: days.toString(),
      include_stability: include_stability.toString(),
      include_load_response: include_load_response.toString(),
      include_annotations: include_annotations.toString(),
    });
    return apiClient.get<EfficiencyTrendsResponse>(
      `/v1/analytics/efficiency-trends?${params.toString()}`
    );
  },
} as const;

