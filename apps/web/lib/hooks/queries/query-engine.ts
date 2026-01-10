/**
 * React Query hooks for Admin Query Engine
 */

import { useQuery, useMutation } from '@tanstack/react-query';
import { queryEngineService } from '@/lib/api/services/query-engine';
import type { QueryResult } from '@/lib/api/services/query-engine';

/**
 * Get available query templates
 */
export function useQueryTemplates() {
  return useQuery({
    queryKey: ['admin', 'query', 'templates'],
    queryFn: () => queryEngineService.getTemplates(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
}

/**
 * Get queryable entities
 */
export function useQueryEntities() {
  return useQuery({
    queryKey: ['admin', 'query', 'entities'],
    queryFn: () => queryEngineService.getEntities(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
}

/**
 * Execute a query template
 */
export function useExecuteTemplate() {
  return useMutation<
    QueryResult,
    Error,
    {
      template: string;
      athleteId?: string;
      days?: number;
      workoutType?: string;
      minStrength?: number;
    }
  >({
    mutationFn: (params) => queryEngineService.executeTemplate(params),
  });
}

/**
 * Execute a custom query
 */
export function useExecuteCustomQuery() {
  return useMutation<
    QueryResult,
    Error,
    {
      entity: string;
      days?: number;
      athleteId?: string;
      groupBy?: string[];
      aggregations?: Record<string, string>;
      filters?: { field: string; operator: string; value: any }[];
      sortBy?: string;
      limit?: number;
    }
  >({
    mutationFn: (params) => queryEngineService.executeCustom(params),
  });
}
