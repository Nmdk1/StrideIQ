/**
 * React Query hooks for bodyweight quick-entry (Strength v1 sandbox).
 *
 * Wraps /v1/body-composition. The strength sandbox surface is gated
 * client-side via the `ff_strength_v1` flag (the body-composition
 * endpoint itself is open to all users — we are reusing it, not
 * gating it).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  bodyweightService,
  type BodyCompEntry,
} from '../../api/services/bodyweight';

export const bodyweightKeys = {
  all: ['bodyweight'] as const,
  list: (start?: string, end?: string) =>
    [...bodyweightKeys.all, 'list', start ?? '', end ?? ''] as const,
} as const;

export function useBodyweightHistory(days = 90) {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - days);
  const startStr = start.toISOString().slice(0, 10);
  const endStr = end.toISOString().slice(0, 10);
  return useQuery<BodyCompEntry[]>({
    queryKey: bodyweightKeys.list(startStr, endStr),
    queryFn: () =>
      bodyweightService.list({ start_date: startStr, end_date: endStr }),
    staleTime: 60 * 1000,
  });
}

export function useUpsertBodyweightToday() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (opts: {
      athleteId: string;
      weightLbs: number;
      bodyFatPct?: number | null;
      notes?: string | null;
    }) => bodyweightService.upsertToday(opts),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: bodyweightKeys.all });
    },
  });
}
