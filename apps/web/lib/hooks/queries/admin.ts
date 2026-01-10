/**
 * React Query hooks for admin dashboard
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminService, type AdminUserDetail } from '../../api/services/admin';
import type { UserListResponse, SystemHealth, SiteMetrics, ImpersonationResponse } from '../../api/services/admin';

export const adminKeys = {
  all: ['admin'] as const,
  users: () => [...adminKeys.all, 'users'] as const,
  userList: (params?: any) => [...adminKeys.users(), 'list', params] as const,
  userDetail: (id: string) => [...adminKeys.users(), 'detail', id] as const,
  health: () => [...adminKeys.all, 'health'] as const,
  metrics: (days: number) => [...adminKeys.all, 'metrics', days] as const,
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


