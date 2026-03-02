/**
 * React Query hooks for the unified Progress page (ADR-17 Phase 3)
 *
 * Aggregates: progress summary (ALL tools), correlations, efficiency trends,
 * training load history, personal bests.
 */

import { useQuery, useMutation } from '@tanstack/react-query';
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

export interface ProgressCoachCard {
  id: string;
  title: string;
  summary: string;
  trend_context: string;
  drivers: string;
  next_step: string;
  ask_coach_query: string;
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
  coach_cards: ProgressCoachCard[] | null;
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

// Training patterns from InsightAggregator (Layer 1 of dual-layer What's Working)
export interface TrainingPatternItem {
  text: string;
  source: string;
}

export interface TrainingPatternsResponse {
  what_works: TrainingPatternItem[];
  what_doesnt: TrainingPatternItem[];
  injury_patterns: TrainingPatternItem[];
  checkin_count: number;
  checkins_needed: number;
}

export function useTrainingPatterns() {
  return useQuery<TrainingPatternsResponse>({
    queryKey: ['progress', 'training-patterns'],
    queryFn: () => apiClient.get<TrainingPatternsResponse>('/v1/progress/training-patterns'),
    staleTime: 10 * 60 * 1000, // 10 min — patterns change slowly
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

// ═══════════════════════════════════════════════════════════════════
// Progress Narrative (Spec V1) — visual-first progress story
// ═══════════════════════════════════════════════════════════════════

export interface NarrativeVerdict {
  sparkline_data: number[];
  sparkline_direction: 'rising' | 'stable' | 'declining';
  current_value: number;
  text: string;
  grounding: string[];
  confidence: 'high' | 'moderate' | 'low';
}

export interface NarrativeChapter {
  title: string;
  topic: string;
  visual_type: 'bar_chart' | 'sparkline' | 'health_strip' | 'gauge' | 'completion_ring' | 'dot_plot' | 'stat_highlight';
  visual_data: Record<string, unknown>;
  observation: string;
  evidence: string;
  interpretation: string;
  action: string;
  relevance_score: number;
}

export interface PersonalPattern {
  narrative: string;
  input_metric: string;
  output_metric: string;
  visual_type: 'paired_sparkline';
  visual_data: {
    input_series: number[];
    output_series: number[];
    input_label: string;
    output_label: string;
  };
  times_confirmed: number;
  current_relevance: string;
  confidence: 'emerging' | 'confirmed' | 'strong';
}

export interface PatternsForming {
  checkin_count: number;
  checkins_needed: number;
  progress_pct: number;
  message: string;
}

export interface RaceScenario {
  label: string;
  narrative: string;
  estimated_finish?: string;
  key_action?: string;
}

export interface RaceAhead {
  race_name: string;
  days_remaining: number;
  readiness_score: number;
  readiness_label: string;
  gauge_zones: string[];
  scenarios: RaceScenario[];
  training_phase: string;
}

export interface TrajectoryCapability {
  distance: string;
  current: string | null;
  previous: string | null;
  confidence: 'high' | 'moderate' | 'low';
}

export interface TrajectoryAhead {
  capabilities: TrajectoryCapability[];
  narrative: string;
  trend_driver: string;
  milestone_hint: string | null;
}

export interface LookingAhead {
  variant: 'race' | 'trajectory';
  race: RaceAhead | null;
  trajectory: TrajectoryAhead | null;
}

export interface AthleteControls {
  feedback_options: string[];
  coach_query: string;
}

export interface DataCoverage {
  activity_days: number;
  checkin_days: number;
  garmin_days: number;
  correlation_findings: number;
}

export interface ProgressNarrativeResponse {
  verdict: NarrativeVerdict;
  chapters: NarrativeChapter[];
  personal_patterns: PersonalPattern[];
  patterns_forming: PatternsForming | null;
  looking_ahead: LookingAhead;
  athlete_controls: AthleteControls;
  generated_at: string;
  data_coverage: DataCoverage;
}

export function useProgressNarrative() {
  return useQuery<ProgressNarrativeResponse>({
    queryKey: ['progress', 'narrative'],
    queryFn: () => apiClient.get<ProgressNarrativeResponse>('/v1/progress/narrative'),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useNarrativeFeedback() {
  return useMutation({
    mutationFn: (body: { feedback_type: string; feedback_detail?: string }) =>
      apiClient.post('/v1/progress/narrative/feedback', body),
  });
}


// ═══════════════════════════════════════════════════════════════════
// Progress Knowledge — Phase 1 types and hook
// ═══════════════════════════════════════════════════════════════════

export interface KnowledgeHeroStat {
  label: string;
  value: string;
  color: string;
}

export interface KnowledgeHero {
  date_label: string;
  headline: string;
  headline_accent: string;
  subtext: string;
  stats: KnowledgeHeroStat[];
}

export interface CorrelationNode {
  id: string;
  label: string;
  group: string;
}

export interface CorrelationEdge {
  source: string;
  target: string;
  r: number;
  direction: string;
  lag_days: number;
  times_confirmed: number;
  strength: string;
  note: string;
}

export interface ProvedFact {
  input_metric: string;
  output_metric: string;
  headline: string;
  evidence: string;
  implication: string;
  times_confirmed: number;
  confidence_tier: string;
  direction: string;
  correlation_coefficient: number;
  lag_days: number;
}

export interface KnowledgePatternsForming {
  checkin_count: number;
  checkins_needed: number;
  progress_pct: number;
  message: string;
}

export interface KnowledgeDataCoverage {
  total_findings: number;
  confirmed_findings: number;
  emerging_findings: number;
  checkin_count: number;
}

export interface ProgressKnowledgeResponse {
  hero: KnowledgeHero;
  correlation_web: {
    nodes: CorrelationNode[];
    edges: CorrelationEdge[];
  };
  proved_facts: ProvedFact[];
  patterns_forming: KnowledgePatternsForming | null;
  generated_at: string;
  data_coverage: KnowledgeDataCoverage;
}

export function useProgressKnowledge() {
  return useQuery<ProgressKnowledgeResponse>({
    queryKey: ['progress', 'knowledge'],
    queryFn: () => apiClient.get<ProgressKnowledgeResponse>('/v1/progress/knowledge'),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
