/**
 * Preferences API Service
 */

import { apiClient } from '../client';

export type UnitSystem = 'metric' | 'imperial';

export interface Preferences {
  preferred_units: UnitSystem;
}

export interface UpdatePreferencesRequest {
  preferred_units?: UnitSystem;
}

export const preferencesService = {
  /**
   * Get current preferences
   */
  async getPreferences(): Promise<Preferences> {
    return apiClient.get<Preferences>('/v1/preferences');
  },

  /**
   * Update preferences
   */
  async updatePreferences(request: UpdatePreferencesRequest): Promise<Preferences> {
    return apiClient.patch<Preferences>('/v1/preferences', request);
  },
};
