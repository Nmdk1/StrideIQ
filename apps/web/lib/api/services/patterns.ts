/**
 * Pattern Recognition API
 * 
 * The upgraded "WHY" engine that uses per-run trailing analysis
 * instead of simple averages.
 */

import { apiClient } from '../client';

// =============================================================================
// TYPES
// =============================================================================

export interface TrailingContext {
  activity_id: string;
  activity_date: string;
  activity_name: string;
  pace_per_km: number | null;
  avg_hr: number | null;
  trailing_volume_km: number;
  trailing_run_count: number;
  trailing_avg_weekly_km: number;
  acwr: number;
  acwr_interpretation: string;
  avg_sleep_hours: number | null;
  sleep_data_points: number;
}

export interface PatternInsight {
  input_name: string;
  display_name: string;
  icon: string;
  pattern_type: 'prerequisite' | 'common_factor' | 'deviation' | 'correlation';
  direction: 'higher' | 'lower' | 'similar' | 'unknown';
  pattern_value: string;
  current_value: string;
  consistency: number;
  consistency_str: string;
  correlation_direction: string;
  confidence: 'high' | 'moderate' | 'low' | 'insufficient';
  insight: string;
}

export interface FatigueContext {
  acwr: number;
  phase: 'taper' | 'recovery' | 'steady' | 'build' | 'overreaching';
  acute_load_km: number;
  chronic_load_km: number;
  explanation: string;
  current_is_fresher: boolean;
  current_is_more_fatigued: boolean;
  fatigue_delta: string;
}

export interface PatternAnalysisResult {
  current_run: {
    id: string;
    name: string;
    date: string;
  };
  comparison_run_count: number;
  prerequisites: PatternInsight[];
  common_factors: PatternInsight[];
  deviations: PatternInsight[];
  fatigue: FatigueContext;
  overall_data_quality: number;
  data_quality_notes: string[];
  context_block: string;
}

export interface TrainingState {
  acwr: number;
  phase: string;
  trailing_7d_km: number;
  trailing_28d_km: number;
  avg_weekly_km: number;
  runs_last_7d: number;
  runs_last_28d: number;
  avg_runs_per_week: number;
  intensity_distribution: {
    easy: number;
    tempo: number;
    long: number;
    interval: number;
  };
}

export interface RecentPerformance {
  last_5_runs_avg_pace_sec: number | null;
  pace_trend: string;
  last_5_runs_avg_hr: number | null;
  hr_trend: string;
  efficiency_trend: string;
  recent_workout_types: string[];
}

export interface DataAvailability {
  total_activities: number;
  activities_with_hr: number;
  activities_with_splits: number;
  checkin_density_30d: number;
  has_sleep_data: boolean;
  has_hrv_data: boolean;
  has_body_comp_data: boolean;
  earliest_activity: string | null;
  latest_activity: string | null;
  days_of_data: number;
}

export interface PersonalPatterns {
  best_performance_patterns: string[];
  typical_weekly_volume_km: number;
  typical_easy_pace_sec: number | null;
  typical_tempo_pace_sec: number | null;
  avg_runs_per_week: number;
  longest_streak_weeks: number;
}

export interface AthleteContextProfile {
  athlete_id: string;
  generated_at: string;
  training_state: TrainingState;
  recent_performance: RecentPerformance;
  data_availability: DataAvailability;
  patterns: PersonalPatterns;
  context_block: string;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Analyze patterns between a current run and comparison runs.
 * Uses per-run trailing analysis (not averages).
 */
export async function analyzePatterns(
  currentActivityId: string,
  comparisonActivityIds: string[]
): Promise<PatternAnalysisResult> {
  const response = await apiClient.post<{ success: boolean; data: PatternAnalysisResult }>(
    '/v1/attribution/patterns',
    {
      current_activity_id: currentActivityId,
      comparison_activity_ids: comparisonActivityIds,
    }
  );
  return response.data;
}

/**
 * Get the athlete's current context profile.
 * The "intelligence dossier" for smarter AI responses.
 */
export async function getAthleteContext(): Promise<AthleteContextProfile> {
  const response = await apiClient.get<{ success: boolean; data: AthleteContextProfile }>(
    '/v1/attribution/context'
  );
  return response.data;
}

/**
 * Get just the context block for GPT injection.
 * Returns plain text.
 */
export async function getContextBlock(): Promise<string> {
  const response = await apiClient.get<string>(
    '/v1/attribution/context/block'
  );
  return response;
}
