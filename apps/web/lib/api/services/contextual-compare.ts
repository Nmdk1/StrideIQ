/**
 * Contextual Comparison API Service
 * 
 * "Context vs Context" comparison - the differentiator.
 */

import { apiClient } from '../client';

// =============================================================================
// TYPES
// =============================================================================

export interface SimilarityBreakdown {
  duration: number;
  intensity: number;
  avg_hr: number;
  max_hr: number;
  type: number;
  conditions: number;
  elevation: number;
}

export interface SplitData {
  split_number: number;
  distance_m: number;
  elapsed_time_s: number;
  pace_per_km: number | null;
  avg_hr: number | null;
  cumulative_distance_m: number;
}

export interface SimilarRun {
  id: string;
  date: string;
  name: string;
  workout_type: string | null;
  distance_m: number;
  distance_km: number;
  duration_s: number;
  pace_per_km: number | null;
  pace_formatted: string | null;
  avg_hr: number | null;
  max_hr: number | null;
  efficiency: number | null;
  intensity_score: number | null;
  elevation_gain: number | null;
  temperature_f: number | null;
  similarity_score: number;
  similarity_breakdown: SimilarityBreakdown;
  splits: SplitData[];
}

export interface GhostAverage {
  num_runs_averaged: number;
  avg_pace_per_km: number | null;
  avg_pace_formatted: string | null;
  avg_hr: number | null;
  avg_max_hr: number | null;
  avg_efficiency: number | null;
  avg_duration_s: number | null;
  avg_duration_formatted: string | null;
  avg_distance_m: number | null;
  avg_distance_km: number | null;
  avg_elevation_gain: number | null;
  avg_temperature_f: number | null;
  avg_intensity_score: number | null;
  avg_splits: {
    split_number: number;
    avg_pace_per_km: number | null;
    avg_hr: number | null;
    num_runs_at_split: number;
  }[];
}

export interface PerformanceScore {
  score: number;
  rating: 'exceptional' | 'strong' | 'solid' | 'average' | 'below' | 'struggling';
  percentile: number;
  pace_vs_baseline: number;
  efficiency_vs_baseline: number;
  hr_vs_baseline: number;
  age_graded_performance: number | null;
}

export interface ContextFactor {
  name: string;
  icon: string;
  this_run_value: string;
  baseline_value: string;
  difference: string;
  impact: 'positive' | 'negative' | 'neutral';
  explanation: string;
}

export interface TargetRun {
  id: string;
  date: string;
  name: string;
  workout_type: string | null;
  distance_m: number;
  distance_km: number;
  duration_s: number;
  pace_per_km: number | null;
  pace_formatted: string | null;
  avg_hr: number | null;
  efficiency: number | null;
  intensity_score: number | null;
  elevation_gain: number | null;
  temperature_f: number | null;
  humidity_pct: number | null;
  performance_percentage: number | null;
  splits: SplitData[];
}

export interface ContextualComparisonResult {
  target_run: TargetRun;
  similar_runs: SimilarRun[];
  ghost_average: GhostAverage;
  performance_score: PerformanceScore;
  context_factors: ContextFactor[];
  headline: string;
  key_insight: string;
}

