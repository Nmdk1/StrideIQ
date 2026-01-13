'use client';

/**
 * Home Page - The Glance Layer
 * 
 * Premium UI powered by shadcn/ui + Lucide + Tailwind
 * 
 * What athletes see when they log in:
 * - Today's workout + why it matters
 * - Yesterday's insight (one key takeaway)
 * - Week progress at a glance
 * 
 * TONE: Sparse, direct, data-driven. No prescriptiveness.
 * EMPTY STATES: Helpful, action-oriented, no guilt.
 */

import React from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useHomeData } from '@/lib/hooks/queries/home';
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
  Flame
} from 'lucide-react';

// Workout type colors and icons
const WORKOUT_CONFIG: Record<string, { color: string; bgColor: string; icon: React.ReactNode }> = {
  rest: { color: 'text-slate-400', bgColor: 'bg-slate-500/10', icon: <Clock className="w-5 h-5" /> },
  recovery: { color: 'text-slate-400', bgColor: 'bg-slate-500/10', icon: <Clock className="w-5 h-5" /> },
  easy: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', icon: <Footprints className="w-5 h-5" /> },
  easy_strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', icon: <Zap className="w-5 h-5" /> },
  strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', icon: <Zap className="w-5 h-5" /> },
  medium_long: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', icon: <TrendingUp className="w-5 h-5" /> },
  long: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', icon: <TrendingUp className="w-5 h-5" /> },
  long_mp: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', icon: <Target className="w-5 h-5" /> },
  threshold: { color: 'text-orange-400', bgColor: 'bg-orange-500/10', icon: <Flame className="w-5 h-5" /> },
  tempo: { color: 'text-orange-400', bgColor: 'bg-orange-500/10', icon: <Flame className="w-5 h-5" /> },
  intervals: { color: 'text-red-400', bgColor: 'bg-red-500/10', icon: <Activity className="w-5 h-5" /> },
  vo2max: { color: 'text-red-400', bgColor: 'bg-red-500/10', icon: <Activity className="w-5 h-5" /> },
  race: { color: 'text-pink-400', bgColor: 'bg-pink-500/10', icon: <Target className="w-5 h-5" /> },
};

function getWorkoutConfig(type?: string) {
  if (!type) return { color: 'text-slate-400', bgColor: 'bg-slate-500/10', icon: <Footprints className="w-5 h-5" /> };
  return WORKOUT_CONFIG[type] || { color: 'text-slate-400', bgColor: 'bg-slate-500/10', icon: <Footprints className="w-5 h-5" /> };
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
      return <Badge variant="success" className="gap-1"><TrendingUp className="w-3 h-3" /> Ahead</Badge>;
    case 'on_track':
      return <Badge variant="info" className="gap-1"><CheckCircle2 className="w-3 h-3" /> On Track</Badge>;
    case 'behind':
      return <Badge variant="warning" className="gap-1"><Clock className="w-3 h-3" /> Behind</Badge>;
    default:
      return null;
  }
}

