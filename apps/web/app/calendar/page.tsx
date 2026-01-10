'use client';

/**
 * Training Calendar Page
 * 
 * Shows:
 * - Current training plan overview
 * - Week-by-week calendar with planned vs actual
 * - Workout details on click
 * - Plan creation if no plan exists
 */

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useCalendar, useCurrentPlan, useCreatePlan } from '@/lib/hooks/queries/training-plans';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useUnits } from '@/lib/context/UnitsContext';
import { UnitToggle } from '@/components/ui/UnitToggle';
import type { CalendarDay, WorkoutSummary } from '@/lib/api/services/training-plans';

// Helper to format date range for display
function formatDateRange(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  const options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  return `${startDate.toLocaleDateString('en-US', options)} - ${endDate.toLocaleDateString('en-US', options)}`;
}

// Workout type colors
const workoutColors: Record<string, string> = {
  rest: 'bg-gray-700 text-gray-400',
  easy: 'bg-green-900/50 text-green-400 border-green-700',
  easy_strides: 'bg-green-900/50 text-green-400 border-green-700',
  long: 'bg-blue-900/50 text-blue-400 border-blue-700',
  long_pace: 'bg-blue-900/50 text-blue-400 border-blue-700',
  tempo: 'bg-orange-900/50 text-orange-400 border-orange-700',
  tempo_short: 'bg-orange-900/50 text-orange-400 border-orange-700',
  threshold: 'bg-orange-900/50 text-orange-400 border-orange-700',
  intervals: 'bg-red-900/50 text-red-400 border-red-700',
  race_pace: 'bg-purple-900/50 text-purple-400 border-purple-700',
  race: 'bg-yellow-900/50 text-yellow-400 border-yellow-600',
  strides: 'bg-green-900/50 text-green-400 border-green-700',
  shakeout: 'bg-gray-800 text-gray-300 border-gray-600',
};

// Phase colors
const phaseColors: Record<string, string> = {
  base: 'text-green-400',
  build: 'text-orange-400',
  peak: 'text-red-400',
  taper: 'text-blue-400',
  race: 'text-yellow-400',
};

function WorkoutCard({ workout, isToday }: { workout: WorkoutSummary; isToday: boolean }) {
  const { formatDistance } = useUnits();
  const colorClass = workoutColors[workout.workout_type] || 'bg-gray-800 text-gray-300';
  
  // Convert km to meters for formatDistance
  const distanceMeters = workout.target_distance_km ? workout.target_distance_km * 1000 : null;
  
  return (
    <div className={`rounded-lg p-2 border ${colorClass} ${isToday ? 'ring-2 ring-orange-500' : ''}`}>
      <div className="font-medium text-sm truncate">{workout.title}</div>
      {distanceMeters && (
        <div className="text-xs opacity-75">
          {formatDistance(distanceMeters, 1)}
        </div>
      )}
      {workout.completed && (
        <div className="text-xs text-green-400 mt-1">✓ Done</div>
      )}
      {workout.skipped && (
        <div className="text-xs text-red-400 mt-1">✗ Skipped</div>
      )}
    </div>
  );
}

function DayCell({ day, showPlan }: { day: CalendarDay; showPlan: boolean }) {
  const { formatDistance } = useUnits();
  const dateObj = new Date(day.date);
  const dayNum = dateObj.getDate();
  const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
  
  const hasActivities = day.actual_activities.length > 0;
  const hasPlannedWorkout = day.planned_workout && showPlan;
  
  return (
    <div className={`min-h-[100px] p-2 border-b border-r border-gray-700 ${day.is_today ? 'bg-gray-800/50' : ''}`}>
      <div className={`text-xs mb-1 ${day.is_today ? 'text-orange-400 font-bold' : 'text-gray-500'}`}>
        {dayName} {dayNum}
      </div>
      
      {/* Activity-first: Show actual activities prominently */}
      {hasActivities && (
        <div className="space-y-1">
          {day.actual_activities.map((activity, i) => (
            <a 
              key={i} 
              href={`/activities/${activity.id}`}
              className="block bg-green-900/40 border border-green-700/50 rounded p-1.5 hover:border-green-500 transition-colors"
            >
              <div className="text-xs font-medium text-green-300">
                {formatDistance(activity.distance_km ? activity.distance_km * 1000 : null, 1)}
              </div>
              {activity.pace_per_km && (
                <div className="text-xs text-green-400/70">
                  {Math.floor(activity.pace_per_km / 60)}:{String(Math.round(activity.pace_per_km % 60)).padStart(2, '0')}/km
                </div>
              )}
            </a>
          ))}
        </div>
      )}
      
      {/* Plan overlay: Show planned workout if enabled and not already completed */}
      {hasPlannedWorkout && day.planned_workout && !day.planned_workout.completed && (
        <div className={`mt-1 ${hasActivities ? 'opacity-50' : ''}`}>
          <WorkoutCard workout={day.planned_workout} isToday={day.is_today} />
        </div>
      )}
      
      {/* Show checkmark if planned workout was completed */}
      {hasPlannedWorkout && day.planned_workout && day.planned_workout.completed && !hasActivities && (
        <WorkoutCard workout={day.planned_workout} isToday={day.is_today} />
      )}
      
      {day.is_race_day && (
        <div className="mt-1 text-xs text-yellow-400 font-bold">🏁 RACE DAY</div>
      )}
    </div>
  );
}

