/**
 * React Query hooks for Contextual Comparison
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  findSimilarRuns,
  autoCompareSimilar,
  compareSelectedRuns,
  getQuickScore,
  findByAvgHR,
  findByMaxHR,
  findByHRRange,
  ContextualComparisonResult,
  QuickScore,
  HRSearchResult,
} from '@/lib/api/services/contextual-compare';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const contextualCompareKeys = {
  all: ['contextual-compare'] as const,
  similar: (activityId: string) => [...contextualCompareKeys.all, 'similar', activityId] as const,
  autoSimilar: (activityId: string) => [...contextualCompareKeys.all, 'auto-similar', activityId] as const,
  quickScore: (activityId: string) => [...contextualCompareKeys.all, 'quick-score', activityId] as const,
  // HR search keys
  byAvgHR: (activityId: string) => [...contextualCompareKeys.all, 'by-avg-hr', activityId] as const,
  byMaxHR: (activityId: string) => [...contextualCompareKeys.all, 'by-max-hr', activityId] as const,
  hrRange: (minHR: number, maxHR: number) => [...contextualCompareKeys.all, 'hr-range', minHR, maxHR] as const,
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

// =============================================================================
// HR-BASED SEARCH HOOKS
// Explicit heart rate queries - foundation for query engine
// =============================================================================

/**
 * Find runs with similar average heart rate
 * Physiologically, same avg HR = same relative effort
 */
export function useByAvgHR(
  activityId: string | null,
  options?: {
    tolerance?: number;
    maxResults?: number;
    daysBack?: number;
  }
) {
  return useQuery({
    queryKey: contextualCompareKeys.byAvgHR(activityId || ''),
    queryFn: () => findByAvgHR(activityId!, options),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Find runs with similar maximum heart rate
 * Same max HR = similar peak cardiovascular stress
 */
export function useByMaxHR(
  activityId: string | null,
  options?: {
    tolerance?: number;
    maxResults?: number;
    daysBack?: number;
  }
) {
  return useQuery({
    queryKey: contextualCompareKeys.byMaxHR(activityId || ''),
    queryFn: () => findByMaxHR(activityId!, options),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Find all runs within an HR range
 * Pure query - no reference activity needed
 * Example: "Show me all runs at 145-155 bpm"
 */
export function useHRRange(
  minHR: number | null,
  maxHR: number | null,
  options?: {
    minDuration?: number;
    maxResults?: number;
    daysBack?: number;
  }
) {
  return useQuery({
    queryKey: contextualCompareKeys.hrRange(minHR || 0, maxHR || 0),
    queryFn: () => findByHRRange(minHR!, maxHR!, options),
    enabled: minHR !== null && maxHR !== null && minHR > 0 && maxHR > 0,
    staleTime: 5 * 60 * 1000,
  });
}
