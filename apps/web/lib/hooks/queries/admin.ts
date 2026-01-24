/**
 * React Query hooks for admin dashboard
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminService, type AdminUserDetail, type FeatureFlag, type ThreeDSelectionMode } from '../../api/services/admin';
import type { UserListResponse, SystemHealth, SiteMetrics, ImpersonationResponse } from '../../api/services/admin';

export const adminKeys = {
  all: ['admin'] as const,
  users: () => [...adminKeys.all, 'users'] as const,
  userList: (params?: any) => [...adminKeys.users(), 'list', params] as const,
  userDetail: (id: string) => [...adminKeys.users(), 'detail', id] as const,
  health: () => [...adminKeys.all, 'health'] as const,
  metrics: (days: number) => [...adminKeys.all, 'metrics', days] as const,
  flags: (prefix?: string) => [...adminKeys.all, 'feature_flags', prefix || ''] as const,
} as const;

/**
 * List users
 */
export function useAdminUsers(params?: {
  search?: string;
  role?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery<UserListResponse>({
    queryKey: adminKeys.userList(params),
    queryFn: () => adminService.listUsers(params),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Get user details
 */
export function useAdminUser(userId: string) {
  return useQuery<AdminUserDetail>({
    queryKey: adminKeys.userDetail(userId),
    queryFn: () => adminService.getUser(userId),
    enabled: !!userId,
  });
}

/**
 * Get system health
 */
export function useSystemHealth() {
  return useQuery<SystemHealth>({
    queryKey: adminKeys.health(),
    queryFn: () => adminService.getSystemHealth(),
    refetchInterval: 30 * 1000, // Refetch every 30 seconds
  });
}

/**
 * Get site metrics
 */
export function useSiteMetrics(days: number = 30) {
  return useQuery<SiteMetrics>({
    queryKey: adminKeys.metrics(days),
    queryFn: () => adminService.getSiteMetrics(days),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Impersonate user mutation
 */
export function useImpersonateUser() {
  return useMutation({
    mutationFn: (userId: string) => adminService.impersonateUser(userId),
    onSuccess: (data) => {
      // Store impersonation token
      localStorage.setItem('impersonation_token', data.token);
      localStorage.setItem('impersonated_user', JSON.stringify(data.user));
      // Reload page to switch user context
      window.location.reload();
    },
  });
}

export function useCompAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; tier: string; reason?: string }) =>
      adminService.compAccess(params.userId, { tier: params.tier, reason: params.reason }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: adminKeys.userDetail(vars.userId) });
      qc.invalidateQueries({ queryKey: adminKeys.userList() });
    },
  });
}

export function useResetOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; stage?: string; reason?: string }) =>
      adminService.resetOnboarding(params.userId, { stage: params.stage, reason: params.reason }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: adminKeys.userDetail(vars.userId) });
    },
  });
}

export function useRetryIngestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; pages?: number; reason?: string }) =>
      adminService.retryIngestion(params.userId, { pages: params.pages, reason: params.reason }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: adminKeys.userDetail(vars.userId) });
    },
  });
}

export function useSetBlocked() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; blocked: boolean; reason?: string }) =>
      adminService.setBlocked(params.userId, { blocked: params.blocked, reason: params.reason }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: adminKeys.userDetail(vars.userId) });
      qc.invalidateQueries({ queryKey: adminKeys.userList() });
    },
  });
}

/**
 * List feature flags (admin)
 */
export function useAdminFeatureFlags(prefix?: string) {
  return useQuery<{ flags: FeatureFlag[] }>({
    queryKey: adminKeys.flags(prefix),
    queryFn: () => adminService.listFeatureFlags(prefix),
    staleTime: 10 * 1000,
  });
}

/**
 * Set 3D quality selection mode (admin)
 */
export function useSet3dQualitySelectionMode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { mode: ThreeDSelectionMode; rollout_percentage?: number; allowlist_emails?: string[] }) =>
      adminService.set3dQualitySelectionMode(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.flags() });
      qc.invalidateQueries({ queryKey: adminKeys.flags('plan.') });
    },
  });
}


