/**
 * Garmin Connect Integration API Service
 */

import { apiClient } from '../client';

export interface GarminStatus {
  connected: boolean;
  garmin_user_id?: string | null;
  last_sync?: string | null;
  /** Whether this athlete can initiate a new Garmin Connect (feature flag). */
  garmin_connect_available?: boolean;
}

export interface GarminAuthUrl {
  auth_url: string;
}

export interface GarminDisconnectResponse {
  success: boolean;
  message: string;
}

export interface GarminBackfillProgress {
  in_progress: boolean;
  activities_ingested: number;
  health_records_ingested: number;
  sweep_complete: boolean;
  findings_count: number;
}

export const garminService = {
  /**
   * Get Garmin Connect connection status
   */
  async getStatus(): Promise<GarminStatus> {
    return apiClient.get<GarminStatus>('/v1/garmin/status');
  },

  /**
   * Get Garmin OAuth PKCE authorization URL
   */
  async getAuthUrl(returnTo: string = '/settings'): Promise<GarminAuthUrl> {
    const qp = encodeURIComponent(returnTo || '/settings');
    return apiClient.get<GarminAuthUrl>(`/v1/garmin/auth-url?return_to=${qp}`);
  },

  /**
   * Disconnect Garmin Connect integration (clears tokens, deregisters with Garmin)
   */
  async disconnect(): Promise<GarminDisconnectResponse> {
    return apiClient.post<GarminDisconnectResponse>('/v1/garmin/disconnect');
  },

  /**
   * Get first-session Garmin backfill progress.
   */
  async getBackfillProgress(): Promise<GarminBackfillProgress> {
    return apiClient.get<GarminBackfillProgress>('/v1/garmin/backfill-progress');
  },
} as const;
