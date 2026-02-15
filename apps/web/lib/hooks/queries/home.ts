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

/** Quick check-in payload */
export interface QuickCheckinPayload {
  date: string; // ISO date
  motivation_1_5?: number;
  sleep_quality_1_5?: number;  // 1=poor, 5=great
  sleep_h?: number;            // actual hours (explicit input)
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
