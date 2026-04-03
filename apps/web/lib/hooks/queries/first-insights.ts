import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface TopCorrelation {
  headline: string;
  input: string;
  output: string;
  direction: string;
  r: number;
  times_confirmed: number;
  strength: string;
  threshold_label?: string | null;
  asymmetry_label?: string | null;
}

export interface TopInvestigation {
  headline: string;
  type: string;
  confidence: string;
}

export interface FirstInsightsResponse {
  ready: boolean;
  activity_count?: number;
  history_span_days?: number;
  correlation_count?: number;
  investigation_count?: number;
  top_correlations?: TopCorrelation[];
  top_investigations?: TopInvestigation[];
}

export function useFirstInsights(enabled = true) {
  return useQuery<FirstInsightsResponse>({
    queryKey: ['progress', 'first-insights'],
    queryFn: () => apiClient.get<FirstInsightsResponse>('/v1/progress/first-insights'),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      if (query.state.data?.ready) return false;
      return 15_000;
    },
    enabled,
  });
}
