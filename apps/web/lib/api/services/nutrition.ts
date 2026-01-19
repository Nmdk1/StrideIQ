/**
 * Nutrition API Service
 * 
 * Service for nutrition entry CRUD operations.
 */

import { apiClient } from '../client';

export interface NutritionEntry {
  id: string;
  athlete_id: string;
  date: string;
  entry_type: 'pre_activity' | 'during_activity' | 'post_activity' | 'daily';
  activity_id?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  timing?: string;
  notes?: string;
  created_at: string;
}

export interface NutritionEntryCreate {
  athlete_id: string;
  date: string;
  entry_type: 'pre_activity' | 'during_activity' | 'post_activity' | 'daily';
  activity_id?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  timing?: string;
  notes?: string;
}

export interface NutritionEntryUpdate {
  date?: string;
  entry_type?: 'pre_activity' | 'during_activity' | 'post_activity' | 'daily';
  activity_id?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  timing?: string;
  notes?: string;
}

export const nutritionService = {
  /**
   * Check whether natural-language parsing is available.
   * No auth required (capability endpoint).
   */
  async nlParsingAvailable(): Promise<{ available: boolean }> {
    return apiClient.get<{ available: boolean }>('/v1/nutrition/parse/available', { skipAuth: true, retries: 0 });
  },

  /**
   * Parse natural-language nutrition text into a NutritionEntryCreate draft.
   */
  async parseText(text: string): Promise<NutritionEntryCreate> {
    // Disable API client retries so errors surface immediately.
    return apiClient.post<NutritionEntryCreate>('/v1/nutrition/parse', { text }, { retries: 0 });
  },

  /**
   * Create nutrition entry
   */
  async createEntry(entry: NutritionEntryCreate): Promise<NutritionEntry> {
    return apiClient.post<NutritionEntry>('/v1/nutrition', entry);
  },

  /**
   * List nutrition entries
   */
  async listEntries(params?: {
    start_date?: string;
    end_date?: string;
    entry_type?: string;
    activity_id?: string;
  }): Promise<NutritionEntry[]> {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      });
    }
    const queryString = queryParams.toString();
    return apiClient.get<NutritionEntry[]>(`/v1/nutrition${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * Get nutrition entry by ID
   */
  async getEntry(id: string): Promise<NutritionEntry> {
    return apiClient.get<NutritionEntry>(`/v1/nutrition/${id}`);
  },

  /**
   * Update nutrition entry
   */
  async updateEntry(id: string, updates: NutritionEntryUpdate): Promise<NutritionEntry> {
    return apiClient.put<NutritionEntry>(`/v1/nutrition/${id}`, updates);
  },

  /**
   * Delete nutrition entry
   */
  async deleteEntry(id: string): Promise<void> {
    return apiClient.delete<void>(`/v1/nutrition/${id}`);
  },
} as const;


