/**
 * React Query hooks for insight feedback
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { insightFeedbackService, type InsightFeedbackCreate } from '../../api/services/insightFeedback';
import type { InsightFeedback, InsightFeedbackStats } from '../../api/services/insightFeedback';

export const insightFeedbackKeys = {
  all: ['insight-feedback'] as const,
  lists: () => [...insightFeedbackKeys.all, 'list'] as const,
  list: (params?: any) => [...insightFeedbackKeys.lists(), params] as const,
  stats: () => [...insightFeedbackKeys.all, 'stats'] as const,
} as const;

/**
 * List insight feedback
 */
export function useInsightFeedback(params?: {
  insight_type?: string;
  helpful?: boolean;
  limit?: number;
  offset?: number;
}) {
  return useQuery<InsightFeedback[]>({
    queryKey: insightFeedbackKeys.list(params),
    queryFn: () => insightFeedbackService.listFeedback(params),
    staleTime: 60 * 1000, // 1 minute
  });
}

/**
 * Get feedback statistics
 */
export function useInsightFeedbackStats() {
  return useQuery<InsightFeedbackStats>({
    queryKey: insightFeedbackKeys.stats(),
    queryFn: () => insightFeedbackService.getStats(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Create insight feedback mutation
 */
export function useCreateInsightFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (feedback: InsightFeedbackCreate) => insightFeedbackService.createFeedback(feedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: insightFeedbackKeys.all });
    },
  });
}


