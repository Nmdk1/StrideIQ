/**
 * Strength v1 routines + goals service (sandbox).
 *
 * Mirrors apps/api/routers/routines_goals_v1.py + schemas_routine_goal_v1.py.
 *
 * Contract: the system never seeds, suggests, or recommends a routine
 * or goal. These routes are pure CRUD on athlete-saved patterns. Do
 * not add a "suggested routine" or "smart goal" endpoint here — the
 * strength_narration_purity test will fail if the service returns one.
 */

import { apiClient } from '../client';
import type { ImplementType } from './strength';

export type GoalType =
  | 'e1rm_target'
  | 'e1rm_maintain'
  | 'bodyweight_target'
  | 'volume_target'
  | 'strength_to_bodyweight_ratio'
  | 'freeform';

export interface RoutineItem {
  exercise_name: string;
  default_sets?: number | null;
  default_reps?: number | null;
  default_weight_kg?: number | null;
  default_implement_type?: ImplementType | null;
}

export interface StrengthRoutineCreate {
  name: string;
  items: RoutineItem[];
}

export interface StrengthRoutineUpdate {
  name?: string;
  items?: RoutineItem[];
}

export interface StrengthRoutineResponse {
  id: string;
  name: string;
  items: RoutineItem[];
  last_used_at?: string | null;
  times_used: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface StrengthGoalCreate {
  goal_type: GoalType;
  exercise_name?: string | null;
  target_value?: number | null;
  target_unit?: string | null;
  target_date?: string | null;
  coupled_running_metric?: string | null;
  notes?: string | null;
}

export interface StrengthGoalUpdate {
  goal_type?: GoalType;
  exercise_name?: string | null;
  target_value?: number | null;
  target_unit?: string | null;
  target_date?: string | null;
  coupled_running_metric?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

export interface StrengthGoalResponse {
  id: string;
  goal_type: GoalType;
  exercise_name?: string | null;
  target_value?: number | null;
  target_unit?: string | null;
  target_date?: string | null;
  coupled_running_metric?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const routinesGoalsService = {
  async listRoutines(): Promise<StrengthRoutineResponse[]> {
    return apiClient.get<StrengthRoutineResponse[]>('/v1/strength/routines');
  },

  async createRoutine(
    payload: StrengthRoutineCreate,
  ): Promise<StrengthRoutineResponse> {
    return apiClient.post<StrengthRoutineResponse>(
      '/v1/strength/routines',
      payload,
    );
  },

  async updateRoutine(
    routineId: string,
    payload: StrengthRoutineUpdate,
  ): Promise<StrengthRoutineResponse> {
    return apiClient.patch<StrengthRoutineResponse>(
      `/v1/strength/routines/${routineId}`,
      payload,
    );
  },

  async archiveRoutine(routineId: string): Promise<{ status: string }> {
    return apiClient.delete<{ status: string }>(
      `/v1/strength/routines/${routineId}`,
    );
  },

  async listGoals(): Promise<StrengthGoalResponse[]> {
    return apiClient.get<StrengthGoalResponse[]>('/v1/strength/goals');
  },

  async createGoal(
    payload: StrengthGoalCreate,
  ): Promise<StrengthGoalResponse> {
    return apiClient.post<StrengthGoalResponse>('/v1/strength/goals', payload);
  },

  async updateGoal(
    goalId: string,
    payload: StrengthGoalUpdate,
  ): Promise<StrengthGoalResponse> {
    return apiClient.patch<StrengthGoalResponse>(
      `/v1/strength/goals/${goalId}`,
      payload,
    );
  },

  async deleteGoal(goalId: string): Promise<{ status: string }> {
    return apiClient.delete<{ status: string }>(
      `/v1/strength/goals/${goalId}`,
    );
  },
};
