'use client';

/**
 * Comparison Page
 * 
 * The key differentiator - compare workouts by type, conditions, time periods.
 * Neither Garmin nor Strava offer this level of comparison.
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { 
  useWorkoutTypeSummary, 
  useCompareByType, 
  useClassifyActivities 
} from '@/lib/hooks/queries/compare';
import { useUnits } from '@/lib/context/UnitsContext';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

// Workout type display names
const WORKOUT_TYPE_LABELS: Record<string, string> = {
  easy_run: 'Easy Run',
  recovery_run: 'Recovery Run',
  long_run: 'Long Run',
  medium_long_run: 'Medium Long Run',
  aerobic_run: 'Aerobic Run',
  tempo_run: 'Tempo Run',
  tempo_intervals: 'Tempo Intervals',
  threshold_run: 'Threshold Run',
  vo2max_intervals: 'VO2max Intervals',
  fartlek: 'Fartlek',
  track_workout: 'Track Workout',
  marathon_pace: 'Marathon Pace',
  progression_run: 'Progression Run',
  fast_finish_long_run: 'Fast Finish Long Run',
  race: 'Race',
  unclassified: 'Unclassified',
};

// Trend colors and icons
const TREND_DISPLAY = {
  improving: { color: 'text-green-400', icon: '↑', label: 'Improving' },
  declining: { color: 'text-red-400', icon: '↓', label: 'Declining' },
  stable: { color: 'text-gray-400', icon: '→', label: 'Stable' },
};

function WorkoutTypeCard({ 
  type, 
  count, 
  isSelected, 
  onClick 
}: { 
  type: string; 
  count: number; 
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`p-4 rounded-lg border transition-all text-left ${
        isSelected 
          ? 'bg-orange-900/30 border-orange-600' 
          : 'bg-gray-800 border-gray-700 hover:border-gray-600'
      }`}
    >
      <div className="text-lg font-medium">
        {WORKOUT_TYPE_LABELS[type] || type}
      </div>
      <div className="text-sm text-gray-400">
        {count} {count === 1 ? 'run' : 'runs'}
      </div>
    </button>
  );
}

function ComparisonDetails({ workoutType, days }: { workoutType: string; days: number }) {
  const { data, isLoading, error } = useCompareByType(workoutType, days);
  const { formatDistance, formatPace } = useUnits();

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-8 text-gray-400">
        Unable to load comparison data
      </div>
    );
  }

  if (data.total_activities === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No activities of this type found in the selected period
      </div>
    );
  }

  const effTrend = data.efficiency_trend ? TREND_DISPLAY[data.efficiency_trend] : null;
  const paceTrend = data.pace_trend ? TREND_DISPLAY[data.pace_trend] : null;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Total Runs</div>
          <div className="text-2xl font-bold">{data.total_activities}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Total Distance</div>
          <div className="text-2xl font-bold">{formatDistance(data.total_distance_km * 1000, 0)}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Avg Pace</div>
          <div className="text-2xl font-bold">
            {data.avg_pace_per_km ? formatPace(data.avg_pace_per_km) : '-'}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Avg HR</div>
          <div className="text-2xl font-bold">
            {data.avg_hr ? `${Math.round(data.avg_hr)} bpm` : '-'}
          </div>
        </div>
      </div>

      {/* Trends */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {effTrend && (
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-sm text-gray-400 mb-2">Efficiency Trend</div>
            <div className={`text-xl font-bold ${effTrend.color}`}>
              {effTrend.icon} {effTrend.label}
              {data.efficiency_change_pct !== null && (
                <span className="text-sm ml-2">
                  ({data.efficiency_change_pct > 0 ? '+' : ''}{data.efficiency_change_pct.toFixed(1)}%)
                </span>
              )}
            </div>
            <div className="text-sm text-gray-500 mt-1">
              Based on comparing recent vs older {WORKOUT_TYPE_LABELS[workoutType] || workoutType}s
            </div>
          </div>
        )}
        {paceTrend && (
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-sm text-gray-400 mb-2">Pace Trend</div>
            <div className={`text-xl font-bold ${paceTrend.color}`}>
              {paceTrend.icon} {paceTrend.label}
              {data.pace_change_pct !== null && (
                <span className="text-sm ml-2">
                  ({data.pace_change_pct > 0 ? '+' : ''}{data.pace_change_pct.toFixed(1)}%)
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Best & Worst */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.best_activity && (
          <Link href={`/activities/${data.best_activity.id}`}>
            <div className="bg-green-900/20 rounded-lg p-4 border border-green-700/50 hover:border-green-600 transition-colors cursor-pointer">
              <div className="text-sm text-green-400 mb-2">🏆 Best Performance</div>
              <div className="text-lg font-medium">
                {new Date(data.best_activity.date).toLocaleDateString('en-US', { 
                  month: 'short', day: 'numeric', year: 'numeric' 
                })}
              </div>
              <div className="text-sm text-gray-400">
                {formatDistance(data.best_activity.distance_m, 1)} • 
                {data.best_activity.pace_formatted || '-'} • 
                {data.best_activity.avg_hr || '-'} bpm
              </div>
            </div>
          </Link>
        )}
        {data.worst_activity && (
          <Link href={`/activities/${data.worst_activity.id}`}>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors cursor-pointer">
              <div className="text-sm text-gray-400 mb-2">📉 Lowest Efficiency</div>
              <div className="text-lg font-medium">
                {new Date(data.worst_activity.date).toLocaleDateString('en-US', { 
                  month: 'short', day: 'numeric', year: 'numeric' 
                })}
              </div>
              <div className="text-sm text-gray-400">
                {formatDistance(data.worst_activity.distance_m, 1)} • 
                {data.worst_activity.pace_formatted || '-'} • 
                {data.worst_activity.avg_hr || '-'} bpm
              </div>
            </div>
          </Link>
        )}
      </div>

      {/* Activity List */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-700">
          <h3 className="font-semibold">All {WORKOUT_TYPE_LABELS[workoutType] || workoutType}s</h3>
        </div>
        <div className="divide-y divide-gray-700">
          {data.activities.slice(0, 15).map((activity) => (
            <Link key={activity.id} href={`/activities/${activity.id}`}>
              <div className="p-4 hover:bg-gray-700/50 transition-colors cursor-pointer flex justify-between items-center">
                <div>
                  <div className="font-medium">
                    {new Date(activity.date).toLocaleDateString('en-US', { 
                      weekday: 'short', month: 'short', day: 'numeric' 
                    })}
                  </div>
                  <div className="text-sm text-gray-400">
                    {formatDistance(activity.distance_m, 1)}
                    {activity.temperature_f && ` • ${activity.temperature_f}°F`}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-medium">{activity.pace_formatted || '-'}</div>
                  <div className="text-sm text-gray-400">{activity.avg_hr || '-'} bpm</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
        {data.activities.length > 15 && (
          <div className="p-4 text-center text-gray-400 text-sm">
            Showing 15 of {data.activities.length} activities
          </div>
        )}
      </div>
    </div>
  );
}

export default function ComparePage() {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [days, setDays] = useState(180);
  
  const { data: summary, isLoading: summaryLoading } = useWorkoutTypeSummary();
  const classifyMutation = useClassifyActivities();

  const handleClassify = async () => {
    await classifyMutation.mutateAsync();
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-6">
        <div className="max-w-6xl mx-auto px-4">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-bold">Compare Workouts</h1>
            <p className="text-gray-400">
              Analyze trends across similar workout types
            </p>
          </div>

          {summaryLoading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner size="lg" />
            </div>
          ) : summary && Object.keys(summary.workout_types).length === 0 ? (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
              <h2 className="text-xl font-semibold mb-4">No Classified Activities Yet</h2>
              <p className="text-gray-400 mb-6">
                Your activities need to be classified into workout types before you can compare them.
              </p>
              <button
                onClick={handleClassify}
                disabled={classifyMutation.isPending}
                className="px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 rounded-lg font-medium transition-colors"
              >
                {classifyMutation.isPending ? 'Classifying...' : 'Classify My Activities'}
              </button>
              {classifyMutation.isSuccess && (
                <p className="mt-4 text-green-400">
                  {classifyMutation.data?.message}
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Workout Type Selector */}
              <div className="lg:col-span-1">
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <div className="flex justify-between items-center mb-4">
                    <h2 className="font-semibold">Workout Types</h2>
                    <button
                      onClick={handleClassify}
                      disabled={classifyMutation.isPending}
                      className="text-xs text-orange-400 hover:text-orange-300"
                      title="Re-classify activities"
                    >
                      {classifyMutation.isPending ? '...' : '🔄 Refresh'}
                    </button>
                  </div>
                  
                  <div className="space-y-2">
                    {summary && Object.entries(summary.workout_types)
                      .sort((a, b) => b[1] - a[1])
                      .map(([type, count]) => (
                        <WorkoutTypeCard
                          key={type}
                          type={type}
                          count={count}
                          isSelected={selectedType === type}
                          onClick={() => setSelectedType(type)}
                        />
                      ))}
                  </div>

                  {/* Time Range Selector */}
                  <div className="mt-6 pt-4 border-t border-gray-700">
                    <label className="text-sm text-gray-400 block mb-2">Time Range</label>
                    <select
                      value={days}
                      onChange={(e) => setDays(parseInt(e.target.value))}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                    >
                      <option value={30}>Last 30 days</option>
                      <option value={60}>Last 60 days</option>
                      <option value={90}>Last 90 days</option>
                      <option value={180}>Last 180 days</option>
                      <option value={365}>Last year</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Comparison Details */}
              <div className="lg:col-span-2">
                {selectedType ? (
                  <ComparisonDetails workoutType={selectedType} days={days} />
                ) : (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
                    <div className="text-4xl mb-4">📊</div>
                    <h2 className="text-xl font-semibold mb-2">Select a Workout Type</h2>
                    <p className="text-gray-400">
                      Choose a workout type from the left to see trends and compare performances
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
