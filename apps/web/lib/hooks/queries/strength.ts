/**
 * React Query hooks for the Strength v1 sandbox.
 *
 * Every hook is gated upstream by the server's strength.v1 flag (404
 * when off). On 404 we return empty arrays / null so the page can
 * render the "feature not available" state without the UI throwing.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  strengthService,
  type ExercisePickerResponse,
  type StrengthNudgesResponse,
  type StrengthSessionCreate,
  type StrengthSessionListItem,
  type StrengthSessionResponse,
  type StrengthSetCreate,
  type StrengthSetUpdate,
} from '../../api/services/strength';

export const strengthKeys = {
  all: ['strength_v1'] as const,
  sessions: () => [...strengthKeys.all, 'sessions'] as const,
  session: (id: string) => [...strengthKeys.all, 'session', id] as const,
  exercises: (q?: string) => [...strengthKeys.all, 'exercises', q ?? ''] as const,
  nudges: () => [...strengthKeys.all, 'nudges'] as const,
} as const;

function isNotFound(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const status = (err as { status?: number }).status;
  return status === 404;
}

export function useStrengthSessions(limit = 20) {
  return useQuery<StrengthSessionListItem[]>({
    queryKey: [...strengthKeys.sessions(), limit],
    queryFn: () => strengthService.listSessions({ limit }),
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
    staleTime: 30 * 1000,
  });
}

export function useStrengthSession(id: string) {
  return useQuery<StrengthSessionResponse>({
    queryKey: strengthKeys.session(id),
    queryFn: () => strengthService.getSession(id),
    enabled: !!id,
  });
}

export function useStrengthExercises(q?: string) {
  return useQuery<ExercisePickerResponse>({
    queryKey: strengthKeys.exercises(q),
    queryFn: () => strengthService.searchExercises(q),
    staleTime: 60 * 1000,
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
  });
}

export function useCreateStrengthSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StrengthSessionCreate) =>
      strengthService.createSession(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strengthKeys.sessions() });
      qc.invalidateQueries({ queryKey: strengthKeys.exercises() });
    },
  });
}

export function useUpdateStrengthSet(activityId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      setId,
      updates,
    }: {
      setId: string;
      updates: StrengthSetUpdate;
    }) => strengthService.updateSet(activityId, setId, updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strengthKeys.session(activityId) });
      qc.invalidateQueries({ queryKey: strengthKeys.sessions() });
    },
  });
}

export function useAppendStrengthSets(activityId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sets: StrengthSetCreate[]) =>
      strengthService.appendSets(activityId, sets),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strengthKeys.session(activityId) });
      qc.invalidateQueries({ queryKey: strengthKeys.sessions() });
      qc.invalidateQueries({ queryKey: strengthKeys.exercises() });
    },
  });
}

export function useDeleteStrengthSet(activityId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (setId: string) =>
      strengthService.deleteSet(activityId, setId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strengthKeys.session(activityId) });
      qc.invalidateQueries({ queryKey: strengthKeys.sessions() });
    },
  });
}

export function useArchiveStrengthSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (activityId: string) =>
      strengthService.archiveSession(activityId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strengthKeys.sessions() });
    },
  });
}

export function useStrengthNudges() {
  return useQuery<StrengthNudgesResponse>({
    queryKey: strengthKeys.nudges(),
    queryFn: () => strengthService.getNudges(),
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 1,
    staleTime: 5 * 60 * 1000,
  });
}
