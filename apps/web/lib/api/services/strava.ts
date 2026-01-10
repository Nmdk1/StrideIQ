/**
 * Strava Integration API Service
 */

import { apiClient } from '../client';

export interface StravaStatus {
  connected: boolean;
  strava_athlete_id?: number;
  last_sync?: string;
}

export interface StravaAuthUrl {
  auth_url: string;
}

export interface StravaSyncResponse {
  status: string;
  message: string;
  task_id: string;
}

export interface StravaSyncStatus {
  task_id: string;
  status: 'pending' | 'started' | 'success' | 'error';
  message?: string;
  result?: any;
  error?: string;
}

export const stravaService = {
  /**
   * Get Strava connection status
   */
  async getStatus(): Promise<StravaStatus> {
    return apiClient.get<StravaStatus>('/v1/strava/status');
  },

  /**
   * Get Strava OAuth authorization URL
   */
  async getAuthUrl(): Promise<StravaAuthUrl> {
    return apiClient.get<StravaAuthUrl>('/v1/strava/auth-url');
  },

  /**
   * Trigger Strava sync
   */
  async triggerSync(): Promise<StravaSyncResponse> {
    return apiClient.post<StravaSyncResponse>('/v1/strava/sync');
  },

  /**
   * Get sync task status
   */
  async getSyncStatus(taskId: string): Promise<StravaSyncStatus> {
    return apiClient.get<StravaSyncStatus>(`/v1/strava/sync/status/${taskId}`);
  },
} as const;