export default function HomePage() {
  const { data, isLoading, error } = useHomeData();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-background">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-background text-foreground p-4">
          <div className="max-w-2xl mx-auto pt-12">
            <Card className="border-destructive/50 bg-destructive/5">
              <CardContent className="pt-6">
                <p className="text-muted-foreground">Could not load data. Try again.</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const { today, yesterday, week, strava_connected, has_any_activities, total_activities } = data;
  
  // Determine user state for conditional rendering
  const isStravaConnected = strava_connected;
  const hasAnyData = has_any_activities || yesterday.has_activity || week.completed_mi > 0;
  
  // Show welcome card only for users who haven't connected Strava AND have no data
  const showWelcomeCard = !isStravaConnected && !hasAnyData;
  
  // Has last activity info (for showing "last ran X days ago")
  const hasLastActivity = yesterday.last_activity_date && yesterday.days_since_last !== undefined;

  const workoutConfig = getWorkoutConfig(today.workout_type);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-b from-background via-background to-background/95">
        <div className="max-w-2xl mx-auto px-4 py-6 md:py-10 space-y-6">
          
          {/* New User Onboarding Banner */}
          {showWelcomeCard && (
            <Card className="border-orange-500/30 bg-gradient-to-br from-orange-950/40 via-orange-900/20 to-background overflow-hidden relative">
              <div className="absolute inset-0 bg-gradient-to-r from-orange-500/5 to-transparent" />
              <CardHeader className="relative">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 rounded-lg bg-orange-500/20">
                    <Zap className="w-5 h-5 text-orange-400" />
                  </div>
                  <CardTitle className="text-lg text-orange-300">Welcome to StrideIQ</CardTitle>
                </div>
                <CardDescription className="text-slate-300 text-sm leading-relaxed">
                  Connect your Strava account to import your runs. We&apos;ll analyze your data and show you what&apos;s actually working.
                </CardDescription>
              </CardHeader>
              <CardContent className="relative flex flex-wrap gap-3">
                <Button asChild className="bg-orange-600 hover:bg-orange-500">
                  <Link href="/settings">Connect Strava</Link>
                </Button>
                <Button asChild variant="secondary">
                  <Link href="/calendar">Create Training Plan</Link>
                </Button>
              </CardContent>
            </Card>
          )}
          
          {/* Today's Workout - Hero Section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Calendar className="w-4 h-4" />
                <span className="text-xs uppercase tracking-wider font-medium">
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                </span>
              </div>
              {today.phase && (
                <Badge variant="outline" className="text-orange-400 border-orange-500/30">
                  {today.phase}
                </Badge>
              )}
            </div>
            
            {today.has_workout ? (
              <Card className={`border-l-4 ${workoutConfig.color.replace('text-', 'border-')} bg-gradient-to-br from-card via-card to-card/80`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-3 rounded-xl ${workoutConfig.bgColor} ${workoutConfig.color}`}>
                        {workoutConfig.icon}
                      </div>
                      <div>
                        <CardTitle className={`text-2xl md:text-3xl ${workoutConfig.color}`}>
                          {today.title || formatWorkoutType(today.workout_type)}
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {today.distance_mi && `${today.distance_mi} mi`}
                          {today.distance_mi && today.pace_guidance && ' · '}
                          {today.pace_guidance}
                        </CardDescription>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                
                {today.why_context && (
                  <CardContent className="pt-0 pb-4">
                    <div className="bg-secondary/50 rounded-lg p-4 border border-border/50">
                      <p className="text-sm text-foreground/80 leading-relaxed">{today.why_context}</p>
                    </div>
                  </CardContent>
                )}
                
                <CardContent className="pt-0">
                  <div className="flex items-center justify-between border-t border-border/50 pt-4">
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      {today.week_number && (
                        <span className="flex items-center gap-1.5">
                          <Target className="w-4 h-4" />
                          Week {today.week_number}
                        </span>
                      )}
                    </div>
                    <Button asChild variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                      <Link href="/calendar">
                        View in Calendar <ArrowRight className="w-4 h-4 ml-1" />
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-gradient-to-br from-card via-card to-secondary/20">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-3 rounded-xl bg-secondary">
                      <Clock className="w-5 h-5 text-muted-foreground" />
                    </div>
                    <div>
                      <CardTitle className="text-xl md:text-2xl text-muted-foreground">
                        No workout scheduled
                      </CardTitle>
                      <CardDescription className="mt-1">
                        {hasAnyData 
                          ? "Good day for easy recovery or complete rest. Your call."
                          : isStravaConnected
                            ? "Create a training plan to see workouts here."
                            : "Connect Strava or create a plan to see workouts here."
                        }
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 flex flex-wrap gap-3">
                  <Button asChild variant="secondary" size="sm">
                    <Link href="/calendar">
                      {hasAnyData ? 'View Calendar' : 'Create Plan'} <ArrowRight className="w-4 h-4 ml-1" />
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
          </section>
          
          {/* Yesterday's Insight */}
          <section>
            <div className="flex items-center gap-2 text-muted-foreground mb-3">
              <Activity className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider font-medium">Yesterday</span>
            </div>
            
            {yesterday.has_activity ? (
              <Card className="bg-gradient-to-br from-card via-card to-emerald-950/20 border-l-4 border-emerald-500/50">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-emerald-500/10">
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{yesterday.activity_name}</CardTitle>
                        <CardDescription>
                          {yesterday.distance_mi && `${yesterday.distance_mi} mi`}
                          {yesterday.distance_mi && yesterday.pace_per_mi && ' · '}
                          {yesterday.pace_per_mi}
                        </CardDescription>
                      </div>
                    </div>
                    {yesterday.activity_id && (
                      <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
                        <Link href={`/activities/${yesterday.activity_id}`}>
                          Details <ArrowRight className="w-4 h-4 ml-1" />
                        </Link>
                      </Button>
                    )}
                  </div>
                </CardHeader>
                
                {yesterday.insight && (
                  <CardContent className="pt-2">
                    <p className="text-sm text-foreground/80 leading-relaxed">{yesterday.insight}</p>
                  </CardContent>
                )}
              </Card>
            ) : (
              <Card className="bg-card/50">
                <CardContent className="py-4">
                  {hasLastActivity ? (
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-secondary">
                          <Footprints className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">No activity yesterday</p>
                          <p className="text-xs text-muted-foreground/70 mt-0.5">
                            Last ran {yesterday.days_since_last === 1 
                              ? 'the day before' 
                              : `${yesterday.days_since_last} days ago`
                            }: {yesterday.last_activity_name}
                          </p>
                        </div>
                      </div>
                      {yesterday.last_activity_id && (
                        <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
                          <Link href={`/activities/${yesterday.last_activity_id}`}>
                            View <ArrowRight className="w-4 h-4 ml-1" />
                          </Link>
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-secondary">
                        <Clock className="w-5 h-5 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">No activity yesterday</p>
                        <p className="text-xs text-muted-foreground/70 mt-0.5">
                          {isStravaConnected
                            ? "Waiting for activities to sync."
                            : "Connect Strava to see insights."
                          }
                        </p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </section>
          
          {/* Week Progress */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-muted-foreground">
                <BarChart3 className="w-4 h-4" />
                <span className="text-xs uppercase tracking-wider font-medium">This Week</span>
              </div>
              {week.week_number && week.total_weeks && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    Week {week.week_number}/{week.total_weeks}
                  </span>
                  {week.phase && (
                    <Badge variant="outline" className="text-orange-400 border-orange-500/30 text-xs">
                      {week.phase}
                    </Badge>
                  )}
                </div>
              )}
            </div>
            
            <Card className="bg-gradient-to-br from-card via-card to-secondary/10">
              <CardContent className="pt-6">
                {/* Day Pills - Visual week overview */}
                <div className="flex justify-between gap-1.5 mb-6">
                  {week.days.map((day) => {
                    const dayConfig = getWorkoutConfig(day.workout_type);
                    return (
                      <div 
                        key={day.date}
                        className={`
                          flex-1 text-center py-3 px-1 rounded-xl transition-all
                          ${day.is_today ? 'ring-2 ring-primary/50 bg-primary/10' : ''}
                          ${day.completed ? 'bg-emerald-500/15 border border-emerald-500/20' : 'bg-secondary/50 border border-transparent'}
                        `}
                      >
                        <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
                          {day.day_abbrev}
                        </div>
                        <div className={`text-sm font-semibold ${day.completed ? 'text-emerald-400' : dayConfig.color}`}>
                          {day.completed && day.distance_mi ? (
                            <span className="flex flex-col items-center">
                              <CheckCircle2 className="w-4 h-4 mb-0.5" />
                              <span className="text-xs">{day.distance_mi}</span>
                            </span>
                          ) : day.workout_type === 'rest' ? (
                            <span className="text-muted-foreground/50">—</span>
                          ) : day.distance_mi ? (
                            <span>{day.distance_mi}</span>
                          ) : (
                            <span className="text-muted-foreground/50">—</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
                
                {week.status === 'no_plan' ? (
                  /* Empty state for no plan */
                  <div className="text-center py-2">
                    {week.completed_mi > 0 ? (
                      <>
                        <div className="flex items-center justify-center gap-2 mb-2">
                          <Footprints className="w-5 h-5 text-primary" />
                          <span className="text-xl font-semibold text-foreground">
                            {week.completed_mi} mi
                          </span>
                          <span className="text-sm text-muted-foreground">this week</span>
                        </div>
                        {week.trajectory_sentence && (
                          <p className="text-sm text-muted-foreground mb-4">{week.trajectory_sentence}</p>
                        )}
                        <Button asChild variant="secondary" size="sm">
                          <Link href="/calendar">
                            Create a plan to track against <ArrowRight className="w-4 h-4 ml-1" />
                          </Link>
                        </Button>
                      </>
                    ) : (
                      <>
                        <p className="text-sm text-muted-foreground mb-2">No training plan active</p>
                        <p className="text-xs text-muted-foreground/70 mb-4">
                          {isStravaConnected
                            ? total_activities > 0
                              ? "No runs this week yet."
                              : "Waiting for activities to sync."
                            : "Connect Strava to track activities."
                          }
                        </p>
                        <div className="flex justify-center gap-3">
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
                    {/* Progress Bar */}
                    {week.planned_mi > 0 && (
                      <div className="space-y-2 mb-4">
                        <Progress 
                          value={Math.min(100, week.progress_pct)} 
                          className="h-3"
                          indicatorClassName={
                            week.status === 'ahead' ? 'bg-emerald-500' :
                            week.status === 'on_track' ? 'bg-blue-500' :
                            week.status === 'behind' ? 'bg-orange-500' : 'bg-primary'
                          }
                        />
                      </div>
                    )}
                    
                    {/* Stats */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-foreground">
                          {week.completed_mi}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          / {week.planned_mi} mi
                        </span>
                      </div>
                      {getStatusBadge(week.status)}
                    </div>
                    
                    {/* Trajectory sentence */}
                    {week.trajectory_sentence && (
                      <p className="text-sm text-muted-foreground mt-3 border-t border-border/50 pt-3">
                        {week.trajectory_sentence}
                      </p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
            
            {/* Calendar Link */}
            <div className="mt-3 text-right">
              <Button asChild variant="link" size="sm" className="text-muted-foreground hover:text-foreground p-0 h-auto">
                <Link href="/calendar">
                  Full Calendar <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
              </Button>
            </div>
          </section>
          
          {/* Quick Links */}
          <section className="grid grid-cols-2 gap-4">
            <Link href="/analytics" className="group">
              <Card className="h-full bg-gradient-to-br from-card via-card to-blue-950/20 border-blue-500/20 hover:border-blue-500/40 transition-all hover:shadow-lg hover:shadow-blue-500/5">
                <CardContent className="pt-5 pb-5">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 rounded-lg bg-blue-500/10 group-hover:bg-blue-500/20 transition-colors">
                      <BarChart3 className="w-5 h-5 text-blue-400" />
                    </div>
                    <span className="font-medium text-foreground group-hover:text-blue-300 transition-colors">Analytics</span>
                  </div>
                  <p className="text-sm text-muted-foreground">Trends & correlations</p>
                </CardContent>
              </Card>
            </Link>
            <Link href="/coach" className="group">
              <Card className="h-full bg-gradient-to-br from-card via-card to-purple-950/20 border-purple-500/20 hover:border-purple-500/40 transition-all hover:shadow-lg hover:shadow-purple-500/5">
                <CardContent className="pt-5 pb-5">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 rounded-lg bg-purple-500/10 group-hover:bg-purple-500/20 transition-colors">
                      <MessageSquare className="w-5 h-5 text-purple-400" />
                    </div>
                    <span className="font-medium text-foreground group-hover:text-purple-300 transition-colors">Coach</span>
                  </div>
                  <p className="text-sm text-muted-foreground">Ask questions</p>
                </CardContent>
              </Card>
            </Link>
          </section>
          
        </div>
      </div>
    </ProtectedRoute>
  );
}
