/**
 * React Query hooks for correlation analysis
 */

import { useQuery } from '@tanstack/react-query';
import { correlationsService } from '@/lib/api/services/correlations';
import type {
  CorrelationAnalysisResponse,
  WhatWorksResponse,
  WhatDoesntWorkResponse,
} from '@/lib/api/services/correlations';

/**
 * Hook to discover all correlations
 */
export function useCorrelations(days: number = 90) {
  return useQuery<CorrelationAnalysisResponse>({
    queryKey: ['correlations', 'discover', days],
    queryFn: () => correlationsService.discoverCorrelations(days),
    staleTime: 1000 * 60 * 60, // 1 hour
    retry: 1,
  });
}

/**
 * Hook to get "What's Working" correlations
 */
export function useWhatWorks(days: number = 90) {
  return useQuery<WhatWorksResponse>({
    queryKey: ['correlations', 'what-works', days],
    queryFn: () => correlationsService.whatWorks(days),
    staleTime: 1000 * 60 * 60, // 1 hour
    retry: 1,
  });
}

/**
 * Hook to get "What Doesn't Work" correlations
 */
export function useWhatDoesntWork(days: number = 90) {
  return useQuery<WhatDoesntWorkResponse>({
    queryKey: ['correlations', 'what-doesnt-work', days],
    queryFn: () => correlationsService.whatDoesntWork(days),
    staleTime: 1000 * 60 * 60, // 1 hour
    retry: 1,
  });
}


