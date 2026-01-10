/**
 * React Query hooks for Activity Comparison
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { compareService } from '@/lib/api/services/compare';

export function useWorkoutTypeSummary() {
  return useQuery({
    queryKey: ['compare', 'workout-types'],
    queryFn: () => compareService.getWorkoutTypeSummary(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useCompareByType(workoutType: string, days: number = 180) {
  return useQuery({
    queryKey: ['compare', 'by-type', workoutType, days],
    queryFn: () => compareService.compareByType(workoutType, days),
    enabled: !!workoutType,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCompareByConditions(params: {
  workout_type?: string;
  temp_min?: number;
  temp_max?: number;
  days?: number;
}) {
  return useQuery({
    queryKey: ['compare', 'by-conditions', params],
    queryFn: () => compareService.compareByConditions(params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useActivityWithComparison(activityId: string) {
  return useQuery({
    queryKey: ['compare', 'activity', activityId],
    queryFn: () => compareService.getActivityWithComparison(activityId),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useClassifyActivities() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => compareService.classifyAll(),
    onSuccess: () => {
      // Invalidate comparison queries since workout types have changed
      queryClient.invalidateQueries({ queryKey: ['compare'] });
      queryClient.invalidateQueries({ queryKey: ['activities'] });
    },
  });
}

/**
 * Compare 2-10 specific activities side-by-side
 * Uses mutation because the user explicitly triggers it with selected IDs
 */
export function useCompareIndividual() {
  return useMutation({
    mutationFn: (activityIds: string[]) => compareService.compareIndividual(activityIds),
  });
}
