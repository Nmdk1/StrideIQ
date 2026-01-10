/**
 * Activities List Page
 * 
 * Displays list of activities with filtering, pagination, and search.
 * Built with modular components that can be swapped/refactored independently.
 * Supports selection mode for the Comparison Engine.
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

import { useState } from 'react';
import { useActivities, useActivitiesSummary } from '@/lib/hooks/queries/activities';
import { ActivityCard } from '@/components/activities/ActivityCard';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { UnitToggle } from '@/components/ui/UnitToggle';
import { useUnits } from '@/lib/context/UnitsContext';
import { useCompareSelection } from '@/lib/context/CompareContext';
import { ComparisonBasket } from '@/components/compare/ComparisonBasket';
import type { ActivityListParams } from '@/lib/api/services/activities';

export default function ActivitiesPage() {
  const { units, formatDistance, formatPace, distanceUnitShort, paceUnit } = useUnits();
  const { 
    isSelected, 
    toggleSelection, 
    canAddMore, 
    selectionCount,
    clearSelection,
  } = useCompareSelection();
  
  const [selectionMode, setSelectionMode] = useState(false);
  
  const [filters, setFilters] = useState<ActivityListParams>({
    limit: 20,
    offset: 0,
    sort_by: 'start_time',
    sort_order: 'desc',
  });

  const { data: activities, isLoading, error } = useActivities(filters);
  const { data: summary } = useActivitiesSummary(30);

  const handleToggleSelectionMode = () => {
    if (selectionMode && selectionCount === 0) {
      // Exiting selection mode with no selections
      setSelectionMode(false);
    } else if (selectionMode) {
      // Exiting with selections - keep them for compare page
      setSelectionMode(false);
    } else {
      // Entering selection mode
      setSelectionMode(true);
    }
  };

  // Calculate distance in user's preferred units
  const getTotalDistance = () => {
    if (!summary) return null;
    // API returns miles, convert to meters then use formatDistance
    const meters = summary.total_distance_miles * 1609.34;
    return formatDistance(meters, 1);
  };

  // Format average pace in user's preferred units
  const getAveragePace = () => {
    if (!summary?.average_pace_per_mile) return 'N/A';
    // Convert min/mile to seconds/km if metric
    const paceMinPerMile = summary.average_pace_per_mile;
    if (units === 'metric') {
      const paceMinPerKm = paceMinPerMile / 1.60934;
      return `${Math.floor(paceMinPerKm)}:${Math.round((paceMinPerKm % 1) * 60).toString().padStart(2, '0')}/km`;
    }
    return `${Math.floor(paceMinPerMile)}:${Math.round((paceMinPerMile % 1) * 60).toString().padStart(2, '0')}/mi`;
  };

  const handleFilterChange = (newFilters: Partial<ActivityListParams>) => {
    setFilters((prev) => ({ ...prev, ...newFilters, offset: 0 })); // Reset to first page
  };

  const handlePageChange = (newOffset: number) => {
    setFilters((prev) => ({ ...prev, offset: newOffset }));
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8 pb-24">
      <div className="max-w-6xl mx-auto px-4">
        
        {/* Selection mode banner */}
        {selectionMode && (
          <div className="mb-4 bg-orange-900/30 border border-orange-700/50 rounded-lg p-3 text-center">
            <p className="text-orange-200">
              📊 <strong>Compare Mode:</strong> Click activities to select them for comparison (max 10)
            </p>
          </div>
        )}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">Activities</h1>
          <div className="flex items-center gap-4">
            {/* Compare mode toggle */}
            <button
              onClick={handleToggleSelectionMode}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectionMode
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
              }`}
            >
              {selectionMode 
                ? selectionCount > 0 
                  ? `${selectionCount} Selected` 
                  : 'Select to Compare'
                : '📊 Compare'}
            </button>
            {selectionMode && selectionCount > 0 && (
              <button
                onClick={clearSelection}
                className="text-sm text-gray-400 hover:text-white"
              >
                Clear
              </button>
            )}
            <UnitToggle />
            {summary && !selectionMode && (
              <div className="text-sm text-gray-400">
                {summary.total_activities} activities in last {summary.period_days} days
              </div>
            )}
          </div>
        </div>

        {/* Summary Stats */}
        {summary && (
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-400">Total Distance</p>
                <p className="text-lg font-semibold">
                  {getTotalDistance()}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Total Time</p>
                <p className="text-lg font-semibold">
                  {summary.total_duration_hours.toFixed(1)} hrs
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Avg Pace</p>
                <p className="text-lg font-semibold">
                  {getAveragePace()}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Races</p>
                <p className="text-lg font-semibold">{summary.race_count}</p>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Sort By</label>
              <select
                value={filters.sort_by || 'start_time'}
                onChange={(e) =>
                  handleFilterChange({
                    sort_by: e.target.value as 'start_time' | 'distance_m' | 'duration_s',
                  })
                }
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
              >
                <option value="start_time">Date</option>
                <option value="distance_m">Distance</option>
                <option value="duration_s">Duration</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Order</label>
              <select
                value={filters.sort_order || 'desc'}
                onChange={(e) =>
                  handleFilterChange({
                    sort_order: e.target.value as 'asc' | 'desc',
                  })
                }
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
              >
                <option value="desc">Newest First</option>
                <option value="asc">Oldest First</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Show</label>
              <select
                value={filters.is_race === undefined ? 'all' : filters.is_race ? 'races' : 'training'}
                onChange={(e) => {
                  const value = e.target.value;
                  handleFilterChange({
                    is_race: value === 'all' ? undefined : value === 'races',
                  });
                }}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
              >
                <option value="all">All Activities</option>
                <option value="races">Races Only</option>
                <option value="training">Training Only</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Per Page</label>
              <select
                value={filters.limit || 20}
                onChange={(e) =>
                  handleFilterChange({ limit: parseInt(e.target.value), offset: 0 })
                }
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
              >
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </div>
          </div>
        </div>

        {/* Activities List */}
        {isLoading && (
          <div className="flex justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {error && (
          <ErrorMessage error={error} title="Failed to load activities" />
        )}

        {activities && activities.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p>No activities found</p>
            <p className="text-sm mt-2">Sync activities from Strava or create one manually</p>
          </div>
        )}

        {activities && activities.length > 0 && (
          <>
            <div className="space-y-4">
              {activities.map((activity) => (
                <ActivityCard 
                  key={activity.id} 
                  activity={activity} 
                  showInsights 
                  selectionMode={selectionMode}
                  isSelected={isSelected(activity.id)}
                  canSelect={canAddMore}
                  onToggleSelection={() => toggleSelection({
                    id: activity.id,
                    name: activity.name,
                    date: activity.start_date,
                    workout_type: activity.workout_type || null,
                    distance_m: activity.distance,
                  })}
                />
              ))}
            </div>

            {/* Pagination */}
            <div className="flex justify-center items-center gap-4 mt-8">
              <button
                onClick={() => handlePageChange(Math.max(0, (filters.offset || 0) - (filters.limit || 20)))}
                disabled={(filters.offset || 0) === 0}
                className="px-4 py-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-400">
                Page {Math.floor((filters.offset || 0) / (filters.limit || 20)) + 1}
              </span>
              <button
                onClick={() =>
                  handlePageChange((filters.offset || 0) + (filters.limit || 20))
                }
                disabled={activities.length < (filters.limit || 20)}
                className="px-4 py-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
    
    {/* Comparison basket (floating) */}
    <ComparisonBasket />
    </ProtectedRoute>
  );
}

