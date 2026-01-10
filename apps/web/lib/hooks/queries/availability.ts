/**
 * React Query Hooks for Training Availability
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { availabilityService } from '../../api/services/availability';
import type {
  TrainingAvailabilityGrid,
  TrainingAvailability,
} from '../../api/types';
import type {
  AvailabilitySlotCreate,
  AvailabilitySlotUpdate,
} from '../../api/services/availability';

export const availabilityKeys = {
  all: ['availability'] as const,
  grid: () => [...availabilityKeys.all, 'grid'] as const,
  summary: () => [...availabilityKeys.all, 'summary'] as const,
} as const;

/**
 * Get availability grid
 */
export function useAvailabilityGrid() {
  return useQuery({
    queryKey: availabilityKeys.grid(),
    queryFn: () => availabilityService.getGrid(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Get availability summary
 */
export function useAvailabilitySummary() {
  return useQuery({
    queryKey: availabilityKeys.summary(),
    queryFn: () => availabilityService.getSummary(),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Create/update slot mutation
 */
export function useCreateAvailabilitySlot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slot: AvailabilitySlotCreate) =>
      availabilityService.createSlot(slot),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });
}

/**
 * Update slot mutation
 */
export function useUpdateAvailabilitySlot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ slotId, updates }: { slotId: string; updates: AvailabilitySlotUpdate }) =>
      availabilityService.updateSlot(slotId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });
}

/**
 * Bulk update mutation
 */
export function useBulkUpdateAvailability() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slots: AvailabilitySlotCreate[]) =>
      availabilityService.bulkUpdate(slots),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });
}

/**
 * Delete slot mutation
 */
export function useDeleteAvailabilitySlot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slotId: string) => availabilityService.deleteSlot(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });
}


