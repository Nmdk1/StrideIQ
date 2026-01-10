/**
 * React Query hooks for Pattern Recognition
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  analyzePatterns, 
  getAthleteContext, 
  getContextBlock,
  type PatternAnalysisResult,
  type AthleteContextProfile,
} from '@/lib/api/services/patterns';

// Query keys
export const patternKeys = {
  all: ['patterns'] as const,
  context: () => [...patternKeys.all, 'context'] as const,
  contextBlock: () => [...patternKeys.all, 'contextBlock'] as const,
  analysis: (currentId: string, comparisonIds: string[]) => 
    [...patternKeys.all, 'analysis', currentId, ...comparisonIds] as const,
};

/**
 * Get athlete's current context profile.
 * Cached and auto-refreshed.
 */
export function useAthleteContext() {
  return useQuery({
    queryKey: patternKeys.context(),
    queryFn: getAthleteContext,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Get context block for GPT injection.
 */
export function useContextBlock() {
  return useQuery({
    queryKey: patternKeys.contextBlock(),
    queryFn: getContextBlock,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Mutation for pattern analysis.
 * Call this when user triggers a comparison.
 */
export function useAnalyzePatterns() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ 
      currentActivityId, 
      comparisonActivityIds 
    }: { 
      currentActivityId: string; 
      comparisonActivityIds: string[];
    }) => analyzePatterns(currentActivityId, comparisonActivityIds),
    onSuccess: () => {
      // Optionally invalidate related queries
      queryClient.invalidateQueries({ queryKey: patternKeys.all });
    },
  });
}
