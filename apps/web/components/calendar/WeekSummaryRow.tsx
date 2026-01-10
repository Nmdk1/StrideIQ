'use client';

/**
 * WeekSummaryRow Component
 * 
 * Summary row displayed after each week in the calendar.
 * Shows planned vs completed volume and key metrics.
 */

import React from 'react';
import type { WeekSummary } from '@/lib/api/services/calendar';

// Phase colors
const phaseColors: Record<string, { bg: string; text: string; border: string }> = {
  base: { bg: 'from-emerald-900/20', text: 'text-emerald-400', border: 'border-emerald-700/30' },
  build1: { bg: 'from-orange-900/20', text: 'text-orange-400', border: 'border-orange-700/30' },
  build2: { bg: 'from-orange-900/20', text: 'text-orange-400', border: 'border-orange-700/30' },
  build: { bg: 'from-orange-900/20', text: 'text-orange-400', border: 'border-orange-700/30' },
  peak: { bg: 'from-pink-900/20', text: 'text-pink-400', border: 'border-pink-700/30' },
  taper: { bg: 'from-blue-900/20', text: 'text-blue-400', border: 'border-blue-700/30' },
  cutback: { bg: 'from-amber-900/20', text: 'text-amber-400', border: 'border-amber-700/30' },
  race: { bg: 'from-yellow-900/20', text: 'text-yellow-400', border: 'border-yellow-700/30' },
};

interface WeekSummaryRowProps {
  week: WeekSummary;
}

export function WeekSummaryRow({ week }: WeekSummaryRowProps) {
  const phase = week.phase?.toLowerCase() || 'base';
  const colors = phaseColors[phase] || phaseColors.base;
  
  const completionPercent = week.planned_miles > 0 
    ? Math.round((week.completed_miles / week.planned_miles) * 100) 
    : 0;
  
  return (
    <div className={`
      col-span-7 px-4 py-3
      bg-gradient-to-r ${colors.bg} to-gray-800/50
      border-y ${colors.border}
      flex items-center justify-between
    `}>
      {/* Week label */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-white">
          WEEK {week.week_number}
        </span>
        {week.phase && (
          <span className={`text-xs uppercase font-medium ${colors.text}`}>
            {week.phase}
          </span>
        )}
      </div>
      
      {/* Stats */}
      <div className="flex items-center gap-6">
        {/* Volume */}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500">Volume:</span>
          <span className={`font-mono font-semibold ${
            completionPercent >= 90 ? 'text-emerald-400' : 
            completionPercent >= 70 ? 'text-amber-400' : 
            'text-gray-400'
          }`}>
            {week.completed_miles.toFixed(0)}
          </span>
          <span className="text-gray-600">/</span>
          <span className="text-gray-400 font-mono">{week.planned_miles.toFixed(0)} mi</span>
        </div>
        
        {/* Quality sessions */}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500">Quality:</span>
          <span className={`font-semibold ${
            week.quality_sessions_completed >= week.quality_sessions_planned 
              ? 'text-emerald-400' 
              : 'text-gray-400'
          }`}>
            {week.quality_sessions_completed}/{week.quality_sessions_planned}
          </span>
        </div>
      </div>
      
      {/* Focus text */}
      {week.focus && (
        <div className="hidden lg:block max-w-md text-sm text-gray-400 italic truncate">
          &ldquo;{week.focus}&rdquo;
        </div>
      )}
    </div>
  );
}
