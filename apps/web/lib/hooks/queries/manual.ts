import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ManualThreshold {
  value: number;
  direction: string;
  label: string;
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
  receipts?: Record<string, any> | null;
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
}

export interface OperatingManualResponse {
  generated_at: string;
  summary: ManualSummary;
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
