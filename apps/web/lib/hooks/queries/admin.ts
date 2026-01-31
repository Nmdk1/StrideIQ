/**
 * React Query hooks for admin dashboard
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminService, type AdminUserDetail, type FeatureFlag, type ThreeDSelectionMode, type Invite, type InviteListResponse, type InviteCreateResponse, type InviteRevokeResponse } from '../../api/services/admin';
import type { UserListResponse, SystemHealth, SiteMetrics, ImpersonationResponse, OpsQueueSnapshot, OpsIngestionStuckResponse, OpsIngestionErrorsResponse, OpsIngestionDeferredResponse, OpsIngestionPauseResponse } from '../../api/services/admin';

export const adminKeys = {
  all: ['admin'] as const,
  users: () => [...adminKeys.all, 'users'] as const,
  userList: (params?: any) => [...adminKeys.users(), 'list', params] as const,
  userDetail: (id: string) => [...adminKeys.users(), 'detail', id] as const,
  health: () => [...adminKeys.all, 'health'] as const,
  metrics: (days: number) => [...adminKeys.all, 'metrics', days] as const,
  flags: (prefix?: string) => [...adminKeys.all, 'feature_flags', prefix || ''] as const,
  ops: () => [...adminKeys.all, 'ops'] as const,
  opsQueue: () => [...adminKeys.ops(), 'queue'] as const,
  opsStuck: (params?: any) => [...adminKeys.ops(), 'stuck', params] as const,
  opsErrors: (params?: any) => [...adminKeys.ops(), 'errors', params] as const,
  opsDeferred: (params?: any) => [...adminKeys.ops(), 'deferred', params] as const,
  opsPause: () => [...adminKeys.ops(), 'pause'] as const,
  invites: () => [...adminKeys.all, 'invites'] as const,
  inviteList: (params?: any) => [...adminKeys.invites(), 'list', params] as const,
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
    mutationFn: (params: { userId: string; reason?: string | null; ttl_minutes?: number | null }) =>
      adminService.impersonateUser(params.userId, { reason: params.reason, ttl_minutes: params.ttl_minutes }),
    onSuccess: (data) => {
      // Switch session token to impersonation token (time-boxed), but preserve original admin session.
      const original = localStorage.getItem('auth_token');
      if (original) {
        localStorage.setItem('impersonation_original_auth_token', original);
      }

      localStorage.setItem('impersonation_token', data.token);
      localStorage.setItem('impersonation_active', 'true');
      if (data.expires_at) localStorage.setItem('impersonation_expires_at', data.expires_at);
      localStorage.setItem('impersonated_user', JSON.stringify(data.user));

      // AuthContext + ApiClient read from auth_token/auth_user; write them to make impersonation actually take effect.
      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));

      if (process.env.NODE_ENV !== 'test') {
        window.location.reload();
      }
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

export function useGrantTrial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; days?: number; reason?: string | null }) =>
      adminService.grantTrial(params.userId, { days: params.days, reason: params.reason }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: adminKeys.userDetail(vars.userId) });
    },
  });
}

export function useRevokeTrial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; reason?: string | null }) =>
      adminService.revokeTrial(params.userId, { reason: params.reason }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: adminKeys.userDetail(vars.userId) });
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

export function useResetPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; reason?: string }) =>
      adminService.resetPassword(params.userId, { reason: params.reason }),
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

export function useRegenerateStarterPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { userId: string; reason?: string | null }) =>
      adminService.regenerateStarterPlan(params.userId, { reason: params.reason }),
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

export function useOpsQueue() {
  return useQuery<OpsQueueSnapshot>({
    queryKey: adminKeys.opsQueue(),
    queryFn: () => adminService.getOpsQueue(),
    refetchInterval: 15 * 1000,
  });
}

export function useOpsIngestionPause() {
  return useQuery<OpsIngestionPauseResponse>({
    queryKey: adminKeys.opsPause(),
    queryFn: () => adminService.getOpsIngestionPause(),
    refetchInterval: 10 * 1000,
  });
}

export function useSetOpsIngestionPause() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { paused: boolean; reason?: string | null }) => adminService.setOpsIngestionPause(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.opsPause() });
    },
  });
}

export function useOpsStuckIngestion(params?: { minutes?: number; limit?: number }) {
  return useQuery<OpsIngestionStuckResponse>({
    queryKey: adminKeys.opsStuck(params),
    queryFn: () => adminService.getOpsStuckIngestion(params),
    refetchInterval: 30 * 1000,
  });
}

export function useOpsIngestionErrors(params?: { days?: number; limit?: number }) {
  return useQuery<OpsIngestionErrorsResponse>({
    queryKey: adminKeys.opsErrors(params),
    queryFn: () => adminService.getOpsIngestionErrors(params),
    refetchInterval: 60 * 1000,
  });
}

export function useOpsDeferredIngestion(params?: { limit?: number }) {
  return useQuery<OpsIngestionDeferredResponse>({
    queryKey: adminKeys.opsDeferred(params),
    queryFn: () => adminService.getOpsDeferredIngestion(params),
    refetchInterval: 30 * 1000,
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

// ============ Invite Hooks ============

/**
 * List invite allowlist entries
 */
export function useAdminInvites(params?: { active_only?: boolean; limit?: number }) {
  return useQuery<InviteListResponse>({
    queryKey: adminKeys.inviteList(params),
    queryFn: () => adminService.listInvites(params),
    staleTime: 30 * 1000,
  });
}

/**
 * Create an invite
 */
export function useCreateInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { email: string; note?: string | null; grant_tier?: 'free' | 'pro' | null }) =>
      adminService.createInvite(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.invites() });
    },
  });
}

/**
 * Revoke an invite
 */
export function useRevokeInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { email: string; reason?: string | null }) =>
      adminService.revokeInvite(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.invites() });
    },
  });
}


