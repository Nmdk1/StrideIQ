/**
 * Admin API Service
 * 
 * Service for admin dashboard endpoints.
 * Admin/owner role required.
 */

import { apiClient } from '../client';

export interface AdminUser {
  id: string;
  email: string | null;
  display_name: string | null;
  role: string;
  subscription_tier: string;
  created_at: string;
  onboarding_completed: boolean;
}

export interface AdminUserDetail extends AdminUser {
  onboarding_stage: string | null;
  stripe_customer_id?: string | null;
  trial_started_at?: string | null;
  trial_ends_at?: string | null;
  trial_source?: string | null;
  has_active_subscription?: boolean;
  subscription?: {
    status?: string | null;
    cancel_at_period_end?: boolean;
    current_period_end?: string | null;
    stripe_subscription_id?: string | null;
    stripe_price_id?: string | null;
  } | null;
  is_blocked?: boolean;
  is_coach_vip?: boolean;
  integrations?: {
    preferred_units?: string | null;
    strava_athlete_id?: number | null;
    last_strava_sync?: string | null;
    garmin_connected?: boolean;
    last_garmin_sync?: string | null;
  };
  ingestion_state?: {
    provider: string;
    updated_at?: string | null;
    last_index_status?: string | null;
    last_index_error?: string | null;
    last_index_started_at?: string | null;
    last_index_finished_at?: string | null;
    last_best_efforts_status?: string | null;
    last_best_efforts_error?: string | null;
    last_best_efforts_started_at?: string | null;
    last_best_efforts_finished_at?: string | null;
  } | null;
  intake_history?: Array<{
    id: string;
    stage: string;
    responses: Record<string, any>;
    completed_at?: string | null;
    created_at?: string | null;
  }>;
  active_plan?: {
    id: string;
    name: string;
    status: string;
    plan_type: string;
    plan_start_date?: string | null;
    plan_end_date?: string | null;
    goal_race_name?: string | null;
    goal_race_date?: string | null;
  } | null;
  stats: {
    activities: number;
    nutrition_entries: number;
    work_patterns: number;
    body_composition_entries: number;
  };
}

export interface UserListResponse {
  total: number;
  users: AdminUser[];
  offset: number;
  limit: number;
}

export interface SystemHealth {
  database: string;
  users: {
    total: number;
    active_30d: number;
  };
  activities: {
    total: number;
    last_7d: number;
  };
  data_collection: {
    nutrition_entries: number;
    work_patterns: number;
    body_composition: number;
  };
  timestamp: string;
}

export interface SiteMetrics {
  period_days: number;
  user_growth: {
    new_users: number;
    growth_rate: number;
  };
  engagement: {
    users_with_activities: number;
    users_with_nutrition: number;
    avg_activities_per_user: number;
  };
  timestamp: string;
}

export interface OpsQueueSnapshot {
  available: boolean;
  error?: string;
  active_count: number;
  reserved_count: number;
  scheduled_count: number;
  workers_seen: string[];
}

export interface OpsIngestionStuckResponse {
  cutoff: string;
  count: number;
  items: Array<{
    athlete_id: string;
    email: string | null;
    display_name: string | null;
    kind: 'index' | 'best_efforts' | null;
    started_at: string | null;
    task_id: string | null;
    updated_at: string | null;
    last_index_status: string | null;
    last_index_error: string | null;
    last_best_efforts_status: string | null;
    last_best_efforts_error: string | null;
  }>;
}

export interface OpsIngestionErrorsResponse {
  cutoff: string;
  count: number;
  items: Array<{
    athlete_id: string;
    email: string | null;
    display_name: string | null;
    updated_at: string | null;
    last_index_status: string | null;
    last_index_error: string | null;
    last_best_efforts_status: string | null;
    last_best_efforts_error: string | null;
  }>;
}

export interface OpsIngestionDeferredResponse {
  now: string;
  count: number;
  items: Array<{
    athlete_id: string;
    email: string | null;
    display_name: string | null;
    deferred_until: string | null;
    deferred_reason: string | null;
    last_index_status: string | null;
    last_best_efforts_status: string | null;
    updated_at: string | null;
  }>;
}

export interface OpsIngestionPauseResponse {
  paused: boolean;
}

export interface ImpersonationResponse {
  token: string;
  user: {
    id: string;
    email: string | null;
    display_name: string | null;
  };
  impersonated_by: {
    id: string;
    email: string | null;
  };
  expires_at?: string | null;
  ttl_minutes?: number | null;
}

export interface FeatureFlag {
  key: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  requires_subscription: boolean;
  requires_tier?: string | null;
  requires_payment?: number | null;
  rollout_percentage: number;
  allowed_athlete_ids: string[];
}

export type ThreeDSelectionMode = 'off' | 'shadow' | 'on';

// ============ Invite Types ============

export interface Invite {
  id: string;
  email: string;
  is_active: boolean;
  note: string | null;
  grant_tier: 'free' | 'pro' | null;
  invited_at: string | null;
  revoked_at: string | null;
  used_at: string | null;
  invited_by_athlete_id: string | null;
  revoked_by_athlete_id: string | null;
  used_by_athlete_id: string | null;
}

