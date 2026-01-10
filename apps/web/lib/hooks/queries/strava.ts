/**
 * React Query Hooks for Strava Integration
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { stravaService } from '../../api/services/strava';
import type { StravaSyncResponse } from '../../api/services/strava';

export const stravaKeys = {
  all: ['strava'] as const,
  status: () => [...stravaKeys.all, 'status'] as const,
  syncStatus: (taskId: string) => [...stravaKeys.all, 'sync-status', taskId] as const,
} as const;

/**
 * Get Strava connection status
 */
export function useStravaStatus() {
  return useQuery({
    queryKey: stravaKeys.status(),
    queryFn: () => stravaService.getStatus(),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Trigger Strava sync mutation
 */
export function useTriggerStravaSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => stravaService.triggerSync(),
    onSuccess: () => {
      // Invalidate activities to refresh after sync
      queryClient.invalidateQueries({ queryKey: ['activities'] });
      queryClient.invalidateQueries({ queryKey: stravaKeys.status() });
    },
  });
}

/**
 * Get sync task status (with polling)
 */
export function useStravaSyncStatus(taskId: string | null, enabled: boolean = true) {
  return useQuery({
    queryKey: stravaKeys.syncStatus(taskId || ''),
    queryFn: () => stravaService.getSyncStatus(taskId!),
    enabled: enabled && !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'pending' || data?.status === 'started') {
        return 2000; // Poll every 2 seconds while in progress
      }
      return false; // Stop polling when done
    },
  });
}


