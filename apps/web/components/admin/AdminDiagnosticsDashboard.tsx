'use client';

import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useDiagnosticsSummary } from '@/lib/hooks/queries/diagnostics';
import { useAuth } from '@/lib/hooks/useAuth';
import type { RecommendedAction } from '@/lib/api/services/diagnostics';

function StatusBadge({ status }: { status: 'ready' | 'degraded' | 'blocked' }) {
  const cls =
    status === 'ready'
      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
      : status === 'degraded'
        ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
        : 'bg-red-500/20 text-red-400 border-red-500/30';
  return <Badge className={`${cls} border`}>{status.toUpperCase()}</Badge>;
}

function ActionButton({ action }: { action: RecommendedAction }) {
  const cls =
    action.severity === 'critical'
      ? 'bg-red-600 hover:bg-red-700 text-white'
      : action.severity === 'recommended'
        ? 'bg-orange-600 hover:bg-orange-700 text-white'
        : 'bg-slate-700 hover:bg-slate-600 text-white';
  return (
    <Link
      href={action.href}
      className={`inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${cls}`}
    >
      {action.title}
    </Link>
  );
}

export function AdminDiagnosticsDashboard() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'owner';
  const { data, isLoading, error, refetch, isFetching } = useDiagnosticsSummary({
    enabled: Boolean(isAdmin),
  });

  if (!isAdmin) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center">
          <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
            <p className="text-red-400">Access denied.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center">
          <div className="text-center">
            <LoadingSpinner size="lg" />
            <p className="text-slate-400 mt-4">Loading data health…</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
          <Card className="bg-slate-800 border-slate-700 max-w-md">
            <CardContent className="pt-6">
              <div className="text-center">
                <h2 className="text-xl font-semibold text-white mb-2">Unable to Load Data Health</h2>
                <p className="text-slate-400 mb-4">
                  {(error as Error)?.message || 'An error occurred while fetching diagnostics.'}
                </p>
                <Button onClick={() => refetch()} className="bg-orange-600 hover:bg-orange-700" disabled={isFetching}>
                  Retry
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </ProtectedRoute>
    );
  }

  const topActions = (data.actions || []).slice(0, 3);
  const moreActions = (data.actions || []).slice(3);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-slate-100 py-6 md:py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold">Admin · Data Health</h1>
              <p className="text-slate-400 text-sm mt-1">Operator view: ingestion, completeness, readiness</p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={data.overall_status} />
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="border-slate-600 text-slate-300 hover:bg-slate-800"
              >
                Refresh
              </Button>
            </div>
          </div>

          <Card className="bg-slate-800/50 border-slate-700 mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">What to do next</CardTitle>
              <CardDescription>Highest leverage fixes first</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {topActions.map((a) => (
                  <ActionButton key={a.id} action={a} />
                ))}
                <Link
                  href="/diagnostic/report"
                  className="inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-slate-700 hover:bg-slate-600 text-white"
                >
                  View legacy report
                </Link>
              </div>
              {moreActions.length > 0 && (
                <div className="mt-4 space-y-2">
                  {moreActions.map((a) => (
                    <div key={a.id} className="text-sm text-slate-300">
                      <span className="text-slate-500 mr-2">•</span>
                      <span className="font-medium">{a.title}:</span> <span className="text-slate-400">{a.detail}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-slate-800/50 border-slate-700 mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Provider health</CardTitle>
              <CardDescription>Connection and last sync</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(data.provider_health || []).map((p) => (
                <div key={p.provider} className="rounded-lg border border-slate-700/50 bg-slate-900/30 p-4">
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-white capitalize">{p.provider}</div>
                    <Badge
                      className={`${
                        p.connected
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : 'bg-red-500/20 text-red-400 border-red-500/30'
                      } border`}
                    >
                      {p.connected ? 'Connected' : 'Disconnected'}
                    </Badge>
                  </div>
                  <div className="text-xs text-slate-500 mt-2">
                    Last sync: {p.last_sync_at ? new Date(p.last_sync_at).toLocaleString() : '—'}
                  </div>
                  {p.detail ? <div className="text-xs text-slate-400 mt-1">{p.detail}</div> : null}
                </div>
              ))}
            </CardContent>
          </Card>

          {data.ingestion && (
            <Card className="bg-slate-800/50 border-slate-700 mb-6">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Ingestion status</CardTitle>
                <CardDescription>Best-efforts extraction coverage (no external calls)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="text-sm text-slate-300">
                    {data.ingestion.coverage_pct.toFixed(1)}% covered • {data.ingestion.remaining_activities} remaining
                  </div>
                  <div className="text-xs text-slate-500">Last task: {data.ingestion.last_task_status || '—'}</div>
                </div>
                {data.ingestion.last_task_error ? (
                  <div className="mt-2 text-xs text-red-400">Last error: {data.ingestion.last_task_error}</div>
                ) : null}
              </CardContent>
            </Card>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Data completeness</CardTitle>
                <CardDescription>Inputs that power accuracy</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Activities</div>
                  <div className="text-white font-semibold">{data.completeness.activities_total}</div>
                </div>
                <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs text-slate-500">With HR</div>
                  <div className="text-white font-semibold">{data.completeness.activities_with_hr}</div>
                </div>
                <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs text-slate-500">With splits</div>
                  <div className="text-white font-semibold">{data.completeness.activities_with_splits}</div>
                </div>
                <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Splits with GAP</div>
                  <div className="text-white font-semibold">{data.completeness.splits_with_gap}</div>
                </div>
                <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Check-ins</div>
                  <div className="text-white font-semibold">{data.completeness.checkins_total}</div>
                </div>
                <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs text-slate-500">PBs</div>
                  <div className="text-white font-semibold">{data.completeness.personal_bests}</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Model readiness</CardTitle>
                <CardDescription>What we can responsibly show</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {[
                  ['Efficiency trend', data.model_readiness.efficiency_trend_ready],
                  ['Load → Response', data.model_readiness.load_response_ready],
                  ['Trend attribution', data.model_readiness.trend_attribution_ready],
                  ['Personal best profile', data.model_readiness.personal_bests_ready],
                ].map(([label, ok]) => (
                  <div key={label as string} className="flex items-center justify-between">
                    <span className="text-slate-300">{label as string}</span>
                    <Badge
                      className={`${
                        ok
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                      } border`}
                    >
                      {ok ? 'Ready' : 'Limited'}
                    </Badge>
                  </div>
                ))}
                {data.model_readiness.notes?.length ? (
                  <div className="mt-3 text-xs text-slate-500 space-y-1">
                    {data.model_readiness.notes.map((n, i) => (
                      <div key={i}>• {n}</div>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}