export interface InviteListResponse {
  invites: Invite[];
}

export interface InviteCreateResponse {
  success: boolean;
  invite: {
    id: string;
    email: string;
    is_active: boolean;
    used_at: string | null;
    grant_tier: 'free' | 'pro' | null;
  };
}

export interface InviteRevokeResponse {
  success: boolean;
  invite: {
    id: string;
    email: string;
    is_active: boolean;
    revoked_at: string | null;
  };
}

export const adminService = {
  /**
   * List users with filtering
   */
  async listUsers(params?: {
    search?: string;
    role?: string;
    limit?: number;
    offset?: number;
  }): Promise<UserListResponse> {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      });
    }
    const queryString = queryParams.toString();
    return apiClient.get<UserListResponse>(`/v1/admin/users${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * Get user details
   */
  async getUser(userId: string): Promise<AdminUserDetail> {
    return apiClient.get<AdminUserDetail>(`/v1/admin/users/${userId}`);
  },

  async compAccess(userId: string, params: { tier: string; reason?: string | null }): Promise<{ success: boolean; user: { id: string; email: string | null; subscription_tier: string } }> {
    return apiClient.post(`/v1/admin/users/${userId}/comp`, params);
  },

  async grantTrial(userId: string, params: { days?: number; reason?: string | null }): Promise<any> {
    return apiClient.post(`/v1/admin/users/${userId}/trial/grant`, params);
  },

  async revokeTrial(userId: string, params: { reason?: string | null }): Promise<any> {
    return apiClient.post(`/v1/admin/users/${userId}/trial/revoke`, params);
  },

  async resetOnboarding(userId: string, params: { stage?: string; reason?: string | null }): Promise<any> {
    return apiClient.post(`/v1/admin/users/${userId}/onboarding/reset`, params);
  },

  async resetPassword(userId: string, params: { reason?: string | null }): Promise<{
    success: boolean;
    user_id: string;
    email: string;
    temporary_password: string;
    message: string;
  }> {
    return apiClient.post(`/v1/admin/users/${userId}/password/reset`, params);
  },

  async retryIngestion(userId: string, params: { pages?: number; reason?: string | null }): Promise<any> {
    return apiClient.post(`/v1/admin/users/${userId}/ingestion/retry`, params);
  },

  async setBlocked(userId: string, params: { blocked: boolean; reason?: string | null }): Promise<any> {
    return apiClient.post(`/v1/admin/users/${userId}/block`, params);
  },

  async setCoachVip(userId: string, params: { is_vip: boolean; reason?: string | null }): Promise<{
    success: boolean;
    user: { id: string; email: string; is_coach_vip: boolean };
  }> {
    return apiClient.post(`/v1/admin/users/${userId}/coach-vip`, params);
  },

  async regenerateStarterPlan(userId: string, params: { reason?: string | null }): Promise<{
    success: boolean;
    archived_plan_ids: string[];
    new_plan_id: string;
    new_generation_method?: string | null;
  }> {
    return apiClient.post(`/v1/admin/users/${userId}/plans/starter/regenerate`, params);
  },

  async getOpsQueue(): Promise<OpsQueueSnapshot> {
    return apiClient.get<OpsQueueSnapshot>('/v1/admin/ops/queue');
  },

  async getOpsIngestionPause(): Promise<OpsIngestionPauseResponse> {
    return apiClient.get<OpsIngestionPauseResponse>('/v1/admin/ops/ingestion/pause');
  },

  async setOpsIngestionPause(params: { paused: boolean; reason?: string | null }): Promise<{ success: boolean; paused: boolean }> {
    return apiClient.post('/v1/admin/ops/ingestion/pause', params);
  },

  async getOpsStuckIngestion(params?: { minutes?: number; limit?: number }): Promise<OpsIngestionStuckResponse> {
    const qs = new URLSearchParams();
    if (params?.minutes != null) qs.set('minutes', String(params.minutes));
    if (params?.limit != null) qs.set('limit', String(params.limit));
    const tail = qs.toString() ? `?${qs.toString()}` : '';
    return apiClient.get<OpsIngestionStuckResponse>(`/v1/admin/ops/ingestion/stuck${tail}`);
  },

  async getOpsIngestionErrors(params?: { days?: number; limit?: number }): Promise<OpsIngestionErrorsResponse> {
    const qs = new URLSearchParams();
    if (params?.days != null) qs.set('days', String(params.days));
    if (params?.limit != null) qs.set('limit', String(params.limit));
    const tail = qs.toString() ? `?${qs.toString()}` : '';
    return apiClient.get<OpsIngestionErrorsResponse>(`/v1/admin/ops/ingestion/errors${tail}`);
  },

  async getOpsDeferredIngestion(params?: { limit?: number }): Promise<OpsIngestionDeferredResponse> {
    const qs = new URLSearchParams();
    if (params?.limit != null) qs.set('limit', String(params.limit));
    const tail = qs.toString() ? `?${qs.toString()}` : '';
    return apiClient.get<OpsIngestionDeferredResponse>(`/v1/admin/ops/ingestion/deferred${tail}`);
  },

  /**
   * Start impersonation session
   */
  async impersonateUser(
    userId: string,
    params?: { reason?: string | null; ttl_minutes?: number | null }
  ): Promise<ImpersonationResponse> {
    return apiClient.post<ImpersonationResponse>(`/v1/admin/users/${userId}/impersonate`, params || undefined);
  },

  /**
   * Get system health
   */
  async getSystemHealth(): Promise<SystemHealth> {
    return apiClient.get<SystemHealth>('/v1/admin/health');
  },

  /**
   * Get site metrics
   */
  async getSiteMetrics(days: number = 30): Promise<SiteMetrics> {
    return apiClient.get<SiteMetrics>(`/v1/admin/metrics?days=${days}`);
  },

  /**
   * Test correlation calculation
   */
  async testCorrelations(athleteId: string, days: number = 90): Promise<any> {
    return apiClient.post(`/v1/admin/correlations/test?athlete_id=${athleteId}&days=${days}`);
  },

  /**
   * Cross-athlete query
   */
  async crossAthleteQuery(queryType: string, minActivities: number = 10): Promise<any> {
    return apiClient.get(`/v1/admin/query?query_type=${queryType}&min_activities=${minActivities}`);
  },

  /**
   * List feature flags
   */
  async listFeatureFlags(prefix?: string): Promise<{ flags: FeatureFlag[] }> {
    const qs = prefix ? `?prefix=${encodeURIComponent(prefix)}` : '';
    return apiClient.get<{ flags: FeatureFlag[] }>(`/v1/admin/feature-flags${qs}`);
  },

  /**
   * Admin-friendly control for 3D quality-session selection
   */
  async set3dQualitySelectionMode(params: {
    mode: ThreeDSelectionMode;
    rollout_percentage?: number;
    allowlist_emails?: string[];
  }): Promise<{
    success: boolean;
    mode: ThreeDSelectionMode;
    rollout_percentage: number | null;
    allowlist_athlete_ids: string[];
  }> {
    return apiClient.post(`/v1/admin/features/3d-quality-selection`, params);
  },

  // ============ Invite Management ============

  /**
   * List invite allowlist entries
   */
  async listInvites(params?: { active_only?: boolean; limit?: number }): Promise<InviteListResponse> {
    const qs = new URLSearchParams();
    if (params?.active_only != null) qs.set('active_only', String(params.active_only));
    if (params?.limit != null) qs.set('limit', String(params.limit));
    const tail = qs.toString() ? `?${qs.toString()}` : '';
    return apiClient.get<InviteListResponse>(`/v1/admin/invites${tail}`);
  },

  /**
   * Create a new invite
   */
  async createInvite(params: { email: string; note?: string | null; grant_tier?: 'free' | 'pro' | null }): Promise<InviteCreateResponse> {
    return apiClient.post<InviteCreateResponse>('/v1/admin/invites', params);
  },

  /**
   * Revoke an invite
   */
  async revokeInvite(params: { email: string; reason?: string | null }): Promise<InviteRevokeResponse> {
    return apiClient.post<InviteRevokeResponse>('/v1/admin/invites/revoke', params);
  },

  // ============ Race Promo Codes ============

  /**
   * List race promo codes
   */
  async listRaceCodes(params?: { include_inactive?: boolean }): Promise<RaceCodeListResponse> {
    const qs = params?.include_inactive ? '?include_inactive=true' : '';
    return apiClient.get<RaceCodeListResponse>(`/v1/admin/race-codes${qs}`);
  },

  /**
   * Create a race promo code
   */
  async createRaceCode(params: {
    code: string;
    race_name: string;
    race_date?: string | null;
    trial_days?: number;
    valid_until?: string | null;
    max_uses?: number | null;
  }): Promise<RaceCodeCreateResponse> {
    return apiClient.post<RaceCodeCreateResponse>('/v1/admin/race-codes', params);
  },

  /**
   * Deactivate a race promo code
   */
  async deactivateRaceCode(code: string): Promise<{ success: boolean; code: string; is_active: boolean }> {
    return apiClient.post(`/v1/admin/race-codes/${encodeURIComponent(code)}/deactivate`, {});
  },

  /**
   * Get QR code URL for a race promo code
   */
  getRaceCodeQrUrl(code: string, size?: number): string {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || '';
    const sizeParam = size ? `?size=${size}` : '';
    // Return the full URL - caller will need to handle auth
    return `${baseUrl}/v1/admin/race-codes/${encodeURIComponent(code)}/qr${sizeParam}`;
  },
} as const;

// Race Code types
export interface RaceCode {
  id: string;
  code: string;
  race_name: string;
  race_date: string | null;
  trial_days: number;
  valid_from: string;
  valid_until: string | null;
  max_uses: number | null;
  current_uses: number;
  is_active: boolean;
  created_at: string;
}

export interface RaceCodeListResponse {
  codes: RaceCode[];
  total: number;
}

export interface RaceCodeCreateResponse {
  success: boolean;
  code: string;
  race_name: string;
  trial_days: number;
  valid_until: string | null;
  max_uses: number | null;
}


