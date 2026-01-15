'use client';

/**
 * WeekSummaryRow Component
 * 
 * Summary row displayed after each week in the calendar.
 * Shows planned vs completed volume and key metrics.
 * 
 * TONE: Data speaks. No praise, no guilt.
 */

import React from 'react';
import type { WeekSummary } from '@/lib/api/services/calendar';

// Phase display names - clean, no abbreviations
const PHASE_NAMES: Record<string, string> = {
  base: 'Base',
  base_speed: 'Base + Speed',
  volume_build: 'Volume Build',
  threshold: 'Threshold',
  marathon_specific: 'Marathon Specific',
  race_specific: 'Race Specific',
  hold: 'Maintenance',
  taper: 'Taper',
  race: 'Race',
  recovery: 'Recovery',
  build: 'Build',
  build1: 'Build',
  build2: 'Build',
  peak: 'Peak',
  cutback: 'Cutback',
};

// Phase colors - subtle, intentional
const phaseColors: Record<string, string> = {
  base: 'text-emerald-400/80',
  base_speed: 'text-emerald-400/80',
  volume_build: 'text-blue-400/80',
  threshold: 'text-orange-400/80',
  marathon_specific: 'text-orange-400/80',
  race_specific: 'text-orange-400/80',
  taper: 'text-blue-400/80',
  race: 'text-pink-400/80',
  recovery: 'text-slate-400',
  build: 'text-orange-400/80',
  peak: 'text-pink-400/80',
  cutback: 'text-amber-400/80',
};

export interface WeekTrajectoryData {
  summary: string;
  trend: 'positive' | 'caution' | 'neutral';
  details?: Record<string, unknown>;
}

interface WeekSummaryRowProps {
  week: WeekSummary;
  previousWeekMiles?: number;  // For trend calculation
  trajectory?: WeekTrajectoryData;
}

export function WeekSummaryRow({ week, previousWeekMiles, trajectory }: WeekSummaryRowProps) {
  const phaseKey = week.phase?.toLowerCase().replace(/ /g, '_') || 'base';
  const phaseName = PHASE_NAMES[phaseKey] || week.phase || '';
  const phaseColor = phaseColors[phaseKey] || 'text-slate-400';
  
  // Calculate completion percentage
  const completionPct = week.planned_miles > 0 
    ? Math.round((week.completed_miles / week.planned_miles) * 100) 
    : 0;
  
  // Calculate week-over-week trend (if previous data available)
  let trend: 'up' | 'down' | 'flat' | null = null;
  let trendPct: number | null = null;
  
  if (previousWeekMiles !== undefined && previousWeekMiles > 0 && week.completed_miles > 0) {
    const change = ((week.completed_miles - previousWeekMiles) / previousWeekMiles) * 100;
    trendPct = Math.abs(Math.round(change));
    if (change > 5) trend = 'up';
    else if (change < -5) trend = 'down';
    else trend = 'flat';
  }
  
  // Trajectory color mapping
  const trajectoryColors: Record<string, string> = {
    positive: 'text-emerald-400/80',
    caution: 'text-yellow-400/80',
    neutral: 'text-slate-400',
  };
  
  return (
    <div className="col-span-7 px-4 py-2.5 bg-slate-800/30 border-y border-slate-700/50/30">
      <div className="flex items-center justify-between">
        {/* Week label + Phase */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-white">
            Week {week.week_number}
          </span>
          {phaseName && (
            <span className={`text-xs ${phaseColor}`}>
              {phaseName}
            </span>
          )}
        </div>
      
      {/* Volume + Quality - compact */}
      <div className="flex items-center gap-4 text-sm">
        {/* Volume with completion indicator */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-500 hidden sm:inline">Vol:</span>
          <span className={`font-medium ${
            completionPct >= 90 ? 'text-emerald-400' : 
            completionPct >= 70 ? 'text-white' : 
            'text-slate-400'
          }`}>
            {week.completed_miles.toFixed(0)}
          </span>
          <span className="text-slate-600">/</span>
          <span className="text-slate-500">{week.planned_miles.toFixed(0)}</span>
        </div>
        
        {/* Quality sessions - only show if planned */}
        {week.quality_sessions_planned > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 hidden sm:inline">Q:</span>
            <span className={`font-medium ${
              week.quality_sessions_completed >= week.quality_sessions_planned 
                ? 'text-emerald-400' 
                : 'text-slate-400'
            }`}>
              {week.quality_sessions_completed}/{week.quality_sessions_planned}
            </span>
          </div>
        )}
        
        {/* Trend indicator - only if meaningful */}
        {trend && trendPct !== null && trendPct > 5 && (
          <div className={`text-xs ${
            trend === 'up' ? 'text-emerald-400/70' :
            trend === 'down' ? 'text-orange-400/70' :
            'text-slate-500'
          }`}>
            {trend === 'up' && '↑'}
            {trend === 'down' && '↓'}
            {trend !== 'flat' && `${trendPct}%`}
          </div>
        )}
      </div>
      </div>
      
      {/* Week Trajectory Sentence */}
      {trajectory && (
        <div className={`mt-1 text-xs ${trajectoryColors[trajectory.trend] || 'text-slate-400'}`}>
          {trajectory.summary}
        </div>
      )}
    </div>
  );
}
