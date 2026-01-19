'use client';

/**
 * Training Calendar Page
 * 
 * THE CENTRAL UI HUB
 * 
 * Everything flows through here:
 * - Planned workouts from active training plan
 * - Actual activities synced from Strava/Garmin
 * - Notes (pre/post workout)
 * - Insights (auto-generated analysis)
 * - Coach chat (contextual GPT interaction)
 * 
 * The calendar is home. Every day click opens the day detail panel.
 */

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useCalendarRange } from '@/lib/hooks/queries/calendar';
import { DayCell, DayDetailPanel, WeekSummaryRow, CreatePlanCTA, PlanBanner } from '@/components/calendar';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useUnits } from '@/lib/context/UnitsContext';
import { UnitToggle } from '@/components/ui/UnitToggle';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, Calendar, Lightbulb, MessageSquare, Activity, Clock, Flame } from 'lucide-react';
import type { CalendarDay, WeekSummary } from '@/lib/api/services/calendar';
import type { DayBadgeData } from '@/components/calendar/DayBadge';
import type { WeekTrajectoryData } from '@/components/calendar/WeekSummaryRow';
import { apiClient } from '@/lib/api/client';

// Types for calendar signals
interface CalendarSignalsResponse {
  day_signals: Record<string, DayBadgeData[]>;
  week_trajectories: Record<string, WeekTrajectoryData>;
  message?: string;
}

// Day names starting from Monday
const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function CalendarHeader({ 
  month, 
  year, 
  onPrevMonth, 
  onNextMonth,
}: {
  month: string;
  year: number;
  onPrevMonth: () => void;
  onNextMonth: () => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <Button 
        variant="ghost"
        size="icon"
        onClick={onPrevMonth}
        className="text-slate-400 hover:text-white hover:bg-slate-800"
        aria-label="Previous month"
      >
        <ChevronLeft className="w-5 h-5" />
      </Button>
      <div className="flex items-center gap-2 min-w-[180px] justify-center">
        <Calendar className="w-5 h-5 text-orange-500" />
        <h1 className="text-xl font-semibold text-white">
          {month} {year}
        </h1>
      </div>
      <Button 
        variant="ghost"
        size="icon"
        onClick={onNextMonth}
        className="text-slate-400 hover:text-white hover:bg-slate-800"
        aria-label="Next month"
      >
        <ChevronRight className="w-5 h-5" />
      </Button>
    </div>
  );
}

// PlanBanner moved to @/components/calendar/PlanBanner.tsx for reusability

function ActionBar({ 
  weekStats,
  isCurrentMonthView
}: { 
  weekStats: { completed: number; planned: number };
  isCurrentMonthView: boolean;
}) {
  const showProgress = weekStats.planned > 0;
  const progressPct = showProgress ? Math.min(100, (weekStats.completed / weekStats.planned) * 100) : 0;
  
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur border-t border-slate-700 px-4 py-3 z-30">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Week progress */}
        <div className="flex items-center gap-4">
          {showProgress ? (
            <>
              <div className="flex items-center gap-2 text-sm">
                <Activity className="w-4 h-4 text-orange-500" />
                <span className="text-slate-400">This week:</span>
                <span className="text-white font-medium">{weekStats.completed.toFixed(0)}</span>
                <span className="text-slate-600">/</span>
                <span className="text-slate-500">{weekStats.planned.toFixed(0)} mi</span>
              </div>
              {/* Mini progress bar */}
              <div className="hidden sm:block w-24 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-orange-500 rounded-full transition-all" 
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </>
          ) : isCurrentMonthView ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Clock className="w-4 h-4" />
              No planned workouts this week
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Calendar className="w-4 h-4" />
              Viewing future/past month
            </div>
          )}
        </div>
        
        {/* Quick actions */}
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" asChild className="text-slate-400 hover:text-white">
            <a href="/insights">
              <Lightbulb className="w-4 h-4 mr-1.5" />
              Insights
            </a>
          </Button>
          <Button variant="ghost" size="sm" asChild className="text-slate-400 hover:text-white">
            <a href="/coach">
              <MessageSquare className="w-4 h-4 mr-1.5" />
              Coach
            </a>
          </Button>
        </div>
      </div>
    </div>
  );
}

