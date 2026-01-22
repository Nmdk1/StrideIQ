'use client';

/**
 * Home Page - The Glance Layer
 * 
 * Aligned with Tools/Compare style: slate-800 cards, slate-900 background, orange accents.
 * 
 * TONE: Sparse, direct, data-driven. No prescriptiveness.
 * EMPTY STATES: Helpful, action-oriented, no guilt.
 */

import React from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useHomeData } from '@/lib/hooks/queries/home';
import { useInsightFeed } from '@/lib/hooks/queries/insights';
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
  Home
} from 'lucide-react';
import { SignalsBanner } from '@/components/home/SignalsBanner';
import type { InsightFeedCard } from '@/lib/api/services/insights';

// Workout type colors and icons
const WORKOUT_CONFIG: Record<string, { color: string; bgColor: string; borderColor: string; icon: React.ReactNode }> = {
  rest: { color: 'text-slate-400', bgColor: 'bg-slate-500/20', borderColor: 'border-slate-500', icon: <Clock className="w-6 h-6" /> },
  recovery: { color: 'text-slate-400', bgColor: 'bg-slate-500/20', borderColor: 'border-slate-500', icon: <Clock className="w-6 h-6" /> },
  easy: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', borderColor: 'border-emerald-500', icon: <Footprints className="w-6 h-6" /> },
  easy_strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', borderColor: 'border-emerald-500', icon: <Zap className="w-6 h-6" /> },
  strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', borderColor: 'border-emerald-500', icon: <Zap className="w-6 h-6" /> },
  medium_long: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', borderColor: 'border-blue-500', icon: <TrendingUp className="w-6 h-6" /> },
  long: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', borderColor: 'border-blue-500', icon: <TrendingUp className="w-6 h-6" /> },
  long_mp: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', borderColor: 'border-blue-500', icon: <Target className="w-6 h-6" /> },
  threshold: { color: 'text-orange-400', bgColor: 'bg-orange-500/20', borderColor: 'border-orange-500', icon: <Flame className="w-6 h-6" /> },
  tempo: { color: 'text-orange-400', bgColor: 'bg-orange-500/20', borderColor: 'border-orange-500', icon: <Flame className="w-6 h-6" /> },
  intervals: { color: 'text-red-400', bgColor: 'bg-red-500/20', borderColor: 'border-red-500', icon: <Activity className="w-6 h-6" /> },
  vo2max: { color: 'text-red-400', bgColor: 'bg-red-500/20', borderColor: 'border-red-500', icon: <Activity className="w-6 h-6" /> },
  race: { color: 'text-pink-400', bgColor: 'bg-pink-500/20', borderColor: 'border-pink-500', icon: <Target className="w-6 h-6" /> },
};

function getWorkoutConfig(type?: string) {
  if (!type) return { color: 'text-slate-400', bgColor: 'bg-slate-500/20', borderColor: 'border-slate-500', icon: <Footprints className="w-6 h-6" /> };
  return WORKOUT_CONFIG[type] || { color: 'text-slate-400', bgColor: 'bg-slate-500/20', borderColor: 'border-slate-500', icon: <Footprints className="w-6 h-6" /> };
}

function formatWorkoutType(type?: string): string {
  if (!type) return '';
  const labels: Record<string, string> = {
    easy: 'Easy Run',
    easy_strides: 'Easy + Strides',
    strides: 'Strides',
    medium_long: 'Medium Long',
    long: 'Long Run',
    long_mp: 'Long + MP',
    threshold: 'Threshold',
    tempo: 'Tempo',
    intervals: 'Intervals',
    vo2max: 'VO2max',
    rest: 'Rest Day',
    recovery: 'Recovery',
    race: 'Race Day',
  };
  return labels[type] || type.replace(/_/g, ' ');
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'ahead':
      return <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 gap-1 text-xs"><TrendingUp className="w-3 h-3" /> Ahead</Badge>;
    case 'on_track':
      return <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 gap-1 text-xs"><CheckCircle2 className="w-3 h-3" /> On Track</Badge>;
    case 'behind':
      return <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 gap-1 text-xs"><Clock className="w-3 h-3" /> Behind</Badge>;
    default:
      return null;
  }
}

