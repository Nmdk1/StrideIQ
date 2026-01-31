/**
 * Admin Dashboard Page
 * 
 * Comprehensive command center for site management, monitoring, testing, and debugging.
 * Owner/admin role only.
 * 
 * Features:
 * - User Management with impersonation
 * - System Health monitoring
 * - Site Metrics and growth
 * - Query Engine for data mining
 * - Testing tools
 */

'use client';

import { useEffect, useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { useAdminUsers, useSystemHealth, useSiteMetrics, useImpersonateUser, useAdminFeatureFlags, useSet3dQualitySelectionMode, useAdminUser, useCompAccess, useGrantTrial, useRevokeTrial, useResetOnboarding, useResetPassword, useRetryIngestion, useRegenerateStarterPlan, useSetBlocked, useOpsQueue, useOpsStuckIngestion, useOpsIngestionErrors, useOpsIngestionPause, useSetOpsIngestionPause, useOpsDeferredIngestion, useAdminInvites, useCreateInvite, useRevokeInvite } from '@/lib/hooks/queries/admin';
import { useQueryTemplates, useQueryEntities, useExecuteTemplate, useExecuteCustomQuery } from '@/lib/hooks/queries/query-engine';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useRouter } from 'next/navigation';

export default function AdminPage() {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [selectedTab, setSelectedTab] = useState<'users' | 'ops' | 'health' | 'metrics' | 'flags' | 'query' | 'testing' | 'invites'>('users');
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [adminReason, setAdminReason] = useState<string>('');
  const [desiredTier, setDesiredTier] = useState<string>('pro');
  const [tempPassword, setTempPassword] = useState<{ email: string; password: string } | null>(null);
  
  // User management
  const { data: users, isLoading: usersLoading } = useAdminUsers({ search, limit: 50 });
  const { data: selectedUser, isLoading: userLoading } = useAdminUser(selectedUserId);
  const { data: health, isLoading: healthLoading } = useSystemHealth();
  const { data: metrics, isLoading: metricsLoading } = useSiteMetrics(30);
  const impersonateUser = useImpersonateUser();
  const compAccess = useCompAccess();
  const grantTrial = useGrantTrial();
  const revokeTrial = useRevokeTrial();
  const resetOnboarding = useResetOnboarding();
  const resetPassword = useResetPassword();
  const retryIngestion = useRetryIngestion();
  const regenerateStarterPlan = useRegenerateStarterPlan();
  const setBlocked = useSetBlocked();
  const { data: opsQueue, isLoading: opsQueueLoading } = useOpsQueue();
  const { data: opsStuck, isLoading: opsStuckLoading } = useOpsStuckIngestion({ minutes: 30, limit: 100 });
  const { data: opsErrors, isLoading: opsErrorsLoading } = useOpsIngestionErrors({ days: 7, limit: 200 });
  const { data: opsPause, isLoading: opsPauseLoading } = useOpsIngestionPause();
  const setOpsPause = useSetOpsIngestionPause();
  const { data: opsDeferred, isLoading: opsDeferredLoading } = useOpsDeferredIngestion({ limit: 200 });

  // Invites
  const { data: invitesData, isLoading: invitesLoading, error: invitesError } = useAdminInvites({ limit: 200 });
  const createInvite = useCreateInvite();
  const revokeInvite = useRevokeInvite();
  const [newInviteEmail, setNewInviteEmail] = useState('');
  const [newInviteNote, setNewInviteNote] = useState('');
  const [newInviteGrantTier, setNewInviteGrantTier] = useState<'free' | 'pro' | ''>('');
  const [inviteFilter, setInviteFilter] = useState<'all' | 'pending' | 'used'>('all');
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  // Feature flags
  const { data: flagsData, isLoading: flagsLoading } = useAdminFeatureFlags('plan.');
  const set3dMode = useSet3dQualitySelectionMode();
  const [desired3dMode, setDesired3dMode] = useState<'off' | 'shadow' | 'on'>('off');
  const [desiredRollout, setDesiredRollout] = useState<number>(0);
  const [allowlistEmails, setAllowlistEmails] = useState<string>('');
  
  // Query Engine
  const { data: templates } = useQueryTemplates();
  const { data: entities } = useQueryEntities();
  const executeTemplate = useExecuteTemplate();
  const executeCustom = useExecuteCustomQuery();
  
  // Query state
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [queryDays, setQueryDays] = useState(180);
  const [queryAthleteId, setQueryAthleteId] = useState('');
  const [queryWorkoutType, setQueryWorkoutType] = useState('');
  const [queryResults, setQueryResults] = useState<any>(null);
  
  // Custom query state
  const [customEntity, setCustomEntity] = useState('activity');
  const [customGroupBy, setCustomGroupBy] = useState('');
  const [customAggregations, setCustomAggregations] = useState('');
  const [customFilters, setCustomFilters] = useState('');
  
  const handleExecuteTemplate = async () => {
    if (!selectedTemplate) return;
    
    const result = await executeTemplate.mutateAsync({
      template: selectedTemplate,
      days: queryDays,
      athleteId: queryAthleteId || undefined,
      workoutType: queryWorkoutType || undefined,
    });
    setQueryResults(result);
  };
  
  const handleExecuteCustom = async () => {
    const result = await executeCustom.mutateAsync({
      entity: customEntity,
      days: queryDays,
      athleteId: queryAthleteId || undefined,
      groupBy: customGroupBy ? customGroupBy.split(',').map(s => s.trim()) : undefined,
      aggregations: customAggregations ? Object.fromEntries(
        customAggregations.split(',').map(pair => {
          const [field, agg] = pair.split(':').map(s => s.trim());
          return [field, agg];
        })
      ) : undefined,
      filters: customFilters ? JSON.parse(customFilters) : undefined,
      limit: 100,
    });
    setQueryResults(result);
  };

  const isAdmin = !!user && (user.role === 'admin' || user.role === 'owner');
  const isOwner = !!user && user.role === 'owner';

  // Hard redirect non-admins away from /admin.
  // IMPORTANT: treat "authenticated but no user yet" as unauthorized until proven otherwise.
  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) return;
    if (!isAdmin) {
      router.replace('/home');
    }
  }, [router, isAdmin, isAuthenticated, isLoading]);

  // Never render admin content unless we have a confirmed admin/owner.
  if (isLoading || !isAuthenticated || !isAdmin) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="mb-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold mb-2">Admin Dashboard</h1>
                <p className="text-slate-400">Command center for site management and monitoring</p>
              </div>
              <a
                href="/admin/diagnostics"
                className="inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 border border-slate-700/50 text-slate-200"
              >
                Data Health
              </a>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mb-6 border-b border-slate-700/50">
            <button
              onClick={() => setSelectedTab('users')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'users'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Users
            </button>
            <button
              onClick={() => setSelectedTab('ops')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'ops'
                  ? 'border-b-2 border-orange-600 text-orange-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Ops
            </button>
            <button
              onClick={() => setSelectedTab('health')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'health'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              System Health
            </button>
            <button
              onClick={() => setSelectedTab('metrics')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'metrics'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Site Metrics
            </button>
            <button
              onClick={() => setSelectedTab('flags')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'flags'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Feature Flags
            </button>
            <button
              onClick={() => setSelectedTab('query')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'query'
                  ? 'border-b-2 border-orange-600 text-orange-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              🔍 Query Engine
            </button>
            <button
              onClick={() => setSelectedTab('testing')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'testing'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Testing
            </button>
            <button
              onClick={() => setSelectedTab('invites')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'invites'
                  ? 'border-b-2 border-green-600 text-green-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Invites
            </button>
          </div>

          {/* Users Tab */}
          {selectedTab === 'users' && (
            <div>
              <div className="mb-4">
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search users by email or name..."
                  className="w-full max-w-md px-4 py-2 bg-slate-800 border border-slate-700/50 rounded text-white"
                />
              </div>

              {usersLoading ? (
                <LoadingSpinner />
              ) : users ? (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                  <div className="xl:col-span-2 bg-slate-800 rounded-lg border border-slate-700/50 overflow-hidden">
                    <table className="w-full">
                    <thead className="bg-slate-900">
                      <tr>
                        <th className="px-4 py-3 text-left text-sm font-semibold">Email</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold">Name</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold">Role</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold">Tier</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold">Created</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.users.map((user) => (
                        <tr key={user.id} className="border-t border-slate-700/50">
                          <td className="px-4 py-3 text-sm">{user.email || '--'}</td>
                          <td className="px-4 py-3 text-sm">{user.display_name || '--'}</td>
                          <td className="px-4 py-3 text-sm">
                            <span className={`px-2 py-1 rounded text-xs ${
                              user.role === 'admin' || user.role === 'owner'
                                ? 'bg-blue-900/50 text-blue-400'
                                : 'bg-slate-700 text-slate-300'
                            }`}>
                              {user.role}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm">{user.subscription_tier}</td>
                          <td className="px-4 py-3 text-sm text-slate-400">
                            {new Date(user.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => setSelectedUserId(user.id)}
                                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs"
                              >
                                View
                              </button>
                              {isOwner ? (
                                <button
                                  onClick={() => impersonateUser.mutate({ userId: user.id })}
                                  disabled={impersonateUser.isPending}
                                  className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-xs"
                                >
                                  {impersonateUser.isPending ? <LoadingSpinner size="sm" /> : 'Impersonate'}
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="px-4 py-3 bg-slate-900 border-t border-slate-700/50 text-sm text-slate-400">
                    Showing {users.users.length} of {users.total} users
                  </div>
                  </div>

                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-4">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <div className="text-sm font-semibold">User detail</div>
                        <div className="text-xs text-slate-400">Select a user to see “God Mode” controls.</div>
                      </div>
                      {selectedUserId && (
                        <button onClick={() => setSelectedUserId('')} className="text-xs text-slate-400 hover:text-slate-200">
                          Clear
                        </button>
                      )}
                    </div>

                    {selectedUserId && userLoading ? (
                      <LoadingSpinner />
                    ) : selectedUserId && selectedUser ? (
                      <div className="space-y-4">
                        <div className="space-y-1">
                          <div className="text-sm font-semibold">{selectedUser.display_name || '—'}</div>
                          <div className="text-xs text-slate-400">{selectedUser.email || '—'}</div>
                          <div className="text-xs text-slate-400">
                            Role: <span className="text-slate-200">{selectedUser.role}</span> • Tier:{' '}
                            <span className="text-slate-200">{selectedUser.subscription_tier}</span> • Blocked:{' '}
                            <span className={selectedUser.is_blocked ? 'text-red-400' : 'text-green-400'}>
                              {selectedUser.is_blocked ? 'yes' : 'no'}
                            </span>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-300">Operator reason (for audit)</div>
                          <input
                            value={adminReason}
                            onChange={(e) => setAdminReason(e.target.value)}
                            placeholder="e.g., VIP tester / stuck ingestion / support reset"
                            className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                          />
                        </div>

                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-300">Billing: Comp access</div>
                          <div className="flex items-center gap-2">
                            <select
                              value={desiredTier}
                              onChange={(e) => setDesiredTier(e.target.value)}
                              className="flex-1 px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                            >
                              <option value="free">free</option>
                              <option value="pro">pro</option>
                            </select>
                            <button
                              onClick={() =>
                                compAccess.mutate({ userId: selectedUser.id, tier: desiredTier, reason: adminReason || undefined })
                              }
                              disabled={compAccess.isPending}
                              className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded text-xs font-semibold"
                            >
                              {compAccess.isPending ? 'Saving…' : 'Apply'}
                            </button>
                          </div>
                          <div className="text-xs text-slate-400">
                            Stripe:{' '}
                            {selectedUser.stripe_customer_id ? (
                              <a
                                href={`https://dashboard.stripe.com/customers/${selectedUser.stripe_customer_id}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-400 hover:text-blue-300"
                              >
                                Open customer
                              </a>
                            ) : (
                              <span className="text-slate-500">not linked</span>
                            )}
                          </div>
                          {selectedUser.subscription?.stripe_subscription_id ? (
                            <div className="text-xs text-slate-400">
                              Subscription:{' '}
                              <a
                                href={`https://dashboard.stripe.com/subscriptions/${selectedUser.subscription.stripe_subscription_id}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-400 hover:text-blue-300"
                              >
                                Open subscription
                              </a>
                              <span className="text-slate-500"> • {selectedUser.subscription.status || '—'}</span>
                            </div>
                          ) : null}
                          <div className="text-xs text-slate-400">
                            Trial:{' '}
                            {selectedUser.trial_ends_at ? (
                              <span className="text-slate-200">
                                ends {new Date(selectedUser.trial_ends_at).toLocaleDateString()}
                              </span>
                            ) : (
                              <span className="text-slate-500">none</span>
                            )}
                            {selectedUser.trial_source ? <span className="text-slate-500"> • {selectedUser.trial_source}</span> : null}
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-300">Actions</div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() => grantTrial.mutate({ userId: selectedUser.id, days: 7, reason: adminReason || null })}
                              disabled={grantTrial.isPending}
                              className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 rounded text-xs"
                            >
                              {grantTrial.isPending ? 'Granting…' : 'Grant 7-day trial'}
                            </button>
                            <button
                              onClick={() => revokeTrial.mutate({ userId: selectedUser.id, reason: adminReason || null })}
                              disabled={revokeTrial.isPending}
                              className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 rounded text-xs"
                            >
                              {revokeTrial.isPending ? 'Revoking…' : 'Revoke trial'}
                            </button>
                            <button
                              onClick={() => resetOnboarding.mutate({ userId: selectedUser.id, stage: 'initial', reason: adminReason || undefined })}
                              disabled={resetOnboarding.isPending}
                              className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 rounded text-xs"
                            >
                              {resetOnboarding.isPending ? 'Resetting…' : 'Reset onboarding'}
                            </button>
                            <button
                              onClick={() => retryIngestion.mutate({ userId: selectedUser.id, pages: 5, reason: adminReason || undefined })}
                              disabled={retryIngestion.isPending}
                              className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 rounded text-xs"
                            >
                              {retryIngestion.isPending ? 'Queuing…' : 'Retry ingestion'}
                            </button>
                            <button
                              onClick={() => {
                                resetPassword.mutate(
                                  { userId: selectedUser.id, reason: adminReason || undefined },
                                  {
                                    onSuccess: (data) => {
                                      setTempPassword({ email: data.email, password: data.temporary_password });
                                    },
                                  }
                                );
                              }}
                              disabled={resetPassword.isPending}
                              className="px-3 py-2 bg-amber-700 hover:bg-amber-600 disabled:bg-slate-700 rounded text-xs"
                            >
                              {resetPassword.isPending ? 'Resetting…' : 'Reset password'}
                            </button>
                            <button
                              onClick={() => setBlocked.mutate({ userId: selectedUser.id, blocked: !selectedUser.is_blocked, reason: adminReason || undefined })}
                              disabled={setBlocked.isPending}
                              className={`px-3 py-2 rounded text-xs ${
                                selectedUser.is_blocked ? 'bg-green-700 hover:bg-green-600' : 'bg-red-700 hover:bg-red-600'
                              } disabled:bg-slate-700`}
                            >
                              {setBlocked.isPending ? 'Saving…' : selectedUser.is_blocked ? 'Unblock' : 'Block'}
                            </button>
                          </div>

                          {/* Temporary password display */}
                          {tempPassword && (
                            <div className="mt-3 p-3 bg-amber-900/50 border border-amber-700 rounded">
                              <div className="text-xs font-semibold text-amber-200 mb-2">Temporary Password Generated</div>
                              <div className="text-xs text-slate-300">
                                <div>Email: <span className="font-mono text-slate-100">{tempPassword.email}</span></div>
                                <div className="mt-1">
                                  Password: <span className="font-mono text-amber-100 bg-slate-800 px-2 py-1 rounded select-all">{tempPassword.password}</span>
                                </div>
                              </div>
                              <div className="mt-2 text-xs text-amber-300">Share this password with the user. They should change it after login.</div>
                              <button
                                onClick={() => setTempPassword(null)}
                                className="mt-2 px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs"
                              >
                                Dismiss
                              </button>
                            </div>
                          )}
                        </div>

                        <details className="bg-slate-900/40 border border-slate-700/50 rounded p-3">
                          <summary className="cursor-pointer text-sm text-slate-200">Integrations / ingestion</summary>
                          <div className="mt-2 text-xs text-slate-300 space-y-1">
                            <div>Units: {selectedUser.integrations?.preferred_units ?? '—'}</div>
                            <div>Strava athlete id: {String(selectedUser.integrations?.strava_athlete_id ?? '—')}</div>
                            <div>Last sync: {selectedUser.integrations?.last_strava_sync ?? '—'}</div>
                            <div>Ingestion status: {selectedUser.ingestion_state?.last_index_status ?? '—'}</div>
                            {selectedUser.ingestion_state?.last_index_error ? (
                              <div className="text-red-300">Index error: {selectedUser.ingestion_state.last_index_error}</div>
                            ) : null}
                          </div>
                        </details>

                        <details className="bg-slate-900/40 border border-slate-700/50 rounded p-3">
                          <summary className="cursor-pointer text-sm text-slate-200">Active plan</summary>
                          <div className="mt-2 text-xs text-slate-300">
                            {selectedUser.active_plan ? (
                              <div className="space-y-1">
                                <div>{selectedUser.active_plan.name}</div>
                                <div>Type: {selectedUser.active_plan.plan_type}</div>
                                <div>Goal: {selectedUser.active_plan.goal_race_name ?? '—'} ({selectedUser.active_plan.goal_race_date ?? '—'})</div>
                                <div className="pt-2">
                                  <button
                                    onClick={() =>
                                      regenerateStarterPlan.mutate({
                                        userId: selectedUser.id,
                                        reason: adminReason || 'beta support: regenerate starter plan',
                                      })
                                    }
                                    disabled={regenerateStarterPlan.isPending}
                                    className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 rounded text-xs"
                                  >
                                    {regenerateStarterPlan.isPending ? 'Regenerating…' : 'Regenerate starter plan'}
                                  </button>
                                  <div className="text-[11px] text-slate-500 mt-1">
                                    Archives current plan and rebuilds from saved intake (use for beta support).
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="text-slate-500">No active plan</div>
                            )}
                          </div>
                        </details>

                        <details className="bg-slate-900/40 border border-slate-700/50 rounded p-3">
                          <summary className="cursor-pointer text-sm text-slate-200">Intake history</summary>
                          <div className="mt-2 space-y-3">
                            {(selectedUser.intake_history || []).length === 0 ? (
                              <div className="text-xs text-slate-500">No intake records</div>
                            ) : (
                              (selectedUser.intake_history || []).slice(0, 5).map((row) => (
                                <div key={row.id} className="text-xs text-slate-300">
                                  <div className="font-semibold">{row.stage}</div>
                                  <pre className="mt-1 p-2 bg-slate-950/60 rounded overflow-x-auto max-h-40">
                                    {JSON.stringify(row.responses, null, 2)}
                                  </pre>
                                </div>
                              ))
                            )}
                          </div>
                        </details>
                      </div>
                    ) : (
                      <div className="text-sm text-slate-500">No user selected</div>
                    )}
                  </div>
                </div>
              ) : (
                <ErrorMessage error={new Error('Failed to load users')} />
              )}
            </div>
          )}

          {/* Ops Tab */}
          {selectedTab === 'ops' && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div>
                    <h3 className="text-lg font-semibold">Queue snapshot</h3>
                    <p className="text-slate-400 text-sm">
                      Best-effort Celery visibility. If unavailable, it won’t block admin operations.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-xs text-slate-400">Pause global ingestion</div>
                    {opsPauseLoading ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={!!opsPause?.paused}
                          onChange={(e) =>
                            setOpsPause.mutate({ paused: e.target.checked, reason: adminReason || null })
                          }
                        />
                        <span className={opsPause?.paused ? 'text-amber-300' : 'text-slate-300'}>
                          {opsPause?.paused ? 'Paused' : 'Running'}
                        </span>
                      </label>
                    )}
                  </div>
                </div>
                <p className="text-slate-400 text-sm mb-4">
                  When paused, Strava connect will still save tokens but will not enqueue ingestion until resumed.
                </p>

                {opsQueueLoading ? (
                  <LoadingSpinner />
                ) : opsQueue ? (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                      <div className="text-xs text-slate-400 mb-1">Inspect</div>
                      <div className={`text-xl font-bold ${opsQueue.available ? 'text-green-400' : 'text-red-400'}`}>
                        {opsQueue.available ? 'Available' : 'Unavailable'}
                      </div>
                      {!opsQueue.available && opsQueue.error ? (
                        <div className="text-xs text-slate-500 mt-2 break-words">{opsQueue.error}</div>
                      ) : null}
                    </div>
                    <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                      <div className="text-xs text-slate-400 mb-1">Active</div>
                      <div className="text-2xl font-bold">{opsQueue.active_count}</div>
                    </div>
                    <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                      <div className="text-xs text-slate-400 mb-1">Reserved</div>
                      <div className="text-2xl font-bold">{opsQueue.reserved_count}</div>
                    </div>
                    <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                      <div className="text-xs text-slate-400 mb-1">Scheduled</div>
                      <div className="text-2xl font-bold">{opsQueue.scheduled_count}</div>
                    </div>
                  </div>
                ) : (
                  <ErrorMessage error={new Error('Failed to load queue snapshot')} />
                )}
              </div>

              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-2">Deferred ingestion</h3>
                <p className="text-slate-400 text-sm mb-4">
                  Athletes intentionally deferred (e.g., Strava rate limits). These are not errors.
                </p>
                {opsDeferredLoading ? (
                  <LoadingSpinner />
                ) : opsDeferred ? (
                  opsDeferred.items.length === 0 ? (
                    <div className="text-sm text-slate-400">No deferred athletes right now.</div>
                  ) : (
                    <div className="overflow-x-auto rounded-lg border border-slate-700/50">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-900">
                          <tr>
                            <th className="px-4 py-3 text-left font-semibold">Athlete</th>
                            <th className="px-4 py-3 text-left font-semibold">Reason</th>
                            <th className="px-4 py-3 text-left font-semibold">Deferred until</th>
                            <th className="px-4 py-3 text-left font-semibold">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {opsDeferred.items.slice(0, 50).map((it) => (
                            <tr key={it.athlete_id} className="border-t border-slate-700/50">
                              <td className="px-4 py-3">
                                <div className="font-medium">{it.display_name || '—'}</div>
                                <div className="text-xs text-slate-400">{it.email || it.athlete_id}</div>
                              </td>
                              <td className="px-4 py-3">{it.deferred_reason || '—'}</td>
                              <td className="px-4 py-3 text-slate-400">{it.deferred_until || '—'}</td>
                              <td className="px-4 py-3">
                                <button
                                  onClick={() => setSelectedUserId(it.athlete_id)}
                                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs"
                                >
                                  View
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                ) : (
                  <ErrorMessage error={new Error('Failed to load deferred ingestion list')} />
                )}
              </div>

              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <h3 className="text-lg font-semibold">Stuck ingestion</h3>
                    <p className="text-slate-400 text-sm">Heuristic: running longer than 30 minutes.</p>
                  </div>
                  <div className="w-full max-w-sm">
                    <div className="text-xs font-semibold text-slate-300 mb-1">Operator reason (for audit)</div>
                    <input
                      value={adminReason}
                      onChange={(e) => setAdminReason(e.target.value)}
                      placeholder="e.g., stuck ingestion"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white text-sm"
                    />
                  </div>
                </div>

                {opsStuckLoading ? (
                  <LoadingSpinner />
                ) : opsStuck ? (
                  opsStuck.items.length === 0 ? (
                    <div className="text-sm text-slate-400">No stuck athletes detected.</div>
                  ) : (
                    <div className="overflow-x-auto rounded-lg border border-slate-700/50">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-900">
                          <tr>
                            <th className="px-4 py-3 text-left font-semibold">Athlete</th>
                            <th className="px-4 py-3 text-left font-semibold">Kind</th>
                            <th className="px-4 py-3 text-left font-semibold">Started</th>
                            <th className="px-4 py-3 text-left font-semibold">Last error</th>
                            <th className="px-4 py-3 text-left font-semibold">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {opsStuck.items.map((it) => (
                            <tr key={it.athlete_id} className="border-t border-slate-700/50">
                              <td className="px-4 py-3">
                                <div className="font-medium">{it.display_name || '—'}</div>
                                <div className="text-xs text-slate-400">{it.email || it.athlete_id}</div>
                              </td>
                              <td className="px-4 py-3">{it.kind || '—'}</td>
                              <td className="px-4 py-3 text-slate-400">{it.started_at || '—'}</td>
                              <td className="px-4 py-3 text-red-300">
                                {it.last_index_error || it.last_best_efforts_error || '—'}
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={() => setSelectedUserId(it.athlete_id)}
                                    className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs"
                                  >
                                    View
                                  </button>
                                  <button
                                    onClick={() =>
                                      retryIngestion.mutate({
                                        userId: it.athlete_id,
                                        pages: 5,
                                        reason: adminReason || 'stuck ingestion',
                                      })
                                    }
                                    disabled={retryIngestion.isPending}
                                    className="px-3 py-1 bg-orange-700 hover:bg-orange-600 disabled:bg-slate-700 rounded text-xs"
                                  >
                                    Retry ingestion
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                ) : (
                  <ErrorMessage error={new Error('Failed to load stuck ingestion list')} />
                )}
              </div>

              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-2">Recent ingestion errors (7d)</h3>
                {opsErrorsLoading ? (
                  <LoadingSpinner />
                ) : opsErrors ? (
                  opsErrors.items.length === 0 ? (
                    <div className="text-sm text-slate-400">No recent ingestion errors.</div>
                  ) : (
                    <div className="space-y-2">
                      {opsErrors.items.slice(0, 20).map((it) => (
                        <div key={`${it.athlete_id}-${it.updated_at}`} className="bg-slate-900/40 border border-slate-700/50 rounded p-3">
                          <div className="text-sm font-medium">{it.display_name || it.email || it.athlete_id}</div>
                          <div className="text-xs text-slate-400">{it.updated_at || '—'}</div>
                          {it.last_index_error ? <div className="text-xs text-red-300 mt-1">Index: {it.last_index_error}</div> : null}
                          {it.last_best_efforts_error ? <div className="text-xs text-red-300 mt-1">Best efforts: {it.last_best_efforts_error}</div> : null}
                        </div>
                      ))}
                    </div>
                  )
                ) : (
                  <ErrorMessage error={new Error('Failed to load ingestion errors')} />
                )}
              </div>
            </div>
          )}

          {/* Health Tab */}
          {selectedTab === 'health' && (
            <div>
              {healthLoading ? (
                <LoadingSpinner />
              ) : health ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                    <h3 className="text-lg font-semibold mb-4">Database</h3>
                    <div className={`text-2xl font-bold ${
                      health.database === 'healthy' ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {health.database === 'healthy' ? '✓ Healthy' : '✗ Unhealthy'}
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                    <h3 className="text-lg font-semibold mb-4">Users</h3>
                    <div className="space-y-2">
                      <div>
                        <span className="text-sm text-slate-400">Total:</span>
                        <span className="ml-2 text-lg font-semibold">{health.users.total}</span>
                      </div>
                      <div>
                        <span className="text-sm text-slate-400">Active (30d):</span>
                        <span className="ml-2 text-lg font-semibold">{health.users.active_30d}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                    <h3 className="text-lg font-semibold mb-4">Activities</h3>
                    <div className="space-y-2">
                      <div>
                        <span className="text-sm text-slate-400">Total:</span>
                        <span className="ml-2 text-lg font-semibold">{health.activities.total}</span>
                      </div>
                      <div>
                        <span className="text-sm text-slate-400">Last 7 days:</span>
                        <span className="ml-2 text-lg font-semibold">{health.activities.last_7d}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                    <h3 className="text-lg font-semibold mb-4">Data Collection</h3>
                    <div className="space-y-2 text-sm">
                      <div>
                        <span className="text-slate-400">Nutrition:</span>
                        <span className="ml-2">{health.data_collection.nutrition_entries}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Work Patterns:</span>
                        <span className="ml-2">{health.data_collection.work_patterns}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Body Composition:</span>
                        <span className="ml-2">{health.data_collection.body_composition}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <ErrorMessage error={new Error('Failed to load health data')} />
              )}
            </div>
          )}

          {/* Metrics Tab */}
          {selectedTab === 'metrics' && (
            <div>
              {metricsLoading ? (
                <LoadingSpinner />
              ) : metrics ? (
                <div className="space-y-6">
                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                    <h3 className="text-lg font-semibold mb-4">User Growth</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-slate-400">New Users ({metrics.period_days}d):</span>
                        <p className="text-2xl font-bold">{metrics.user_growth.new_users}</p>
                      </div>
                      <div>
                        <span className="text-sm text-slate-400">Growth Rate:</span>
                        <p className="text-2xl font-bold">{metrics.user_growth.growth_rate}%</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                    <h3 className="text-lg font-semibold mb-4">Engagement</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <span className="text-sm text-slate-400">Users with Activities:</span>
                        <p className="text-xl font-semibold">{metrics.engagement.users_with_activities}</p>
                      </div>
                      <div>
                        <span className="text-sm text-slate-400">Users with Nutrition:</span>
                        <p className="text-xl font-semibold">{metrics.engagement.users_with_nutrition}</p>
                      </div>
                      <div>
                        <span className="text-sm text-slate-400">Avg Activities/User:</span>
                        <p className="text-xl font-semibold">{metrics.engagement.avg_activities_per_user}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <ErrorMessage error={new Error('Failed to load metrics')} />
              )}
            </div>
          )}

          {/* Feature Flags Tab */}
          {selectedTab === 'flags' && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-2">3D Quality-Session Selection</h3>
                <p className="text-slate-400 text-sm mb-4">
                  Admin-friendly control for the new quality workout selector.
                  You can run it in shadow (logs only) or turn it on for a rollout/allowlist.
                </p>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                    <div className="text-sm font-medium mb-2">Mode</div>
                    <div className="space-y-2 text-sm">
                      <label className="flex items-center gap-2">
                        <input type="radio" name="mode" checked={desired3dMode === 'off'} onChange={() => setDesired3dMode('off')} />
                        Off
                      </label>
                      <label className="flex items-center gap-2">
                        <input type="radio" name="mode" checked={desired3dMode === 'shadow'} onChange={() => setDesired3dMode('shadow')} />
                        Shadow (log only)
                      </label>
                      <label className="flex items-center gap-2">
                        <input type="radio" name="mode" checked={desired3dMode === 'on'} onChange={() => setDesired3dMode('on')} />
                        On (serve new selection)
                      </label>
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                    <div className="text-sm font-medium mb-2">Rollout %</div>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={desiredRollout}
                      onChange={(e) => setDesiredRollout(Math.max(0, Math.min(100, parseInt(e.target.value || '0', 10))))}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700/50 rounded text-white"
                    />
                    <p className="text-xs text-slate-500 mt-2">
                      Tip: set to 0 and use allowlist for targeted rollout.
                    </p>
                  </div>

                  <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-4">
                    <div className="text-sm font-medium mb-2">Allowlist emails (optional)</div>
                    <textarea
                      value={allowlistEmails}
                      onChange={(e) => setAllowlistEmails(e.target.value)}
                      rows={4}
                      placeholder="one email per line"
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700/50 rounded text-white text-sm"
                    />
                    <p className="text-xs text-slate-500 mt-2">
                      These users will get access even if rollout % is 0.
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-3">
                  <button
                    onClick={() =>
                      set3dMode.mutate({
                        mode: desired3dMode,
                        rollout_percentage: desiredRollout,
                        allowlist_emails: allowlistEmails
                          .split('\n')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                    disabled={set3dMode.isPending}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded font-medium"
                  >
                    {set3dMode.isPending ? 'Saving...' : 'Save'}
                  </button>
                  {set3dMode.isSuccess && (
                    <div className="text-sm text-green-400">✓ Updated</div>
                  )}
                  {set3dMode.isError && (
                    <div className="text-sm text-red-400">Failed to update</div>
                  )}
                </div>
              </div>

              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-2">Plan-related flags (read-only)</h3>
                <p className="text-slate-400 text-sm mb-4">A quick view of `plan.*` flags in the system.</p>
                {flagsLoading ? (
                  <LoadingSpinner />
                ) : flagsData?.flags ? (
                  <div className="overflow-hidden rounded-lg border border-slate-700/50">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-900">
                        <tr>
                          <th className="px-4 py-3 text-left font-semibold">Key</th>
                          <th className="px-4 py-3 text-left font-semibold">Enabled</th>
                          <th className="px-4 py-3 text-left font-semibold">Rollout</th>
                          <th className="px-4 py-3 text-left font-semibold">Allowlist</th>
                        </tr>
                      </thead>
                      <tbody>
                        {flagsData.flags.slice(0, 50).map((f) => (
                          <tr key={f.key} className="border-t border-slate-700/50">
                            <td className="px-4 py-3">{f.key}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded text-xs ${f.enabled ? 'bg-green-900/40 text-green-300' : 'bg-slate-700 text-slate-300'}`}>
                                {f.enabled ? 'true' : 'false'}
                              </span>
                            </td>
                            <td className="px-4 py-3">{f.rollout_percentage}%</td>
                            <td className="px-4 py-3 text-slate-400">{f.allowed_athlete_ids?.length || 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <ErrorMessage error={new Error('Failed to load feature flags')} />
                )}
              </div>
            </div>
          )}

          {/* Query Engine Tab */}
          {selectedTab === 'query' && (
            <div className="space-y-6">
              {/* Template Queries */}
              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-4">📊 Template Queries</h3>
                <p className="text-slate-400 mb-4 text-sm">
                  Pre-built queries for common data mining tasks.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                  {templates?.templates.map((t) => (
                    <button
                      key={t.name}
                      onClick={() => setSelectedTemplate(t.name)}
                      className={`p-4 rounded-lg border text-left transition-all ${
                        selectedTemplate === t.name
                          ? 'bg-orange-900/30 border-orange-600'
                          : 'bg-slate-900 border-slate-700/50 hover:border-slate-500'
                      }`}
                    >
                      <div className="font-medium text-sm">{t.name.replace(/_/g, ' ')}</div>
                      <div className="text-xs text-slate-400 mt-1">{t.description}</div>
                      <div className="text-xs text-slate-500 mt-2">
                        Params: {t.params.join(', ')}
                      </div>
                    </button>
                  ))}
                </div>
                
                {/* Query Parameters */}
                {selectedTemplate && (
                  <div className="border-t border-slate-700/50 pt-4 mt-4">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Days</label>
                        <input
                          type="number"
                          value={queryDays}
                          onChange={(e) => setQueryDays(parseInt(e.target.value) || 180)}
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                          min={1}
                          max={730}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Athlete ID (optional)</label>
                        <input
                          type="text"
                          value={queryAthleteId}
                          onChange={(e) => setQueryAthleteId(e.target.value)}
                          placeholder="Leave empty for all"
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Workout Type (optional)</label>
                        <input
                          type="text"
                          value={queryWorkoutType}
                          onChange={(e) => setQueryWorkoutType(e.target.value)}
                          placeholder="e.g., tempo_run"
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                        />
                      </div>
                      <div className="flex items-end">
                        <button
                          onClick={handleExecuteTemplate}
                          disabled={executeTemplate.isPending}
                          className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-700 rounded font-medium"
                        >
                          {executeTemplate.isPending ? 'Running...' : 'Execute Query'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Custom Query Builder */}
              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-4">⚡ Custom Query Builder</h3>
                <p className="text-slate-400 mb-4 text-sm">
                  Build custom queries with full flexibility. Power user interface.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Entity</label>
                    <select
                      value={customEntity}
                      onChange={(e) => setCustomEntity(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                    >
                      {entities && Object.keys(entities.entities).map(entity => (
                        <option key={entity} value={entity}>{entity}</option>
                      ))}
                    </select>
                    {entities?.entities[customEntity] && (
                      <p className="text-xs text-slate-500 mt-1">
                        Fields: {entities.entities[customEntity].fields.slice(0, 5).join(', ')}...
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Group By</label>
                    <input
                      type="text"
                      value={customGroupBy}
                      onChange={(e) => setCustomGroupBy(e.target.value)}
                      placeholder="e.g., workout_type"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Aggregations</label>
                    <input
                      type="text"
                      value={customAggregations}
                      onChange={(e) => setCustomAggregations(e.target.value)}
                      placeholder="e.g., efficiency:avg,distance_m:sum"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                    />
                  </div>
                </div>
                
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1">Filters (JSON)</label>
                  <input
                    type="text"
                    value={customFilters}
                    onChange={(e) => setCustomFilters(e.target.value)}
                    placeholder='[{"field": "workout_type", "operator": "eq", "value": "tempo_run"}]'
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white font-mono text-sm"
                  />
                </div>
                
                <button
                  onClick={handleExecuteCustom}
                  disabled={executeCustom.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded font-medium"
                >
                  {executeCustom.isPending ? 'Running...' : 'Execute Custom Query'}
                </button>
              </div>

              {/* Query Results */}
              {queryResults && (
                <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold">
                      📋 Results 
                      {queryResults.success ? (
                        <span className="text-green-400 text-sm ml-2">✓</span>
                      ) : (
                        <span className="text-red-400 text-sm ml-2">✗</span>
                      )}
                    </h3>
                    <div className="text-sm text-slate-400">
                      {queryResults.total_count} records • {queryResults.execution_time_ms}ms
                    </div>
                  </div>
                  
                  {queryResults.error && (
                    <div className="bg-red-900/30 border border-red-700 rounded p-3 mb-4 text-red-400 text-sm">
                      {queryResults.error}
                    </div>
                  )}
                  
                  {queryResults.data && queryResults.data.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-900">
                          <tr>
                            {Object.keys(queryResults.data[0]).map(key => (
                              <th key={key} className="px-3 py-2 text-left font-medium text-slate-400">
                                {key}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {queryResults.data.slice(0, 50).map((row: any, idx: number) => (
                            <tr key={idx} className="border-t border-slate-700/50">
                              {Object.values(row).map((value: any, vIdx: number) => (
                                <td key={vIdx} className="px-3 py-2">
                                  {typeof value === 'number' 
                                    ? value.toLocaleString(undefined, { maximumFractionDigits: 4 })
                                    : String(value ?? '-')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {queryResults.data.length > 50 && (
                        <p className="text-center text-slate-400 text-sm mt-2">
                          Showing 50 of {queryResults.data.length} results
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-slate-400 text-center py-4">No results</p>
                  )}
                  
                  {/* Raw JSON toggle */}
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-300">
                      View Raw JSON
                    </summary>
                    <pre className="mt-2 p-3 bg-slate-900 rounded text-xs overflow-x-auto max-h-64">
                      {JSON.stringify(queryResults, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          )}

          {/* Testing Tab */}
          {selectedTab === 'testing' && (
            <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Testing Tools</h3>
              <p className="text-slate-400 mb-4">
                Correlation testing and cross-athlete queries available via API.
                Use API endpoints directly or the Query Engine tab.
              </p>
              <div className="space-y-2 text-sm text-slate-400">
                <p>• POST /v1/admin/correlations/test?athlete_id={'{id}'}&days=90</p>
                <p>• POST /v1/admin/query/execute?template=efficiency_by_workout_type</p>
                <p>• POST /v1/admin/query/custom?entity=activity&group_by=workout_type</p>
              </div>
            </div>
          )}

          {/* Invites Tab */}
          {selectedTab === 'invites' && (
            <div className="space-y-6">
              {/* Create Invite Form */}
              <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold mb-4">Create Invite</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <input
                    type="email"
                    value={newInviteEmail}
                    onChange={(e) => setNewInviteEmail(e.target.value)}
                    placeholder="Email address"
                    className="px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                  />
                  <input
                    type="text"
                    value={newInviteNote}
                    onChange={(e) => setNewInviteNote(e.target.value)}
                    placeholder="Note (e.g., Beta tester - Brian)"
                    className="px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                  />
                  <select
                    value={newInviteGrantTier}
                    onChange={(e) => setNewInviteGrantTier(e.target.value as 'free' | 'pro' | '')}
                    className="px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                  >
                    <option value="">Standard (free tier)</option>
                    <option value="pro">Grant Pro Access</option>
                  </select>
                  <button
                    onClick={async () => {
                      if (!newInviteEmail) return;
                      // Basic email validation
                      if (!newInviteEmail.includes('@') || !newInviteEmail.includes('.')) {
                        setInviteError('Please enter a valid email address');
                        return;
                      }
                      setInviteError(null);
                      setInviteSuccess(null);
                      try {
                        await createInvite.mutateAsync({
                          email: newInviteEmail.trim().toLowerCase(),
                          note: newInviteNote.trim() || null,
                          grant_tier: newInviteGrantTier || null,
                        });
                        setInviteSuccess(`Invite created for ${newInviteEmail}`);
                        setNewInviteEmail('');
                        setNewInviteNote('');
                        setNewInviteGrantTier('');
                        // Clear success message after 5 seconds
                        setTimeout(() => setInviteSuccess(null), 5000);
                      } catch (err: any) {
                        setInviteError(err?.message || 'Failed to create invite');
                      }
                    }}
                    disabled={!newInviteEmail || createInvite.isPending}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded text-white font-medium"
                  >
                    {createInvite.isPending ? 'Creating...' : 'Create Invite'}
                  </button>
                </div>
                {inviteSuccess && (
                  <p className="mt-2 text-green-400 text-sm">{inviteSuccess}</p>
                )}
                {inviteError && (
                  <p className="mt-2 text-red-400 text-sm">{inviteError}</p>
                )}
              </div>

              {/* Filter Tabs */}
              <div className="flex gap-2">
                <button
                  onClick={() => setInviteFilter('all')}
                  className={`px-3 py-1 rounded text-sm font-medium ${
                    inviteFilter === 'all' ? 'bg-slate-600 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setInviteFilter('pending')}
                  className={`px-3 py-1 rounded text-sm font-medium ${
                    inviteFilter === 'pending' ? 'bg-green-600 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  Pending
                </button>
                <button
                  onClick={() => setInviteFilter('used')}
                  className={`px-3 py-1 rounded text-sm font-medium ${
                    inviteFilter === 'used' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  Used
                </button>
              </div>

              {/* Invites List */}
              <div className="bg-slate-800 rounded-lg border border-slate-700/50 overflow-hidden">
                {invitesLoading ? (
                  <div className="p-6"><LoadingSpinner /></div>
                ) : invitesError ? (
                  <div className="p-6">
                    <ErrorMessage message="Failed to load invites" />
                  </div>
                ) : !invitesData?.invites?.length ? (
                  <div className="p-6 text-center text-slate-400">
                    <p>No invites yet. Create one above to get started.</p>
                  </div>
                ) : (
                  <table className="w-full">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Email</th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Note</th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Grant Tier</th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Status</th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Invited</th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/50">
                      {invitesData.invites
                        .filter((inv) => {
                          if (inviteFilter === 'pending') return inv.is_active && !inv.used_at;
                          if (inviteFilter === 'used') return !!inv.used_at;
                          return true;
                        })
                        .map((inv) => (
                          <tr key={inv.id} className="hover:bg-slate-700/30">
                            <td className="px-4 py-3 text-sm text-slate-200">{inv.email}</td>
                            <td className="px-4 py-3 text-sm text-slate-400">{inv.note || '-'}</td>
                            <td className="px-4 py-3">
                              {inv.grant_tier === 'pro' ? (
                                <span className="px-2 py-1 text-xs font-medium bg-purple-600/20 text-purple-400 rounded">
                                  PRO
                                </span>
                              ) : (
                                <span className="text-sm text-slate-500">-</span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {inv.used_at ? (
                                <span className="px-2 py-1 text-xs font-medium bg-blue-600/20 text-blue-400 rounded">
                                  Used
                                </span>
                              ) : inv.revoked_at ? (
                                <span className="px-2 py-1 text-xs font-medium bg-red-600/20 text-red-400 rounded">
                                  Revoked
                                </span>
                              ) : inv.is_active ? (
                                <span className="px-2 py-1 text-xs font-medium bg-green-600/20 text-green-400 rounded">
                                  Pending
                                </span>
                              ) : (
                                <span className="px-2 py-1 text-xs font-medium bg-slate-600/20 text-slate-400 rounded">
                                  Inactive
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-400">
                              {inv.invited_at ? new Date(inv.invited_at).toLocaleDateString() : '-'}
                            </td>
                            <td className="px-4 py-3">
                              {inv.is_active && !inv.used_at && (
                                <button
                                  onClick={() => revokeInvite.mutate({ email: inv.email })}
                                  disabled={revokeInvite.isPending}
                                  className="px-2 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded text-white"
                                >
                                  Revoke
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}


