/**
 * React Query hooks for nutrition entries
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { nutritionService, type NutritionEntryCreate, type NutritionEntryUpdate } from '../../api/services/nutrition';
import type { NutritionEntry } from '../../api/services/nutrition';

export const nutritionKeys = {
  all: ['nutrition'] as const,
  lists: () => [...nutritionKeys.all, 'list'] as const,
  list: (params?: any) => [...nutritionKeys.lists(), params] as const,
  detail: (id: string) => [...nutritionKeys.all, 'detail', id] as const,
} as const;

/**
 * List nutrition entries
 */
export function useNutritionEntries(params?: {
  start_date?: string;
  end_date?: string;
  entry_type?: string;
  activity_id?: string;
}) {
  return useQuery<NutritionEntry[]>({
    queryKey: nutritionKeys.list(params),
    queryFn: () => nutritionService.listEntries(params),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Get nutrition entry by ID
 */
export function useNutritionEntry(id: string) {
  return useQuery<NutritionEntry>({
    queryKey: nutritionKeys.detail(id),
    queryFn: () => nutritionService.getEntry(id),
    enabled: !!id,
  });
}

/**
 * Create nutrition entry mutation
 */
export function useCreateNutritionEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (entry: NutritionEntryCreate) => nutritionService.createEntry(entry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.lists() });
    },
  });
}

/**
 * Update nutrition entry mutation
 */
export function useUpdateNutritionEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: NutritionEntryUpdate }) =>
      nutritionService.updateEntry(id, updates),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: nutritionKeys.lists() });
    },
  });
}

/**
 * Delete nutrition entry mutation
 */
export function useDeleteNutritionEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => nutritionService.deleteEntry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.all });
    },
  });
}


