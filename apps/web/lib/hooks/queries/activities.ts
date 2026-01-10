/**
 * React Query Hooks for Activities
 * 
 * Provides type-safe, cached, and optimized data fetching for activities.
 * Can be swapped for different query strategies without breaking components.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { activitiesService, type ActivityListParams } from '../../api/services/activities';
import type {
  Activity,
  ActivityAnalysis,
  RunDelivery,
  ActivityFeedback,
  ActivityFeedbackCreate,
} from '../../api/types';

// Query keys - centralized for easy invalidation
export const activityKeys = {
  all: ['activities'] as const,
  lists: () => [...activityKeys.all, 'list'] as const,
  list: (params?: ActivityListParams) => [...activityKeys.lists(), params] as const,
  detail: (id: string) => [...activityKeys.all, 'detail', id] as const,
  analysis: (id: string) => [...activityKeys.all, 'analysis', id] as const,
  delivery: (id: string) => [...activityKeys.all, 'delivery', id] as const,
  feedback: (activityId: string) => [...activityKeys.all, 'feedback', activityId] as const,
  pendingPrompts: () => [...activityKeys.all, 'pending-prompts'] as const,
  summary: (days: number) => [...activityKeys.all, 'summary', days] as const,
} as const;

/**
 * List activities with filtering and pagination
 */
export function useActivities(params?: ActivityListParams) {
  return useQuery({
    queryKey: activityKeys.list(params),
    queryFn: () => activitiesService.listActivities(params),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Get activities summary statistics
 */
export function useActivitiesSummary(days: number = 30) {
  return useQuery({
    queryKey: activityKeys.summary(days),
    queryFn: () => activitiesService.getSummary(days),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Get activity by ID
 */
export function useActivity(activityId: string) {
  return useQuery({
    queryKey: activityKeys.detail(activityId),
    queryFn: () => activitiesService.getActivity(activityId),
    enabled: !!activityId,
  });
}

/**
 * Get activity analysis
 */
export function useActivityAnalysis(activityId: string) {
  return useQuery({
    queryKey: activityKeys.analysis(activityId),
    queryFn: () => activitiesService.getActivityAnalysis(activityId),
    enabled: !!activityId,
  });
}

/**
 * Get run delivery (complete experience)
 */
export function useRunDelivery(activityId: string) {
  return useQuery({
    queryKey: activityKeys.delivery(activityId),
    queryFn: () => activitiesService.getRunDelivery(activityId),
    enabled: !!activityId,
    staleTime: 5 * 60 * 1000, // 5 minutes - delivery doesn't change often
  });
}

/**
 * Get feedback for activity
 */
export function useActivityFeedback(activityId: string) {
  return useQuery({
    queryKey: activityKeys.feedback(activityId),
    queryFn: () => activitiesService.getFeedback(activityId),
    enabled: !!activityId,
    retry: false, // Don't retry on 404 (no feedback yet)
  });
}

/**
 * Get pending feedback prompts
 */
export function usePendingPrompts(limit: number = 10) {
  return useQuery({
    queryKey: activityKeys.pendingPrompts(),
    queryFn: () => activitiesService.getPendingPrompts(limit),
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });
}

/**
 * Create feedback mutation
 */
export function useCreateFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (feedback: ActivityFeedbackCreate) =>
      activitiesService.createFeedback(feedback),
    onSuccess: (data) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: activityKeys.feedback(data.activity_id) });
      queryClient.invalidateQueries({ queryKey: activityKeys.delivery(data.activity_id) });
      queryClient.invalidateQueries({ queryKey: activityKeys.pendingPrompts() });
    },
  });
}

/**
 * Update feedback mutation
 */
export function useUpdateFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ feedbackId, updates }: { feedbackId: string; updates: Partial<ActivityFeedbackCreate> }) =>
      activitiesService.updateFeedback(feedbackId, updates),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: activityKeys.feedback(data.activity_id) });
      queryClient.invalidateQueries({ queryKey: activityKeys.delivery(data.activity_id) });
    },
  });
}

/**
 * Delete feedback mutation
 */
export function useDeleteFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (feedbackId: string) => activitiesService.deleteFeedback(feedbackId),
    onSuccess: () => {
      // Invalidate all activity queries
      queryClient.invalidateQueries({ queryKey: activityKeys.all });
    },
  });
}
