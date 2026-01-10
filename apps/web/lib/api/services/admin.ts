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

  /**
   * Start impersonation session
   */
  async impersonateUser(userId: string): Promise<ImpersonationResponse> {
    return apiClient.post<ImpersonationResponse>(`/v1/admin/users/${userId}/impersonate`);
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
} as const;


