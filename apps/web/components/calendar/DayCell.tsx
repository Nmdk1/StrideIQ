'use client';

/**
 * DayCell Component
 * 
 * A single day in the calendar grid.
 * Shows planned workout + actual activity overlay.
 */

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import type { CalendarDay } from '@/lib/api/services/calendar';

// Workout type colors
const workoutColors: Record<string, { bg: string; border: string; text: string }> = {
  rest: { bg: 'bg-gray-800/50', border: 'border-gray-700', text: 'text-gray-500' },
  gym: { bg: 'bg-gray-800/50', border: 'border-gray-700', text: 'text-gray-400' },
  easy: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400' },
  easy_strides: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400' },
  easy_hills: { bg: 'bg-emerald-900/40', border: 'border-emerald-700/50', text: 'text-emerald-400' },
  recovery: { bg: 'bg-gray-800/60', border: 'border-gray-600', text: 'text-gray-400' },
  medium_long: { bg: 'bg-sky-900/40', border: 'border-sky-700/50', text: 'text-sky-400' },
  medium_long_mp: { bg: 'bg-violet-900/40', border: 'border-violet-700/50', text: 'text-violet-400' },
  long: { bg: 'bg-blue-900/40', border: 'border-blue-700/50', text: 'text-blue-400' },
  long_mp: { bg: 'bg-pink-900/40', border: 'border-pink-700/50', text: 'text-pink-400' },
  threshold: { bg: 'bg-orange-900/40', border: 'border-orange-700/50', text: 'text-orange-400' },
  threshold_light: { bg: 'bg-orange-900/30', border: 'border-orange-700/40', text: 'text-orange-400' },
  threshold_short: { bg: 'bg-orange-900/30', border: 'border-orange-700/40', text: 'text-orange-400' },
  tempo: { bg: 'bg-orange-900/40', border: 'border-orange-700/50', text: 'text-orange-400' },
  intervals: { bg: 'bg-red-900/40', border: 'border-red-700/50', text: 'text-red-400' },
  race: { bg: 'bg-gradient-to-br from-pink-900/60 to-orange-900/60', border: 'border-pink-600', text: 'text-white' },
  shakeout: { bg: 'bg-gray-800/50', border: 'border-gray-600', text: 'text-gray-400' },
  shakeout_strides: { bg: 'bg-gray-800/50', border: 'border-gray-600', text: 'text-gray-400' },
};

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
  const colors = workoutColors[workoutType] || workoutColors.rest;
  const statusStyle = statusStyles[day.status] || '';
  
  // Compact mode for mobile
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
        
        {/* Workout type indicator dot/bar */}
        {hasPlanned && (
          <div className={`h-1 rounded-full mt-1 ${colors.bg} ${colors.border} border`} />
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
      
      {/* Planned workout card */}
      {hasPlanned && day.planned_workout && (
        <div className={`
          rounded-md p-1.5 mb-1.5 border
          ${colors.bg} ${colors.border}
          ${day.status === 'completed' ? 'opacity-50' : ''}
        `}>
          <div className={`text-xs font-semibold uppercase tracking-wide ${colors.text}`}>
            {day.planned_workout.workout_type.replace(/_/g, ' ')}
          </div>
          {day.planned_workout.target_distance_km && (
            <div className="text-xs text-gray-400 mt-0.5">
              {formatDistance(day.planned_workout.target_distance_km * 1000, 0)}
            </div>
          )}
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
