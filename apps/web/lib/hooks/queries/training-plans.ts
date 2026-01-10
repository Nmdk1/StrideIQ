/**
 * React Query Hooks for Training Plans
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingPlansService, CreatePlanRequest } from '../../api/services/training-plans';

export const planKeys = {
  all: ['training-plans'] as const,
  current: () => [...planKeys.all, 'current'] as const,
  currentWeek: () => [...planKeys.all, 'current-week'] as const,
  calendar: (startDate?: string, endDate?: string) => [...planKeys.all, 'calendar', startDate, endDate] as const,
};

/**
 * Get current active training plan
 */
export function useCurrentPlan() {
  return useQuery({
    queryKey: planKeys.current(),
    queryFn: () => trainingPlansService.getCurrentPlan(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Get this week's workouts
 */
export function useCurrentWeek() {
  return useQuery({
    queryKey: planKeys.currentWeek(),
    queryFn: () => trainingPlansService.getCurrentWeek(),
    staleTime: 60 * 1000, // 1 minute
  });
}

/**
 * Get calendar view
 */
export function useCalendar(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: planKeys.calendar(startDate, endDate),
    queryFn: () => trainingPlansService.getCalendar(startDate, endDate),
    staleTime: 60 * 1000, // 1 minute
  });
}

/**
 * Create a new training plan
 */
export function useCreatePlan() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: CreatePlanRequest) => trainingPlansService.createPlan(request),
    onSuccess: () => {
      // Invalidate all plan queries
      queryClient.invalidateQueries({ queryKey: planKeys.all });
    },
  });
}

/**
 * Mark workout as completed
 */
export function useCompleteWorkout() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ planId, workoutId, activityId }: { planId: string; workoutId: string; activityId?: string }) =>
      trainingPlansService.completeWorkout(planId, workoutId, activityId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.all });
    },
  });
}

/**
 * Mark workout as skipped
 */
export function useSkipWorkout() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ planId, workoutId, reason }: { planId: string; workoutId: string; reason?: string }) =>
      trainingPlansService.skipWorkout(planId, workoutId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.all });
    },
  });
}
