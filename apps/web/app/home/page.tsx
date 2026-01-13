'use client';

/**
 * Home Page - The Glance Layer (Premium Edition)
 * 
 * Million-dollar SaaS feel with:
 * - Subtle grid background + gradient
 * - Fade-in animations
 * - Hover micro-interactions
 * - Strong visual hierarchy
 * - Tighter spacing
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
  Flame,
  Sparkles
} from 'lucide-react';

// Workout type colors and icons
const WORKOUT_CONFIG: Record<string, { color: string; bgColor: string; borderColor: string; icon: React.ReactNode }> = {
  rest: { color: 'text-slate-400', bgColor: 'bg-slate-500/10', borderColor: 'border-slate-500', icon: <Clock className="w-6 h-6" /> },
  recovery: { color: 'text-slate-400', bgColor: 'bg-slate-500/10', borderColor: 'border-slate-500', icon: <Clock className="w-6 h-6" /> },
  easy: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', borderColor: 'border-emerald-500', icon: <Footprints className="w-6 h-6" /> },
  easy_strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', borderColor: 'border-emerald-500', icon: <Zap className="w-6 h-6" /> },
  strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', borderColor: 'border-emerald-500', icon: <Zap className="w-6 h-6" /> },
  medium_long: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500', icon: <TrendingUp className="w-6 h-6" /> },
  long: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500', icon: <TrendingUp className="w-6 h-6" /> },
  long_mp: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500', icon: <Target className="w-6 h-6" /> },
  threshold: { color: 'text-orange-400', bgColor: 'bg-orange-500/10', borderColor: 'border-orange-500', icon: <Flame className="w-6 h-6" /> },
  tempo: { color: 'text-orange-400', bgColor: 'bg-orange-500/10', borderColor: 'border-orange-500', icon: <Flame className="w-6 h-6" /> },
  intervals: { color: 'text-red-400', bgColor: 'bg-red-500/10', borderColor: 'border-red-500', icon: <Activity className="w-6 h-6" /> },
  vo2max: { color: 'text-red-400', bgColor: 'bg-red-500/10', borderColor: 'border-red-500', icon: <Activity className="w-6 h-6" /> },
  race: { color: 'text-pink-400', bgColor: 'bg-pink-500/10', borderColor: 'border-pink-500', icon: <Target className="w-6 h-6" /> },
};

function getWorkoutConfig(type?: string) {
  if (!type) return { color: 'text-slate-400', bgColor: 'bg-slate-500/10', borderColor: 'border-slate-500', icon: <Footprints className="w-6 h-6" /> };
  return WORKOUT_CONFIG[type] || { color: 'text-slate-400', bgColor: 'bg-slate-500/10', borderColor: 'border-slate-500', icon: <Footprints className="w-6 h-6" /> };
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
      return <Badge variant="success" className="gap-1 text-xs"><TrendingUp className="w-3 h-3" /> Ahead</Badge>;
    case 'on_track':
      return <Badge variant="info" className="gap-1 text-xs"><CheckCircle2 className="w-3 h-3" /> On Track</Badge>;
    case 'behind':
      return <Badge variant="warning" className="gap-1 text-xs"><Clock className="w-3 h-3" /> Behind</Badge>;
    default:
      return null;
  }
}

export default function HomePage() {
  const { data, isLoading, error } = useHomeData();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-[#0a0a0f] text-foreground p-4">
          <div className="max-w-xl mx-auto pt-12">
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
  
  const isStravaConnected = strava_connected;
  const hasAnyData = has_any_activities || yesterday.has_activity || week.completed_mi > 0;
  const showWelcomeCard = !isStravaConnected && !hasAnyData;
  const hasLastActivity = yesterday.last_activity_date && yesterday.days_since_last !== undefined;
  const workoutConfig = getWorkoutConfig(today.workout_type);

  return (
    <ProtectedRoute>
      {/* Premium background with subtle grid */}
      <div className="min-h-screen bg-[#0a0a0f] relative overflow-hidden">
        {/* Gradient overlays */}
        <div className="absolute inset-0 bg-gradient-to-b from-slate-900/50 via-transparent to-black/80 pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-orange-950/20 via-transparent to-transparent pointer-events-none" />
        
        {/* Subtle grid pattern */}
        <div 
          className="absolute inset-0 opacity-[0.015] pointer-events-none"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '64px 64px'
          }}
        />
        
        {/* Main content with fade-in */}
        <div className="relative max-w-xl mx-auto px-4 py-5 md:py-8 space-y-5 animate-fade-in">
          
          {/* Welcome Banner - New Users */}
          {showWelcomeCard && (
            <Card className="border-orange-500/40 bg-gradient-to-br from-orange-950/50 via-orange-900/30 to-transparent overflow-hidden group hover:border-orange-500/60 transition-all duration-300 hover:shadow-xl hover:shadow-orange-500/10">
              <div className="absolute inset-0 bg-gradient-to-r from-orange-500/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              <CardHeader className="relative pb-3">
                <div className="flex items-center gap-3 mb-1">
                  <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                    <Zap className="w-5 h-5 text-orange-400" />
                  </div>
                  <CardTitle className="text-lg text-orange-300">Welcome to StrideIQ</CardTitle>
                </div>
                <CardDescription className="text-slate-300/90 text-sm leading-relaxed">
                  Connect Strava to import your runs. We&apos;ll show you what&apos;s actually working.
                </CardDescription>
              </CardHeader>
              <CardContent className="relative flex flex-wrap gap-2 pt-0">
                <Button asChild size="sm" className="bg-orange-600 hover:bg-orange-500 shadow-lg shadow-orange-500/20 hover:shadow-orange-500/40 transition-all">
                  <Link href="/settings">Connect Strava</Link>
                </Button>
                <Button asChild variant="outline" size="sm" className="border-slate-700 hover:bg-slate-800">
                  <Link href="/calendar">Create Plan</Link>
                </Button>
              </CardContent>
            </Card>
          )}
          
          {/* TODAY - Hero Section */}
          <section className="animate-fade-in" style={{ animationDelay: '50ms' }}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-primary/10">
                  <Calendar className="w-3.5 h-3.5 text-primary" />
                </div>
                <span className="text-xs uppercase tracking-widest font-semibold text-slate-400">
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                </span>
              </div>
              {today.phase && (
                <Badge variant="outline" className="text-orange-400 border-orange-500/40 bg-orange-500/5 text-xs">
                  {today.phase}
                </Badge>
              )}
            </div>
            
            {today.has_workout ? (
              <Card className={`border-l-4 ${workoutConfig.borderColor} bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-slate-950 backdrop-blur-sm group hover:shadow-2xl hover:shadow-primary/5 transition-all duration-300 hover:-translate-y-0.5`}>
                <CardHeader className="pb-2 pt-5">
                  <div className="flex items-start gap-4">
                    <div className={`p-3.5 rounded-2xl ${workoutConfig.bgColor} ${workoutConfig.color} ring-1 ring-white/5 group-hover:scale-105 transition-transform duration-300`}>
                      {workoutConfig.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <CardTitle className={`text-2xl md:text-3xl font-bold ${workoutConfig.color} tracking-tight`}>
                        {today.title || formatWorkoutType(today.workout_type)}
                      </CardTitle>
                      <CardDescription className="mt-1 text-base">
                        {today.distance_mi && <span className="font-medium text-foreground/70">{today.distance_mi} mi</span>}
                        {today.distance_mi && today.pace_guidance && <span className="mx-2 text-slate-600">·</span>}
                        {today.pace_guidance && <span className="text-slate-400">{today.pace_guidance}</span>}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                
                {today.why_context && (
                  <CardContent className="pt-3 pb-3">
                    <div className="bg-slate-800/50 rounded-xl p-3.5 border border-slate-700/50">
                      <div className="flex gap-2">
                        <Sparkles className="w-4 h-4 text-primary/70 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-slate-300 leading-relaxed">{today.why_context}</p>
                      </div>
                    </div>
                  </CardContent>
                )}
                
                <CardContent className="pt-0 pb-4">
                  <div className="flex items-center justify-between border-t border-slate-800 pt-3">
                    <div className="flex items-center gap-3 text-sm text-slate-500">
                      {today.week_number && (
                        <span className="flex items-center gap-1.5">
                          <Target className="w-3.5 h-3.5" />
                          Week {today.week_number}
                        </span>
                      )}
                    </div>
                    <Button asChild variant="ghost" size="sm" className="text-slate-400 hover:text-white h-8">
                      <Link href="/calendar">
                        Calendar <ArrowRight className="w-3.5 h-3.5 ml-1" />
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-slate-950 border-slate-800 group hover:border-slate-700 transition-all duration-300">
                <CardHeader className="pb-3 pt-5">
                  <div className="flex items-start gap-4">
                    <div className="p-3.5 rounded-2xl bg-slate-800 ring-1 ring-slate-700">
                      <Clock className="w-6 h-6 text-slate-500" />
                    </div>
                    <div>
                      <CardTitle className="text-xl md:text-2xl text-slate-400 font-medium">
                        No workout scheduled
                      </CardTitle>
                      <CardDescription className="mt-1 text-sm">
                        {hasAnyData 
                          ? "Recovery day. Your call."
                          : isStravaConnected
                            ? "Create a plan to see workouts."
                            : "Connect Strava or create a plan."
                        }
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 pb-4 flex flex-wrap gap-2">
                  <Button asChild variant="secondary" size="sm" className="h-8">
                    <Link href="/calendar">
                      {hasAnyData ? 'Calendar' : 'Create Plan'} <ArrowRight className="w-3.5 h-3.5 ml-1" />
                    </Link>
                  </Button>
                  {!isStravaConnected && !hasAnyData && (
                    <Button asChild variant="ghost" size="sm" className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10 h-8">
                      <Link href="/settings">Connect Strava</Link>
                    </Button>
                  )}
                </CardContent>
              </Card>
            )}
          </section>
          
          {/* YESTERDAY - Insight Section */}
          <section className="animate-fade-in" style={{ animationDelay: '100ms' }}>
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 rounded-lg bg-emerald-500/10">
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <span className="text-xs uppercase tracking-widest font-semibold text-slate-400">Yesterday</span>
            </div>
            
            {yesterday.has_activity ? (
              <Card className="bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-emerald-950/30 border-l-4 border-emerald-500/60 group hover:shadow-lg hover:shadow-emerald-500/5 transition-all duration-300 hover:-translate-y-0.5">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-xl bg-emerald-500/15 ring-1 ring-emerald-500/20 group-hover:scale-105 transition-transform">
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      </div>
                      <div>
                        <p className="font-semibold text-white">{yesterday.activity_name}</p>
                        <p className="text-sm text-slate-400 mt-0.5">
                          {yesterday.distance_mi && <span>{yesterday.distance_mi} mi</span>}
                          {yesterday.distance_mi && yesterday.pace_per_mi && <span className="mx-1.5 text-slate-600">·</span>}
                          {yesterday.pace_per_mi}
                        </p>
                        {yesterday.insight && (
                          <p className="text-sm text-slate-300 mt-2 leading-relaxed">{yesterday.insight}</p>
                        )}
                      </div>
                    </div>
                    {yesterday.activity_id && (
                      <Button asChild variant="ghost" size="sm" className="text-slate-400 hover:text-white h-7 px-2">
                        <Link href={`/activities/${yesterday.activity_id}`}>
                          <ArrowRight className="w-4 h-4" />
                        </Link>
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-slate-900/50 border-slate-800/50 group hover:border-slate-700 transition-all">
                <CardContent className="py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-slate-800 ring-1 ring-slate-700">
                        <Footprints className="w-4 h-4 text-slate-500" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-400">No activity yesterday</p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {hasLastActivity 
                            ? `Last ran ${yesterday.days_since_last === 1 ? 'the day before' : `${yesterday.days_since_last} days ago`}`
                            : isStravaConnected
                              ? "Waiting for sync."
                              : "Connect Strava to see insights."
                          }
                        </p>
                      </div>
                    </div>
                    {hasLastActivity && yesterday.last_activity_id && (
                      <Button asChild variant="ghost" size="sm" className="text-slate-500 hover:text-white h-7 px-2">
                        <Link href={`/activities/${yesterday.last_activity_id}`}>
                          <ArrowRight className="w-4 h-4" />
                        </Link>
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </section>
          
          {/* WEEK - Progress Section */}
          <section className="animate-fade-in" style={{ animationDelay: '150ms' }}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-blue-500/10">
                  <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
                </div>
                <span className="text-xs uppercase tracking-widest font-semibold text-slate-400">This Week</span>
              </div>
              {week.week_number && week.total_weeks && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 font-medium">
                    {week.week_number}/{week.total_weeks}
                  </span>
                  {week.phase && (
                    <Badge variant="outline" className="text-orange-400 border-orange-500/30 bg-orange-500/5 text-[10px] px-1.5 py-0">
                      {week.phase}
                    </Badge>
                  )}
                </div>
              )}
            </div>
            
            <Card className="bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-slate-950 border-slate-800 group hover:border-slate-700 transition-all">
              <CardContent className="pt-4 pb-4">
                {/* Day Pills - Compact visual week */}
                <div className="flex justify-between gap-1 mb-4">
                  {week.days.map((day) => {
                    const dayConfig = getWorkoutConfig(day.workout_type);
                    return (
                      <div 
                        key={day.date}
                        className={`
                          flex-1 text-center py-2.5 px-0.5 rounded-lg transition-all duration-200
                          ${day.is_today 
                            ? 'ring-2 ring-orange-500/70 bg-orange-500/10 shadow-lg shadow-orange-500/10' 
                            : ''
                          }
                          ${day.completed 
                            ? 'bg-emerald-500/15 border border-emerald-500/25' 
                            : 'bg-slate-800/50 border border-transparent hover:border-slate-700'
                          }
                        `}
                      >
                        <div className={`text-[10px] uppercase tracking-wide mb-1 ${day.is_today ? 'text-orange-400 font-semibold' : 'text-slate-500'}`}>
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
                  <div className="text-center py-1">
                    {week.completed_mi > 0 ? (
                      <>
                        <div className="flex items-center justify-center gap-2 mb-1.5">
                          <Footprints className="w-5 h-5 text-primary" />
                          <span className="text-xl font-bold text-white">
                            {week.completed_mi} mi
                          </span>
                          <span className="text-sm text-slate-500">logged</span>
                        </div>
                        {week.trajectory_sentence && (
                          <p className="text-xs text-slate-400 mb-3">{week.trajectory_sentence}</p>
                        )}
                        <Button asChild variant="secondary" size="sm" className="h-8 text-xs">
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
                            : "Connect Strava to track."
                          }
                        </p>
                        <div className="flex justify-center gap-2">
                          <Button asChild variant="secondary" size="sm" className="h-8 text-xs">
                            <Link href="/calendar">Create Plan</Link>
                          </Button>
                          {!isStravaConnected && (
                            <Button asChild variant="ghost" size="sm" className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10 h-8 text-xs">
                              <Link href="/settings">Connect Strava</Link>
                            </Button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    {/* Animated Progress Bar */}
                    {week.planned_mi > 0 && (
                      <div className="mb-3">
                        <Progress 
                          value={Math.min(100, week.progress_pct)} 
                          className="h-2.5 bg-slate-800"
                          indicatorClassName={`transition-all duration-1000 ease-out ${
                            week.status === 'ahead' ? 'bg-gradient-to-r from-emerald-600 to-emerald-400' :
                            week.status === 'on_track' ? 'bg-gradient-to-r from-blue-600 to-blue-400' :
                            week.status === 'behind' ? 'bg-gradient-to-r from-orange-600 to-orange-400' : 'bg-primary'
                          }`}
                        />
                      </div>
                    )}
                    
                    {/* Stats Row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-lg font-bold text-white">{week.completed_mi}</span>
                        <span className="text-sm text-slate-500">/ {week.planned_mi} mi</span>
                      </div>
                      {getStatusBadge(week.status)}
                    </div>
                    
                    {/* Trajectory */}
                    {week.trajectory_sentence && (
                      <p className="text-xs text-slate-400 mt-2.5 pt-2.5 border-t border-slate-800">
                        {week.trajectory_sentence}
                      </p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
            
            <div className="mt-2 text-right">
              <Button asChild variant="link" size="sm" className="text-slate-500 hover:text-white p-0 h-auto text-xs">
                <Link href="/calendar">
                  Full Calendar <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </Button>
            </div>
          </section>
          
          {/* Quick Links - Compact */}
          <section className="grid grid-cols-2 gap-3 animate-fade-in" style={{ animationDelay: '200ms' }}>
            <Link href="/analytics" className="group">
              <Card className="h-full bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-blue-950/30 border-slate-800 hover:border-blue-500/40 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 hover:-translate-y-0.5 active:scale-[0.98]">
                <CardContent className="py-4 px-4">
                  <div className="flex items-center gap-2.5 mb-1">
                    <div className="p-2 rounded-lg bg-blue-500/15 ring-1 ring-blue-500/20 group-hover:bg-blue-500/25 transition-colors">
                      <BarChart3 className="w-4 h-4 text-blue-400" />
                    </div>
                    <span className="font-semibold text-sm text-white group-hover:text-blue-300 transition-colors">Analytics</span>
                  </div>
                  <p className="text-xs text-slate-500 ml-[42px]">Trends & correlations</p>
                </CardContent>
              </Card>
            </Link>
            <Link href="/coach" className="group">
              <Card className="h-full bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-purple-950/30 border-slate-800 hover:border-purple-500/40 transition-all duration-300 hover:shadow-lg hover:shadow-purple-500/10 hover:-translate-y-0.5 active:scale-[0.98]">
                <CardContent className="py-4 px-4">
                  <div className="flex items-center gap-2.5 mb-1">
                    <div className="p-2 rounded-lg bg-purple-500/15 ring-1 ring-purple-500/20 group-hover:bg-purple-500/25 transition-colors">
                      <MessageSquare className="w-4 h-4 text-purple-400" />
                    </div>
                    <span className="font-semibold text-sm text-white group-hover:text-purple-300 transition-colors">Coach</span>
                  </div>
                  <p className="text-xs text-slate-500 ml-[42px]">Ask questions</p>
                </CardContent>
              </Card>
            </Link>
          </section>
          
        </div>
      </div>
    </ProtectedRoute>
  );
}
