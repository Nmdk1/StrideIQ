/**
 * Home Page Queries
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getHomeData } from '@/lib/api/services/home';
import { apiClient } from '@/lib/api/client';
import { toast } from 'sonner';

export function useHomeData() {
  return useQuery({
    queryKey: ['home'],
    queryFn: getHomeData,
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnWindowFocus: true,
  });
}

/** Quick check-in payload (3 taps) */
export interface QuickCheckinPayload {
  date: string; // ISO date
  motivation_1_5?: number;
  sleep_h?: number;
  soreness_1_5?: number;
}

/** Submit quick check-in from home page */
export function useQuickCheckin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuickCheckinPayload) =>
      apiClient.post('/v1/daily-checkin', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['home'] });
      toast.success('Check-in saved');
    },
    onError: () => {
      toast.error('Check-in failed', {
        description: 'Please try again.',
      });
    },
  });
}
