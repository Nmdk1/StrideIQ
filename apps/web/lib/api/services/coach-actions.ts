/**
 * Coach Action Automation API Service (Phase 10)
 *
 * Thin client over `/v2/coach/actions/*` endpoints.
 */
import { apiClient } from '../client';

export type ProposalStatus = 'proposed' | 'confirmed' | 'rejected' | 'applied' | 'failed';

export type WorkoutSnapshot = {
  id: string;
  scheduled_date: string | null;
  title: string | null;
  workout_type: string | null;
  target_distance_km?: number | null;
  target_duration_minutes?: number | null;
  skipped?: boolean | null;
};

export type DiffPreviewEntry = {
  plan_id: string;
  workout_id: string;
  before: WorkoutSnapshot;
  after: WorkoutSnapshot;
};

export type ApplyReceipt = {
  actions_applied: number;
  changes: DiffPreviewEntry[];
};

export type ConfirmResponse = {
  proposal_id: string;
  status: ProposalStatus;
  confirmed_at: string | null;
  applied_at: string | null;
  receipt?: ApplyReceipt | null;
  error?: string | null;
};

export type RejectResponse = {
  proposal_id: string;
  status: ProposalStatus;
  rejected_at: string;
};

export const coachActionsService = {
  async confirm(proposalId: string, idempotencyKey: string): Promise<ConfirmResponse> {
    return apiClient.post<ConfirmResponse>(`/v2/coach/actions/${proposalId}/confirm`, { idempotency_key: idempotencyKey });
  },

  async reject(proposalId: string, reason: string): Promise<RejectResponse> {
    return apiClient.post<RejectResponse>(`/v2/coach/actions/${proposalId}/reject`, { reason });
  },
};

