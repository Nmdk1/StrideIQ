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
import { DayBadge, type DayBadgeData } from './DayBadge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

// Simplified workout type display - categories, not individual types
const WORKOUT_CATEGORIES: Record<string, { label: string; color: string }> = {
  // Rest / Recovery
  rest: { label: 'Rest', color: 'text-slate-500' },
  recovery: { label: 'Recovery', color: 'text-slate-400' },
  gym: { label: 'Gym', color: 'text-slate-400' },
  
  // Easy efforts - green (but strides/hills VISIBLE)
  easy: { label: 'Easy', color: 'text-emerald-400' },
  easy_strides: { label: 'Easy+Strides', color: 'text-emerald-400' },  // VISIBLE
  easy_hills: { label: 'Easy+Hills', color: 'text-emerald-400' },      // VISIBLE
  strides: { label: 'Strides', color: 'text-lime-400' },               // Distinct
  hill_strides: { label: 'Hill Strides', color: 'text-lime-400' },     // VISIBLE
  hill_sprints: { label: 'Hill Sprints', color: 'text-amber-400' },    // VISIBLE, distinct
  
  // Medium efforts - blue
  medium_long: { label: 'Med Long', color: 'text-blue-400' },
  medium_long_mp: { label: 'MLR+MP', color: 'text-blue-400' },
  aerobic: { label: 'Aerobic', color: 'text-blue-400' },
  long: { label: 'Long', color: 'text-blue-400' },
  long_mp: { label: 'Long+MP', color: 'text-blue-400' },
  
  // Quality - orange (NO tempo - use threshold only)
  threshold: { label: 'Threshold', color: 'text-orange-400' },
  threshold_light: { label: 'Threshold', color: 'text-orange-400' },
  threshold_short: { label: 'Threshold', color: 'text-orange-400' },
  
  // Speed - red  
  intervals: { label: 'Intervals', color: 'text-red-400' },
  vo2max: { label: 'VO2max', color: 'text-red-400' },
  speed: { label: 'Speed', color: 'text-red-400' },
  
  // Race
  race: { label: 'RACE', color: 'text-pink-400' },
  shakeout: { label: 'Shakeout', color: 'text-slate-400' },
  shakeout_strides: { label: 'Shakeout', color: 'text-slate-400' },
  pre_race: { label: 'Pre-Race', color: 'text-slate-400' },
  tune_up_ra: { label: 'Tune-up', color: 'text-pink-400' },
};

function getWorkoutInfo(type: string): { label: string; color: string } {
  return WORKOUT_CATEGORIES[type] || { 
    label: type.replace(/_/g, ' ').substring(0, 10), 
    color: 'text-slate-400' 
  };
}

interface DayCellProps {
  day: CalendarDay;
  isToday: boolean;
  isSelected: boolean;
  onClick: () => void;
  compact?: boolean;
  signals?: DayBadgeData[];
}

