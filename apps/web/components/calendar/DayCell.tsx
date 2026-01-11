'use client';

/**
 * DayCell Component
 * 
 * A single day in the calendar grid.
 * Shows planned workout + actual activity overlay.
 * 
 * DESIGN: Clear, readable workout display with meaningful colors
 */

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import type { CalendarDay } from '@/lib/api/services/calendar';

// Workout type colors - organized by effort category
const workoutColors: Record<string, { bg: string; border: string; text: string; label: string }> = {
  // Rest / Recovery
  rest: { bg: 'bg-gray-800/50', border: 'border-gray-700', text: 'text-gray-500', label: 'Rest' },
  gym: { bg: 'bg-gray-800/50', border: 'border-gray-700', text: 'text-gray-400', label: 'Gym' },
  recovery: { bg: 'bg-gray-800/60', border: 'border-gray-600', text: 'text-gray-400', label: 'Recovery' },
  
  // Easy / Aerobic (Green family)
  easy: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400', label: 'Easy Run' },
  easy_strides: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400', label: 'Easy + Strides' },
  easy_hills: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400', label: 'Easy + Hills' },
  strides: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400', label: 'Strides' },
  
  // Medium Effort (Blue family)
  medium_long: { bg: 'bg-sky-900/40', border: 'border-sky-700/50', text: 'text-sky-400', label: 'Medium Long' },
  medium_long_mp: { bg: 'bg-violet-900/40', border: 'border-violet-700/50', text: 'text-violet-400', label: 'MLR w/ MP' },
  aerobic: { bg: 'bg-sky-900/40', border: 'border-sky-700/50', text: 'text-sky-400', label: 'Aerobic' },
  
  // Long Runs (Blue family - deeper)
  long: { bg: 'bg-blue-900/40', border: 'border-blue-700/50', text: 'text-blue-400', label: 'Long Run' },
  long_mp: { bg: 'bg-pink-900/40', border: 'border-pink-700/50', text: 'text-pink-400', label: 'Long Run + MP' },
  
  // Quality - Threshold (Orange family)
  threshold: { bg: 'bg-orange-900/40', border: 'border-orange-700/50', text: 'text-orange-400', label: 'Threshold' },
  threshold_light: { bg: 'bg-orange-900/30', border: 'border-orange-700/40', text: 'text-orange-400', label: 'Light Threshold' },
  threshold_short: { bg: 'bg-orange-900/30', border: 'border-orange-700/40', text: 'text-orange-400', label: 'Short Threshold' },
  tempo: { bg: 'bg-orange-900/40', border: 'border-orange-700/50', text: 'text-orange-400', label: 'Tempo' },
  
  // Quality - Speed (Red family)
  intervals: { bg: 'bg-red-900/40', border: 'border-red-700/50', text: 'text-red-400', label: 'Intervals' },
  vo2max: { bg: 'bg-red-900/40', border: 'border-red-700/50', text: 'text-red-400', label: 'VO2max' },
  speed: { bg: 'bg-red-900/40', border: 'border-red-700/50', text: 'text-red-400', label: 'Speed Work' },
  
  // Special
  race: { bg: 'bg-gradient-to-br from-pink-900/60 to-orange-900/60', border: 'border-pink-600', text: 'text-white', label: '🏁 Race Day' },
  shakeout: { bg: 'bg-gray-800/50', border: 'border-gray-600', text: 'text-gray-400', label: 'Shakeout' },
  shakeout_strides: { bg: 'bg-gray-800/50', border: 'border-gray-600', text: 'text-gray-400', label: 'Shakeout + Strides' },
};