function WeekRow({ week, weekIndex, showPlan }: { week: any; weekIndex: number; showPlan: boolean }) {
  const { formatDistance } = useUnits();
  const phaseColor = week.phase ? phaseColors[week.phase] : 'text-gray-400';
  
  // Convert km to meters for formatDistance
  const plannedMeters = week.planned_volume_km * 1000;
  const actualMeters = week.actual_volume_km * 1000;
  
  return (
    <div className="border-l border-gray-700">
      {/* Week header */}
      <div className="flex items-center justify-between px-3 py-1 bg-gray-800/50 border-b border-gray-700">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-white">Week {week.week_number || weekIndex + 1}</span>
          {week.phase && showPlan && (
            <span className={`text-xs uppercase font-medium ${phaseColor}`}>
              {week.phase}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400">
          {showPlan && plannedMeters > 0 && (
            <>
              <span className="text-gray-500">Plan:</span> {formatDistance(plannedMeters, 0)}
              <span className="mx-2">|</span>
            </>
          )}
          <span className="text-green-400">Actual:</span> {formatDistance(actualMeters, 0)}
        </div>
      </div>
      
      {/* Days grid */}
      <div className="grid grid-cols-7">
        {week.days.map((day: CalendarDay, i: number) => (
          <DayCell key={i} day={day} showPlan={showPlan} />
        ))}
      </div>
    </div>
  );
}

function CreatePlanForm({ onSuccess }: { onSuccess: () => void }) {
  const createPlan = useCreatePlan();
  const [formData, setFormData] = useState({
    goal_race_name: '',
    goal_race_date: '',
    goal_race_distance: 'half_marathon',
    goal_hours: '',
    goal_minutes: '',
    goal_seconds: '',
  });
  
  const distanceOptions = [
    { value: '5k', label: '5K', meters: 5000 },
    { value: '10k', label: '10K', meters: 10000 },
    { value: 'half_marathon', label: 'Half Marathon', meters: 21097 },
    { value: 'marathon', label: 'Marathon', meters: 42195 },
  ];
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const distance = distanceOptions.find(d => d.value === formData.goal_race_distance);
    if (!distance) return;
    
    const hours = parseInt(formData.goal_hours) || 0;
    const minutes = parseInt(formData.goal_minutes) || 0;
    const seconds = parseInt(formData.goal_seconds) || 0;
    const goalTimeSeconds = (hours * 3600) + (minutes * 60) + seconds;
    
    await createPlan.mutateAsync({
      goal_race_name: formData.goal_race_name || `${distance.label} Goal Race`,
      goal_race_date: formData.goal_race_date,
      goal_race_distance_m: distance.meters,
      goal_time_seconds: goalTimeSeconds > 0 ? goalTimeSeconds : undefined,
    });
    
    onSuccess();
  };
  
  return (
    <div className="max-w-lg mx-auto">
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-xl font-bold mb-4">Create Training Plan</h2>
        <p className="text-gray-400 mb-6">
          Set your goal race and we&apos;ll generate a personalized training plan.
        </p>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Race Name</label>
            <input
              type="text"
              value={formData.goal_race_name}
              onChange={e => setFormData({ ...formData, goal_race_name: e.target.value })}
              placeholder="e.g., Boston Marathon 2026"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Race Date</label>
            <input
              type="date"
              value={formData.goal_race_date}
              onChange={e => setFormData({ ...formData, goal_race_date: e.target.value })}
              required
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Distance</label>
            <select
              value={formData.goal_race_distance}
              onChange={e => setFormData({ ...formData, goal_race_distance: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
            >
              {distanceOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Goal Time (optional)</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={formData.goal_hours}
                onChange={e => setFormData({ ...formData, goal_hours: e.target.value })}
                placeholder="HH"
                min="0"
                max="24"
                className="w-20 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-center"
              />
              <span className="text-gray-400 self-center">:</span>
              <input
                type="number"
                value={formData.goal_minutes}
                onChange={e => setFormData({ ...formData, goal_minutes: e.target.value })}
                placeholder="MM"
                min="0"
                max="59"
                className="w-20 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-center"
              />
              <span className="text-gray-400 self-center">:</span>
              <input
                type="number"
                value={formData.goal_seconds}
                onChange={e => setFormData({ ...formData, goal_seconds: e.target.value })}
                placeholder="SS"
                min="0"
                max="59"
                className="w-20 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-center"
              />
            </div>
          </div>
          
          <button
            type="submit"
            disabled={createPlan.isPending || !formData.goal_race_date}
            className="w-full py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            {createPlan.isPending ? 'Creating Plan...' : 'Generate Training Plan'}
          </button>
        </form>
      </div>
    </div>
  );
}

function PlanOverview({ plan }: { plan: any }) {
  const raceDate = new Date(plan.goal_race_date);
  const daysUntilRace = Math.ceil((raceDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  
  // Format goal time
  let goalTimeStr = '';
  if (plan.goal_time_seconds) {
    const hours = Math.floor(plan.goal_time_seconds / 3600);
    const minutes = Math.floor((plan.goal_time_seconds % 3600) / 60);
    const seconds = plan.goal_time_seconds % 60;
    goalTimeStr = `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
  
  return (
    <div className="bg-gradient-to-r from-orange-900/30 to-gray-800 rounded-lg border border-orange-700/50 p-4 mb-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">{plan.name}</h2>
          <p className="text-gray-400">
            {plan.goal_race_name} • {raceDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
          </p>
        </div>
        
        <div className="flex gap-6 text-center">
          <div>
            <div className="text-2xl font-bold text-orange-400">{daysUntilRace}</div>
            <div className="text-xs text-gray-400">days to go</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {plan.current_week || 0}/{plan.total_weeks}
            </div>
            <div className="text-xs text-gray-400">weeks</div>
          </div>
          {goalTimeStr && (
            <div>
              <div className="text-2xl font-bold text-white">{goalTimeStr}</div>
              <div className="text-xs text-gray-400">goal time</div>
            </div>
          )}
        </div>
      </div>
      
      {/* Progress bar */}
      <div className="mt-4">
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div 
            className="h-full bg-orange-500 transition-all duration-500"
            style={{ width: `${plan.progress_percent}%` }}
          />
        </div>
        <div className="text-xs text-gray-400 mt-1">{plan.progress_percent}% complete</div>
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const router = useRouter();
  const { data: plan, isLoading: planLoading } = useCurrentPlan();
  const { data: calendar, isLoading: calendarLoading, refetch } = useCalendar();
  
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showPlan, setShowPlan] = useState(true);  // Toggle for plan overlay
  
  const isLoading = planLoading || calendarLoading;
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-6">
        <div className="max-w-7xl mx-auto px-4">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-2xl font-bold">Training Calendar</h1>
              <p className="text-gray-400">Your activities with plan overlay</p>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Plan toggle */}
              {plan && (
                <button
                  onClick={() => setShowPlan(!showPlan)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    showPlan 
                      ? 'bg-orange-600/20 text-orange-400 border border-orange-600/50' 
                      : 'bg-gray-800 text-gray-400 border border-gray-700'
                  }`}
                >
                  {showPlan ? '📋 Plan On' : '📋 Plan Off'}
                </button>
              )}
              <UnitToggle />
              {plan && (
                <button
                  onClick={() => setShowCreateForm(true)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
                >
                  New Plan
                </button>
              )}
            </div>
          </div>
          
          {isLoading ? (
            <div className="flex justify-center py-20">
              <LoadingSpinner size="lg" />
            </div>
          ) : showCreateForm ? (
            <CreatePlanForm onSuccess={() => {
              setShowCreateForm(false);
              refetch();
            }} />
          ) : (
            <>
              {/* Plan overview - only show if there's a plan */}
              {calendar?.plan && showPlan && <PlanOverview plan={calendar.plan} />}
              
              {/* No plan prompt */}
              {!plan && (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-6 flex items-center justify-between">
                  <div>
                    <p className="text-gray-300">No training plan active</p>
                    <p className="text-sm text-gray-500">Create a plan to see prescribed workouts</p>
                  </div>
                  <button
                    onClick={() => setShowCreateForm(true)}
                    className="px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg text-sm font-medium transition-colors"
                  >
                    Create Plan
                  </button>
                </div>
              )}
              
              {/* Day headers */}
              <div className="grid grid-cols-7 border-l border-t border-gray-700 bg-gray-800">
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                  <div key={day} className="py-2 text-center text-sm font-medium text-gray-400 border-r border-b border-gray-700">
                    {day}
                  </div>
                ))}
              </div>
              
              {/* Calendar weeks */}
              <div className="border-t border-gray-700">
                {calendar?.weeks.map((week, i) => (
                  <WeekRow key={i} week={week} weekIndex={i} showPlan={showPlan} />
                ))}
              </div>
              
              {(!calendar?.weeks || calendar.weeks.length === 0) && (
                <div className="text-center py-12 text-gray-400">
                  No calendar data available for this period.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