export function DayCell({ day, isToday, isSelected, onClick, compact = false, signals = [] }: DayCellProps) {
  const { formatDistance } = useUnits();
  
  const dayNum = parseInt(day.date.split('-')[2], 10);
  const hasActivities = day.activities.length > 0;
  const hasPlanned = !!day.planned_workout;
  const isCompleted = day.status === 'completed' || hasActivities;
  
  // Detect if this is a past day with a missed workout
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dayDate = new Date(day.date + 'T00:00:00');
  const isPast = dayDate < today;
  const isMissed = isPast && hasPlanned && !hasActivities;
  
  const workoutType = day.planned_workout?.workout_type || 'rest';
  const workoutInfo = getWorkoutInfo(workoutType);
  
  // Sort activities by distance (longest first = primary)
  const sortedActivities = [...day.activities].sort((a, b) => (b.distance_m || 0) - (a.distance_m || 0));
  const hasMultipleActivities = day.activities.length > 1;
  
  // Compact mobile view
  if (compact) {
    return (
      <div 
        onClick={onClick}
        className={`
          min-h-[60px] min-w-0 p-1.5 border-b border-r border-slate-700/50 cursor-pointer
          transition-colors active:bg-slate-800/50 overflow-hidden
          ${isToday ? 'bg-blue-900/20' : ''}
          ${isSelected ? 'ring-1 ring-blue-500' : ''}
        `}
      >
        <div className={`text-xs font-medium mb-1 ${isToday ? 'text-blue-400' : 'text-slate-500'}`}>
          {dayNum}
        </div>
        
        {/* Completed - show each activity */}
        {isCompleted && sortedActivities.map((activity, idx) => (
          <div key={activity.id || idx} className="text-[10px] text-emerald-400 font-medium">
            ✓ {formatDistance(activity.distance_m || 0, 0)}
          </div>
        ))}
        
        {/* Missed workout - past day with plan but no activity */}
        {isMissed && (
          <div className="text-[10px] font-medium text-slate-500 line-through">
            {workoutInfo.label}
          </div>
        )}
        
        {/* Planned but not completed - show workout type (future days only) */}
        {hasPlanned && !isCompleted && !isMissed && (
          <div className={`text-[10px] font-medium ${workoutInfo.color}`}>
            {workoutInfo.label}
          </div>
        )}
        
        {/* Signal badges - compact */}
        {signals.length > 0 && (
          <div className="flex gap-0.5 mt-1 flex-wrap">
            {signals.slice(0, 1).map((signal, idx) => (
              <DayBadge key={idx} badge={signal} compact />
            ))}
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
        min-h-[100px] min-w-0 p-2 border-b border-r border-slate-700/50 cursor-pointer
        transition-colors hover:bg-slate-800/30 overflow-hidden
        ${isToday ? 'bg-blue-900/15' : ''}
        ${isSelected ? 'ring-1 ring-blue-500' : ''}
      `}
    >
      {/* Day number */}
      <div className={`text-sm mb-2 font-medium ${isToday ? 'text-blue-400' : 'text-slate-500'}`}>
        {dayNum}
      </div>
      
      {/* Content area */}
      <div className="space-y-1.5">
        {/* Completed activities - show each separately */}
        {isCompleted && sortedActivities.map((activity, idx) => {
          // Calculate pace if we have distance and duration
          let paceStr = '';
          let durationStr = '';
          
          if (activity.duration_s) {
            const hours = Math.floor(activity.duration_s / 3600);
            const mins = Math.floor((activity.duration_s % 3600) / 60);
            const secs = Math.floor(activity.duration_s % 60);
            if (hours > 0) {
              durationStr = `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            } else {
              durationStr = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
          }
          
          if (activity.distance_m && activity.duration_s && activity.distance_m > 0) {
            const pacePerMile = activity.duration_s / (activity.distance_m / 1609.344);
            const mins = Math.floor(pacePerMile / 60);
            const secs = Math.floor(pacePerMile % 60);
            paceStr = `${mins}:${secs.toString().padStart(2, '0')}`;
          }
          
          return (
            <div key={activity.id || idx} className="flex items-center gap-1.5 flex-wrap">
              <span className="text-emerald-400 text-xs">✓</span>
              <span className="text-sm font-medium text-white">
                {formatDistance(activity.distance_m || 0, 1)}
              </span>
              {/* Duration */}
              {durationStr && (
                <span className="text-[10px] text-slate-300">
                  {durationStr}
                </span>
              )}
              {/* Pace */}
              {paceStr && (
                <span className="text-[10px] text-blue-400">
                  {paceStr}/mi
                </span>
              )}
              {/* HR */}
              {activity.avg_hr && (
                <span className="text-[10px] text-slate-500">
                  ♥{activity.avg_hr}
                </span>
              )}
            </div>
          );
        })}
        
        {/* Inline insight removed - metrics now shown directly on each activity */}
        
        {/* Missed workout - past day with plan but no activity */}
        {isMissed && day.planned_workout && (
          <div className="overflow-hidden opacity-60">
            <div className="text-xs font-medium text-slate-500 truncate line-through">
              {workoutInfo.label}
              {day.planned_workout.target_distance_km && (
                <span className="text-slate-600 ml-1">
                  {formatDistance(day.planned_workout.target_distance_km * 1000, 0)}
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-600 mt-0.5">
              Missed
            </div>
          </div>
        )}
        
        {/* Planned workout - secondary if completed, primary if not (future days only) */}
        {hasPlanned && day.planned_workout && !isMissed && (
          <div className={`${isCompleted ? 'opacity-50' : ''} overflow-hidden`}>
            <div className={`text-xs font-medium ${workoutInfo.color} truncate`}>
              {workoutInfo.label}
              {day.planned_workout.target_distance_km && !isCompleted && (
                <span className="text-slate-500 ml-1">
                  {formatDistance(day.planned_workout.target_distance_km * 1000, 0)}
                </span>
              )}
            </div>
            {/* Show pace hint - extract pace value from coach_notes */}
            {day.planned_workout.coach_notes && !isCompleted && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="text-[10px] text-slate-500 truncate mt-0.5">
                    {(() => {
                      // Extract first pace (e.g., "easy: 8:04/mi" from "Paces: easy: 8:04/mi | ...")
                      const notes = day.planned_workout.coach_notes || '';
                      const paceMatch = notes.match(/Paces:\s*(\w+):\s*([\d:]+\/mi)/);
                      if (paceMatch) {
                        return `${paceMatch[1]}: ${paceMatch[2]}`;
                      }
                      // Fallback: first 30 chars
                      return notes.substring(0, 30);
                    })()}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top">
                  {day.planned_workout.coach_notes}
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        )}
        
        {/* Rest day indicator */}
        {!hasPlanned && !hasActivities && (
          <div className="text-xs text-slate-600">—</div>
        )}
        
        {/* Signal badges - desktop */}
        {signals.length > 0 && (
          <div className="flex gap-1 mt-1.5 flex-wrap">
            {signals.slice(0, 2).map((signal, idx) => (
              <DayBadge key={idx} badge={signal} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
