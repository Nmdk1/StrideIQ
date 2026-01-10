/**
 * Correlations API Service
 * 
 * Service for correlation analysis endpoints.
 * Discovers which inputs lead to efficiency improvements.
 */

import { apiClient } from '../client';

export interface Correlation {
  input_name: string;
  correlation_coefficient: number;
  p_value: number;
  sample_size: number;
  is_significant: boolean;
  direction: 'positive' | 'negative';
  strength: 'weak' | 'moderate' | 'strong';
  time_lag_days: number;
  combination_factors: string[];
}

export interface CorrelationAnalysisResponse {
  athlete_id: string;
  analysis_period: {
    start: string;
    end: string;
    days: number;
  };
  sample_sizes: {
    activities: number;
    inputs: Record<string, number>;
  };
  correlations: Correlation[];
  total_correlations_found: number;
}

export interface WhatWorksResponse {
  athlete_id: string;
  analysis_period: {
    start: string;
    end: string;
    days: number;
  };
  what_works: Correlation[];
  count: number;
}

export interface WhatDoesntWorkResponse {
  athlete_id: string;
  analysis_period: {
    start: string;
    end: string;
    days: number;
  };
  what_doesnt_work: Correlation[];
  count: number;
}

export const correlationsService = {
  /**
   * Discover all correlations between inputs and efficiency
   */
  async discoverCorrelations(
    days: number = 90
  ): Promise<CorrelationAnalysisResponse> {
    const params = new URLSearchParams({
      days: days.toString(),
    });
    return apiClient.get<CorrelationAnalysisResponse>(
      `/v1/correlations/discover?${params.toString()}`
    );
  },

  /**
   * Get "What's Working" - positive correlations (improves efficiency)
   */
  async whatWorks(days: number = 90): Promise<WhatWorksResponse> {
    const params = new URLSearchParams({
      days: days.toString(),
    });
    return apiClient.get<WhatWorksResponse>(
      `/v1/correlations/what-works?${params.toString()}`
    );
  },

  /**
   * Get "What Doesn't Work" - negative correlations (reduces efficiency)
   */
  async whatDoesntWork(days: number = 90): Promise<WhatDoesntWorkResponse> {
    const params = new URLSearchParams({
      days: days.toString(),
    });
    return apiClient.get<WhatDoesntWorkResponse>(
      `/v1/correlations/what-doesnt-work?${params.toString()}`
    );
  },
} as const;


