/**
 * Body-area symptom log service (Strength v1, sandbox phase D).
 * Mirrors apps/api/routers/symptoms_v1.py + schemas_symptom_v1.py.
 */

import { apiClient } from '../client';

export type SymptomSeverity = 'niggle' | 'ache' | 'pain' | 'injury';

export const BODY_AREAS = [
  'left_foot',
  'right_foot',
  'left_ankle',
  'right_ankle',
  'left_calf',
  'right_calf',
  'left_shin',
  'right_shin',
  'left_knee',
  'right_knee',
  'left_quad',
  'right_quad',
  'left_hamstring',
  'right_hamstring',
  'left_hip',
  'right_hip',
  'left_glute',
  'right_glute',
  'lower_back',
  'upper_back',
  'left_shoulder',
  'right_shoulder',
  'neck',
  'core_abdominals',
  'other',
] as const;

export type BodyArea = (typeof BODY_AREAS)[number];

export interface SymptomLogCreate {
  body_area: BodyArea;
  severity: SymptomSeverity;
  started_at: string;
  resolved_at?: string | null;
  triggered_by?: string | null;
  notes?: string | null;
}

export interface SymptomLogUpdate {
  resolved_at?: string | null;
  triggered_by?: string | null;
  notes?: string | null;
}

export interface SymptomLogResponse {
  id: string;
  body_area: string;
  severity: string;
  started_at: string;
  resolved_at?: string | null;
  triggered_by?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SymptomLogListResponse {
  active: SymptomLogResponse[];
  history: SymptomLogResponse[];
}

export const symptomService = {
  async list(): Promise<SymptomLogListResponse> {
    return apiClient.get<SymptomLogListResponse>('/v1/symptoms');
  },

  async create(payload: SymptomLogCreate): Promise<SymptomLogResponse> {
    return apiClient.post<SymptomLogResponse>('/v1/symptoms', payload);
  },

  async update(
    id: string,
    payload: SymptomLogUpdate,
  ): Promise<SymptomLogResponse> {
    return apiClient.patch<SymptomLogResponse>(`/v1/symptoms/${id}`, payload);
  },

  async remove(id: string): Promise<{ status: string }> {
    return apiClient.delete<{ status: string }>(`/v1/symptoms/${id}`);
  },
};
