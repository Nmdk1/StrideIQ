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

export interface LoadResponseExplainResponse {
  week: { week_start: string; week_end: string };
  load_type: 'productive' | 'wasted' | 'harmful' | 'neutral';
  confidence: 'low' | 'moderate' | 'high';
  interpretation: {
    meaning: string;
    taper_cutback_note: string;
    volume_change_pct: number | null;
  };
  data_sources: {
    activities_week: number;
    activities_previous_week: number;
    checkins_week: number;
    checkins_baseline: number;
    activities_baseline: number;
  };
  rule: {
    productive_if_delta_lt: number;
    harmful_if_delta_gt: number;
    wasted_if_abs_delta_lt: number;
    note: string;
  };
  metrics: {
    current: {
      total_distance_miles: number;
      total_distance_km: number;
      total_duration_hours: number;
      activity_count: number;
      avg_efficiency: number | null;
    };
    previous: {
      total_distance_miles: number;
      total_distance_km: number;
      total_duration_hours: number;
      activity_count: number;
      avg_efficiency: number | null;
    };
    efficiency_delta: number | null;
    volume_change_pct: number | null;
  };
  signals: Array<{
    factor: string;
    label: string;
    week_avg: number;
    baseline_avg: number;
    delta: number;
    z: number | null;
    direction: 'higher_better' | 'lower_better';
    is_worse: boolean | null;
    sample_size_week: number;
    sample_size_baseline: number;
  }>;
  activity_signals: Array<{
    factor: string;
    label: string;
    week_avg: number;
    baseline_avg: number;
    delta: number;
    direction: 'higher_more_strain' | 'higher_better' | 'lower_better';
    is_worse: boolean | null;
    sample_size_week: number;
    sample_size_baseline: number;
  }>;
  week_vs_prev_activity_signals: Array<{
    factor: string;
    label: string;
    week_avg: number;
    previous_week_avg: number;
    delta: number;
    direction: 'higher_more_strain' | 'higher_better' | 'lower_better';
    is_worse: boolean | null;
    sample_size_week: number;
    sample_size_previous_week: number;
  }>;
  generated_at: string;
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

  async explainLoadResponseWeek(weekStart: string): Promise<LoadResponseExplainResponse> {
    return apiClient.get<LoadResponseExplainResponse>(
      `/v1/analytics/load-response-explain?week_start=${encodeURIComponent(weekStart)}`
    );
  },
} as const;

