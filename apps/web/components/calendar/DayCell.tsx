'use client';

/**
 * DayCell Component
 * 
 * A single day in the calendar grid.
 * 
 * DESIGN PRINCIPLES:
 * 1. Minimal - Show essentials, expand on click
 * 2. Unified - Same visual language for planned and completed
 * 3. Scannable - Quick visual differentiation without reading
 * 4. Professional - Clean typography, intentional colors
 */

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import type { CalendarDay } from '@/lib/api/services/calendar';

// Simplified workout type display - categories, not individual types
const WORKOUT_CATEGORIES: Record<string, { label: string; color: string }> = {
  // Rest / Recovery
  rest: { label: 'Rest', color: 'text-gray-500' },
  recovery: { label: 'Recovery', color: 'text-gray-400' },
  gym: { label: 'Gym', color: 'text-gray-400' },
  
  // Easy efforts - green
  easy: { label: 'Easy', color: 'text-emerald-400' },
  easy_strides: { label: 'Easy', color: 'text-emerald-400' },
  easy_hills: { label: 'Easy', color: 'text-emerald-400' },
  strides: { label: 'Strides', color: 'text-emerald-400' },
  
  // Medium efforts - blue
  medium_long: { label: 'Med Long', color: 'text-blue-400' },
  medium_long_mp: { label: 'MLR+MP', color: 'text-blue-400' },
  aerobic: { label: 'Aerobic', color: 'text-blue-400' },
  long: { label: 'Long', color: 'text-blue-400' },
  long_mp: { label: 'Long+MP', color: 'text-blue-400' },
  
  // Quality - orange
  threshold: { label: 'Threshold', color: 'text-orange-400' },
  threshold_light: { label: 'Threshold', color: 'text-orange-400' },
  threshold_short: { label: 'Threshold', color: 'text-orange-400' },
  tempo: { label: 'Tempo', color: 'text-orange-400' },
  
  // Speed - red  
  intervals: { label: 'Intervals', color: 'text-red-400' },
  vo2max: { label: 'VO2max', color: 'text-red-400' },
  speed: { label: 'Speed', color: 'text-red-400' },
  
  // Race
  race: { label: 'RACE', color: 'text-pink-400' },
  shakeout: { label: 'Shakeout', color: 'text-gray-400' },
  shakeout_strides: { label: 'Shakeout', color: 'text-gray-400' },
};

function getWorkoutInfo(type: string): { label: string; color: string } {
  return WORKOUT_CATEGORIES[type] || { 
    label: type.replace(/_/g, ' ').substring(0, 10), 
    color: 'text-gray-400' 
  };
}

interface DayCellProps {
  day: CalendarDay;
  isToday: boolean;
  isSelected: boolean;
  onClick: () => void;
  compact?: boolean;
}

export function DayCell({ day, isToday, isSelected, onClick, compact = false }: DayCellProps) {
  const { formatDistance } = useUnits();
  
  const dayNum = parseInt(day.date.split('-')[2], 10);
  const hasActivities = day.activities.length > 0;
  const hasPlanned = !!day.planned_workout;
  const isCompleted = day.status === 'completed' || hasActivities;
  
  const workoutType = day.planned_workout?.workout_type || 'rest';
  const workoutInfo = getWorkoutInfo(workoutType);
  
  // Calculate total distance for the day
  const totalDistance = day.activities.reduce((sum, a) => sum + (a.distance_m || 0), 0);
  
  // Compact mobile view
  if (compact) {
    return (
      <div 
        onClick={onClick}
        className={`
          min-h-[60px] p-1.5 border-b border-r border-gray-700/30 cursor-pointer
          transition-colors active:bg-gray-800/50
          ${isToday ? 'bg-blue-900/20' : ''}
          ${isSelected ? 'ring-1 ring-blue-500' : ''}
        `}
      >
        <div className={`text-xs font-medium mb-1 ${isToday ? 'text-blue-400' : 'text-gray-500'}`}>
          {dayNum}
        </div>
        
        {/* Completed - show checkmark and distance */}
        {isCompleted && (
          <div className="text-[10px] text-emerald-400 font-medium">
            ✓ {formatDistance(totalDistance, 0)}
          </div>
        )}
        
        {/* Planned but not completed - show workout type */}
        {hasPlanned && !isCompleted && (
          <div className={`text-[10px] font-medium ${workoutInfo.color}`}>
            {workoutInfo.label}
          </div>
        )}
      </div>
    );
  }
  
  // Desktop view
  return (
    <div 
      onClick={onClick}
      className={`
        min-h-[100px] p-2 border-b border-r border-gray-700/30 cursor-pointer
        transition-colors hover:bg-gray-800/30
        ${isToday ? 'bg-blue-900/15' : ''}
        ${isSelected ? 'ring-1 ring-blue-500' : ''}
      `}
    >
      {/* Day number */}
      <div className={`text-sm mb-2 font-medium ${isToday ? 'text-blue-400' : 'text-gray-500'}`}>
        {dayNum}
      </div>
      
      {/* Content area */}
      <div className="space-y-1.5">
        {/* Completed activity - primary display */}
        {isCompleted && (
          <div className="flex items-center gap-1.5">
            <span className="text-emerald-400 text-xs">✓</span>
            <span className="text-sm font-medium text-white">
              {formatDistance(totalDistance, 1)}
            </span>
          </div>
        )}
        
        {/* Inline insight - key metric for the day */}
        {isCompleted && day.inline_insight && (
          <div className={`text-[10px] ${
            day.inline_insight.sentiment === 'positive' ? 'text-emerald-400/80' :
            day.inline_insight.sentiment === 'negative' ? 'text-orange-400/80' :
            'text-gray-400'
          }`}>
            {day.inline_insight.value}
          </div>
        )}
        
        {/* Planned workout - secondary if completed, primary if not */}
        {hasPlanned && day.planned_workout && (
          <div className={`${isCompleted ? 'opacity-50' : ''}`}>
            <div className={`text-xs font-medium ${workoutInfo.color}`}>
              {workoutInfo.label}
              {day.planned_workout.target_distance_km && !isCompleted && (
                <span className="text-gray-500 ml-1">
                  {formatDistance(day.planned_workout.target_distance_km * 1000, 0)}
                </span>
              )}
            </div>
            {/* Show pace hint on hover - truncated */}
            {day.planned_workout.coach_notes && !isCompleted && (
              <div 
                className="text-[10px] text-gray-500 truncate mt-0.5" 
                title={day.planned_workout.coach_notes}
              >
                {day.planned_workout.coach_notes.split(' ').slice(0, 2).join(' ')}
              </div>
            )}
          </div>
        )}
        
        {/* Rest day indicator */}
        {!hasPlanned && !hasActivities && (
          <div className="text-xs text-gray-600">—</div>
        )}
      </div>
    </div>
  );
}
