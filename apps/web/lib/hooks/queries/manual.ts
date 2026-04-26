import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ManualThreshold {
  value: number;
  direction: string;
  label: string;
  input_name?: string;
  human_input?: string;
}

export interface ManualAsymmetry {
  ratio: number;
  direction: string;
  label: string;
}

export interface ManualTiming {
  half_life_days?: number;
  decay_type?: string;
  lag_days?: number;
}

export interface ManualCascade {
  mediator: string;
  mediator_variable?: string;
  direct_effect: number | null;
  indirect_effect: number | null;
  mediation_ratio: number | null;
  is_full_mediation: boolean;
}

export interface ManualEntry {
  id: string;
  source: 'correlation' | 'investigation';
  headline: string;
  times_confirmed?: number;
  confidence_tier?: string;
  confidence?: string;
  direction?: string;
  direction_counterintuitive?: boolean;
  r?: number;
  strength?: string;
  category?: string;
  input?: string;
  output?: string;
  investigation?: string;
  finding_type?: string;
  layer?: string;
  first_detected?: string | null;
  last_confirmed?: string | null;
  threshold?: ManualThreshold | null;
  asymmetry?: ManualAsymmetry | null;
  timing?: ManualTiming | null;
  cascade?: ManualCascade[] | null;
  lifecycle_state?: string | null;
  receipts?: Record<string, unknown> | null;
}

export interface ManualSection {
  domain: string;
  label: string;
  description: string;
  entry_count: number;
  entries: ManualEntry[];
}

export interface ManualSummary {
  total_entries: number;
  correlation_findings: number;
  confirmed_findings: number;
  strong_findings: number;
  investigation_findings: number;
  domains_covered: number;
  learning_since: string | null;
  cascade_story_count?: number;
}

export interface RaceEntry {
  date: string;
  name: string;
  distance_m: number;
  race_pace: string;
  race_pace_s: number;
  avg_hr: number | null;
  is_pb: boolean;
  training_pace?: string;
  gap_pct?: number;
  training_runs_compared?: number;
}

export interface RaceCounterevidence {
  race_date: string;
  race_name: string;
  gap_pct: number;
  finding_input: string;
  finding_output: string;
  threshold: number;
  threshold_direction: string;
  actual_value: number;
  times_confirmed: number;
  text: string;
}

export interface RaceCharacter {
  races: RaceEntry[];
  race_count: number;
  has_gap_data: boolean;
  avg_gap_pct?: number;
  pb_count?: number;
  all_pbs?: boolean;
  narrative?: string;
  counterevidence?: RaceCounterevidence[];
}

export interface CascadeMediator {
  name: string;
  mediation_pct: number;
}

export interface CascadeStory {
  id: string;
  title?: string;
  input: string;
  input_name: string;
  outputs: string[];
  chain: string[];
  mediators: CascadeMediator[];
  narrative: string;
  times_confirmed: number;
  finding_count: number;
  finding_ids: string[];
}

export interface OperatingManualResponse {
  generated_at: string;
  summary: ManualSummary;
  race_character: RaceCharacter | null;
  cascade_stories: CascadeStory[];
  highlighted_findings: ManualEntry[];
  sections: ManualSection[];
}

export function useOperatingManual() {
  return useQuery<OperatingManualResponse>({
    queryKey: ['progress', 'manual'],
    queryFn: () => apiClient.get<OperatingManualResponse>('/v1/progress/manual'),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
