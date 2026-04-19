/**
 * React Query hooks for the symptom log (Strength v1 sandbox).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  symptomService,
  type SymptomLogCreate,
  type SymptomLogListResponse,
  type SymptomLogUpdate,
} from '../../api/services/symptoms';

export const symptomKeys = {
  all: ['symptoms_v1'] as const,
  list: () => [...symptomKeys.all, 'list'] as const,
} as const;

function isNotFound(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  return (err as { status?: number }).status === 404;
}

export function useSymptomList() {
  return useQuery<SymptomLogListResponse>({
    queryKey: symptomKeys.list(),
    queryFn: () => symptomService.list(),
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
    staleTime: 30 * 1000,
  });
}

export function useCreateSymptom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SymptomLogCreate) => symptomService.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: symptomKeys.list() });
    },
  });
}

export function useUpdateSymptom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      updates,
    }: {
      id: string;
      updates: SymptomLogUpdate;
    }) => symptomService.update(id, updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: symptomKeys.list() });
    },
  });
}

export function useDeleteSymptom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => symptomService.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: symptomKeys.list() });
    },
  });
}
