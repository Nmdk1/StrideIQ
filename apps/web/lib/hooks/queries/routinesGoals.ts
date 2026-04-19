/**
 * React Query hooks for strength routines + goals (Strength v1 sandbox).
 *
 * Server gates with the strength.v1 flag (404 when off). On 404 the
 * UI should show "not available" rather than retrying forever.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  routinesGoalsService,
  type StrengthGoalCreate,
  type StrengthGoalResponse,
  type StrengthGoalUpdate,
  type StrengthRoutineCreate,
  type StrengthRoutineResponse,
  type StrengthRoutineUpdate,
} from '../../api/services/routinesGoals';

export const routinesGoalsKeys = {
  all: ['strength_v1_rg'] as const,
  routines: () => [...routinesGoalsKeys.all, 'routines'] as const,
  goals: () => [...routinesGoalsKeys.all, 'goals'] as const,
} as const;

function isNotFound(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const status = (err as { status?: number }).status;
  return status === 404;
}

// --- Routines --------------------------------------------------------

export function useStrengthRoutines() {
  return useQuery<StrengthRoutineResponse[]>({
    queryKey: routinesGoalsKeys.routines(),
    queryFn: () => routinesGoalsService.listRoutines(),
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
    staleTime: 60 * 1000,
  });
}

export function useCreateStrengthRoutine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StrengthRoutineCreate) =>
      routinesGoalsService.createRoutine(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: routinesGoalsKeys.routines() });
    },
  });
}

export function useUpdateStrengthRoutine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      routineId,
      payload,
    }: {
      routineId: string;
      payload: StrengthRoutineUpdate;
    }) => routinesGoalsService.updateRoutine(routineId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: routinesGoalsKeys.routines() });
    },
  });
}

export function useArchiveStrengthRoutine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (routineId: string) =>
      routinesGoalsService.archiveRoutine(routineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: routinesGoalsKeys.routines() });
    },
  });
}

// --- Goals -----------------------------------------------------------

export function useStrengthGoals() {
  return useQuery<StrengthGoalResponse[]>({
    queryKey: routinesGoalsKeys.goals(),
    queryFn: () => routinesGoalsService.listGoals(),
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
    staleTime: 60 * 1000,
  });
}

export function useCreateStrengthGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StrengthGoalCreate) =>
      routinesGoalsService.createGoal(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: routinesGoalsKeys.goals() });
    },
  });
}

export function useUpdateStrengthGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      goalId,
      payload,
    }: {
      goalId: string;
      payload: StrengthGoalUpdate;
    }) => routinesGoalsService.updateGoal(goalId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: routinesGoalsKeys.goals() });
    },
  });
}

export function useDeleteStrengthGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (goalId: string) => routinesGoalsService.deleteGoal(goalId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: routinesGoalsKeys.goals() });
    },
  });
}
