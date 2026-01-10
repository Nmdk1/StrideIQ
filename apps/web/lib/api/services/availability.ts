/**
 * Training Availability API Service
 */

import { apiClient } from '../client';
import type {
  TrainingAvailability,
  TrainingAvailabilityGrid,
} from '../types';

export interface AvailabilitySlotCreate {
  day_of_week: number;
  time_block: 'morning' | 'afternoon' | 'evening';
  status: 'available' | 'preferred' | 'unavailable';
  notes?: string;
}

export interface AvailabilitySlotUpdate {
  status?: 'available' | 'preferred' | 'unavailable';
  notes?: string;
}

export const availabilityService = {
  /**
   * Get full availability grid
   */
  async getGrid(): Promise<TrainingAvailabilityGrid> {
    return apiClient.get<TrainingAvailabilityGrid>('/v1/training-availability/grid');
  },

  /**
   * Create or update availability slot
   */
  async createSlot(slot: AvailabilitySlotCreate): Promise<TrainingAvailability> {
    return apiClient.post<TrainingAvailability>('/v1/training-availability', slot);
  },

  /**
   * Update availability slot
   */
  async updateSlot(
    slotId: string,
    updates: AvailabilitySlotUpdate
  ): Promise<TrainingAvailability> {
    return apiClient.put<TrainingAvailability>(`/v1/training-availability/${slotId}`, updates);
  },

  /**
   * Bulk update multiple slots
   */
  async bulkUpdate(slots: AvailabilitySlotCreate[]): Promise<TrainingAvailability[]> {
    return apiClient.put<TrainingAvailability[]>('/v1/training-availability/bulk', slots);
  },

  /**
   * Delete slot (sets to unavailable)
   */
  async deleteSlot(slotId: string): Promise<void> {
    return apiClient.delete<void>(`/v1/training-availability/${slotId}`);
  },

  /**
   * Get availability summary
   */
  async getSummary(): Promise<{
    total_slots: number;
    available_slots: number;
    preferred_slots: number;
    unavailable_slots: number;
    total_available_slots: number;
    available_percentage: number;
    preferred_percentage: number;
    total_available_percentage: number;
  }> {
    return apiClient.get('/v1/training-availability/summary');
  },
} as const;