function MonthTotals({ days }: { days: CalendarDay[] }) {
  const totalDistance = days.reduce((sum, d) => sum + (d.total_distance_m || 0), 0);
  const totalDuration = days.reduce((sum, d) => sum + (d.total_duration_s || 0), 0);
  const totalActivities = days.reduce((sum, d) => sum + d.activities.length, 0);
  
  const totalMiles = (totalDistance / 1609.344).toFixed(1);
  const hours = Math.floor(totalDuration / 3600);
  const mins = Math.floor((totalDuration % 3600) / 60);
  const secs = totalDuration % 60;
  const timeStr = `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  
  const estCalories = Math.round((totalDistance / 1609.344) * 100);
  
  if (totalActivities === 0) return null;
  
  return (
    <Card className="mt-4 bg-slate-800/50 border-slate-700">
      <CardContent className="py-4 px-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <span className="text-sm text-slate-400 flex items-center gap-2">
            <Flame className="w-4 h-4 text-orange-500" />
            Month Totals
          </span>
          <div className="flex items-center gap-6 text-sm">
            <div>
              <span className="text-slate-500">Activities: </span>
              <span className="text-white font-semibold">{totalActivities}</span>
            </div>
            <div>
              <span className="text-slate-500">Distance: </span>
              <span className="text-white font-semibold">{totalMiles} mi</span>
            </div>
            <div>
              <span className="text-slate-500">Time: </span>
              <span className="text-white font-semibold">{timeStr}</span>
            </div>
            <div>
              <span className="text-slate-500">Calories: </span>
              <span className="text-white font-semibold">{estCalories.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  
  // Calculate date range for current month view
  const { startDate, endDate, monthName, year } = useMemo(() => {
    const start = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const end = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    
    // Extend to show full weeks
    const startDayOfWeek = start.getDay() === 0 ? 6 : start.getDay() - 1; // Convert to Monday-based
    start.setDate(start.getDate() - startDayOfWeek);
    
    const endDayOfWeek = end.getDay() === 0 ? 6 : end.getDay() - 1;
    end.setDate(end.getDate() + (6 - endDayOfWeek));
    
    return {
      startDate: start.toISOString().split('T')[0],
      endDate: end.toISOString().split('T')[0],
      monthName: currentDate.toLocaleDateString('en-US', { month: 'long' }),
      year: currentDate.getFullYear(),
    };
  }, [currentDate]);
  
  const { data: calendar, isLoading, error } = useCalendarRange(startDate, endDate);
  
  // Fetch calendar signals (ADR-016)
  const { data: signals } = useQuery({
    queryKey: ['calendar-signals', startDate, endDate],
    queryFn: () => apiClient.get<CalendarSignalsResponse>(
      `/calendar/signals?start_date=${startDate}&end_date=${endDate}`
    ),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
    enabled: !!calendar, // Only fetch once calendar data is loaded
  });
  
  // Get signals for a specific date
  const getDaySignals = (dateStr: string): DayBadgeData[] => {
    return signals?.day_signals?.[dateStr] || [];
  };
  
  // Get trajectory for a week (from week number to ISO week string)
  const getWeekTrajectory = (weekNumber: number | undefined): WeekTrajectoryData | undefined => {
    if (!weekNumber || !signals?.week_trajectories) return undefined;
    // Find matching week trajectory by week number
    const weekKey = Object.keys(signals.week_trajectories).find(key => {
      const match = key.match(/W(\d+)$/);
      return match && parseInt(match[1]) === weekNumber;
    });
    return weekKey ? signals.week_trajectories[weekKey] : undefined;
  };
  
  const handlePrevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };
  
  const handleNextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };
  
  const handleDayClick = (date: string) => {
    setSelectedDate(date);
  };
  
  // Get today's date in local timezone (YYYY-MM-DD format)
  const today = useMemo(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }, []);
  
  // Check if we're viewing the current month
  const isCurrentMonthView = useMemo(() => {
    const now = new Date();
    return currentDate.getFullYear() === now.getFullYear() && 
           currentDate.getMonth() === now.getMonth();
  }, [currentDate]);
  
  // Group days by week for display
  const weeksWithDays = useMemo(() => {
    if (!calendar?.days) return [];
    
    const weeks: { days: CalendarDay[]; weekNumber?: number; summary?: WeekSummary }[] = [];
    let currentWeek: CalendarDay[] = [];
    
    calendar.days.forEach((day, index) => {
      currentWeek.push(day);
      
      // End of week (Sunday) or last day
      if (day.day_of_week === 6 || index === calendar.days.length - 1) {
        // Find matching week summary
        const weekSummary = calendar.week_summaries.find(ws => 
          ws.days.some(d => d.date === currentWeek[0]?.date)
        );
        
        weeks.push({ 
          days: currentWeek, 
          weekNumber: weekSummary?.week_number,
          summary: weekSummary
        });
        currentWeek = [];
      }
    });
    
    return weeks;
  }, [calendar]);
  
  // Calculate current week stats - always shows TODAY's week, even when viewing other months
  // First check if today's week is in the viewed calendar, otherwise use week_summaries[0] 
  // which should be the current/most relevant week from the API
  const weekStats = useMemo(() => {
    if (!calendar?.week_summaries?.length) {
      return { completed: 0, planned: 0 };
    }
    
    // Look for the week containing today
    const todayWeek = calendar.week_summaries.find(w => 
      w.days.some(d => d.date === today)
    );
    
    // If viewing a different month, today won't be in the summaries
    // In that case, we still want to show today's week stats
    // The API should include this in a separate field, but for now return zeros
    // to clearly indicate we're not in the current week view
    if (!todayWeek) {
      // When viewing future/past months, don't show misleading stats
      return { completed: 0, planned: 0 };
    }
    
    return {
      completed: todayWeek.completed_miles || 0,
      planned: todayWeek.planned_miles || 0,
    };
  }, [calendar, today]);
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 pb-24">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {/* Header - clean, minimal */}
          <div className="flex justify-between items-center mb-6">
            <CalendarHeader
              month={monthName}
              year={year}
              onPrevMonth={handlePrevMonth}
              onNextMonth={handleNextMonth}
            />
            <UnitToggle />
          </div>
          
          {/* Plan banner or Create Plan CTA */}
          {calendar?.active_plan ? (
            <PlanBanner 
              plan={{
                id: calendar.active_plan.id || '',
                name: calendar.active_plan.name,
                goal_race_name: calendar.active_plan.goal_race_name,
                goal_race_date: calendar.active_plan.goal_race_date,
                total_weeks: calendar.active_plan.total_weeks,
              }}
              currentWeek={calendar.current_week}
              currentPhase={calendar.current_phase}
            />
          ) : !isLoading && (
            <div className="mb-6">
              <CreatePlanCTA />
            </div>
          )}
          
          {isLoading ? (
            <div className="flex justify-center py-20">
              <LoadingSpinner size="lg" />
            </div>
          ) : error ? (
            <div className="text-center py-12 text-red-400">
              Error loading calendar. Please try again.
            </div>
          ) : (
            <>
              {/* Day headers with Weekly Totals column */}
              <div className="hidden md:grid grid-cols-[repeat(7,1fr)_120px] border-l border-t border-slate-700 bg-slate-800/50">
                {DAY_NAMES.map(day => (
                  <div key={day} className="py-3 text-center text-sm font-semibold text-slate-400 border-r border-b border-slate-700">
                    {day}
                  </div>
                ))}
                <div className="py-3 text-center text-sm font-semibold text-slate-400 border-r border-b border-slate-700 hidden lg:block">
                  Weekly Totals
                </div>
              </div>
              
              {/* Mobile day headers - abbreviated */}
              <div className="grid md:hidden grid-cols-7 border-l border-t border-slate-700 bg-slate-800/50">
                {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, i) => (
                  <div key={i} className="py-2 text-center text-xs font-semibold text-slate-400 border-r border-b border-slate-700">
                    {day}
                  </div>
                ))}
              </div>
              
              {/* Calendar grid with aligned weekly totals */}
              <div className="border-l border-slate-700">
                {weeksWithDays.map((week, weekIndex) => {
                  const weekDistance = week.days.reduce((sum, d) => sum + (d.total_distance_m || 0), 0);
                  const weekDuration = week.days.reduce((sum, d) => sum + (d.total_duration_s || 0), 0);
                  const hasActivity = weekDistance > 0;
                  const weekMiles = (weekDistance / 1609.344).toFixed(1);
                  const hours = Math.floor(weekDuration / 3600);
                  const mins = Math.floor((weekDuration % 3600) / 60);
                  const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
                  
                  return (
                    <React.Fragment key={weekIndex}>
                      {/* Desktop: 7 days + weekly totals column */}
                      <div className="hidden md:grid grid-cols-[repeat(7,1fr)_120px]">
                        {week.days.map((day) => (
                          <DayCell
                            key={day.date}
                            day={day}
                            isToday={day.date === today}
                            isSelected={day.date === selectedDate}
                            onClick={() => handleDayClick(day.date)}
                            signals={getDaySignals(day.date)}
                          />
                        ))}
                        
                        {/* Weekly total cell - only show if there's activity */}
                        <div className="hidden lg:flex flex-col justify-center items-end p-3 border-r border-b border-slate-700/30 min-h-[120px]">
                          {hasActivity ? (
                            <div className="text-right">
                              <div className="text-white font-medium text-sm">{weekMiles} mi</div>
                              <div className="text-slate-500 text-xs">{timeStr}</div>
                              {/* Week trajectory sentence */}
                              {getWeekTrajectory(week.weekNumber) && (
                                <div className={`text-[10px] mt-1.5 max-w-[130px] leading-tight ${
                                  getWeekTrajectory(week.weekNumber)?.trend === 'positive' 
                                    ? 'text-emerald-400/80' 
                                    : getWeekTrajectory(week.weekNumber)?.trend === 'caution' 
                                    ? 'text-yellow-400/80' 
                                    : 'text-slate-400'
                                }`}>
                                  {getWeekTrajectory(week.weekNumber)?.summary}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-slate-600 text-xs">—</div>
                          )}
                        </div>
                      </div>
                      
                      {/* Mobile: 7 days, no weekly totals column */}
                      <div className="grid md:hidden grid-cols-7">
                        {week.days.map((day) => (
                          <DayCell
                            key={day.date}
                            day={day}
                            isToday={day.date === today}
                            isSelected={day.date === selectedDate}
                            onClick={() => handleDayClick(day.date)}
                            compact
                            signals={getDaySignals(day.date)}
                          />
                        ))}
                      </div>
                      
                      {/* Mobile week total - only show if there's activity */}
                      {hasActivity && (
                        <div className="md:hidden px-3 py-2 bg-slate-800/20 border-b border-slate-700/30 text-sm">
                          <div className="flex justify-between items-center">
                            <span className="text-slate-500">Week</span>
                            <span className="text-slate-300 font-medium">{weekMiles} mi · {timeStr}</span>
                          </div>
                          {/* Week trajectory sentence - mobile */}
                          {getWeekTrajectory(week.weekNumber) && (
                            <div className={`text-[10px] mt-1 ${
                              getWeekTrajectory(week.weekNumber)?.trend === 'positive' 
                                ? 'text-emerald-400/80' 
                                : getWeekTrajectory(week.weekNumber)?.trend === 'caution' 
                                ? 'text-yellow-400/80' 
                                : 'text-slate-400'
                            }`}>
                              {getWeekTrajectory(week.weekNumber)?.summary}
                            </div>
                          )}
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
              
              {/* Month totals footer */}
              <MonthTotals days={calendar?.days || []} />
              
              {weeksWithDays.length === 0 && (
                <div className="text-center py-12 text-slate-400">
                  No calendar data available for this period.
                </div>
              )}
            </>
          )}
        </div>
        
        {/* Action bar */}
        <ActionBar weekStats={weekStats} isCurrentMonthView={isCurrentMonthView} />
        
        {/* Day detail panel */}
        <DayDetailPanel
          date={selectedDate || today}
          isOpen={selectedDate !== null}
          onClose={() => setSelectedDate(null)}
        />
      </div>
    </ProtectedRoute>
  );
}
