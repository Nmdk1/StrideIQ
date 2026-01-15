"use client";

/**
 * Empty State Components
 * 
 * Educational prompts when data is missing.
 * Explains WHY logging matters and WHAT insights they'll unlock.
 * 
 * Tone: Curious, inviting, never guilt-inducing.
 */

import Link from 'next/link';

interface EmptyStateProps {
  className?: string;
}

export function EmptyNutritionState({ className = '' }: EmptyStateProps) {
  return (
    <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 text-center ${className}`}>
      <div className="text-4xl mb-4">🍽️</div>
      <h3 className="text-lg font-semibold text-slate-200 mb-2">
        No meals logged yet
      </h3>
      <p className="text-slate-400 text-sm mb-4 max-w-md mx-auto">
        When you log what you eat, we can find patterns like: 
        <span className="text-orange-400"> &quot;Your pace improves 3% when you eat carbs 2 hours before running.&quot;</span>
      </p>
      <p className="text-slate-500 text-xs mb-4">
        Just log when you remember. Partial data still reveals patterns.
      </p>
      <Link
        href="/nutrition"
        className="inline-block px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Log a meal
      </Link>
    </div>
  );
}

export function EmptyCheckinState({ className = '' }: EmptyStateProps) {
  return (
    <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 text-center ${className}`}>
      <div className="text-4xl mb-4">😴</div>
      <h3 className="text-lg font-semibold text-slate-200 mb-2">
        No check-ins yet
      </h3>
      <p className="text-slate-400 text-sm mb-4 max-w-md mx-auto">
        A 5-second morning check-in lets us find patterns like:
        <span className="text-orange-400"> &quot;You run 8% faster after 7+ hours of sleep.&quot;</span>
      </p>
      <p className="text-slate-500 text-xs mb-4">
        Sleep, stress, soreness. Three sliders. Done.
      </p>
      <Link
        href="/checkin"
        className="inline-block px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Do quick check-in
      </Link>
    </div>
  );
}

export function EmptyCorrelationsState({ className = '' }: EmptyStateProps) {
  return (
    <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 text-center ${className}`}>
      <div className="text-4xl mb-4">🔍</div>
      <h3 className="text-lg font-semibold text-slate-200 mb-2">
        Not enough data for correlations yet
      </h3>
      <p className="text-slate-400 text-sm mb-4 max-w-md mx-auto">
        We need about <span className="text-orange-400">2-3 weeks of logging</span> to find what actually works for you.
        Keep logging sleep, nutrition, and letting Strava sync your runs.
      </p>
      <div className="text-slate-500 text-xs space-y-1">
        <p>✓ Strava activities syncing</p>
        <p>○ Morning check-ins (sleep, stress, soreness)</p>
        <p>○ Nutrition logging (when convenient)</p>
      </div>
    </div>
  );
}

export function EmptyActivitiesState({ className = '' }: EmptyStateProps) {
  return (
    <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 text-center ${className}`}>
      <div className="text-4xl mb-4">🏃</div>
      <h3 className="text-lg font-semibold text-slate-200 mb-2">
        No activities synced yet
      </h3>
      <p className="text-slate-400 text-sm mb-4 max-w-md mx-auto">
        Connect Strava to automatically sync your runs. 
        We analyze pace, heart rate, and efficiency—not just distance.
      </p>
      <Link
        href="/settings"
        className="inline-block px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Connect Strava
      </Link>
    </div>
  );
}

export function EmptyLabResultsState({ className = '' }: EmptyStateProps) {
  return (
    <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 text-center ${className}`}>
      <div className="text-4xl mb-4">🧪</div>
      <h3 className="text-lg font-semibold text-slate-200 mb-2">
        No lab results yet
      </h3>
      <p className="text-slate-400 text-sm mb-4 max-w-md mx-auto">
        Add your blood work to find patterns like:
        <span className="text-orange-400"> &quot;Your efficiency dropped when ferritin fell below 50.&quot;</span>
      </p>
      <p className="text-slate-500 text-xs mb-4">
        We track: ferritin, vitamin D, hemoglobin, thyroid, and more.
      </p>
      <Link
        href="/lab-results"
        className="inline-block px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Add lab results
      </Link>
    </div>
  );
}

/**
 * Data Quality Indicator
 * Shows athletes how complete their data is and what they're missing
 */
interface DataQualityProps {
  activitiesCount: number;
  checkinsCount: number;
  nutritionCount: number;
  daysTracked: number;
}

export function DataQualityIndicator({ 
  activitiesCount, 
  checkinsCount, 
  nutritionCount,
  daysTracked 
}: DataQualityProps) {
  const checkinsPercent = Math.min(100, (checkinsCount / daysTracked) * 100);
  const hasEnoughData = activitiesCount >= 10 && checkinsCount >= 14;
  
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-slate-300">Data Quality</h4>
        <span className={`text-xs px-2 py-1 rounded ${hasEnoughData ? 'bg-green-900/50 text-green-400' : 'bg-yellow-900/50 text-yellow-400'}`}>
          {hasEnoughData ? 'Ready for insights' : 'Building patterns...'}
        </span>
      </div>
      
      <div className="space-y-2 text-sm">
        <div className="flex justify-between items-center">
          <span className="text-slate-400">Activities</span>
          <span className={activitiesCount >= 10 ? 'text-green-400' : 'text-slate-500'}>
            {activitiesCount} {activitiesCount >= 10 ? '✓' : `(need ${10 - activitiesCount} more)`}
          </span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-slate-400">Check-ins</span>
          <span className={checkinsPercent >= 70 ? 'text-green-400' : 'text-slate-500'}>
            {checkinsCount}/{daysTracked} days ({Math.round(checkinsPercent)}%)
          </span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-slate-400">Nutrition logs</span>
          <span className="text-slate-500">
            {nutritionCount} entries
          </span>
        </div>
      </div>
      
      {!hasEnoughData && (
        <p className="mt-3 text-xs text-slate-500 border-t border-slate-700/50 pt-3">
          The more consistently you log, the more patterns we can find. 
          Even 3-4 days/week reveals insights.
        </p>
      )}
    </div>
  );
}

/**
 * Weekly Logging Nudge
 * Shown on dashboard to encourage consistent logging
 */
interface WeeklyNudgeProps {
  daysLoggedThisWeek: number;
  onDismiss: () => void;
}

export function WeeklyLoggingNudge({ daysLoggedThisWeek, onDismiss }: WeeklyNudgeProps) {
  if (daysLoggedThisWeek >= 5) return null; // Good logging, no nudge needed
  
  const messages = [
    { threshold: 0, message: "Start your week strong. One check-in takes 5 seconds." },
    { threshold: 1, message: "1 day logged. Keep going—patterns emerge around day 3." },
    { threshold: 2, message: "2 days this week. You're building something useful." },
    { threshold: 3, message: "3 days! Halfway to a great data week." },
    { threshold: 4, message: "4 days. One more and you unlock weekly trends." },
  ];
  
  const relevantMessage = messages.find(m => m.threshold === daysLoggedThisWeek)?.message 
    || "Keep logging to unlock insights.";
  
  return (
    <div className="bg-orange-900/20 border border-orange-800/50 rounded-lg p-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="text-2xl">📊</div>
        <div>
          <p className="text-sm text-orange-200">{relevantMessage}</p>
          <p className="text-xs text-orange-400/70 mt-0.5">
            {daysLoggedThisWeek}/7 days this week
          </p>
        </div>
      </div>
      <button 
        onClick={onDismiss}
        className="text-orange-400/50 hover:text-orange-400 p-1"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

