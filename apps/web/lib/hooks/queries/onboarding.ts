import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { onboardingService } from '@/lib/api/services/onboarding';

export const onboardingKeys = {
  all: ['onboarding'] as const,
  status: () => [...onboardingKeys.all, 'status'] as const,
} as const;

export function useOnboardingStatus(enabled: boolean = true) {
  return useQuery({
    queryKey: onboardingKeys.status(),
    queryFn: () => onboardingService.getStatus(),
    enabled,
    staleTime: 10 * 1000,
    refetchInterval: (query) => {
      const s = query.state.data?.ingestion_state?.last_index_status;
      if (s === 'running') return 2000;
      return false;
    },
  });
}

export function useBootstrapOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => onboardingService.bootstrap(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: onboardingKeys.status() });
      qc.invalidateQueries({ queryKey: ['home'] });
      qc.invalidateQueries({ queryKey: ['activities'] });
    },
  });
}

