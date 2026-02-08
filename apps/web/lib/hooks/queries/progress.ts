/**
 * React Query hooks for the unified Progress page (ADR-17 Phase 3)
 *
 * Aggregates: progress summary, correlations, efficiency trends,
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
  distance_name: string;
  distance_m: number;
  elapsed_time_s: number;
  pace_per_mile_s?: number;
  date: string;
  activity_id?: string;
  source?: string;
}

// --- Hooks ---

export function useProgressSummary(days: number = 28) {
  return useQuery<ProgressSummary>({
    queryKey: ['progress', 'summary', days],
    queryFn: () => apiClient.get<ProgressSummary>(`/v1/progress/summary?days=${days}`),
    staleTime: 5 * 60 * 1000, // 5 min
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
      // Get athlete ID first
      const me = await apiClient.get<{ id: string }>('/v1/auth/me');
      return apiClient.get<PersonalBest[]>(`/v1/athletes/${me.id}/personal-bests`);
    },
    staleTime: 30 * 60 * 1000, // 30 min
    retry: 1,
  });
}
