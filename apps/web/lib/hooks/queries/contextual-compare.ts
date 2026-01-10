/**
 * React Query hooks for Contextual Comparison
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  findSimilarRuns,
  autoCompareSimilar,
  compareSelectedRuns,
  getQuickScore,
  ContextualComparisonResult,
  QuickScore,
} from '@/lib/api/services/contextual-compare';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const contextualCompareKeys = {
  all: ['contextual-compare'] as const,
  similar: (activityId: string) => [...contextualCompareKeys.all, 'similar', activityId] as const,
  autoSimilar: (activityId: string) => [...contextualCompareKeys.all, 'auto-similar', activityId] as const,
  quickScore: (activityId: string) => [...contextualCompareKeys.all, 'quick-score', activityId] as const,
};

// =============================================================================
// QUERIES
// =============================================================================

/**
 * Find similar runs with full contextual comparison
 */
export function useSimilarRuns(
  activityId: string | null,
  options?: {
    maxResults?: number;
    minSimilarity?: number;
    daysBack?: number;
  }
) {
  return useQuery({
    queryKey: contextualCompareKeys.similar(activityId || ''),
    queryFn: () => findSimilarRuns(activityId!, options),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Auto-compare with similar runs (one-click)
 */
export function useAutoCompareSimilar(activityId: string | null) {
  return useQuery({
    queryKey: contextualCompareKeys.autoSimilar(activityId || ''),
    queryFn: () => autoCompareSimilar(activityId!),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Get quick performance score
 */
export function useQuickScore(activityId: string | null) {
  return useQuery({
    queryKey: contextualCompareKeys.quickScore(activityId || ''),
    queryFn: () => getQuickScore(activityId!),
    enabled: !!activityId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// =============================================================================
// MUTATIONS
// =============================================================================

/**
 * Compare user-selected runs
 */
export function useCompareSelected() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ 
      activityIds, 
      baselineId 
    }: { 
      activityIds: string[]; 
      baselineId?: string;
    }) => compareSelectedRuns(activityIds, baselineId),
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: contextualCompareKeys.all });
    },
  });
}
