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

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { useAdminUsers, useSystemHealth, useSiteMetrics, useImpersonateUser } from '@/lib/hooks/queries/admin';
import { useQueryTemplates, useQueryEntities, useExecuteTemplate, useExecuteCustomQuery } from '@/lib/hooks/queries/query-engine';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

export default function AdminPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [selectedTab, setSelectedTab] = useState<'users' | 'health' | 'metrics' | 'query' | 'testing'>('users');
  
  // User management
  const { data: users, isLoading: usersLoading } = useAdminUsers({ search, limit: 50 });
  const { data: health, isLoading: healthLoading } = useSystemHealth();
  const { data: metrics, isLoading: metricsLoading } = useSiteMetrics(30);
  const impersonateUser = useImpersonateUser();
  
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

  // Check if user is admin/owner
  if (user && user.role !== 'admin' && user.role !== 'owner') {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <p className="text-red-400">Access denied. Admin access required.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Admin Dashboard</h1>
            <p className="text-gray-400">Command center for site management and monitoring</p>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mb-6 border-b border-gray-700">
            <button
              onClick={() => setSelectedTab('users')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'users'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Users
            </button>
            <button
              onClick={() => setSelectedTab('health')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'health'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              System Health
            </button>
            <button
              onClick={() => setSelectedTab('metrics')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'metrics'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Site Metrics
            </button>
            <button
              onClick={() => setSelectedTab('query')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'query'
                  ? 'border-b-2 border-orange-600 text-orange-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              🔍 Query Engine
            </button>
            <button
              onClick={() => setSelectedTab('testing')}
              className={`px-4 py-2 font-medium ${
                selectedTab === 'testing'
                  ? 'border-b-2 border-blue-600 text-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Testing
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
                  className="w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white"
                />
              </div>

              {usersLoading ? (
                <LoadingSpinner />
              ) : users ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-gray-900">
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
                        <tr key={user.id} className="border-t border-gray-700">
                          <td className="px-4 py-3 text-sm">{user.email || '--'}</td>
                          <td className="px-4 py-3 text-sm">{user.display_name || '--'}</td>
                          <td className="px-4 py-3 text-sm">
                            <span className={`px-2 py-1 rounded text-xs ${
                              user.role === 'admin' || user.role === 'owner'
                                ? 'bg-blue-900/50 text-blue-400'
                                : 'bg-gray-700 text-gray-300'
                            }`}>
                              {user.role}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm">{user.subscription_tier}</td>
                          <td className="px-4 py-3 text-sm text-gray-400">
                            {new Date(user.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <button
                              onClick={() => impersonateUser.mutate(user.id)}
                              disabled={impersonateUser.isPending}
                              className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded text-xs"
                            >
                              {impersonateUser.isPending ? <LoadingSpinner size="sm" /> : 'Impersonate'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="px-4 py-3 bg-gray-900 border-t border-gray-700 text-sm text-gray-400">
                    Showing {users.users.length} of {users.total} users
                  </div>
                </div>
              ) : (
                <ErrorMessage error={new Error('Failed to load users')} />
              )}
            </div>
          )}

          {/* Health Tab */}
          {selectedTab === 'health' && (
            <div>
              {healthLoading ? (
                <LoadingSpinner />
              ) : health ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <h3 className="text-lg font-semibold mb-4">Database</h3>
                    <div className={`text-2xl font-bold ${
                      health.database === 'healthy' ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {health.database === 'healthy' ? '✓ Healthy' : '✗ Unhealthy'}
                    </div>
                  </div>

                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <h3 className="text-lg font-semibold mb-4">Users</h3>
                    <div className="space-y-2">
                      <div>
                        <span className="text-sm text-gray-400">Total:</span>
                        <span className="ml-2 text-lg font-semibold">{health.users.total}</span>
                      </div>
                      <div>
                        <span className="text-sm text-gray-400">Active (30d):</span>
                        <span className="ml-2 text-lg font-semibold">{health.users.active_30d}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <h3 className="text-lg font-semibold mb-4">Activities</h3>
                    <div className="space-y-2">
                      <div>
                        <span className="text-sm text-gray-400">Total:</span>
                        <span className="ml-2 text-lg font-semibold">{health.activities.total}</span>
                      </div>
                      <div>
                        <span className="text-sm text-gray-400">Last 7 days:</span>
                        <span className="ml-2 text-lg font-semibold">{health.activities.last_7d}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <h3 className="text-lg font-semibold mb-4">Data Collection</h3>
                    <div className="space-y-2 text-sm">
                      <div>
                        <span className="text-gray-400">Nutrition:</span>
                        <span className="ml-2">{health.data_collection.nutrition_entries}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Work Patterns:</span>
                        <span className="ml-2">{health.data_collection.work_patterns}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Body Composition:</span>
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
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <h3 className="text-lg font-semibold mb-4">User Growth</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-gray-400">New Users ({metrics.period_days}d):</span>
                        <p className="text-2xl font-bold">{metrics.user_growth.new_users}</p>
                      </div>
                      <div>
                        <span className="text-sm text-gray-400">Growth Rate:</span>
                        <p className="text-2xl font-bold">{metrics.user_growth.growth_rate}%</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <h3 className="text-lg font-semibold mb-4">Engagement</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <span className="text-sm text-gray-400">Users with Activities:</span>
                        <p className="text-xl font-semibold">{metrics.engagement.users_with_activities}</p>
                      </div>
                      <div>
                        <span className="text-sm text-gray-400">Users with Nutrition:</span>
                        <p className="text-xl font-semibold">{metrics.engagement.users_with_nutrition}</p>
                      </div>
                      <div>
                        <span className="text-sm text-gray-400">Avg Activities/User:</span>
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

          {/* Query Engine Tab */}
          {selectedTab === 'query' && (
            <div className="space-y-6">
              {/* Template Queries */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <h3 className="text-lg font-semibold mb-4">📊 Template Queries</h3>
                <p className="text-gray-400 mb-4 text-sm">
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
                          : 'bg-gray-900 border-gray-700 hover:border-gray-500'
                      }`}
                    >
                      <div className="font-medium text-sm">{t.name.replace(/_/g, ' ')}</div>
                      <div className="text-xs text-gray-400 mt-1">{t.description}</div>
                      <div className="text-xs text-gray-500 mt-2">
                        Params: {t.params.join(', ')}
                      </div>
                    </button>
                  ))}
                </div>
                
                {/* Query Parameters */}
                {selectedTemplate && (
                  <div className="border-t border-gray-700 pt-4 mt-4">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Days</label>
                        <input
                          type="number"
                          value={queryDays}
                          onChange={(e) => setQueryDays(parseInt(e.target.value) || 180)}
                          className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
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
                          className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Workout Type (optional)</label>
                        <input
                          type="text"
                          value={queryWorkoutType}
                          onChange={(e) => setQueryWorkoutType(e.target.value)}
                          placeholder="e.g., tempo_run"
                          className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                        />
                      </div>
                      <div className="flex items-end">
                        <button
                          onClick={handleExecuteTemplate}
                          disabled={executeTemplate.isPending}
                          className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 rounded font-medium"
                        >
                          {executeTemplate.isPending ? 'Running...' : 'Execute Query'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Custom Query Builder */}
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <h3 className="text-lg font-semibold mb-4">⚡ Custom Query Builder</h3>
                <p className="text-gray-400 mb-4 text-sm">
                  Build custom queries with full flexibility. Power user interface.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Entity</label>
                    <select
                      value={customEntity}
                      onChange={(e) => setCustomEntity(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                    >
                      {entities && Object.keys(entities.entities).map(entity => (
                        <option key={entity} value={entity}>{entity}</option>
                      ))}
                    </select>
                    {entities?.entities[customEntity] && (
                      <p className="text-xs text-gray-500 mt-1">
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
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Aggregations</label>
                    <input
                      type="text"
                      value={customAggregations}
                      onChange={(e) => setCustomAggregations(e.target.value)}
                      placeholder="e.g., efficiency:avg,distance_m:sum"
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
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
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white font-mono text-sm"
                  />
                </div>
                
                <button
                  onClick={handleExecuteCustom}
                  disabled={executeCustom.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded font-medium"
                >
                  {executeCustom.isPending ? 'Running...' : 'Execute Custom Query'}
                </button>
              </div>

              {/* Query Results */}
              {queryResults && (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold">
                      📋 Results 
                      {queryResults.success ? (
                        <span className="text-green-400 text-sm ml-2">✓</span>
                      ) : (
                        <span className="text-red-400 text-sm ml-2">✗</span>
                      )}
                    </h3>
                    <div className="text-sm text-gray-400">
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
                        <thead className="bg-gray-900">
                          <tr>
                            {Object.keys(queryResults.data[0]).map(key => (
                              <th key={key} className="px-3 py-2 text-left font-medium text-gray-400">
                                {key}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {queryResults.data.slice(0, 50).map((row: any, idx: number) => (
                            <tr key={idx} className="border-t border-gray-700">
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
                        <p className="text-center text-gray-400 text-sm mt-2">
                          Showing 50 of {queryResults.data.length} results
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-gray-400 text-center py-4">No results</p>
                  )}
                  
                  {/* Raw JSON toggle */}
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-300">
                      View Raw JSON
                    </summary>
                    <pre className="mt-2 p-3 bg-gray-900 rounded text-xs overflow-x-auto max-h-64">
                      {JSON.stringify(queryResults, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          )}

          {/* Testing Tab */}
          {selectedTab === 'testing' && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-semibold mb-4">Testing Tools</h3>
              <p className="text-gray-400 mb-4">
                Correlation testing and cross-athlete queries available via API.
                Use API endpoints directly or the Query Engine tab.
              </p>
              <div className="space-y-2 text-sm text-gray-400">
                <p>• POST /v1/admin/correlations/test?athlete_id={'{id}'}&days=90</p>
                <p>• POST /v1/admin/query/execute?template=efficiency_by_workout_type</p>
                <p>• POST /v1/admin/query/custom?entity=activity&group_by=workout_type</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}


