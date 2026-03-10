/**
 * React Query Hooks for Strava Integration
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { stravaService } from '../../api/services/strava';
import type { StravaSyncResponse } from '../../api/services/strava';
import { toast } from 'sonner';

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
    // Status should refresh when the user returns to the app after being away.
    refetchOnWindowFocus: true,
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
      toast.success('Sync started', {
        description: 'Importing your latest Strava activities...',
      });
    },
    onError: () => {
      toast.error('Sync failed', {
        description: 'Could not start Strava sync. Please try again.',
      });
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
      // Only poll while task is actively in progress
      // Stop for: success, error, unknown (task not found/expired)
      if (
        data?.status === 'pending' ||
        data?.status === 'started' ||
        data?.status === 'progress'
      ) {
        return 2000; // Poll every 2 seconds while in progress
      }
      return false; // Stop polling when done or unknown
    },
  });
}