function ConfidenceBadge({ card }: { card: InsightFeedCard }) {
  const label = (card.confidence?.label || 'insufficient').toLowerCase();
  const cls =
    label === 'high'
      ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30'
      : label === 'moderate'
        ? 'bg-yellow-600/20 text-yellow-300 border-yellow-500/30'
        : label === 'low'
          ? 'bg-orange-600/20 text-orange-300 border-orange-500/30'
          : 'bg-slate-700/40 text-slate-300 border-slate-600/40';
  return <span className={`text-xs px-2 py-0.5 rounded border ${cls}`}>{label} confidence</span>;
}

function TopInsightsPreview({
  hasAnyData,
}: {
  hasAnyData: boolean;
}) {
  const { data, isLoading, error } = useInsightFeed(3);

  if (!hasAnyData) return null;

  if (isLoading) {
    return (
      <Card className="bg-slate-800/50 border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-slate-300">Top insights</CardTitle>
          <CardDescription>Ranked engine output</CardDescription>
        </CardHeader>
        <CardContent className="py-6 flex justify-center">
          <LoadingSpinner />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-slate-800/50 border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-slate-300">Top insights</CardTitle>
          <CardDescription>Ranked engine output</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-slate-500">
          Unable to load insights right now.
        </CardContent>
      </Card>
    );
  }

  const cards = data?.cards || [];
  if (!cards.length) {
    return (
      <Card className="bg-slate-800/50 border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-slate-300">Top insights</CardTitle>
          <CardDescription>Ranked engine output</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-slate-500">
          No insights yet. Sync a few HR runs and we’ll start ranking what matters.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-orange-400" />
              Top insights
            </CardTitle>
            <CardDescription>Ranked engine output</CardDescription>
          </div>
          <Button asChild variant="ghost" size="sm" className="text-slate-400 hover:text-white">
            <Link href="/insights">
              Open <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {cards.slice(0, 2).map((card) => (
          <div key={card.key} className="rounded-lg border border-slate-700/60 bg-slate-900/30 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] uppercase tracking-wide text-slate-500">
                    {card.type.replace(/_/g, ' ')}
                  </span>
                  <ConfidenceBadge card={card} />
                </div>
                <div className="text-sm font-semibold text-white truncate">{card.title}</div>
                <div className="text-xs text-slate-400 mt-1 line-clamp-2">{card.summary}</div>
              </div>
              {card.actions?.[0]?.href ? (
                <a
                  href={card.actions[0].href}
                  className="shrink-0 px-2.5 py-2 bg-slate-800/60 border border-slate-700/60 hover:border-slate-600 rounded-lg text-xs font-medium text-slate-200 transition-colors"
                >
                  {card.actions[0].label}
                </a>
              ) : null}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function HomePage() {
  const { data, isLoading, error } = useHomeData();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-slate-900">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 text-slate-100 p-4">
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

  const { today, yesterday, week, hero_narrative, strava_connected, has_any_activities, total_activities } = data;

  const isStravaConnected = strava_connected;
  const hasAnyData = has_any_activities || yesterday.has_activity || week.completed_mi > 0;
  const showWelcomeCard = !isStravaConnected && !hasAnyData;
  const hasLastActivity = yesterday.last_activity_date && yesterday.days_since_last !== undefined;
  const workoutConfig = getWorkoutConfig(today.workout_type);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
          
          {/* Header */}
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
              <Home className="w-6 h-6 text-orange-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Home</h1>
              <p className="text-sm text-slate-400">
                {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
              </p>
            </div>
          </div>
          
          {/* Welcome Banner - New Users */}
          {showWelcomeCard && (
            <Card className="bg-gradient-to-r from-orange-500/10 to-pink-500/10 border-orange-500/30">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3 mb-1">
                  <div className="p-2 bg-orange-500/20 rounded-lg ring-1 ring-orange-500/30">
                    <Zap className="w-5 h-5 text-orange-500" />
                  </div>
                  <CardTitle className="text-lg text-orange-300">Welcome to StrideIQ</CardTitle>
                </div>
                <CardDescription className="text-slate-300">
                  Connect Strava to import your runs. We&apos;ll show you what&apos;s actually working.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2 pt-0">
                <Button asChild className="bg-orange-600 hover:bg-orange-500">
                  <Link href="/settings">Connect Strava</Link>
                </Button>
                <Button asChild variant="outline" className="border-slate-600 hover:bg-slate-800">
                  <Link href="/calendar">Create Plan</Link>
                </Button>
              </CardContent>
            </Card>
          )}
          
          {/* Signals Banner - Analytics Insights (only for users with data) */}
          {hasAnyData && !showWelcomeCard && (
            <SignalsBanner />
          )}

          {/* Hero Narrative - ADR-033: First-3-seconds impact */}
          {hero_narrative && hasAnyData && (
            <div className="px-4 py-3 bg-slate-800/50 border border-slate-700/50 rounded-lg">
              <p className="text-sm text-slate-300 italic leading-relaxed">
                &ldquo;{hero_narrative}&rdquo;
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
            {/* Row 1, Col 1: Today */}
            <div>
              {today.has_workout ? (
                <Card className="bg-slate-800/50 border-slate-700/50 h-full">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-orange-500" />
                        <span className="text-sm font-semibold text-slate-300">Today</span>
                      </div>
                      {today.phase ? (
                        <Badge variant="outline" className="text-orange-400 border-orange-500/30 text-xs">
                          {today.phase}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="h-px bg-slate-700/50 my-3" />
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-xl ${workoutConfig.bgColor} ${workoutConfig.color} ring-1 ring-white/10`}>
                        {workoutConfig.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <CardTitle className={`text-xl md:text-2xl font-bold ${workoutConfig.color}`}>
                          {today.title || formatWorkoutType(today.workout_type)}
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {today.distance_mi && <span className="font-medium text-slate-300">{today.distance_mi} mi</span>}
                          {today.distance_mi && today.pace_guidance && <span className="mx-2 text-slate-600">·</span>}
                          {today.pace_guidance && <span className="text-slate-400">{today.pace_guidance}</span>}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  {today.why_context && (
                    <CardContent className="pt-2 pb-3">
                      <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600/50">
                        <div className="flex gap-2">
                          <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                          <p className="text-sm text-slate-300">{today.why_context}</p>
                        </div>
                      </div>
                    </CardContent>
                  )}
                  <CardContent className="pt-0 pb-4">
                    <div className="flex items-center justify-between border-t border-slate-700 pt-3">
                      <div className="flex items-center gap-3 text-sm text-slate-500">
                        {today.week_number && (
                          <span className="flex items-center gap-1.5">
                            <Target className="w-3.5 h-3.5" />
                            Week {today.week_number}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button asChild variant="ghost" size="sm" className="text-slate-400 hover:text-white">
                          <Link href="/calendar">
                            Calendar <ArrowRight className="w-3.5 h-3.5 ml-1" />
                          </Link>
                        </Button>
                        <Button asChild variant="ghost" size="sm" className="text-slate-400 hover:text-white">
                          <Link href="/coach">
                            Coach <ArrowRight className="w-3.5 h-3.5 ml-1" />
                          </Link>
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card className="bg-slate-800/50 border-slate-700/50 h-full">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-orange-500" />
                        <span className="text-sm font-semibold text-slate-300">Today</span>
                      </div>
                      {today.phase ? (
                        <Badge variant="outline" className="text-orange-400 border-orange-500/30 text-xs">
                          {today.phase}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="h-px bg-slate-700/50 my-3" />
                    <div className="flex items-start gap-4">
                      <div className="p-3 rounded-xl bg-slate-700 ring-1 ring-slate-600">
                        <Clock className="w-6 h-6 text-slate-500" />
                      </div>
                      <div>
                        <CardTitle className="text-xl text-slate-400">No workout scheduled</CardTitle>
                        <CardDescription className="mt-1">
                          {hasAnyData
                            ? "Recovery day. Your call."
                            : isStravaConnected
                              ? "Create a plan to see workouts."
                              : "Connect Strava or create a plan."}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0 pb-4 flex flex-wrap gap-2">
                    <Button asChild variant="secondary" size="sm">
                      <Link href="/calendar">
                        {hasAnyData ? 'Calendar' : 'Create Plan'} <ArrowRight className="w-3.5 h-3.5 ml-1" />
                      </Link>
                    </Button>
                    <Button asChild variant="secondary" size="sm">
                      <Link href="/coach">
                        Ask the coach <ArrowRight className="w-3.5 h-3.5 ml-1" />
                      </Link>
                    </Button>
                    {!isStravaConnected && !hasAnyData && (
                      <Button asChild variant="ghost" size="sm" className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10">
                        <Link href="/settings">Connect Strava</Link>
                      </Button>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Row 1, Col 2: Top insights */}
            <div>
              <TopInsightsPreview hasAnyData={hasAnyData && !showWelcomeCard} />
            </div>

            {/* Row 2, Col 1: This week */}
            <div>
              <Card className="bg-slate-800/50 border-slate-700/50 h-full">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-blue-500" />
                      <span className="text-sm font-semibold text-slate-300">This Week</span>
                    </div>
                    {week.week_number && week.total_weeks ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">
                          Week {week.week_number}/{week.total_weeks}
                        </span>
                        {week.phase ? (
                          <Badge variant="outline" className="text-orange-400 border-orange-500/30 text-xs">
                            {week.phase}
                          </Badge>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </CardHeader>
                <CardContent className="pt-4 pb-4">
                  <div className="flex justify-between gap-1 mb-4">
                    {week.days.map((day) => {
                      const dayConfig = getWorkoutConfig(day.workout_type);
                      return (
                        <div
                          key={day.date}
                          className={`
                            flex-1 text-center py-2.5 px-0.5 rounded-lg transition-all
                            ${day.is_today ? 'ring-2 ring-orange-500 bg-orange-500/10' : ''}
                            ${day.completed ? 'bg-emerald-500/15 border border-emerald-500/25' : 'bg-slate-700/50 border border-transparent'}
                          `}
                        >
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
                              <span className="text-slate-600">—</span>
                            ) : day.distance_mi ? (
                              <span>{day.distance_mi}</span>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {week.status === 'no_plan' ? (
                    <div className="text-center py-2">
                      {week.completed_mi > 0 ? (
                        <>
                          <div className="flex items-center justify-center gap-2 mb-1.5">
                            <Footprints className="w-5 h-5 text-orange-500" />
                            <span className="text-xl font-bold text-white">{week.completed_mi} mi</span>
                            <span className="text-sm text-slate-500">logged</span>
                          </div>
                          {week.trajectory_sentence && (
                            <p className="text-xs text-slate-400 mb-3">{week.trajectory_sentence}</p>
                          )}
                          <Button asChild variant="secondary" size="sm">
                            <Link href="/calendar">
                              Track with a plan <ArrowRight className="w-3.5 h-3.5 ml-1" />
                            </Link>
                          </Button>
                        </>
                      ) : (
                        <>
                          <p className="text-sm text-slate-500 mb-1">No plan active</p>
                          <p className="text-xs text-slate-600 mb-3">
                            {isStravaConnected
                              ? total_activities > 0
                                ? "No runs this week yet."
                                : "Waiting for sync."
                              : "Connect Strava to track."}
                          </p>
                          <div className="flex justify-center gap-2">
                            <Button asChild variant="secondary" size="sm">
                              <Link href="/calendar">Create Plan</Link>
                            </Button>
                            {!isStravaConnected && (
                              <Button asChild variant="ghost" size="sm" className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10">
                                <Link href="/settings">Connect Strava</Link>
                              </Button>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <>
                      {week.planned_mi > 0 && (
                        <div className="mb-3">
                          <Progress
                            value={Math.min(100, week.progress_pct)}
                            className="h-2.5"
                            indicatorClassName={
                              week.status === 'ahead'
                                ? 'bg-emerald-500'
                                : week.status === 'on_track'
                                  ? 'bg-blue-500'
                                  : week.status === 'behind'
                                    ? 'bg-orange-500'
                                    : 'bg-orange-500'
                            }
                          />
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-lg font-bold text-white">{week.completed_mi}</span>
                          <span className="text-sm text-slate-500">/ {week.planned_mi} mi</span>
                        </div>
                        {getStatusBadge(week.status)}
                      </div>
                      {week.trajectory_sentence && (
                        <p className="text-xs text-slate-400 mt-3 pt-3 border-t border-slate-700">
                          {week.trajectory_sentence}
                        </p>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Row 2, Col 2: Quick access + Yesterday */}
            <div>
              <div className="flex flex-col gap-6 h-full">
                <Card className="bg-slate-800/50 border-slate-700/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm text-slate-300">Quick access</CardTitle>
                    <CardDescription>Shortcuts</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-2">
                      <Button asChild variant="outline" size="sm" className="border-slate-700 hover:bg-slate-800 justify-start">
                        <Link href="/calendar">
                          <Calendar className="w-4 h-4 mr-2" /> Calendar
                        </Link>
                      </Button>
                      <Button asChild variant="outline" size="sm" className="border-slate-700 hover:bg-slate-800 justify-start">
                        <Link href="/coach">
                          <MessageSquare className="w-4 h-4 mr-2" /> Coach
                        </Link>
                      </Button>
                      <Button asChild variant="outline" size="sm" className="border-slate-700 hover:bg-slate-800 justify-start">
                        <Link href="/analytics">
                          <BarChart3 className="w-4 h-4 mr-2" /> Analytics
                        </Link>
                      </Button>
                      <Button asChild variant="outline" size="sm" className="border-slate-700 hover:bg-slate-800 justify-start">
                        <Link href="/personal-bests">
                          <Target className="w-4 h-4 mr-2" /> PBs
                        </Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-slate-800/50 border-slate-700/50 flex-1">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-500" />
                      <CardTitle className="text-sm text-slate-300">Yesterday</CardTitle>
                    </div>
                    <CardDescription>Most recent activity</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {yesterday.has_activity ? (
                      <div className="rounded-lg border border-slate-700/60 bg-slate-900/30 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 min-w-0">
                            <div className="p-2 rounded-lg bg-emerald-500/10 ring-1 ring-emerald-500/20">
                              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold text-white truncate">{yesterday.activity_name}</p>
                              <p className="text-sm text-slate-400 mt-0.5">
                                {yesterday.distance_mi && <span>{yesterday.distance_mi} mi</span>}
                                {yesterday.distance_mi && yesterday.pace_per_mi && <span className="mx-1.5 text-slate-600">·</span>}
                                {yesterday.pace_per_mi}
                              </p>
                              {yesterday.insight && <p className="text-sm text-slate-300 mt-2">{yesterday.insight}</p>}
                            </div>
                          </div>
                          {yesterday.activity_id && (
                            <Button asChild variant="ghost" size="icon" className="text-slate-400 hover:text-white">
                              <Link href={`/activities/${yesterday.activity_id}`}>
                                <ArrowRight className="w-4 h-4" />
                              </Link>
                            </Button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-lg border border-slate-700/60 bg-slate-900/30 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="p-2 rounded-lg bg-slate-700 ring-1 ring-slate-600">
                              <Footprints className="w-4 h-4 text-slate-500" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-slate-400">No activity yesterday</p>
                              <p className="text-xs text-slate-500 mt-0.5">
                                {hasLastActivity
                                  ? `Last ran ${yesterday.days_since_last === 1 ? 'the day before' : `${yesterday.days_since_last} days ago`}`
                                  : isStravaConnected
                                    ? "Waiting for sync."
                                    : "Connect Strava to see insights."}
                              </p>
                            </div>
                          </div>
                          {hasLastActivity && yesterday.last_activity_id && (
                            <Button asChild variant="ghost" size="icon" className="text-slate-500 hover:text-white">
                              <Link href={`/activities/${yesterday.last_activity_id}`}>
                                <ArrowRight className="w-4 h-4" />
                              </Link>
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
          
        </div>
      </div>
    </ProtectedRoute>
  );
}
