'use client';

// NOTE: This file intentionally preserves the existing long-form diagnostic report UI.
// The route `/diagnostic` is being repurposed into a "trust & readiness" dashboard,
// while the report remains available at `/diagnostic/report`.

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import {
  FileText,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Info,
  Trophy,
  Activity,
  Heart,
  Target,
  ArrowRight,
  Clock,
  Zap,
  AlertCircle,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';

interface KeyFinding {
  type: 'positive' | 'warning' | 'info';
  text: string;
}

interface PersonalBest {
  distance: string;
  distance_meters: number;
  time_seconds: number;
  pace_per_km: string;
  is_race: boolean;
  validated: boolean;
}

interface WeekVolume {
  week: string;
  distance_km: number;
  duration_hrs: number;
  runs: number;
  phase: string;
}

interface RecentRun {
  date: string;
  name: string;
  distance_km: number;
  pace_min_km: number;
  avg_hr: number;
  efficiency: number;
}

interface RaceEntry {
  date: string;
  name: string;
  distance_km: number;
  time_seconds: number;
  pace_per_km: string;
  notes: string;
}

interface Recommendation {
  action: string;
  reason: string;
  effort?: string;
}

interface DiagnosticReport {
  generated_at: string;
  athlete_id: string;
  period_start: string;
  period_end: string;
  executive_summary: {
    total_activities: number;
    total_distance_km: number;
    peak_volume_km: number;
    current_phase: string;
    efficiency_trend_pct: number | null;
    key_findings: KeyFinding[];
    date_range_start: string;
    date_range_end: string;
  };
  personal_bests: PersonalBest[];
  volume_trajectory: {
    weeks: WeekVolume[];
    total_km: number;
    total_runs: number;
    peak_week: string;
    peak_volume_km: number;
    current_vs_peak_pct: number;
  };
  efficiency_analysis: {
    average: number | null;
    trend_pct: number | null;
    interpretation: string;
    recent_runs: RecentRun[];
    runs_with_hr: number;
  };
  race_history: RaceEntry[];
  data_quality: {
    available: Record<string, { count: number; quality: string }>;
    missing: Record<string, { impact: string }>;
    unanswerable_questions: string[];
  };
  recommendations: {
    high_priority: Recommendation[];
    medium_priority: Recommendation[];
    do_not_do: Recommendation[];
  };
}

async function fetchDiagnosticReport(): Promise<DiagnosticReport> {
  return apiClient.get('/v1/analytics/diagnostic-report');
}

function formatTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function FindingIcon({ type }: { type: string }) {
  switch (type) {
    case 'positive':
      return <CheckCircle2 className="w-5 h-5 text-green-400" />;
    case 'warning':
      return <AlertTriangle className="w-5 h-5 text-orange-400" />;
    default:
      return <Info className="w-5 h-5 text-blue-400" />;
  }
}

function PhaseLabel({ phase }: { phase: string }) {
  const colors: Record<string, string> = {
    build: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    peak: 'bg-green-500/20 text-green-400 border-green-500/30',
    taper: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    recovery: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    return: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    base: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  };

  return (
    <Badge className={`${colors[phase] || colors.base} border`}>
      {phase.charAt(0).toUpperCase() + phase.slice(1)}
    </Badge>
  );
}

function QualityBadge({ quality }: { quality: string }) {
  const colors: Record<string, string> = {
    excellent: 'bg-green-500/20 text-green-400 border-green-500/30',
    good: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    limited: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    insufficient: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  return (
    <Badge className={`${colors[quality] || colors.limited} border`}>
      {quality.charAt(0).toUpperCase() + quality.slice(1)}
    </Badge>
  );
}

export function DiagnosticReportPage() {
  const { data: report, isLoading, error, refetch, isFetching } = useQuery<DiagnosticReport>({
    queryKey: ['diagnostic-report'],
    queryFn: fetchDiagnosticReport,
    staleTime: 1000 * 60 * 60, // 1 hour
    retry: 1,
  });

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center">
          <div className="text-center">
            <LoadingSpinner size="lg" />
            <p className="text-slate-400 mt-4">Generating your diagnostic report...</p>
            <p className="text-slate-500 text-sm mt-2">This may take a few seconds</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (error) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
          <Card className="bg-slate-800 border-slate-700 max-w-md">
            <CardContent className="pt-6">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-orange-400 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-white mb-2">Unable to Generate Report</h2>
                <p className="text-slate-400 mb-4">
                  {(error as Error).message || 'An error occurred while generating your report.'}
                </p>
                <Button onClick={() => refetch()} className="bg-orange-500 hover:bg-orange-600">
                  Try Again
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </ProtectedRoute>
    );
  }

  if (!report) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 flex items-center justify-center">
          <p className="text-slate-400">No report data available.</p>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-slate-100 py-6 md:py-8">
        <div className="max-w-4xl mx-auto px-4">
          {/* Header */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                  <FileText className="w-6 h-6 text-orange-500" />
                </div>
                <div>
                  <h1 className="text-2xl md:text-3xl font-bold">Diagnostic Report</h1>
                  <p className="text-slate-400 text-sm">
                    Generated {new Date(report.generated_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="border-slate-600 text-slate-300 hover:bg-slate-800"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>

          {/* Executive Summary */}
          <Card className="bg-gradient-to-br from-slate-800 to-slate-800/50 border-slate-700 mb-6 shadow-xl">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Zap className="w-5 h-5 text-orange-400" />
                Executive Summary
              </CardTitle>
              <CardDescription>
                {report.executive_summary.date_range_start} to {report.executive_summary.date_range_end}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-white">{report.executive_summary.total_activities}</div>
                  <div className="text-xs text-slate-400">Activities</div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-white">{report.executive_summary.total_distance_km.toFixed(0)}</div>
                  <div className="text-xs text-slate-400">km (12 weeks)</div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-white">{report.executive_summary.peak_volume_km.toFixed(0)}</div>
                  <div className="text-xs text-slate-400">Peak km/week</div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <PhaseLabel phase={report.executive_summary.current_phase} />
                  <div className="text-xs text-slate-400 mt-1">Current Phase</div>
                </div>
              </div>

              {/* Key Findings */}
              <div className="space-y-2">
                {report.executive_summary.key_findings.map((finding, idx) => (
                  <div
                    key={idx}
                    className={`flex items-start gap-3 p-3 rounded-lg ${
                      finding.type === 'positive'
                        ? 'bg-green-900/20 border border-green-800/30'
                        : finding.type === 'warning'
                          ? 'bg-orange-900/20 border border-orange-800/30'
                          : 'bg-blue-900/20 border border-blue-800/30'
                    }`}
                  >
                    <FindingIcon type={finding.type} />
                    <span className="text-sm text-slate-200">{finding.text}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Personal Bests */}
          {report.personal_bests.length > 0 && (
            <Card className="bg-slate-800 border-slate-700 mb-6">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Trophy className="w-5 h-5 text-yellow-400" />
                  Personal Bests
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left py-2 text-slate-400 font-medium">Distance</th>
                        <th className="text-left py-2 text-slate-400 font-medium">Time</th>
                        <th className="text-left py-2 text-slate-400 font-medium">Pace</th>
                        <th className="text-left py-2 text-slate-400 font-medium">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.personal_bests.map((pb, idx) => (
                        <tr key={idx} className="border-b border-slate-700/50">
                          <td className="py-2 font-medium text-white">{pb.distance}</td>
                          <td className="py-2 text-slate-300">{formatTime(pb.time_seconds)}</td>
                          <td className="py-2 text-slate-300">{pb.pace_per_km}/km</td>
                          <td className="py-2">
                            {pb.is_race ? (
                              <Badge className="bg-green-500/20 text-green-400 border border-green-500/30">Race</Badge>
                            ) : (
                              <Badge className="bg-slate-600/50 text-slate-400 border border-slate-500/30">Training</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Volume Trajectory */}
          <Card className="bg-slate-800 border-slate-700 mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Activity className="w-5 h-5 text-blue-400" />
                Volume Trajectory
              </CardTitle>
              <CardDescription>
                Peak: {report.volume_trajectory.peak_volume_km.toFixed(0)} km in {report.volume_trajectory.peak_week}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-400">Current vs Peak</span>
                  <span className={report.volume_trajectory.current_vs_peak_pct < 0 ? 'text-orange-400' : 'text-green-400'}>
                    {report.volume_trajectory.current_vs_peak_pct > 0 ? '+' : ''}
                    {report.volume_trajectory.current_vs_peak_pct.toFixed(0)}%
                  </span>
                </div>
                <Progress
                  value={Math.min(100, 100 + report.volume_trajectory.current_vs_peak_pct)}
                  className="h-2 bg-slate-700"
                />
              </div>

              {/* Week list */}
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {report.volume_trajectory.weeks.slice(-8).map((week, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm py-2 border-b border-slate-700/50">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400 w-20">{week.week}</span>
                      <PhaseLabel phase={week.phase} />
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-slate-300">{week.distance_km.toFixed(0)} km</span>
                      <span className="text-slate-500">{week.runs} runs</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Efficiency Analysis */}
          <Card className="bg-slate-800 border-slate-700 mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Heart className="w-5 h-5 text-red-400" />
                Efficiency Trend
              </CardTitle>
              <CardDescription>{report.efficiency_analysis.runs_with_hr} runs with heart rate data</CardDescription>
            </CardHeader>
            <CardContent>
              {report.efficiency_analysis.trend_pct !== null ? (
                <>
                  <div className="flex items-center gap-4 mb-4">
                    <div className="text-3xl font-bold">
                      {report.efficiency_analysis.trend_pct > 0 ? (
                        <span className="text-green-400">+{report.efficiency_analysis.trend_pct.toFixed(1)}%</span>
                      ) : (
                        <span className="text-orange-400">{report.efficiency_analysis.trend_pct.toFixed(1)}%</span>
                      )}
                    </div>
                    {report.efficiency_analysis.trend_pct > 0 ? (
                      <TrendingUp className="w-8 h-8 text-green-400" />
                    ) : (
                      <TrendingDown className="w-8 h-8 text-orange-400" />
                    )}
                  </div>
                  <p className="text-slate-400 text-sm mb-4">{report.efficiency_analysis.interpretation}</p>
                </>
              ) : (
                <p className="text-slate-400">{report.efficiency_analysis.interpretation}</p>
              )}
            </CardContent>
          </Card>

          {/* Data Quality */}
          <Card className="bg-slate-800 border-slate-700 mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Target className="w-5 h-5 text-purple-400" />
                Data Quality
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Available */}
              <div className="mb-4">
                <h4 className="text-sm font-medium text-slate-300 mb-2">Available Data</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {Object.entries(report.data_quality.available).map(([key, data]) => (
                    <div key={key} className="bg-slate-900/50 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400 capitalize">{key.replace('_', ' ')}</span>
                        <QualityBadge quality={data.quality} />
                      </div>
                      <div className="text-lg font-semibold text-white">{data.count}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Missing */}
              {Object.keys(report.data_quality.missing).length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-slate-300 mb-2">Missing Data</h4>
                  <div className="space-y-2">
                    {Object.entries(report.data_quality.missing).map(([key, data]) => (
                      <div key={key} className="flex items-start gap-3 p-3 rounded-lg bg-orange-900/10 border border-orange-800/20">
                        <XCircle className="w-4 h-4 text-orange-400 mt-0.5" />
                        <div>
                          <span className="text-sm text-slate-300 capitalize">{key.replace('_', ' ')}</span>
                          <p className="text-xs text-slate-500">{data.impact}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recommendations */}
          <Card className="bg-gradient-to-br from-slate-800 to-orange-900/20 border-orange-700/30 mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <ArrowRight className="w-5 h-5 text-orange-400" />
                Recommendations
              </CardTitle>
              <CardDescription>Prioritized next steps based on your data</CardDescription>
            </CardHeader>
            <CardContent>
              {report.recommendations.high_priority.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-green-400 mb-2 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    High Priority
                  </h4>
                  <div className="space-y-2">
                    {report.recommendations.high_priority.map((rec, idx) => (
                      <div key={idx} className="bg-green-900/10 border border-green-800/30 rounded-lg p-3">
                        <div className="font-medium text-white mb-1">{rec.action}</div>
                        <div className="text-sm text-slate-400">{rec.reason}</div>
                        {rec.effort && (
                          <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {rec.effort}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Footer */}
          <div className="text-center text-sm text-slate-500 mt-8 pb-8">
            <p>This analysis is descriptive, not prescriptive.</p>
            <p className="mt-1">Recovery and personal context take precedence over metrics.</p>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}

