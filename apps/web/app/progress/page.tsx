'use client';

/**
 * Progress Page — ADR-17 Phase 3: Unified "Am I Getting Better?"
 *
 * Surfaces ALL system data in one page:
 *   1. Headline (LLM with full athlete brief)
 *   2. Quick metrics (Fitness, Form, Volume, Consistency)
 *   3. Recovery & Durability
 *   4. Race Readiness (predictions + goal race)
 *   5. Runner Profile (type, paces, RPI)
 *   6. What's Working / What's Not (correlation engine)
 *   7. Fitness & Load (CTL/ATL/TSB)
 *   8. Efficiency Trend
 *   9. Volume Trajectory (8 week trend)
 *  10. Wellness Trends
 *  11. Personal Bests
 *  12. Period Comparison
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
  useTrainingPatterns,
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
  Minus,
  Shield,
  Timer,
  Heart,
  User,
  Moon,
  AlertTriangle,
  CheckCircle,
  Flame,
} from 'lucide-react';

// --- Collapsible Section ---

function Section({
  title,
  icon,
  children,
  askCoachQuery,
  defaultOpen = true,
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

function MetricBox({ label, value, sub, color = 'text-white' }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="bg-slate-700/30 rounded-lg p-2.5 text-center">
      <p className="text-xs text-slate-500 mb-0.5">{label}</p>
      <p className={`text-base font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function CoachProgressCard({
  title,
  summary,
  trendContext,
  drivers,
  nextStep,
  askCoachQuery,
  expanded,
  onToggle,
}: {
  title: string;
  summary: string;
  trendContext: string;
  drivers: string;
  nextStep: string;
  askCoachQuery: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardHeader className="pb-2 cursor-pointer select-none" onClick={onToggle}>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-sm text-slate-200">{title}</CardTitle>
            <p className="text-sm text-slate-300 mt-1 leading-relaxed">{summary}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Link
              href={`/coach?q=${encodeURIComponent(askCoachQuery)}`}
              className="text-xs font-semibold text-orange-400 hover:text-orange-300 flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              Ask Coach <ArrowRight className="w-3 h-3" />
            </Link>
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </div>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0 pb-4 space-y-2.5">
          <div className="bg-slate-700/30 rounded-lg p-2.5">
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Trend Context</p>
            <p className="text-sm text-slate-300">{trendContext}</p>
          </div>
          <div className="bg-slate-700/30 rounded-lg p-2.5">
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">What Is Driving This</p>
            <p className="text-sm text-slate-300">{drivers}</p>
          </div>
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2.5">
            <p className="text-xs text-emerald-400/80 uppercase tracking-wide mb-1">Next Focus</p>
            <p className="text-sm text-emerald-300">{nextStep}</p>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function CorrelationItem({ name, r, n, direction }: {
  name: string; r: number; n: number; direction: 'positive' | 'negative';
}) {
  const label = name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const strength = Math.abs(r) >= 0.6 ? 'Strong' : Math.abs(r) >= 0.4 ? 'Moderate' : 'Weak';
  const strengthCls = Math.abs(r) >= 0.6 ? 'text-emerald-400' : Math.abs(r) >= 0.4 ? 'text-blue-400' : 'text-slate-400';

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
  const [expandedCoachCard, setExpandedCoachCard] = useState<string | null>(null);

  const summary = useProgressSummary(days);
  const whatWorks = useWhatWorks(90);
  const whatDoesntWork = useWhatDoesntWork(90);
  const trainingPatterns = useTrainingPatterns();
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
  const recovery = s?.recovery;
  const profile = s?.runner_profile;
  const paces = profile?.training_paces;
  const wellness = s?.wellness;
  const volTraj = s?.volume_trajectory;
  const coachCards = s?.coach_cards ?? [];

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

          {/* ═══ SECTION 2: Coach Interpreted Progress Cards ═══ */}
          {s && coachCards.length > 0 && (
            <div className="grid gap-2 sm:grid-cols-2">
              {coachCards.map((card) => {
                const expanded = expandedCoachCard === card.id;
                return (
                  <CoachProgressCard
                    key={card.id}
                    title={card.title}
                    summary={card.summary}
                    trendContext={card.trend_context}
                    drivers={card.drivers}
                    nextStep={card.next_step}
                    askCoachQuery={card.ask_coach_query}
                    expanded={expanded}
                    onToggle={() => setExpandedCoachCard(expanded ? null : card.id)}
                  />
                );
              })}
            </div>
          )}

          {/* ═══ SECTION 3: Goal Race + Race Predictions ═══ */}
          {(s?.goal_race_name || (s?.race_predictions && s.race_predictions.length > 0)) && (
            <Section
              title="Race Readiness"
              icon={<Target className="w-4 h-4 text-purple-400" />}
              askCoachQuery="Am I on track for my race goal?"
              defaultOpen={true}
            >
              <div className="space-y-3">
                {/* Goal race card */}
                {s?.goal_race_name && (
                  <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-purple-300">{s.goal_race_name}</p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {s.goal_race_date} — <span className="text-purple-400 font-medium">{s.goal_race_days_remaining} days away</span>
                        </p>
                      </div>
                      {s.goal_time && (
                        <div className="text-right">
                          <p className="text-xs text-slate-500">Goal</p>
                          <p className="text-sm font-bold text-white">{s.goal_time}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Predictions */}
                {s?.race_predictions && s.race_predictions.length > 0 && (
                  <div className="grid grid-cols-2 gap-2">
                    {s.race_predictions.map((rp) => (
                      <div key={rp.distance} className="bg-slate-700/30 rounded-lg p-2.5 text-center">
                        <p className="text-xs text-slate-500">{rp.distance}</p>
                        <p className="text-sm font-bold text-white">{rp.predicted_time}</p>
                        {rp.confidence && (
                          <p className="text-xs text-slate-500 capitalize">{rp.confidence}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Section>
          )}

          {/* ═══ SECTION 4: Recovery & Durability ═══ */}
          {recovery && (
            <Section
              title="Recovery & Durability"
              icon={<Shield className="w-4 h-4 text-cyan-400" />}
              askCoachQuery="What does my recovery data tell you about my readiness?"
              defaultOpen={true}
            >
              <div className="space-y-3">
                {/* Warnings first */}
                {(recovery.false_fitness || recovery.masked_fatigue) && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 space-y-1">
                    {recovery.false_fitness && (
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                        <p className="text-sm text-red-300">False fitness detected — CTL may overstate readiness</p>
                      </div>
                    )}
                    {recovery.masked_fatigue && (
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                        <p className="text-sm text-red-300">Masked fatigue — cumulative load may be hiding fatigue signals</p>
                      </div>
                    )}
                  </div>
                )}

                {!recovery.false_fitness && !recovery.masked_fatigue && (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2.5">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <p className="text-sm text-emerald-300">No red flags in recovery signals</p>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-3 gap-2">
                  {recovery.durability_index != null && (
                    <MetricBox
                      label="Durability"
                      value={recovery.durability_index.toFixed(1)}
                      color={recovery.durability_index >= 70 ? 'text-emerald-400' : recovery.durability_index >= 40 ? 'text-blue-400' : 'text-orange-400'}
                    />
                  )}
                  {recovery.recovery_half_life_hours != null && (
                    <MetricBox
                      label="Recovery t½"
                      value={`${(recovery.recovery_half_life_hours / 24).toFixed(1)}d`}
                      color="text-cyan-400"
                    />
                  )}
                  {recovery.injury_risk_score != null && (
                    <MetricBox
                      label="Injury Risk"
                      value={`${recovery.injury_risk_score}`}
                      color={recovery.injury_risk_score < 30 ? 'text-emerald-400' : recovery.injury_risk_score < 60 ? 'text-yellow-400' : 'text-red-400'}
                    />
                  )}
                </div>
              </div>
            </Section>
          )}

          {/* ═══ SECTION 5: Runner Profile ═══ */}
          {profile && (profile.runner_type || paces) && (
            <Section
              title="Runner Profile"
              icon={<User className="w-4 h-4 text-blue-400" />}
              askCoachQuery="Tell me about my runner type and what it means for my training"
              defaultOpen={true}
            >
              <div className="space-y-3">
                {/* Runner type + RPI */}
                <div className="flex items-center gap-3">
                  {profile.runner_type && (
                    <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 text-xs capitalize">
                      {profile.runner_type.replace(/_/g, ' ')}
                    </Badge>
                  )}
                  {profile.rpi && (
                    <span className="text-sm text-slate-300">
                      RPI: <span className="text-white font-bold">{profile.rpi.toFixed(1)}</span>
                    </span>
                  )}
                  {profile.max_hr && (
                    <span className="text-sm text-slate-300">
                      Max HR: <span className="text-white font-bold">{profile.max_hr}</span>
                    </span>
                  )}
                </div>

                {/* Training paces */}
                {paces && (
                  <div className="grid grid-cols-5 gap-1.5 text-center">
                    {[
                      { label: 'Easy', val: paces.easy, clr: 'text-emerald-400' },
                      { label: 'Marathon', val: paces.marathon, clr: 'text-blue-400' },
                      { label: 'Threshold', val: paces.threshold, clr: 'text-orange-400' },
                      { label: 'Interval', val: paces.interval, clr: 'text-red-400' },
                      { label: 'Rep', val: paces.repetition, clr: 'text-purple-400' },
                    ].map((p) =>
                      p.val ? (
                        <div key={p.label} className="bg-slate-700/30 rounded-lg p-2">
                          <p className="text-xs text-slate-500">{p.label}</p>
                          <p className={`text-xs font-bold ${p.clr}`}>{p.val}</p>
                        </div>
                      ) : null
                    )}
                  </div>
                )}
              </div>
            </Section>
          )}

          {/* ═══ SECTION 6: What's Working / What's Not ═══ */}
          <Section
            title="What's Working"
            icon={<Zap className="w-4 h-4 text-emerald-400" />}
            askCoachQuery="What patterns in my training are helping me improve?"
            defaultOpen={true}
          >
            {/* Layer 1: Training Patterns (from activity data — always available) */}
            {trainingPatterns.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : trainingPatterns.data?.what_works && trainingPatterns.data.what_works.length > 0 ? (
              <ul className="space-y-2 mb-4">
                {trainingPatterns.data.what_works.map((item, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500 py-2">Keep running — patterns emerge with more data.</p>
            )}

            {/* Layer 2: Personal Correlations (from check-in data — grows over time) */}
            {whatWorks.data?.what_works && whatWorks.data.what_works.length > 0 ? (
              <div className="border-t border-slate-700/50 pt-3 mt-1">
                <p className="text-xs text-emerald-400/70 font-semibold uppercase tracking-wide mb-2">Your personal correlations</p>
                <div className="space-y-0">
                  {whatWorks.data.what_works.slice(0, 5).map((c: { input_name: string; correlation_coefficient: number; sample_size: number }, i: number) => (
                    <CorrelationItem
                      key={i}
                      name={c.input_name}
                      r={c.correlation_coefficient}
                      n={c.sample_size}
                      direction="positive"
                    />
                  ))}
                </div>
              </div>
            ) : trainingPatterns.data ? (
              <div className="border-t border-slate-700/50 pt-3 mt-1">
                <div className="flex items-center gap-2 mb-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-orange-400" />
                  <p className="text-xs font-semibold text-slate-400">N=1 Correlation Model</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-orange-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (trainingPatterns.data.checkin_count / trainingPatterns.data.checkins_needed) * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-500 whitespace-nowrap">
                    {trainingPatterns.data.checkin_count}/{trainingPatterns.data.checkins_needed} check-ins
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1.5">
                  Daily check-ins unlock personal correlations — what sleep, soreness, and motivation patterns drive <em>your</em> best performances.
                </p>
              </div>
            ) : null}
          </Section>

          <Section
            title="What's Not Working"
            icon={<TrendingDown className="w-4 h-4 text-red-400" />}
            askCoachQuery="What patterns in my training are hurting my performance?"
            defaultOpen={true}
          >
            {/* Layer 1: Training Patterns */}
            {trainingPatterns.isLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
            ) : trainingPatterns.data?.what_doesnt && trainingPatterns.data.what_doesnt.length > 0 ? (
              <ul className="space-y-2 mb-4">
                {trainingPatterns.data.what_doesnt.map((item, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500 py-2">No negative patterns detected.</p>
            )}

            {/* Layer 2: Personal Correlations */}
            {whatDoesntWork.data?.what_doesnt_work && whatDoesntWork.data.what_doesnt_work.length > 0 && (
              <div className="border-t border-slate-700/50 pt-3 mt-1">
                <p className="text-xs text-red-400/70 font-semibold uppercase tracking-wide mb-2">Your personal correlations</p>
                <div className="space-y-0">
                  {whatDoesntWork.data.what_doesnt_work.slice(0, 5).map((c: { input_name: string; correlation_coefficient: number; sample_size: number }, i: number) => (
                    <CorrelationItem
                      key={i}
                      name={c.input_name}
                      r={c.correlation_coefficient}
                      n={c.sample_size}
                      direction="negative"
                    />
                  ))}
                </div>
              </div>
            )}
          </Section>

          {/* ═══ Injury Patterns (from training data) ═══ */}
          {trainingPatterns.data?.injury_patterns && trainingPatterns.data.injury_patterns.length > 0 && (
            <Section
              title="Injury Risk Patterns"
              icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}
              askCoachQuery="What injury risk patterns do you see in my training?"
              defaultOpen={true}
            >
              <ul className="space-y-2">
                {trainingPatterns.data.injury_patterns.map((item, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}


          {/* ═══ SECTION 7: Fitness & Load ═══ */}
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
                <div className="bg-slate-700/40 rounded-lg p-3 border border-slate-600/40">
                  <div className="flex gap-2">
                    <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-slate-300">
                      {loadHistory.data.summary.training_phase}. {loadHistory.data.summary.recommendation}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <MetricBox label="Fitness (CTL)" value={loadHistory.data.summary.ctl.toFixed(1)} sub={loadHistory.data.summary.ctl_trend} color="text-blue-400" />
                  <MetricBox label="Fatigue (ATL)" value={loadHistory.data.summary.atl.toFixed(1)} sub={loadHistory.data.summary.atl_trend} color="text-orange-400" />
                  <MetricBox
                    label="Form (TSB)"
                    value={`${loadHistory.data.summary.tsb > 0 ? '+' : ''}${loadHistory.data.summary.tsb.toFixed(1)}`}
                    sub={loadHistory.data.summary.tsb_trend}
                    color={loadHistory.data.summary.tsb > 0 ? 'text-emerald-400' : loadHistory.data.summary.tsb < -15 ? 'text-red-400' : 'text-white'}
                  />
                </div>

                {loadHistory.data.personal_zones && (
                  <div className="text-xs text-slate-400 text-center">
                    Zone: <span className="text-slate-200 font-medium">{loadHistory.data.personal_zones.current_zone.replace(/_/g, ' ')}</span>
                    {' — '}{loadHistory.data.personal_zones.zone_description}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">Insufficient training data for load analysis.</p>
            )}
          </Section>


          {/* ═══ SECTION 8: Efficiency Trend ═══ */}
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
                  <MetricBox label="Current" value={efficiency.data.summary.current_efficiency.toFixed(1)} />
                  <MetricBox label="Average" value={efficiency.data.summary.average_efficiency.toFixed(1)} color="text-slate-300" />
                  <MetricBox label="Best" value={efficiency.data.summary.best_efficiency.toFixed(1)} color="text-emerald-400" />
                  <MetricBox label="Worst" value={efficiency.data.summary.worst_efficiency.toFixed(1)} color="text-red-400" />
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500 py-2">Not enough efficiency data yet.</p>
            )}
          </Section>


          {/* ═══ SECTION 9: Volume Trajectory ═══ */}
          {volTraj && volTraj.recent_weeks && volTraj.recent_weeks.length > 0 && (
            <Section
              title="Volume Trajectory"
              icon={<Flame className="w-4 h-4 text-orange-400" />}
              askCoachQuery="How is my training volume trending?"
              defaultOpen={true}
            >
              <div className="space-y-3">
                {/* Bar chart representation */}
                <div className="space-y-1.5">
                  {volTraj.recent_weeks.map((w) => {
                    const maxMi = Math.max(...(volTraj.recent_weeks?.map(wk => wk.miles) ?? [1]), 1);
                    const pct = (w.miles / maxMi) * 100;
                    return (
                      <div key={w.week_start} className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 w-16 text-right flex-shrink-0">
                          {w.week_start.slice(5)}
                        </span>
                        <div className="flex-1 bg-slate-700/30 rounded-full h-5 overflow-hidden">
                          <div
                            className="bg-orange-500/40 h-full rounded-full flex items-center justify-end pr-2"
                            style={{ width: `${Math.max(pct, 8)}%` }}
                          >
                            <span className="text-xs text-white font-medium">{w.miles}</span>
                          </div>
                        </div>
                        <span className="text-xs text-slate-500 w-8">{w.runs}r</span>
                      </div>
                    );
                  })}
                  {volTraj.current_week_mi != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-orange-400 w-16 text-right flex-shrink-0 font-medium">
                        This wk
                      </span>
                      <div className="flex-1 bg-slate-700/30 rounded-full h-5 overflow-hidden">
                        <div
                          className="bg-orange-500/60 h-full rounded-full flex items-center justify-end pr-2 border border-orange-500/30"
                          style={{ width: `${Math.max((volTraj.current_week_mi / Math.max(...(volTraj.recent_weeks?.map(w => w.miles) ?? [1]), 1)) * 100, 8)}%` }}
                        >
                          <span className="text-xs text-white font-medium">{volTraj.current_week_mi}</span>
                        </div>
                      </div>
                      <span className="text-xs text-slate-500 w-8"></span>
                    </div>
                  )}
                </div>

                {/* Summary row */}
                <div className="flex items-center justify-between text-xs text-slate-400">
                  {volTraj.peak_week_mi && (
                    <span>Peak: <span className="text-white font-medium">{volTraj.peak_week_mi}mi</span></span>
                  )}
                  {volTraj.trend_pct != null && (
                    <DeltaBadge value={volTraj.trend_pct} />
                  )}
                </div>
              </div>
            </Section>
          )}


          {/* ═══ SECTION 10: Wellness Trends ═══ */}
          {wellness && wellness.checkin_count > 0 && (
            <Section
              title="Wellness Trends"
              icon={<Moon className="w-4 h-4 text-indigo-400" />}
              askCoachQuery="How are my wellness patterns affecting my running?"
              defaultOpen={true}
            >
              <div className="space-y-3">
                <div className="grid grid-cols-4 gap-2 text-center">
                  {wellness.avg_sleep != null && (
                    <MetricBox label="Avg Sleep" value={`${wellness.avg_sleep.toFixed(1)}h`} color="text-indigo-400" />
                  )}
                  {wellness.avg_motivation != null && (
                    <MetricBox
                      label="Motivation"
                      value={wellness.avg_motivation.toFixed(1)}
                      sub="/5"
                      color={wellness.avg_motivation >= 4 ? 'text-emerald-400' : wellness.avg_motivation >= 3 ? 'text-blue-400' : 'text-orange-400'}
                    />
                  )}
                  {wellness.avg_soreness != null && (
                    <MetricBox
                      label="Soreness"
                      value={wellness.avg_soreness.toFixed(1)}
                      sub="/5"
                      color={wellness.avg_soreness <= 2 ? 'text-emerald-400' : wellness.avg_soreness <= 3 ? 'text-blue-400' : 'text-red-400'}
                    />
                  )}
                  {wellness.avg_stress != null && (
                    <MetricBox
                      label="Stress"
                      value={wellness.avg_stress.toFixed(1)}
                      sub="/5"
                      color={wellness.avg_stress <= 2 ? 'text-emerald-400' : wellness.avg_stress <= 3 ? 'text-blue-400' : 'text-red-400'}
                    />
                  )}
                </div>
                <p className="text-xs text-slate-500 text-center">
                  Based on {wellness.checkin_count} check-in{wellness.checkin_count !== 1 ? 's' : ''} over {days} days
                  {wellness.trend_direction && <> — overall trend: <span className="text-slate-300">{wellness.trend_direction}</span></>}
                </p>
              </div>
            </Section>
          )}


          {/* ═══ SECTION 11: Personal Bests ═══ */}
          <Section
            title={`Personal Bests${s?.pb_count_last_90d ? ` (${s.pb_count_last_90d} in 90d)` : ''}`}
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
                      <span className="text-sm text-slate-200 font-medium">{pb.distance_category}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-white font-semibold">{formatTime(pb.time_seconds)}</span>
                      {pb.pace_per_mile && (
                        <span className="text-slate-400">{formatPace(pb.pace_per_mile)}</span>
                      )}
                      <span className="text-slate-500">{pb.achieved_at?.slice(0, 10)}</span>
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


          {/* ═══ SECTION 12: Period Comparison ═══ */}
          <Section
            title={`Last ${days} Days vs Prior ${days} Days`}
            icon={<Timer className="w-4 h-4 text-purple-400" />}
            askCoachQuery={`Compare my last ${days} days of training to the ${days} days before that`}
            defaultOpen={true}
          >
            {!pc ? (
              <p className="text-sm text-slate-500 py-2">Not enough data for comparison.</p>
            ) : (
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
            )}
          </Section>

        </div>
      </div>
    </ProtectedRoute>
  );
}