// Get human-readable label for workout type
function getWorkoutLabel(workoutType: string): string {
  return workoutColors[workoutType]?.label || workoutType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Status indicator styles
const statusStyles: Record<string, string> = {
  completed: 'ring-2 ring-emerald-500/50',
  modified: 'ring-2 ring-amber-500/50',
  missed: 'ring-2 ring-red-500/30 opacity-60',
  future: '',
  rest: '',
};

interface DayCellProps {
  day: CalendarDay;
  isToday: boolean;
  isSelected: boolean;
  onClick: () => void;
  compact?: boolean; // Mobile compact view
}

// Format pace from distance (meters) and duration (seconds)
function formatPace(distanceM: number, durationS: number, useMiles: boolean): string {
  if (!distanceM || !durationS || distanceM === 0) return '';
  
  const distanceUnit = useMiles ? distanceM / 1609.344 : distanceM / 1000;
  const paceSeconds = durationS / distanceUnit;
  const mins = Math.floor(paceSeconds / 60);
  const secs = Math.round(paceSeconds % 60);
  
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function DayCell({ day, isToday, isSelected, onClick, compact = false }: DayCellProps) {
  const { formatDistance, units } = useUnits();
  const useMiles = units === 'imperial';
  
  // Parse date without timezone issues - extract day directly from YYYY-MM-DD string
  const dayNum = parseInt(day.date.split('-')[2], 10);
  
  const hasActivities = day.activities.length > 0;
  const hasPlanned = !!day.planned_workout;
  const hasNotes = day.notes.length > 0;
  const hasInsights = day.insights.length > 0;
  
  const workoutType = day.planned_workout?.workout_type || 'rest';
  const colors = workoutColors[workoutType] || { bg: 'bg-gray-800/50', border: 'border-gray-700', text: 'text-gray-500', label: workoutType };
  const statusStyle = statusStyles[day.status] || '';
  
  // Compact mode for mobile - still readable
  if (compact) {
    return (
      <div 
        onClick={onClick}
        className={`
          min-h-[70px] p-1 border-b border-r border-gray-700/50 cursor-pointer
          transition-all duration-200 active:bg-gray-800/50
          ${isToday ? 'bg-blue-900/20' : ''}
          ${isSelected ? 'ring-2 ring-pink-500' : ''}
          ${statusStyle}
        `}
      >
        {/* Day number */}
        <div className={`text-xs font-medium ${isToday ? 'text-blue-400' : 'text-gray-500'}`}>
          {dayNum}
        </div>
        
        {/* Workout type indicator - abbreviated but readable */}
        {hasPlanned && day.planned_workout && (
          <div className={`mt-1 px-1 py-0.5 rounded text-[9px] font-medium truncate ${colors.bg} ${colors.text}`}>
            {getWorkoutLabel(day.planned_workout.workout_type).substring(0, 8)}
          </div>
        )}
        
        {/* Activity indicator */}
        {hasActivities && (
          <div className="mt-1 text-[10px] text-emerald-400 font-medium truncate">
            ✓ {formatDistance(day.activities[0].distance_m || 0, 0)}
          </div>
        )}
        
        {/* Indicators */}
        {(hasNotes || hasInsights) && (
          <div className="flex gap-0.5 mt-0.5">
            {hasNotes && <span className="text-[8px]">📝</span>}
            {hasInsights && <span className="text-[8px]">🔥</span>}
          </div>
        )}
      </div>
    );
  }
  
  // Full desktop view
  return (
    <div 
      onClick={onClick}
      className={`
        min-h-[120px] p-2 border-b border-r border-gray-700/50 cursor-pointer
        transition-all duration-200 hover:bg-gray-800/50
        ${isToday ? 'bg-blue-900/20' : ''}
        ${isSelected ? 'ring-2 ring-pink-500' : ''}
        ${statusStyle}
      `}
    >
      {/* Day number */}
      <div className={`text-sm mb-1.5 font-medium ${isToday ? 'text-blue-400' : 'text-gray-500'}`}>
        {dayNum}
      </div>
      
      {/* Planned workout card - Clear, readable format */}
      {hasPlanned && day.planned_workout && (
        <div className={`
          rounded-md p-1.5 mb-1.5 border
          ${colors.bg} ${colors.border}
          ${day.status === 'completed' ? 'opacity-50' : ''}
        `}>
          {/* Workout type label - human readable */}
          <div className={`text-xs font-semibold ${colors.text}`}>
            {getWorkoutLabel(day.planned_workout.workout_type)}
          </div>
          
          {/* Title if different from type, or distance */}
          {day.planned_workout.title && day.planned_workout.title !== getWorkoutLabel(day.planned_workout.workout_type) ? (
            <div className="text-[10px] text-gray-400 mt-0.5 truncate" title={day.planned_workout.title}>
              {day.planned_workout.title}
            </div>
          ) : day.planned_workout.target_distance_km ? (
            <div className="text-[10px] text-gray-400 mt-0.5">
              {formatDistance(day.planned_workout.target_distance_km * 1000, 0)}
            </div>
          ) : null}
        </div>
      )}
      
      {/* Actual activities */}
      {hasActivities && (
        <div className="space-y-1">
          {day.activities.slice(0, 2).map((activity) => {
            const pace = formatPace(activity.distance_m || 0, activity.duration_s || 0, useMiles);
            const paceUnit = useMiles ? '/mi' : '/km';
            
            return (
              <div 
                key={activity.id}
                className="bg-emerald-900/30 border border-emerald-700/40 rounded px-1.5 py-0.5"
              >
                <div className="text-xs font-medium text-emerald-400">
                  ✓ {formatDistance(activity.distance_m || 0, 1)}
                </div>
                {pace && (
                  <div className="text-[10px] text-emerald-500/70">
                    {pace}{paceUnit}
                  </div>
                )}
              </div>
            );
          })}
          {day.activities.length > 2 && (
            <div className="text-xs text-gray-500">+{day.activities.length - 2} more</div>
          )}
        </div>
      )}
      
      {/* Indicators */}
      <div className="flex gap-1 mt-1">
        {hasNotes && <span className="text-xs" title="Has notes">📝</span>}
        {hasInsights && <span className="text-xs" title="Has insights">🔥</span>}
      </div>
    </div>
  );
}
