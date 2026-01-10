/**
 * React Query hooks for Attribution Engine
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  analyzeAttribution,
  getActivityAttribution,
  getAttributionSummary,
} from '@/lib/api/services/attribution';

// Query keys
export const attributionKeys = {
  all: ['attribution'] as const,
  activity: (id: string) => [...attributionKeys.all, 'activity', id] as const,
  summary: (id: string) => [...attributionKeys.all, 'summary', id] as const,
};

/**
 * Hook for full attribution analysis of an activity
 */
export function useActivityAttribution(
  activityId: string | null,
  options?: { daysBack?: number; maxComparisons?: number }
) {
  return useQuery({
    queryKey: attributionKeys.activity(activityId || ''),
    queryFn: () => getActivityAttribution(
      activityId!,
      options?.daysBack,
      options?.maxComparisons
    ),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook for lightweight attribution summary
 */
export function useAttributionSummary(activityId: string | null) {
  return useQuery({
    queryKey: attributionKeys.summary(activityId || ''),
    queryFn: () => getAttributionSummary(activityId!),
    enabled: !!activityId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Mutation hook for analyzing attribution between selected activities
 */
export function useAnalyzeAttribution() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({
      currentActivityId,
      baselineActivityIds,
      performanceDelta,
    }: {
      currentActivityId: string;
      baselineActivityIds: string[];
      performanceDelta?: number;
    }) => analyzeAttribution(currentActivityId, baselineActivityIds, performanceDelta),
    onSuccess: (data, variables) => {
      // Cache the result
      queryClient.setQueryData(
        attributionKeys.activity(variables.currentActivityId),
        data
      );
    },
  });
}
