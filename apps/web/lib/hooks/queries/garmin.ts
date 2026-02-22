/**
 * React Query Hooks for Garmin Connect Integration
 */

import { useQuery } from '@tanstack/react-query';
import { garminService } from '../../api/services/garmin';

export const garminKeys = {
  all: ['garmin'] as const,
  status: () => [...garminKeys.all, 'status'] as const,
} as const;

/**
 * Get Garmin Connect connection status
 */
export function useGarminStatus() {
  return useQuery({
    queryKey: garminKeys.status(),
    queryFn: () => garminService.getStatus(),
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  });
}
