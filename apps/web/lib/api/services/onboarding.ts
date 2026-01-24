/**
 * Onboarding ("Latency Bridge") API Service
 */

import { apiClient } from '../client';

export interface OnboardingIngestionState {
  last_index_task_id?: string | null;
  last_index_started_at?: string | null;
  last_index_finished_at?: string | null;
  last_index_status?: string | null;
  last_index_error?: string | null;
  last_index_pages_fetched?: number | null;
  last_index_created?: number | null;
  last_index_already_present?: number | null;
  last_index_skipped_non_runs?: number | null;

  last_best_efforts_task_id?: string | null;
  last_best_efforts_started_at?: string | null;
  last_best_efforts_finished_at?: string | null;
  last_best_efforts_status?: string | null;
  last_best_efforts_error?: string | null;
}

export interface OnboardingStatusResponse {
  strava_connected: boolean;
  last_sync?: string | null;
  ingestion_state?: OnboardingIngestionState | null;
}

export interface OnboardingBootstrapResponse {
  queued: boolean;
  index_task_id?: string | null;
  sync_task_id?: string | null;
  message?: string;
}

export const onboardingService = {
  async getStatus(): Promise<OnboardingStatusResponse> {
    return apiClient.get<OnboardingStatusResponse>('/v1/onboarding/status');
  },

  async bootstrap(): Promise<OnboardingBootstrapResponse> {
    return apiClient.post<OnboardingBootstrapResponse>('/v1/onboarding/bootstrap', {});
  },
} as const;

