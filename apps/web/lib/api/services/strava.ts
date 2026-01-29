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
  status: 'pending' | 'started' | 'success' | 'error' | 'unknown';
  message?: string;
  result?: any;
  error?: string;
}

export interface StravaVerifyResponse {
  valid: boolean;
  connected: boolean;
  strava_athlete_id?: number;
  reason?: 'revoked' | 'error' | 'timeout';
}

export interface StravaDisconnectResponse {
  success: boolean;
  message: string;
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
  async getAuthUrl(returnTo: string = '/onboarding'): Promise<StravaAuthUrl> {
    const qp = encodeURIComponent(returnTo || '/onboarding');
    return apiClient.get<StravaAuthUrl>(`/v1/strava/auth-url?return_to=${qp}`);
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

  /**
   * Verify Strava connection is still valid (token not revoked)
   */
  async verifyConnection(): Promise<StravaVerifyResponse> {
    return apiClient.get<StravaVerifyResponse>('/v1/strava/verify');
  },

  /**
   * Disconnect Strava integration (clear tokens)
   */
  async disconnect(): Promise<StravaDisconnectResponse> {
    return apiClient.post<StravaDisconnectResponse>('/v1/strava/disconnect');
  },
} as const;


