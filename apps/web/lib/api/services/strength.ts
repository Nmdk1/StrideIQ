/**
 * Strength v1 API service (sandbox).
 *
 * Mirrors apps/api/routers/strength_v1.py + schemas_strength_v1.py.
 * The whole module is self-contained so the rollback story is "delete
 * one folder of files."
 */

import { apiClient } from '../client';

export type ImplementType =
  | 'barbell'
  | 'dumbbell_each'
  | 'dumbbell_total'
  | 'kettlebell_each'
  | 'kettlebell_total'
  | 'plate_per_side'
  | 'machine'
  | 'cable'
  | 'bodyweight'
  | 'band'
  | 'other';

export type SetModifier =
  | 'straight'
  | 'warmup'
  | 'drop'
  | 'failure'
  | 'amrap'
  | 'pyramid_up'
  | 'pyramid_down'
  | 'tempo'
  | 'paused';

export type SetSource =
  | 'garmin'
  | 'manual'
  | 'voice'
  | 'garmin_then_manual_edit';

export interface StrengthSetCreate {
  exercise_name: string;
  reps?: number | null;
  weight_kg?: number | null;
  duration_s?: number | null;
  rpe?: number | null;
  implement_type?: ImplementType | null;
  set_modifier?: SetModifier | null;
  tempo?: string | null;
  notes?: string | null;
  set_type?: 'active' | 'rest';
}

export interface StrengthSetUpdate {
  reps?: number | null;
  weight_kg?: number | null;
  duration_s?: number | null;
  rpe?: number | null;
  implement_type?: ImplementType | null;
  set_modifier?: SetModifier | null;
  tempo?: string | null;
  notes?: string | null;
}

export interface StrengthSetResponse {
  id: string;
  set_order: number;
  exercise_name: string;
  exercise_category: string;
  movement_pattern: string;
  muscle_group?: string | null;
  is_unilateral: boolean;
  set_type: string;
  reps?: number | null;
  weight_kg?: number | null;
  duration_s?: number | null;
  estimated_1rm_kg?: number | null;
  rpe?: number | null;
  implement_type?: string | null;
  set_modifier?: string | null;
  tempo?: string | null;
  notes?: string | null;
  source: SetSource | string;
  manually_augmented: boolean;
  superseded_by_id?: string | null;
  superseded_at?: string | null;
  created_at: string;
}

export interface StrengthSessionCreate {
  start_time?: string;
  duration_s?: number | null;
  name?: string | null;
  sets: StrengthSetCreate[];
  routine_id?: string | null;
}

export interface StrengthSessionResponse {
  id: string;
  athlete_id: string;
  start_time: string;
  duration_s?: number | null;
  name?: string | null;
  sport: string;
  source: string;
  sets: StrengthSetResponse[];
  set_count: number;
  total_volume_kg?: number | null;
  movement_patterns: string[];
}

export interface StrengthSessionListItem {
  id: string;
  start_time: string;
  duration_s?: number | null;
  name?: string | null;
  set_count: number;
  total_volume_kg?: number | null;
  movement_patterns: string[];
}

export interface ExercisePickerEntry {
  name: string;
  movement_pattern: string;
  muscle_group?: string | null;
  is_unilateral: boolean;
}

export interface ExercisePickerResponse {
  query?: string | null;
  results: ExercisePickerEntry[];
  recent: ExercisePickerEntry[];
}

export interface StrengthNudge {
  activity_id: string;
  start_time: string | null;
  name: string | null;
  duration_s: number | null;
  current_set_count: number;
  source: string;
}

export interface StrengthNudgesResponse {
  count: number;
  nudges: StrengthNudge[];
}

export const strengthService = {
  async listSessions(params?: {
    limit?: number;
    offset?: number;
  }): Promise<StrengthSessionListItem[]> {
    const qs = new URLSearchParams();
    if (params?.limit != null) qs.set('limit', String(params.limit));
    if (params?.offset != null) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs}` : '';
    return apiClient.get<StrengthSessionListItem[]>(
      `/v1/strength/sessions${suffix}`,
    );
  },

  async getSession(activityId: string): Promise<StrengthSessionResponse> {
    return apiClient.get<StrengthSessionResponse>(
      `/v1/strength/sessions/${activityId}`,
    );
  },

  async createSession(
    payload: StrengthSessionCreate,
  ): Promise<StrengthSessionResponse> {
    return apiClient.post<StrengthSessionResponse>(
      '/v1/strength/sessions',
      payload,
    );
  },

  async updateSet(
    activityId: string,
    setId: string,
    updates: StrengthSetUpdate,
  ): Promise<StrengthSessionResponse> {
    return apiClient.patch<StrengthSessionResponse>(
      `/v1/strength/sessions/${activityId}/sets/${setId}`,
      updates,
    );
  },

  async archiveSession(activityId: string): Promise<{ status: string }> {
    return apiClient.delete<{ status: string }>(
      `/v1/strength/sessions/${activityId}`,
    );
  },

  async getEditHistory(activityId: string): Promise<{
    activity_id: string;
    rows: Array<Record<string, unknown>>;
  }> {
    return apiClient.get(
      `/v1/strength/sessions/${activityId}/edit-history`,
    );
  },

  async searchExercises(
    q?: string,
    limit = 30,
  ): Promise<ExercisePickerResponse> {
    const qs = new URLSearchParams();
    if (q) qs.set('q', q);
    qs.set('limit', String(limit));
    return apiClient.get<ExercisePickerResponse>(
      `/v1/strength/exercises?${qs}`,
    );
  },

  async getNudges(): Promise<StrengthNudgesResponse> {
    return apiClient.get<StrengthNudgesResponse>('/v1/strength/nudges');
  },
};
