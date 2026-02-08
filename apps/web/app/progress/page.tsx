'use client';

/**
 * Progress Page — ADR-17 Phase 3: Unified "Am I Getting Better?"
 *
 * 6 sections merging Analytics, Training Load, PBs, Insights, Compare:
 *   1. Headline (LLM coaching sentence)
 *   2. What's Working / What's Not (correlation engine)
 *   3. Fitness & Load (CTL/ATL/TSB)
 *   4. Efficiency Trend
 *   5. Personal Bests in Context
 *   6. Period Comparison (last N days vs prior N days)
 *
 * Old pages stay live — redirected only in Phase 5 after approval.
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  useProgressSummary,
  useWhatWorks,
  useWhatDoesntWork,
  useEfficiencyTrends,
  useTrainingLoadHistory,
  usePersonalBests,
} from '@/lib/hooks/queries/progress';
import {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Trophy,
  BarChart3,
  Activity,
  Target,
  Zap,
  Clock,
  Minus,
} from 'lucide-react';

// --- Collapsible Section ---

function Section({
  title,
  icon,
  children,
  askCoachQuery,
  defaultOpen = false,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  askCoachQuery?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardHeader
        className="pb-2 cursor-pointer select-none"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <CardTitle className="text-sm text-slate-300">{title}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {askCoachQuery && (
              <Link
                href={`/coach?q=${encodeURIComponent(askCoachQuery)}`}
                className="text-xs font-semibold text-orange-400 hover:text-orange-300 flex items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                Ask Coach <ArrowRight className="w-3 h-3" />
              </Link>
            )}
            {open ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </div>
        </div>
      </CardHeader>
      {open && <CardContent className="pt-0 pb-4">{children}</CardContent>}
    </Card>
  );
}

// --- Helpers ---

function formatPace(seconds: number): string {
  const min = Math.floor(seconds / 60);
  const sec = Math.round(seconds % 60);
  return `${min}:${sec.toString().padStart(2, '0')}/mi`;
}

function formatTime(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.round(totalSeconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function DeltaBadge({ value, suffix = '%', invert = false }: { value: number | null; suffix?: string; invert?: boolean }) {
  if (value === null || value === undefined) return null;
  const positive = invert ? value < 0 : value > 0;
  const negative = invert ? value > 0 : value < 0;
  const cls = positive
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
    : negative
      ? 'bg-red-500/20 text-red-400 border-red-500/30'
      : 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  const icon = positive ? <TrendingUp className="w-3 h-3" /> : negative ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />;
  return (
    <Badge className={`${cls} gap-1 text-xs`}>
      {icon} {value > 0 ? '+' : ''}{value}{suffix}
    </Badge>
  );
}

function CorrelationItem({ name, r, n, direction }: {
  name: string; r: number; n: number; direction: 'positive' | 'negative';
}) {
  const label = name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const strength = Math.abs(r) >= 0.6 ? 'Strong' : Math.abs(r) >= 0.4 ? 'Moderate' : 'Weak';
  const strengthCls = Math.abs(r) >= 0.6
    ? 'text-emerald-400'
    : Math.abs(r) >= 0.4
      ? 'text-blue-400'
      : 'text-slate-400';

  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-700/50 last:border-0">
      <div className="flex items-center gap-2">
        {direction === 'positive' ? (
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
        ) : (
          <TrendingDown className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
        )}
        <span className="text-sm text-slate-200">{label}</span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className={strengthCls}>{strength}</span>
        <span className="text-slate-500">r={r.toFixed(2)}</span>
        <span className="text-slate-600">n={n}</span>
      </div>
    </div>
  );
}


// --- Main Page ---

export default function ProgressPage() {
  const [days] = useState(28);

  const summary = useProgressSummary(days);
  const whatWorks = useWhatWorks(90);
  const whatDoesntWork = useWhatDoesntWork(90);
  const efficiency = useEfficiencyTrends(90, false, false, false);
  const loadHistory = useTrainingLoadHistory(90);
  const personalBests = usePersonalBests();

  const isLoading = summary.isLoading;

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  const s = summary.data;
  const pc = s?.period_comparison;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-3xl mx-auto px-4 py-6 pb-24 md:pb-8 space-y-4">

          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <TrendingUp className="w-6 h-6 text-orange-500" />
              <h1 className="text-xl font-bold text-white">Progress</h1>
            </div>
            <Link
              href="/coach?q=How%20is%20my%20training%20going%20overall%3F"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-orange-600/20 text-orange-400 hover:bg-orange-600/30 transition-colors"
            >
              Ask Coach <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {/* ═══ SECTION 1: Headline ═══ */}
          {s?.headline && (
            <Card className="bg-gradient-to-br from-orange-500/10 via-slate-800/60 to-slate-800/60 border-orange-500/25">
              <CardContent className="pt-5 pb-4 px-5">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-orange-500/20 ring-1 ring-orange-500/30 flex-shrink-0 mt-0.5">
                    <Sparkles className="w-4 h-4 text-orange-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-200 leading-relaxed font-medium">
                      {s.headline.text}
                    </p>
                    {s.headline.subtext && (
                      <p className="text-xs text-slate-400 mt-1">{s.headline.subtext}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Quick metrics row */}
          {s && s.ctl !== null && (
            <div className={`grid gap-2 ${pc ? 'grid-cols-3' : 'grid-cols-2'}`}>
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 text-center">
                <p className="text-xs text-slate-500 mb-1">Fitness</p>
                <p className="text-lg font-bold text-white">{s.ctl}</p>
                {s.ctl_trend && (
                  <p className="text-xs text-slate-400 mt-0.5">{s.ctl_trend}</p>
                )}
              </div>
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 text-center">
                <p className="text-xs text-slate-500 mb-1">Form</p>
                <p className={`text-lg font-bold ${(s.tsb ?? 0) > 0 ? 'text-emerald-400' : (s.tsb ?? 0) < -15 ? 'text-red-400' : 'text-white'}`}>
                  {(s.tsb ?? 0) > 0 ? '+' : ''}{s.tsb}
                </p>
                {s.tsb_zone && (
                  <p className="text-xs text-slate-400 mt-0.5 capitalize">{s.tsb_zone.replace(/_/g, ' ')}</p>
                )}
              </div>
              {pc && (
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 text-center">
                  <p className="text-xs text-slate-500 mb-1">Volume ({days}d)</p>
                  <p className="text-lg font-bold text-white">{pc.current.total_distance_mi}mi</p>
                  <DeltaBadge value={pc.volume_change_pct} />
                </div>
              )}
            </div>
          )}


          {/* ═══ SECTION 2: What's Working / What's Not ═══ */}
          <Section
            title="What's Working"
            icon={<Zap className="w-4 h-4 text-emerald-400" />}
            askCoachQuery="What patterns in my training are helping me improve?"
            defaultOpen={true}
          >
            {whatWorks.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : whatWorks.data?.what_works && whatWorks.data.what_works.length > 0 ? (
              <div className="space-y-0">
                {whatWorks.data.what_works.slice(0, 5).map((c, i) => (
                  <CorrelationItem
                    key={i}
                    name={c.input_name}
                    r={c.correlation_coefficient}
                    n={c.sample_size}
                    direction="positive"
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">
                No positive patterns detected yet. Daily check-ins (sleep, soreness, motivation) are needed to discover what drives your best performances.
              </p>
            )}
          </Section>

          <Section
            title="What's Not Working"
            icon={<TrendingDown className="w-4 h-4 text-red-400" />}
            askCoachQuery="What patterns in my training are hurting my performance?"
            defaultOpen={true}
          >
            {whatDoesntWork.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : whatDoesntWork.data?.what_doesnt_work && whatDoesntWork.data.what_doesnt_work.length > 0 ? (
              <div className="space-y-0">
                {whatDoesntWork.data.what_doesnt_work.slice(0, 5).map((c, i) => (
                  <CorrelationItem
                    key={i}
                    name={c.input_name}
                    r={c.correlation_coefficient}
                    n={c.sample_size}
                    direction="negative"
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">
                No negative patterns detected yet.
              </p>
            )}
          </Section>


          {/* ═══ SECTION 3: Fitness & Load ═══ */}
          <Section
            title="Fitness & Load"
            icon={<BarChart3 className="w-4 h-4 text-blue-400" />}
            askCoachQuery="Explain my current fitness and fatigue levels"
            defaultOpen={true}
          >
            {loadHistory.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : loadHistory.data ? (
              <div className="space-y-3">
                {/* Summary */}
                <div className="bg-slate-700/40 rounded-lg p-3 border border-slate-600/40">
                  <div className="flex gap-2">
                    <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-slate-300">
                      {loadHistory.data.summary.training_phase}. {loadHistory.data.summary.recommendation}
                    </p>
                  </div>
                </div>

                {/* Metrics grid */}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Fitness (CTL)</p>
                    <p className="text-base font-bold text-blue-400">{loadHistory.data.summary.ctl.toFixed(1)}</p>
                    <p className="text-xs text-slate-500">{loadHistory.data.summary.ctl_trend}</p>
                  </div>
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Fatigue (ATL)</p>
                    <p className="text-base font-bold text-orange-400">{loadHistory.data.summary.atl.toFixed(1)}</p>
                    <p className="text-xs text-slate-500">{loadHistory.data.summary.atl_trend}</p>
                  </div>
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Form (TSB)</p>
                    <p className={`text-base font-bold ${loadHistory.data.summary.tsb > 0 ? 'text-emerald-400' : loadHistory.data.summary.tsb < -15 ? 'text-red-400' : 'text-white'}`}>
                      {loadHistory.data.summary.tsb > 0 ? '+' : ''}{loadHistory.data.summary.tsb.toFixed(1)}
                    </p>
                    <p className="text-xs text-slate-500">{loadHistory.data.summary.tsb_trend}</p>
                  </div>
                </div>

                {/* Personal zone */}
                {loadHistory.data.personal_zones && (
                  <div className="text-xs text-slate-400 text-center">
                    Zone: <span className="text-slate-200 font-medium">{loadHistory.data.personal_zones.current_zone.replace(/_/g, ' ')}</span>
                    {' — '}{loadHistory.data.personal_zones.zone_description}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">Insufficient training data.</p>
            )}
          </Section>


          {/* ═══ SECTION 4: Efficiency Trend ═══ */}
          <Section
            title="Efficiency Trend"
            icon={<Activity className="w-4 h-4 text-emerald-400" />}
            askCoachQuery="What does my efficiency trend mean and how can I improve it?"
            defaultOpen={true}
          >
            {efficiency.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : efficiency.data?.summary ? (
              <div className="space-y-3">
                <div className="bg-slate-700/40 rounded-lg p-3 border border-slate-600/40">
                  <div className="flex gap-2">
                    <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-slate-300">
                      Efficiency is{' '}
                      <span className={
                        efficiency.data.summary.trend_direction === 'improving' ? 'text-emerald-400 font-medium' :
                        efficiency.data.summary.trend_direction === 'declining' ? 'text-red-400 font-medium' :
                        'text-slate-200 font-medium'
                      }>
                        {efficiency.data.summary.trend_direction}
                      </span>
                      {efficiency.data.summary.trend_magnitude != null && (
                        <> ({efficiency.data.summary.trend_magnitude > 0 ? '+' : ''}{efficiency.data.summary.trend_magnitude.toFixed(1)}%)</>
                      )}
                      {' '}over {efficiency.data.summary.total_activities} runs.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Current</p>
                    <p className="text-sm font-bold text-white">{efficiency.data.summary.current_efficiency.toFixed(1)}</p>
                  </div>
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Average</p>
                    <p className="text-sm font-bold text-slate-300">{efficiency.data.summary.average_efficiency.toFixed(1)}</p>
                  </div>
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Best</p>
                    <p className="text-sm font-bold text-emerald-400">{efficiency.data.summary.best_efficiency.toFixed(1)}</p>
                  </div>
                  <div className="bg-slate-700/30 rounded-lg p-2">
                    <p className="text-xs text-slate-500">Worst</p>
                    <p className="text-sm font-bold text-red-400">{efficiency.data.summary.worst_efficiency.toFixed(1)}</p>
                  </div>
                </div>

                {efficiency.data.stability && (
                  <div className="text-xs text-slate-400 text-center">
                    Consistency: <span className="text-slate-200 font-medium">{efficiency.data.stability.consistency_score?.toFixed(0)}%</span>
                    {' — '}{efficiency.data.stability.easy_runs} easy, {efficiency.data.stability.moderate_runs} moderate, {efficiency.data.stability.hard_runs} hard
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">Not enough efficiency data yet.</p>
            )}
          </Section>


          {/* ═══ SECTION 5: Personal Bests ═══ */}
          <Section
            title="Personal Bests"
            icon={<Trophy className="w-4 h-4 text-yellow-400" />}
            askCoachQuery="Analyze my personal bests and what conditions led to them"
            defaultOpen={true}
          >
            {personalBests.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : personalBests.data && Array.isArray(personalBests.data) && personalBests.data.length > 0 ? (
              <div className="space-y-0">
                {personalBests.data.slice(0, 8).map((pb, i) => (
                  <div key={i} className="flex items-center justify-between py-2.5 border-b border-slate-700/50 last:border-0">
                    <div className="flex items-center gap-2">
                      <Trophy className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" />
                      <span className="text-sm text-slate-200 font-medium">{pb.distance_name}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-white font-semibold">{formatTime(pb.elapsed_time_s)}</span>
                      {pb.pace_per_mile_s && (
                        <span className="text-slate-400">{formatPace(pb.pace_per_mile_s)}</span>
                      )}
                      <span className="text-slate-500">{pb.date}</span>
                      {pb.activity_id && (
                        <Link
                          href={`/activities/${pb.activity_id}`}
                          className="text-orange-400 hover:text-orange-300"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">
                No personal bests recorded yet. Sync activities to discover them.
              </p>
            )}
          </Section>


          {/* ═══ SECTION 6: Period Comparison ═══ */}
          <Section
            title={`Last ${days} Days vs Prior ${days} Days`}
            icon={<Target className="w-4 h-4 text-purple-400" />}
            askCoachQuery={`Compare my last ${days} days of training to the ${days} days before that`}
            defaultOpen={true}
          >
            {!pc ? (
              <p className="text-sm text-slate-500 py-2">Not enough data for comparison.</p>
            ) : (
              <div className="space-y-3">
                {/* Comparison table */}
                <div className="overflow-hidden rounded-lg border border-slate-700/50">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-700/30">
                        <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Metric</th>
                        <th className="text-right py-2 px-3 text-xs text-slate-500 font-medium">Current</th>
                        <th className="text-right py-2 px-3 text-xs text-slate-500 font-medium">Previous</th>
                        <th className="text-right py-2 px-3 text-xs text-slate-500 font-medium">Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-slate-700/50">
                        <td className="py-2 px-3 text-slate-300">Volume</td>
                        <td className="py-2 px-3 text-right text-white font-medium">{pc.current.total_distance_mi}mi</td>
                        <td className="py-2 px-3 text-right text-slate-400">{pc.previous.total_distance_mi}mi</td>
                        <td className="py-2 px-3 text-right"><DeltaBadge value={pc.volume_change_pct} /></td>
                      </tr>
                      <tr className="border-t border-slate-700/50">
                        <td className="py-2 px-3 text-slate-300">Runs</td>
                        <td className="py-2 px-3 text-right text-white font-medium">{pc.current.run_count}</td>
                        <td className="py-2 px-3 text-right text-slate-400">{pc.previous.run_count}</td>
                        <td className="py-2 px-3 text-right">
                          <DeltaBadge
                            value={pc.previous.run_count > 0 ? Math.round(((pc.current.run_count - pc.previous.run_count) / pc.previous.run_count) * 100) : null}
                          />
                        </td>
                      </tr>
                      <tr className="border-t border-slate-700/50">
                        <td className="py-2 px-3 text-slate-300">Duration</td>
                        <td className="py-2 px-3 text-right text-white font-medium">{pc.current.total_duration_hr}h</td>
                        <td className="py-2 px-3 text-right text-slate-400">{pc.previous.total_duration_hr}h</td>
                        <td className="py-2 px-3 text-right">
                          <DeltaBadge
                            value={pc.previous.total_duration_hr > 0 ? Math.round(((pc.current.total_duration_hr - pc.previous.total_duration_hr) / pc.previous.total_duration_hr) * 100) : null}
                          />
                        </td>
                      </tr>
                      {(pc.current.avg_hr || pc.previous.avg_hr) && (
                        <tr className="border-t border-slate-700/50">
                          <td className="py-2 px-3 text-slate-300">Avg HR</td>
                          <td className="py-2 px-3 text-right text-white font-medium">{pc.current.avg_hr ?? '—'}</td>
                          <td className="py-2 px-3 text-right text-slate-400">{pc.previous.avg_hr ?? '—'}</td>
                          <td className="py-2 px-3 text-right">
                            <DeltaBadge value={pc.hr_change} suffix=" bpm" invert />
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Section>

        </div>
      </div>
    </ProtectedRoute>
  );
}
