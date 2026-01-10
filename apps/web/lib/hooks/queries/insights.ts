import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { insightsService } from '@/lib/api/services/insights';

export const useActiveInsights = (limit = 10) => {
  return useQuery({
    queryKey: ['insights', 'active', limit],
    queryFn: () => insightsService.getActiveInsights(limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useBuildStatus = () => {
  return useQuery({
    queryKey: ['insights', 'build-status'],
    queryFn: () => insightsService.getBuildStatus(),
    staleTime: 5 * 60 * 1000,
  });
};

export const useAthleteIntelligence = () => {
  return useQuery({
    queryKey: ['insights', 'intelligence'],
    queryFn: () => insightsService.getAthleteIntelligence(),
    staleTime: 10 * 60 * 1000, // 10 minutes - this data changes slowly
  });
};

export const useDismissInsight = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (insightId: string) => insightsService.dismissInsight(insightId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['insights', 'active'] });
    },
  });
};

export const useSaveInsight = () => {
  return useMutation({
    mutationFn: (insightId: string) => insightsService.saveInsight(insightId),
  });
};

export const useGenerateInsights = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => insightsService.generateInsights(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['insights'] });
    },
  });
};
