/**
 * React Query Hooks for Analytics
 */

import { useQuery } from '@tanstack/react-query';
import { analyticsService } from '../../api/services/analytics';
import type { EfficiencyTrendsResponse } from '../../api/services/analytics';

export const analyticsKeys = {
  all: ['analytics'] as const,
  efficiencyTrends: (days: number, includeStability: boolean, includeLoadResponse: boolean, includeAnnotations: boolean) =>
    [...analyticsKeys.all, 'efficiency-trends', days, includeStability, includeLoadResponse, includeAnnotations] as const,
} as const;

/**
 * Get efficiency trends
 */
export function useEfficiencyTrends(
  days: number = 90,
  includeStability: boolean = true,
  includeLoadResponse: boolean = true,
  includeAnnotations: boolean = true
) {
  return useQuery({
    queryKey: analyticsKeys.efficiencyTrends(days, includeStability, includeLoadResponse, includeAnnotations),
    queryFn: () => analyticsService.getEfficiencyTrends(days, includeStability, includeLoadResponse, includeAnnotations),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

