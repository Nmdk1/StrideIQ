/**
 * Attribution Engine API Service
 * 
 * The "WHY" behind performance changes.
 */

import { apiClient } from '../client';

// =============================================================================
// TYPES
// =============================================================================

export interface InputDelta {
  category: string;
  name: string;
  icon: string;
  current_value: number | null;
  baseline_value: number | null;
  delta: number | null;
  delta_pct: number | null;
  unit: string;
  data_points_current: number;
  data_points_baseline: number;
  has_sufficient_data: boolean;
}

export interface PerformanceDriver {
  category: string;
  name: string;
  icon: string;
  direction: 'positive' | 'negative' | 'neutral';
  magnitude: string;
  contribution_score: number;
  confidence: 'high' | 'moderate' | 'low' | 'insufficient';
  insight: string;
  delta: InputDelta;
}

export interface AttributionResult {
  performance_delta: number;
  performance_direction: 'improved' | 'declined' | 'stable';
  input_deltas: InputDelta[];
  key_drivers: PerformanceDriver[];
  summary_positive: string | null;
  summary_negative: string | null;
  overall_confidence: 'high' | 'moderate' | 'low' | 'insufficient';
  current_period: { start: string; end: string };
  baseline_period: { start: string; end: string };
  data_quality_score: number;
}

export interface AttributionResponse {
  success: boolean;
  data: AttributionResult | null;
  message?: string;
}

export interface AttributionSummary {
  activity_id: string;
  has_attribution: boolean;
  top_drivers: Array<{
    name: string;
    icon: string;
    direction: string;
    magnitude: string;
  }>;
  summary: string | null;
  data_quality?: number;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Analyze performance drivers for a comparison
 */
export async function analyzeAttribution(
  currentActivityId: string,
  baselineActivityIds: string[],
  performanceDelta?: number
): Promise<AttributionResponse> {
  return apiClient.post('/v1/attribution/analyze', {
    current_activity_id: currentActivityId,
    baseline_activity_ids: baselineActivityIds,
    performance_delta: performanceDelta,
  });
}

/**
 * Get attribution for a single activity against history
 */
export async function getActivityAttribution(
  activityId: string,
  daysBack: number = 90,
  maxComparisons: number = 10
): Promise<AttributionResponse> {
  const params = new URLSearchParams({
    days_back: daysBack.toString(),
    max_comparisons: maxComparisons.toString(),
  });
  return apiClient.get(`/v1/attribution/activity/${activityId}?${params}`);
}

/**
 * Get lightweight attribution summary for activity cards
 */
export async function getAttributionSummary(
  activityId: string
): Promise<AttributionSummary> {
  return apiClient.get(`/v1/attribution/summary/${activityId}`);
}
