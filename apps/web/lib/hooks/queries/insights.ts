/**
 * React Query hooks for Athlete Insights
 */

import { useQuery, useMutation } from '@tanstack/react-query';
import { insightsService } from '@/lib/api/services/insights';
import type { InsightResult } from '@/lib/api/services/insights';

/**
 * Get available insight templates
 */
export function useInsightTemplates() {
  return useQuery({
    queryKey: ['insights', 'templates'],
    queryFn: () => insightsService.getTemplates(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * Execute an insight template
 */
export function useExecuteInsight() {
  return useMutation<
    InsightResult,
    Error,
    {
      templateId: string;
      days?: number;
      weeks?: number;
      limit?: number;
    }
  >({
    mutationFn: (params) => insightsService.executeInsight(params),
  });
}
