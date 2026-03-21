/**
 * Home Page Queries
 */

import { useQuery, useMutation, useQueryClient, QueryClient } from '@tanstack/react-query';
import { getHomeData, type HomeData } from '@/lib/api/services/home';
import { apiClient } from '@/lib/api/client';
import { toast } from 'sonner';

const BRIEFING_PENDING_STATES = new Set(['stale', 'missing', 'refreshing']);

export function useHomeData() {
  return useQuery({
    queryKey: ['home'],
    queryFn: getHomeData,
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const state = query.state.data?.briefing_state;
      const isInterim = Boolean(query.state.data?.briefing_is_interim);
      if (state === 'fresh' && !isInterim) return false;
      if ((state && BRIEFING_PENDING_STATES.has(state)) || isInterim) return 2000;
      return false;
    },
  });
}

/** Return a stable callback that invalidates the ['home'] query. */
export function useInvalidateHome(): () => void {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ['home'] });
}

/** Quick check-in payload */
export interface QuickCheckinPayload {
  date: string; // ISO date
  readiness_1_5?: number;
  sleep_quality_1_5?: number;  // 1=poor, 5=great
  sleep_h?: number;            // actual hours (explicit input)
  soreness_1_5?: number;
}

// Label maps for optimistic cache update (match backend maps)
const READINESS_LABELS: Record<number, string> = { 5: 'High', 4: 'Good', 3: 'Neutral', 2: 'Low', 1: 'Poor' };
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
      // Also mark briefing_state as 'refreshing' so the polling loop
      // starts immediately and the pending UI appears.
      queryClient.setQueryData<HomeData | undefined>(['home'], (old) => {
        if (!old) return old;
        return {
          ...old,
          checkin_needed: false,
          briefing_state: 'refreshing',
          today_checkin: {
            readiness_label: READINESS_LABELS[variables.readiness_1_5 ?? -1] ?? null,
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
