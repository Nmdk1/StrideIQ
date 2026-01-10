/**
 * Activity Card Component
 * 
 * Displays a single activity in a card format.
 * Can be swapped for different card designs without breaking list page.
 * Supports selection mode for comparison feature.
 */

'use client';

import Link from 'next/link';
import type { Activity } from '@/lib/api/types';
import { useUnits } from '@/lib/context/UnitsContext';

interface ActivityCardProps {
  activity: Activity;
  showInsights?: boolean;
  className?: string;
  selectionMode?: boolean;
  isSelected?: boolean;
  onToggleSelection?: () => void;
  canSelect?: boolean;
}

// Workout type badge colors
const WORKOUT_TYPE_COLORS: Record<string, string> = {
  recovery_run: 'bg-gray-600',
  easy_run: 'bg-green-700',
  aerobic_run: 'bg-green-600',
  long_run: 'bg-blue-700',
  medium_long_run: 'bg-blue-600',
  tempo_run: 'bg-orange-600',
  tempo_intervals: 'bg-orange-600',
  threshold_run: 'bg-orange-700',
  vo2max_intervals: 'bg-red-600',
  track_workout: 'bg-red-600',
  fartlek: 'bg-purple-600',
  marathon_pace: 'bg-yellow-600',
  progression_run: 'bg-blue-500',
  race: 'bg-yellow-500',
};

const WORKOUT_TYPE_LABELS: Record<string, string> = {
  recovery_run: 'Recovery',
  easy_run: 'Easy',
  aerobic_run: 'Aerobic',
  long_run: 'Long',
  medium_long_run: 'Med Long',
  tempo_run: 'Tempo',
  tempo_intervals: 'Tempo Int',
  threshold_run: 'Threshold',
  vo2max_intervals: 'VO2max',
  track_workout: 'Track',
  fartlek: 'Fartlek',
  marathon_pace: 'MP',
  progression_run: 'Progression',
  race: 'Race',
};

export function ActivityCard({ 
  activity, 
  showInsights = false, 
  className = '',
  selectionMode = false,
  isSelected = false,
  onToggleSelection,
  canSelect = true,
}: ActivityCardProps) {
  const { formatDistance, formatPace, units } = useUnits();
  
  const date = new Date(activity.start_date);
  const formattedDate = date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
  const formattedTime = date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });

  // Format distance using user's preferred units
  const formattedDistancePrimary = formatDistance(activity.distance, 2);

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (onToggleSelection && (canSelect || isSelected)) {
      onToggleSelection();
    }
  };

  const cardContent = (
    <div
      className={`
        bg-gray-800 border rounded-lg p-4 transition-colors cursor-pointer
        ${isSelected 
          ? 'border-orange-500 bg-orange-900/10' 
          : 'border-gray-700 hover:border-blue-600'}
        ${className}
      `}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-start gap-3">
          {/* Selection checkbox */}
          {selectionMode && (
            <button
              onClick={handleCheckboxClick}
              className={`mt-1 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                isSelected 
                  ? 'bg-orange-600 border-orange-600' 
                  : canSelect 
                    ? 'border-gray-500 hover:border-orange-500' 
                    : 'border-gray-700 cursor-not-allowed opacity-50'
              }`}
              disabled={!canSelect && !isSelected}
              title={!canSelect && !isSelected ? 'Maximum 10 activities selected' : undefined}
            >
              {isSelected && (
                <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          )}
          <div>
            <h3 className="font-semibold text-lg">{activity.name}</h3>
            <p className="text-sm text-gray-400">
              {formattedDate} at {formattedTime}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {activity.workout_type && (
            <span className={`px-2 py-1 rounded text-xs text-white ${WORKOUT_TYPE_COLORS[activity.workout_type] || 'bg-gray-600'}`}>
              {WORKOUT_TYPE_LABELS[activity.workout_type] || activity.workout_type}
            </span>
          )}
          {activity.is_race_candidate && !activity.workout_type?.includes('race') && (
            <span className="px-2 py-1 bg-yellow-900/50 border border-yellow-700/50 rounded text-xs text-yellow-400">
              Race
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        {activity.distance > 0 && (
          <div>
            <p className="text-xs text-gray-400">Distance</p>
            <p className="font-semibold">{formattedDistancePrimary}</p>
          </div>
        )}

        {activity.pace_per_mile && (
          <div>
            <p className="text-xs text-gray-400">Pace</p>
            <p className="font-semibold">{activity.pace_per_mile}</p>
          </div>
        )}

        {activity.duration_formatted && (
          <div>
            <p className="text-xs text-gray-400">Duration</p>
            <p className="font-semibold">{activity.duration_formatted}</p>
          </div>
        )}

        {activity.average_heartrate && (
          <div>
            <p className="text-xs text-gray-400">Avg HR</p>
            <p className="font-semibold">{activity.average_heartrate} bpm</p>
          </div>
        )}
      </div>

      {showInsights && activity.performance_percentage && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-400">
            Age-Graded: {activity.performance_percentage.toFixed(1)}%
          </p>
        </div>
      )}
    </div>
  );

  // In selection mode, clicking the card also toggles selection
  if (selectionMode) {
    return (
      <div onClick={handleCheckboxClick}>
        {cardContent}
      </div>
    );
  }

  // Normal mode: link to activity detail
  return (
    <Link href={`/activities/${activity.id}`}>
      {cardContent}
    </Link>
  );
}


