/**
 * Home Page Queries
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getHomeData, type HomeData } from '@/lib/api/services/home';
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

// Label maps for optimistic cache update (match backend maps)
const MOTIVATION_LABELS: Record<number, string> = { 5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough' };
const SLEEP_QUALITY_LABELS: Record<number, string> = { 5: 'Great', 4: 'Good', 3: 'OK', 2: 'Poor', 1: 'Awful' };
const SORENESS_LABELS: Record<number, string> = { 1: 'None', 2: 'Mild', 4: 'Yes' };

/** Submit quick check-in from home page */
export function useQuickCheckin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuickCheckinPayload) =>
      apiClient.post('/v1/daily-checkin', payload),
    onSuccess: (_data, variables) => {
      // Optimistically update the home cache so the UI switches from
      // QuickCheckin → CheckinSummary instantly, without waiting for
      // the slow /v1/home refetch (coach briefing, LLM, etc.).
      queryClient.setQueryData<HomeData | undefined>(['home'], (old) => {
        if (!old) return old;
        return {
          ...old,
          checkin_needed: false,
          today_checkin: {
            motivation_label: MOTIVATION_LABELS[variables.motivation_1_5 ?? -1] ?? null,
            sleep_label: SLEEP_QUALITY_LABELS[variables.sleep_quality_1_5 ?? -1] ?? null,
            soreness_label: SORENESS_LABELS[variables.soreness_1_5 ?? -1] ?? null,
          },
        };
      });
      // Also refetch in background to get full server-rendered data
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
