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
  history?: {
    is_thin: boolean;
    reasons: string[];
    run_count_28d: number;
    total_distance_m_28d: number;
    last_run_at?: string | null;
  };
  baseline?: {
    completed: boolean;
    needed: boolean;
  };
}

export interface OnboardingBootstrapResponse {
  queued: boolean;
  index_task_id?: string | null;
  sync_task_id?: string | null;
  message?: string;
}

export type IntakeStage =
  | 'initial'
  | 'basic_profile'
  | 'goals'
  | 'baseline'
  | 'connect_strava'
  | 'nutrition_setup'
  | 'work_setup';

export interface OnboardingIntakeGetResponse {
  stage: IntakeStage;
  responses: Record<string, any> | null;
  completed_at?: string | null;
}

export interface OnboardingIntakeSaveResponse {
  ok: boolean;
  stage?: IntakeStage;
  status?: 'computed' | 'missing_anchor' | 'invalid_anchor' | string;
  error?: string;
  pace_profile?: Record<string, any> | null;
}

export const onboardingService = {
  async getStatus(): Promise<OnboardingStatusResponse> {
    return apiClient.get<OnboardingStatusResponse>('/v1/onboarding/status');
  },

  async bootstrap(): Promise<OnboardingBootstrapResponse> {
    return apiClient.post<OnboardingBootstrapResponse>('/v1/onboarding/bootstrap', {});
  },

  async getIntake(stage: IntakeStage): Promise<OnboardingIntakeGetResponse> {
    return apiClient.get<OnboardingIntakeGetResponse>(`/v1/onboarding/intake?stage=${encodeURIComponent(stage)}`);
  },

  async saveIntake(stage: IntakeStage, responses: Record<string, any>, completed?: boolean): Promise<OnboardingIntakeSaveResponse> {
    return apiClient.post<OnboardingIntakeSaveResponse>('/v1/onboarding/intake', { stage, responses, completed });
  },
} as const;

