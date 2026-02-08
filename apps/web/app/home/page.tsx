'use client';

/**
 * Home Page — ADR-17 Phase 2: Coach-Led Experience
 *
 * Tier 1 (above fold): Coach Noticed + Quick Check-in
 * Tier 2 (below fold): Today's workout, This Week, Race Countdown
 *
 * Removed: Quick Access, Yesterday, Hero Narrative, Welcome card, Import Progress
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useHomeData, useQuickCheckin } from '@/lib/hooks/queries/home';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Calendar,
  TrendingUp,
  Activity,
  Zap,
  ArrowRight,
  CheckCircle2,
  Clock,
  Target,
  BarChart3,
  MessageSquare,
  Footprints,
  Flame,
  Sparkles,
} from 'lucide-react';

// --- Workout styling ---

const WORKOUT_CONFIG: Record<string, { color: string; bgColor: string; icon: React.ReactNode }> = {
  rest:         { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Clock className="w-6 h-6" /> },
  recovery:     { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Clock className="w-6 h-6" /> },
  easy:         { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Footprints className="w-6 h-6" /> },
  easy_strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Zap className="w-6 h-6" /> },
  strides:      { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Zap className="w-6 h-6" /> },
  medium_long:  { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <TrendingUp className="w-6 h-6" /> },
  long:         { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <TrendingUp className="w-6 h-6" /> },
  long_mp:      { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <Target className="w-6 h-6" /> },
  threshold:    { color: 'text-orange-400', bgColor: 'bg-orange-500/20', icon: <Flame className="w-6 h-6" /> },
  tempo:        { color: 'text-orange-400', bgColor: 'bg-orange-500/20', icon: <Flame className="w-6 h-6" /> },
  intervals:    { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: <Activity className="w-6 h-6" /> },
  vo2max:       { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: <Activity className="w-6 h-6" /> },
  race:         { color: 'text-pink-400', bgColor: 'bg-pink-500/20', icon: <Target className="w-6 h-6" /> },
};

const DEFAULT_WORKOUT = { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Footprints className="w-6 h-6" /> };

function getWorkoutConfig(type?: string) {
  return type ? (WORKOUT_CONFIG[type] ?? DEFAULT_WORKOUT) : DEFAULT_WORKOUT;
}

function formatWorkoutType(type?: string): string {
  if (!type) return '';
  const labels: Record<string, string> = {
    easy: 'Easy Run', easy_strides: 'Easy + Strides', strides: 'Strides',
    medium_long: 'Medium Long', long: 'Long Run', long_mp: 'Long + MP',
    threshold: 'Threshold', tempo: 'Tempo', intervals: 'Intervals',
    vo2max: 'VO2max', rest: 'Rest Day', recovery: 'Recovery', race: 'Race Day',
  };
  return labels[type] || type.replace(/_/g, ' ');
}

function getStatusBadge(status: string) {
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    ahead:    { cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', icon: <TrendingUp className="w-3 h-3" />, label: 'Ahead' },
    on_track: { cls: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: <CheckCircle2 className="w-3 h-3" />, label: 'On Track' },
    behind:   { cls: 'bg-orange-500/20 text-orange-400 border-orange-500/30', icon: <Clock className="w-3 h-3" />, label: 'Behind' },
  };
  const s = map[status];
  if (!s) return null;
  return <Badge className={`${s.cls} gap-1 text-xs`}>{s.icon} {s.label}</Badge>;
}


// ── Coach Noticed Card ──────────────────────────────────────────────

function CoachNoticedCard({ text, askQuery }: { text: string; askQuery: string }) {
  return (
    <Card className="bg-gradient-to-br from-orange-500/10 via-slate-800/60 to-slate-800/60 border-orange-500/25">
      <CardContent className="pt-5 pb-4 px-5">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-orange-500/20 ring-1 ring-orange-500/30 flex-shrink-0 mt-0.5">
            <Sparkles className="w-4 h-4 text-orange-400" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-400/80 mb-1.5">
              Coach noticed
            </p>
            <p className="text-sm text-slate-200 leading-relaxed">{text}</p>
            <Link
              href={`/coach?q=${encodeURIComponent(askQuery)}`}
              className="inline-flex items-center gap-1.5 mt-3 text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors"
            >
              Ask Coach <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}


// ── Quick Check-in ──────────────────────────────────────────────────

const FEEL_OPTIONS = [
  { label: 'Great', value: 5, emoji: '💪' },
  { label: 'Fine',  value: 4, emoji: '👍' },
  { label: 'Tired', value: 2, emoji: '😴' },
  { label: 'Rough', value: 1, emoji: '😓' },
];

const SLEEP_OPTIONS = [
  { label: 'Great', value: 8, emoji: '🌙' },
  { label: 'OK',    value: 7, emoji: '😐' },
  { label: 'Poor',  value: 5, emoji: '😵' },
];

const SORENESS_OPTIONS = [
  { label: 'No',   value: 1, emoji: '✅' },
  { label: 'Mild', value: 2, emoji: '🤏' },
  { label: 'Yes',  value: 4, emoji: '🔥' },
];

function QuickCheckin() {
  const [feel, setFeel] = useState<number | null>(null);
  const [sleep, setSleep] = useState<number | null>(null);
  const [soreness, setSoreness] = useState<number | null>(null);
  const checkin = useQuickCheckin();

  const handleSubmit = () => {
    if (feel === null || sleep === null || soreness === null) return;
    const today = new Date().toISOString().split('T')[0];
    checkin.mutate(
      { date: today, motivation_1_5: feel, sleep_h: sleep, soreness_1_5: soreness },
    );
  };

  const allSelected = feel !== null && sleep !== null && soreness !== null;

  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardContent className="pt-4 pb-4 px-5 space-y-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Quick check-in
        </p>

        {/* Feel */}
        <div>
          <p className="text-sm text-slate-300 mb-2">How do you feel today?</p>
          <div className="flex gap-2">
            {FEEL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFeel(opt.value)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                  feel === opt.value
                    ? 'bg-orange-600/30 text-orange-300 ring-1 ring-orange-500/50'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <span className="block text-base mb-0.5">{opt.emoji}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sleep */}
        <div>
          <p className="text-sm text-slate-300 mb-2">Sleep?</p>
          <div className="flex gap-2">
            {SLEEP_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSleep(opt.value)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                  sleep === opt.value
                    ? 'bg-orange-600/30 text-orange-300 ring-1 ring-orange-500/50'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <span className="block text-base mb-0.5">{opt.emoji}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Soreness */}
        <div>
          <p className="text-sm text-slate-300 mb-2">Any soreness?</p>
          <div className="flex gap-2">
            {SORENESS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSoreness(opt.value)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                  soreness === opt.value
                    ? 'bg-orange-600/30 text-orange-300 ring-1 ring-orange-500/50'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <span className="block text-base mb-0.5">{opt.emoji}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Submit */}
        {allSelected && (
          <Button
            onClick={handleSubmit}
            disabled={checkin.isPending}
            className="w-full bg-orange-600 hover:bg-orange-700 text-white"
            size="sm"
          >
            {checkin.isPending ? 'Saving...' : 'Save check-in'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}


// ── Check-in Summary (shown after check-in) ────────────────────────

function CheckinSummary({ motivation, sleep, soreness }: {
  motivation?: string | null; sleep?: string | null; soreness?: string | null;
}) {
  const items = [
    { label: 'Feeling', value: motivation, emoji: motivation === 'Great' ? '💪' : motivation === 'Fine' ? '👍' : motivation === 'Tired' ? '😴' : '😓' },
    { label: 'Sleep', value: sleep, emoji: sleep === 'Great' ? '🌙' : sleep === 'OK' ? '😐' : '😵' },
    { label: 'Soreness', value: soreness, emoji: soreness === 'None' ? '✅' : soreness === 'Mild' ? '🤏' : '🔥' },
  ].filter((i) => i.value);

  if (items.length === 0) return null;

  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardContent className="py-3 px-5">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Today&apos;s check-in
          </p>
        </div>
        <div className="flex gap-4">
          {items.map((item) => (
            <div key={item.label} className="flex items-center gap-1.5 text-sm">
              <span>{item.emoji}</span>
              <span className="text-slate-400 text-xs">{item.label}:</span>
              <span className="text-slate-200 text-xs font-medium">{item.value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}


// ── Race Countdown Card ─────────────────────────────────────────────

function RaceCountdownCard({
  raceName, raceDate, daysRemaining, goalTime, goalPace, predictedTime,
}: {
  raceName?: string; raceDate: string; daysRemaining: number;
  goalTime?: string; goalPace?: string; predictedTime?: string;
}) {
  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-pink-400" />
          <CardTitle className="text-sm text-slate-300">Race Countdown</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="pb-4 space-y-2">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">{daysRemaining}</span>
          <span className="text-sm text-slate-400">days to go</span>
        </div>
        {raceName && (
          <p className="text-sm text-slate-300">{raceName}</p>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          {goalTime && <span>Goal: <span className="text-white font-medium">{goalTime}</span></span>}
          {goalPace && <span>Pace: <span className="text-white font-medium">{goalPace}</span></span>}
          {predictedTime && <span>Predicted: <span className="text-white font-medium">{predictedTime}</span></span>}
        </div>
        <Link
          href={`/coach?q=${encodeURIComponent(`Am I on track for my ${raceName || 'race'} in ${daysRemaining} days?`)}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors pt-1"
        >
          Ask Coach <ArrowRight className="w-3 h-3" />
        </Link>
      </CardContent>
    </Card>
  );
}


// ── Main Page ───────────────────────────────────────────────────────

export default function HomePage() {
  const { data, isLoading, error } = useHomeData();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen p-4">
          <div className="max-w-xl mx-auto pt-12">
            <Card className="bg-slate-800 border-red-700/50">
              <CardContent className="pt-6">
                <p className="text-slate-400">Could not load data. Try again.</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const {
    today,
    week,
    strava_connected,
    has_any_activities,
    total_activities,
    coach_noticed,
    race_countdown,
    checkin_needed,
    today_checkin,
  } = data;

  const hasAnyData = has_any_activities || week.completed_mi > 0;
  const workoutConfig = getWorkoutConfig(today.workout_type);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">
                {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
              </h1>
            </div>
            <Link
              href="/coach"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-orange-600/20 text-orange-400 hover:bg-orange-600/30 transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" /> Coach
            </Link>
          </div>

          {/* ═══ TIER 1: Above the fold ═══ */}

          {/* Coach Noticed */}
          {coach_noticed && (
            <CoachNoticedCard
              text={coach_noticed.text}
              askQuery={coach_noticed.ask_coach_query}
            />
          )}

          {/* Quick Check-in (only when needed) / Check-in Summary (after) */}
          {checkin_needed && hasAnyData ? (
            <QuickCheckin />
          ) : today_checkin ? (
            <CheckinSummary
              motivation={today_checkin.motivation_label}
              sleep={today_checkin.sleep_label}
              soreness={today_checkin.soreness_label}
            />
          ) : null}

          {/* ═══ TIER 2: Below the fold ═══ */}

          {/* Today */}
          {today.has_workout ? (
            <Card className="bg-slate-800/50 border-slate-700/50">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-orange-500" />
                    <span className="text-sm font-semibold text-slate-300">Today</span>
                  </div>
                  {today.phase && (
                    <Badge variant="outline" className="text-orange-400 border-orange-500/30 text-xs">
                      {today.phase}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pb-4 space-y-3">
                <div className="flex items-start gap-3">
                  <div className={`p-3 rounded-xl ${workoutConfig.bgColor} ${workoutConfig.color} ring-1 ring-white/10`}>
                    {workoutConfig.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-lg font-bold ${workoutConfig.color}`}>
                      {today.title || formatWorkoutType(today.workout_type)}
                    </p>
                    <p className="text-sm text-slate-400">
                      {today.distance_mi && <span className="font-medium text-slate-300">{today.distance_mi} mi</span>}
                      {today.distance_mi && today.pace_guidance && <span className="mx-2 text-slate-600">&middot;</span>}
                      {today.pace_guidance && <span>{today.pace_guidance}</span>}
                    </p>
                  </div>
                </div>
                {today.why_context && (
                  <div className="bg-slate-700/40 rounded-lg p-3 border border-slate-600/40">
                    <div className="flex gap-2">
                      <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-slate-300">{today.why_context}</p>
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between pt-1">
                  <div className="text-xs text-slate-500">
                    {today.week_number && <span>Week {today.week_number}</span>}
                  </div>
                  <Link
                    href={`/coach?q=${encodeURIComponent(`Tell me about today's ${formatWorkoutType(today.workout_type) || 'workout'}`)}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-orange-400 hover:text-orange-300"
                  >
                    Ask Coach <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="bg-slate-800/50 border-slate-700/50">
              <CardContent className="py-5 px-5">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-slate-700 ring-1 ring-slate-600">
                    <Clock className="w-5 h-5 text-slate-500" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-slate-400">No workout scheduled</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {hasAnyData
                        ? 'Recovery day.'
                        : strava_connected
                          ? 'Create a plan to see workouts.'
                          : 'Connect Strava or create a plan.'}
                    </p>
                  </div>
                  <Link
                    href="/coach?q=What%20should%20I%20do%20today%3F"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-orange-400 hover:text-orange-300 flex-shrink-0"
                  >
                    Ask Coach <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          )}

          {/* This Week */}
          <Card className="bg-slate-800/50 border-slate-700/50">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-semibold text-slate-300">This Week</span>
                </div>
                {week.week_number && week.total_weeks ? (
                  <span className="text-xs text-slate-500">
                    Week {week.week_number}/{week.total_weeks}
                  </span>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="pb-4 space-y-3">
              {/* Day chips */}
              <div className="flex justify-between gap-1">
                {week.days.map((day) => {
                  const dayConfig = getWorkoutConfig(day.workout_type);
                  const linkHref = day.activity_id
                    ? `/activities/${day.activity_id}`
                    : day.workout_id
                      ? `/calendar?date=${day.date}`
                      : null;

                  const chip = (
                    <>
                      <div className={`text-[10px] uppercase mb-1 ${day.is_today ? 'text-orange-400 font-semibold' : 'text-slate-500'}`}>
                        {day.day_abbrev}
                      </div>
                      <div className={`text-xs font-semibold ${day.completed ? 'text-emerald-400' : dayConfig.color}`}>
                        {day.completed && day.distance_mi ? (
                          <span className="flex flex-col items-center gap-0.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span className="text-[10px]">{day.distance_mi}</span>
                          </span>
                        ) : day.workout_type === 'rest' ? (
                          <span className="text-slate-600">&mdash;</span>
                        ) : day.distance_mi ? (
                          <span>{day.distance_mi}</span>
                        ) : (
                          <span className="text-slate-600">&mdash;</span>
                        )}
                      </div>
                    </>
                  );

                  const cls = `flex-1 text-center py-2.5 px-0.5 rounded-lg transition-all ${
                    day.is_today ? 'ring-2 ring-orange-500 bg-orange-500/10' : ''
                  } ${day.completed ? 'bg-emerald-500/15 border border-emerald-500/25' : 'bg-slate-700/50 border border-transparent'
                  } ${linkHref ? 'cursor-pointer hover:bg-slate-600/50' : ''}`;

                  return linkHref ? (
                    <Link key={day.date} href={linkHref} className={cls}>{chip}</Link>
                  ) : (
                    <div key={day.date} className={cls}>{chip}</div>
                  );
                })}
              </div>

              {/* Progress / Volume */}
              {week.status === 'no_plan' ? (
                <div className="text-center py-1">
                  {week.completed_mi > 0 ? (
                    <>
                      <div className="flex items-center justify-center gap-2 mb-1">
                        <Footprints className="w-4 h-4 text-orange-500" />
                        <span className="text-lg font-bold text-white">{week.completed_mi} mi</span>
                        <span className="text-xs text-slate-500">logged</span>
                      </div>
                      {week.trajectory_sentence && (
                        <p className="text-xs text-slate-400">{week.trajectory_sentence}</p>
                      )}
                    </>
                  ) : (
                    <p className="text-sm text-slate-500">
                      {strava_connected
                        ? total_activities > 0 ? 'No runs this week yet.' : 'Waiting for sync.'
                        : 'Connect Strava to track.'}
                    </p>
                  )}
                </div>
              ) : (
                <>
                  {week.planned_mi > 0 && (
                    <Progress
                      value={Math.min(100, week.progress_pct)}
                      className="h-2"
                      indicatorClassName={
                        week.status === 'ahead' ? 'bg-emerald-500'
                          : week.status === 'on_track' ? 'bg-blue-500'
                            : 'bg-orange-500'
                      }
                    />
                  )}
                  <div className="flex items-center justify-between">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-lg font-bold text-white">{week.completed_mi}</span>
                      <span className="text-sm text-slate-500">/ {week.planned_mi} mi</span>
                    </div>
                    {getStatusBadge(week.status)}
                  </div>
                  {week.trajectory_sentence && (
                    <p className="text-xs text-slate-400 pt-1 border-t border-slate-700/50">
                      {week.trajectory_sentence}
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Race Countdown */}
          {race_countdown && (
            <RaceCountdownCard
              raceName={race_countdown.race_name ?? undefined}
              raceDate={race_countdown.race_date}
              daysRemaining={race_countdown.days_remaining}
              goalTime={race_countdown.goal_time ?? undefined}
              goalPace={race_countdown.goal_pace ?? undefined}
              predictedTime={race_countdown.predicted_time ?? undefined}
            />
          )}

        </div>
      </div>
    </ProtectedRoute>
  );
}
