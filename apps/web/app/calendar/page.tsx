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
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useCalendarRange } from '@/lib/hooks/queries/calendar';
import { DayCell, DayDetailPanel, WeekSummaryRow, CreatePlanCTA, PlanBanner } from '@/components/calendar';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useUnits } from '@/lib/context/UnitsContext';
import { UnitToggle } from '@/components/ui/UnitToggle';
import type { CalendarDay, WeekSummary } from '@/lib/api/services/calendar';

// Day names starting from Monday
const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function CalendarHeader({ 
  month, 
  year, 
  onPrevMonth, 
  onNextMonth,
  activePlan,
  currentWeek,
  currentPhase 
}: {
  month: string;
  year: number;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  activePlan?: { name: string; goal_race_name?: string; goal_race_date?: string; total_weeks: number } | null;
  currentWeek?: number | null;
  currentPhase?: string | null;
}) {
  // Calculate days until race without timezone issues
  const daysUntilRace = (() => {
    if (!activePlan?.goal_race_date) return null;
    const [y, m, d] = activePlan.goal_race_date.split('-').map(Number);
    const raceDate = new Date(y, m - 1, d);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.ceil((raceDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  })();

  return (
    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
      <div className="flex items-center gap-4">
        <button 
          onClick={onPrevMonth}
          className="p-2 bg-gray-800 border border-gray-700 rounded-lg hover:border-blue-500 transition-colors"
        >
          ◀
        </button>
        <h1 className="text-2xl font-bold text-white">
          {month} {year}
        </h1>
        <button 
          onClick={onNextMonth}
          className="p-2 bg-gray-800 border border-gray-700 rounded-lg hover:border-blue-500 transition-colors"
        >
          ▶
        </button>
      </div>
      
      {activePlan && (
        <div className="flex items-center gap-4">
          {currentWeek && (
            <span className="px-3 py-1.5 bg-blue-600 text-white rounded-full text-sm font-medium">
              Week {currentWeek}
            </span>
          )}
          {currentPhase && (
            <span className="px-3 py-1.5 bg-orange-900/50 text-orange-400 border border-orange-700/50 rounded-full text-sm font-medium">
              {currentPhase}
            </span>
          )}
          {daysUntilRace !== null && daysUntilRace > 0 && (
            <span className="text-gray-400 text-sm">
              <span className="text-white font-bold">{daysUntilRace}</span> days to race
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// PlanBanner moved to @/components/calendar/PlanBanner.tsx for reusability

function ActionBar({ 
  weekStats 
}: { 
  weekStats: { completed: number; planned: number; trajectory?: string } 
}) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-700 px-4 md:px-6 py-3 md:py-4 z-30 safe-area-bottom">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Stats - simplified on mobile */}
        <div className="flex items-center gap-2 md:gap-8">
          <div className="flex items-center gap-1 md:gap-2">
            <span className="text-gray-400 hidden md:inline">📊</span>
            <span className="text-xs md:text-sm text-gray-400">
              <span className="hidden md:inline">This week: </span>
              <span className="text-white font-bold">{weekStats.completed.toFixed(0)}</span>
              <span className="text-gray-600">/</span>
              <span className="text-gray-400">{weekStats.planned.toFixed(0)} mi</span>
            </span>
          </div>
          {weekStats.trajectory && (
            <div className="hidden md:flex items-center gap-2">
              <span className="text-gray-400">🎯</span>
              <span className="text-sm text-gray-400">
                Trajectory: <span className="text-emerald-400 font-bold">{weekStats.trajectory}</span>
              </span>
            </div>
          )}
        </div>
        
        {/* Buttons - compact on mobile */}
        <div className="flex items-center gap-2 md:gap-3">
          <a 
            href="/insights"
            className="px-3 md:px-4 py-2 bg-gray-800 border border-gray-700 hover:border-blue-500 rounded-lg text-xs md:text-sm transition-colors"
          >
            <span className="md:hidden">📊</span>
            <span className="hidden md:inline">📊 Weekly Summary</span>
          </a>
          <a 
            href="/coach"
            className="px-3 md:px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-lg text-xs md:text-sm font-medium transition-colors"
          >
            <span className="md:hidden">💬</span>
            <span className="hidden md:inline">💬 Ask Coach</span>
          </a>
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
  
  // Estimate calories (rough: ~100 cal/mile for running)
  const estCalories = Math.round((totalDistance / 1609.344) * 100);
  
  if (totalActivities === 0) return null;
  
  return (
    <div className="mt-4 bg-gray-800/50 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <span className="text-sm text-gray-400">Month Totals</span>
        <div className="flex items-center gap-6 text-sm">
          <div>
            <span className="text-gray-500">Activities: </span>
            <span className="text-white font-semibold">{totalActivities}</span>
          </div>
          <div>
            <span className="text-gray-500">Distance: </span>
            <span className="text-white font-semibold">{totalMiles} mi</span>
          </div>
          <div>
            <span className="text-gray-500">Time: </span>
            <span className="text-white font-semibold">{timeStr}</span>
          </div>
          <div>
            <span className="text-gray-500">Calories: </span>
            <span className="text-white font-semibold">{estCalories.toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
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
  
  // Calculate current week stats
  const weekStats = useMemo(() => {
    if (!calendar?.week_summaries?.length) {
      return { completed: 0, planned: 0 };
    }
    
    const currentWeekSummary = calendar.week_summaries.find(w => 
      w.days.some(d => d.date === today)
    );
    
    return {
      completed: currentWeekSummary?.completed_miles || 0,
      planned: currentWeekSummary?.planned_miles || 0,
      trajectory: '3:12-3:18' // TODO: Calculate from build data
    };
  }, [calendar, today]);
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 pb-24">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <CalendarHeader
              month={monthName}
              year={year}
              onPrevMonth={handlePrevMonth}
              onNextMonth={handleNextMonth}
              activePlan={calendar?.active_plan}
              currentWeek={calendar?.current_week}
              currentPhase={calendar?.current_phase}
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
              <div className="hidden md:grid grid-cols-[repeat(7,1fr)_140px] border-l border-t border-gray-700 bg-gray-800/50">
                {DAY_NAMES.map(day => (
                  <div key={day} className="py-3 text-center text-sm font-semibold text-gray-400 border-r border-b border-gray-700">
                    {day}
                  </div>
                ))}
                <div className="py-3 text-center text-sm font-semibold text-gray-400 border-r border-b border-gray-700 hidden lg:block">
                  Weekly Totals
                </div>
              </div>
              
              {/* Mobile day headers - abbreviated */}
              <div className="grid md:hidden grid-cols-7 border-l border-t border-gray-700 bg-gray-800/50">
                {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, i) => (
                  <div key={i} className="py-2 text-center text-xs font-semibold text-gray-400 border-r border-b border-gray-700">
                    {day}
                  </div>
                ))}
              </div>
              
              {/* Calendar grid with aligned weekly totals */}
              <div className="border-l border-gray-700">
                {weeksWithDays.map((week, weekIndex) => {
                  const weekDistance = week.days.reduce((sum, d) => sum + (d.total_distance_m || 0), 0);
                  const weekDuration = week.days.reduce((sum, d) => sum + (d.total_duration_s || 0), 0);
                  const weekMiles = (weekDistance / 1609.344).toFixed(1);
                  const hours = Math.floor(weekDuration / 3600);
                  const mins = Math.floor((weekDuration % 3600) / 60);
                  const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
                  
                  return (
                    <React.Fragment key={weekIndex}>
                      {/* Desktop: 7 days + weekly totals column */}
                      <div className="hidden md:grid grid-cols-[repeat(7,1fr)_140px]">
                        {week.days.map((day) => (
                          <DayCell
                            key={day.date}
                            day={day}
                            isToday={day.date === today}
                            isSelected={day.date === selectedDate}
                            onClick={() => handleDayClick(day.date)}
                          />
                        ))}
                        
                        {/* Weekly total cell - aligned with this week's row */}
                        <div className="hidden lg:flex flex-col justify-center items-end p-3 border-r border-b border-gray-700/50 bg-gray-800/30 min-h-[120px]">
                          <div className="text-right">
                            <div className="text-white font-semibold text-sm">{weekMiles} mi</div>
                            <div className="text-gray-500 text-xs">{timeStr}</div>
                          </div>
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
                          />
                        ))}
                      </div>
                      
                      {/* Mobile week total - below the week */}
                      <div className="md:hidden flex justify-between items-center px-3 py-2 bg-gray-800/30 border-b border-gray-700/50 text-sm">
                        <span className="text-gray-500">Week Total</span>
                        <span className="text-white font-medium">{weekMiles} mi • {timeStr}</span>
                      </div>
                    </React.Fragment>
                  );
                })}
              </div>
              
              {/* Month totals footer */}
              <MonthTotals days={calendar?.days || []} />
              
              {weeksWithDays.length === 0 && (
                <div className="text-center py-12 text-gray-400">
                  No calendar data available for this period.
                </div>
              )}
            </>
          )}
        </div>
        
        {/* Action bar */}
        <ActionBar weekStats={weekStats} />
        
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