export interface QuickScore {
  activity_id: string;
  score: number | null;
  rating: string | null;
  headline: string;
  similar_runs_count: number;
  key_insight: string | null;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Find similar runs and build contextual comparison
 */
export async function findSimilarRuns(
  activityId: string,
  options: {
    maxResults?: number;
    minSimilarity?: number;
    daysBack?: number;
  } = {}
): Promise<ContextualComparisonResult> {
  const params = new URLSearchParams();
  if (options.maxResults) params.set('max_results', options.maxResults.toString());
  if (options.minSimilarity) params.set('min_similarity', options.minSimilarity.toString());
  if (options.daysBack) params.set('days_back', options.daysBack.toString());
  
  const queryString = params.toString();
  const url = `/v1/compare/similar/${activityId}${queryString ? `?${queryString}` : ''}`;
  
  return apiClient.get<ContextualComparisonResult>(url);
}

/**
 * Auto-compare with most similar runs (one-click magic)
 */
export async function autoCompareSimilar(
  activityId: string
): Promise<ContextualComparisonResult> {
  return apiClient.get<ContextualComparisonResult>(`/v1/compare/auto-similar/${activityId}`);
}

/**
 * Compare user-selected runs
 */
export async function compareSelectedRuns(
  activityIds: string[],
  baselineId?: string
): Promise<ContextualComparisonResult> {
  return apiClient.post<ContextualComparisonResult>('/v1/compare/selected', {
    activity_ids: activityIds,
    baseline_id: baselineId,
  });
}

/**
 * Get quick performance score for an activity
 */
export async function getQuickScore(
  activityId: string
): Promise<QuickScore> {
  return apiClient.get<QuickScore>(`/v1/compare/quick-score/${activityId}`);
}

// =============================================================================
// HR-BASED SEARCH FUNCTIONS
// Explicit heart rate based queries - foundation for query engine
// =============================================================================

export interface HRSearchActivity {
  id: string;
  name: string;
  date: string;
  workout_type: string | null;
  distance_m: number | null;
  distance_km: number | null;
  duration_s: number | null;
  pace_per_km: number | null;
  pace_formatted: string | null;
  avg_hr: number | null;
  max_hr: number | null;
  intensity_score: number | null;
  temperature_f: number | null;
  elevation_gain: number | null;
  hr_diff?: number; // Difference from target avg HR
  max_hr_diff?: number; // Difference from target max HR
}

export interface HRSearchResult {
  target_activity_id?: string;
  hr_tolerance?: number;
  hr_range?: { min: number; max: number };
  min_duration_minutes?: number | null;
  count: number;
  activities: HRSearchActivity[];
}

/**
 * Find runs with similar average heart rate
 */
export async function findByAvgHR(
  activityId: string,
  options: {
    tolerance?: number;
    maxResults?: number;
    daysBack?: number;
  } = {}
): Promise<HRSearchResult> {
  const params = new URLSearchParams();
  if (options.tolerance) params.set('tolerance', options.tolerance.toString());
  if (options.maxResults) params.set('max_results', options.maxResults.toString());
  if (options.daysBack) params.set('days_back', options.daysBack.toString());
  
  const queryString = params.toString();
  const url = `/v1/compare/by-avg-hr/${activityId}${queryString ? `?${queryString}` : ''}`;
  
  return apiClient.get<HRSearchResult>(url);
}

/**
 * Find runs with similar maximum heart rate
 */
export async function findByMaxHR(
  activityId: string,
  options: {
    tolerance?: number;
    maxResults?: number;
    daysBack?: number;
  } = {}
): Promise<HRSearchResult> {
  const params = new URLSearchParams();
  if (options.tolerance) params.set('tolerance', options.tolerance.toString());
  if (options.maxResults) params.set('max_results', options.maxResults.toString());
  if (options.daysBack) params.set('days_back', options.daysBack.toString());
  
  const queryString = params.toString();
  const url = `/v1/compare/by-max-hr/${activityId}${queryString ? `?${queryString}` : ''}`;
  
  return apiClient.get<HRSearchResult>(url);
}

/**
 * Find all runs within an average HR range (no reference activity needed)
 */
export async function findByHRRange(
  minHR: number,
  maxHR: number,
  options: {
    minDuration?: number; // in minutes
    maxResults?: number;
    daysBack?: number;
  } = {}
): Promise<HRSearchResult> {
  const params = new URLSearchParams();
  params.set('min_hr', minHR.toString());
  params.set('max_hr', maxHR.toString());
  if (options.minDuration) params.set('min_duration', options.minDuration.toString());
  if (options.maxResults) params.set('max_results', options.maxResults.toString());
  if (options.daysBack) params.set('days_back', options.daysBack.toString());
  
  return apiClient.get<HRSearchResult>(`/v1/compare/hr-range?${params.toString()}`);
}
