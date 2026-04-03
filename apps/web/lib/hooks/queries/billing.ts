import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface TrialStatus {
  has_trial: boolean;
  trial_days_remaining: number;
  trial_ends_at: string | null;
  subscription_status: string | null;
  subscription_tier: string;
  facts_learned: number;
  findings_discovered: number;
  activities_analyzed: number;
}

export function useTrialStatus() {
  return useQuery<TrialStatus>({
    queryKey: ['billing', 'trial-status'],
    queryFn: () => apiClient.get<TrialStatus>('/v1/billing/trial/status'),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
