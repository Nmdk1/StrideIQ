/**
 * React Query hooks for the unified Progress page (ADR-17 Phase 3)
 *
 * Aggregates: progress summary (ALL tools), correlations, efficiency trends,
 * training load history, personal bests.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { useWhatWorks, useWhatDoesntWork } from './correlations';
import { useEfficiencyTrends } from './analytics';

// Re-export correlation hooks for convenience
export { useWhatWorks, useWhatDoesntWork, useEfficiencyTrends };

// --- Types ---

export interface PeriodMetrics {
  run_count: number;
  total_distance_mi: number;
  total_duration_hr: number;
  avg_hr: number | null;
}

export interface PeriodComparison {
  current: PeriodMetrics;
  previous: PeriodMetrics;
  volume_change_pct: number | null;
  run_count_change: number;
  hr_change: number | null;
}

export interface ProgressHeadline {
  text: string;
  subtext?: string;
}

export interface RecoveryData {
  durability_index: number | null;
  recovery_half_life_hours: number | null;
  injury_risk_score: number | null;
  false_fitness: boolean;
  masked_fatigue: boolean;
  status: string | null;
}

export interface RacePrediction {
  distance: string;
  predicted_time: string | null;
  confidence: string | null;
}

export interface TrainingPaces {
  rpi: number | null;
  easy: string | null;
  marathon: string | null;
  threshold: string | null;
  interval: string | null;
  repetition: string | null;
}

export interface RunnerProfile {
  runner_type: string | null;
  max_hr: number | null;
  rpi: number | null;
  training_paces: TrainingPaces | null;
  age: number | null;
  sex: string | null;
}

export interface WellnessTrends {
  avg_sleep: number | null;
  avg_motivation: number | null;
  avg_soreness: number | null;
  avg_stress: number | null;
  checkin_count: number;
  trend_direction: string | null;
}

export interface VolumeWeek {
  week_start: string;
  miles: number;
  runs: number;
}

export interface VolumeTrajectory {
  recent_weeks: VolumeWeek[] | null;
  current_week_mi: number | null;
  peak_week_mi: number | null;
  trend_pct: number | null;
}

export interface ProgressSummary {
  headline: ProgressHeadline | null;
  period_comparison: PeriodComparison | null;
  ctl: number | null;
  atl: number | null;
  tsb: number | null;
  ctl_trend: string | null;
  tsb_zone: string | null;
  efficiency_trend: string | null;
  efficiency_current: number | null;
  efficiency_average: number | null;
  efficiency_best: number | null;
  // Full system data
  recovery: RecoveryData | null;
  race_predictions: RacePrediction[] | null;
  runner_profile: RunnerProfile | null;
  wellness: WellnessTrends | null;
  volume_trajectory: VolumeTrajectory | null;
  consistency_index: number | null;
  pb_count_last_90d: number;
  pb_patterns: Record<string, unknown> | null;
  goal_race_name: string | null;
  goal_race_date: string | null;
  goal_race_days_remaining: number | null;
  goal_time: string | null;
}

export interface TrainingLoadDay {
  date: string;
  total_tss: number;
  workout_count: number;
  atl: number;
  ctl: number;
  tsb: number;
}

export interface PersonalBest {
  id: string;
  athlete_id: string;
  distance_category: string;
  distance_meters: number;
  time_seconds: number;
  pace_per_mile: number | null;
  activity_id: string;
  achieved_at: string;
  is_race: boolean;
  age_at_achievement: number | null;
}

// --- Hooks ---

export function useProgressSummary(days: number = 28) {
  return useQuery<ProgressSummary>({
    queryKey: ['progress', 'summary', days],
    queryFn: () => apiClient.get<ProgressSummary>(`/v1/progress/summary?days=${days}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useTrainingLoadHistory(days: number = 90) {
  return useQuery({
    queryKey: ['training-load', 'history', days],
    queryFn: () =>
      apiClient.get<{
        history: TrainingLoadDay[];
        summary: {
          atl: number;
          ctl: number;
          tsb: number;
          atl_trend: string;
          ctl_trend: string;
          tsb_trend: string;
          training_phase: string;
          recommendation: string;
        };
        personal_zones?: {
          current_zone: string;
          zone_description: string;
          is_personalized: boolean;
        };
      }>(`/v1/training-load/history?days=${days}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function usePersonalBests() {
  return useQuery({
    queryKey: ['personal-bests'],
    queryFn: async () => {
      const me = await apiClient.get<{ id: string }>('/v1/auth/me');
      return apiClient.get<PersonalBest[]>(`/v1/athletes/${me.id}/personal-bests`);
    },
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
}
