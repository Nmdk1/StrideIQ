/**
 * Activities List Page
 * 
 * Displays list of activities with filtering, pagination, and search.
 * Built with modular components that can be swapped/refactored independently.
 * Supports selection mode for the Comparison Engine.
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useActivities, useActivitiesSummary } from '@/lib/hooks/queries/activities';
import { ActivityCard } from '@/components/activities/ActivityCard';
import {
  ActivityFilterPanel,
  EMPTY_FILTERS,
  filtersToParams,
  paramsToFilters,
  isFiltersActive,
  type ActivityFiltersState,
} from '@/components/activities/ActivityFilterPanel';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { UnitToggle } from '@/components/ui/UnitToggle';
import { useUnits } from '@/lib/context/UnitsContext';
import { useCompareSelection } from '@/lib/context/CompareContext';
import { ComparisonBasket } from '@/components/compare/ComparisonBasket';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Activity, BarChart3, Clock, Flame, Trophy, ChevronLeft, ChevronRight, Footprints, Layers } from 'lucide-react';
import type { ActivityListParams, ActivitySummaryBucket } from '@/lib/api/services/activities';

type SportView = 'running' | 'other' | 'combined';

const SPORT_VIEW_OPTIONS: { value: SportView; label: string; icon: React.ReactNode }[] = [
  { value: 'running',  label: 'Running', icon: <Footprints className="w-3.5 h-3.5" /> },
  { value: 'other',    label: 'Other',   icon: <Activity className="w-3.5 h-3.5" /> },
  { value: 'combined', label: 'All',     icon: <Layers className="w-3.5 h-3.5" /> },
];

export default function ActivitiesPage() {
  // useSearchParams must be inside a Suspense boundary per Next.js 14
  return (
    <Suspense fallback={null}>
      <ActivitiesPageInner />
    </Suspense>
  );
}

/** Exported for behavioral tests (sport view toggle + stat cards). */
export function ActivitiesPageInner() {
  const { units, formatDistance, formatPace, distanceUnitShort, paceUnit } = useUnits();
  const { 
    isSelected, 
    toggleSelection, 
    canAddMore, 
    selectionCount,
    clearSelection,
  } = useCompareSelection();
  
  const [selectionMode, setSelectionMode] = useState(false);
  const [sportView, setSportView] = useState<SportView>('running');
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState<ActivityListParams>({
    limit: 20,
    offset: 0,
    sort_by: 'start_time',
    sort_order: 'desc',
  });
  const [filterState, setFilterState] = useState<ActivityFiltersState>(EMPTY_FILTERS);

  // Hydrate filter state from URL on first load (deep-link restore).
  // We intentionally only run this on mount — subsequent URL changes are
  // driven by user filter input, which already updates state directly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!searchParams) return;
    const restored = paramsToFilters(searchParams);
    setFilterState(restored);
  }, []);

  // Combine sort/pagination filters with the structural filter state
  const combinedParams = useMemo<ActivityListParams>(() => {
    const fp = filtersToParams(filterState);
    return {
      ...filters,
      ...fp,
      ...(fp.min_distance_m ? { min_distance_m: Number(fp.min_distance_m) } : {}),
      ...(fp.max_distance_m ? { max_distance_m: Number(fp.max_distance_m) } : {}),
      ...(fp.temp_min ? { temp_min: Number(fp.temp_min) } : {}),
      ...(fp.temp_max ? { temp_max: Number(fp.temp_max) } : {}),
      ...(fp.dew_min ? { dew_min: Number(fp.dew_min) } : {}),
      ...(fp.dew_max ? { dew_max: Number(fp.dew_max) } : {}),
      ...(fp.elev_gain_min ? { elev_gain_min: Number(fp.elev_gain_min) } : {}),
      ...(fp.elev_gain_max ? { elev_gain_max: Number(fp.elev_gain_max) } : {}),
    };
  }, [filters, filterState]);

  const { data: activities, isLoading, error } = useActivities(combinedParams);
  const { data: summary } = useActivitiesSummary(30);

  // Sync filter state to URL — shareable, refresh-stable
  useEffect(() => {
    const sp = new URLSearchParams();
    const fp = filtersToParams(filterState);
    Object.entries(fp).forEach(([k, v]) => {
      if (v != null) sp.set(k, String(v));
    });
    const qs = sp.toString();
    const target = qs ? `/activities?${qs}` : '/activities';
    router.replace(target, { scroll: false });
  }, [filterState, router]);

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

  // Pick the active stat-bucket. New API returns running/other/combined; old
  // API only had top-level fields — fall back to those so this works during
  // the deploy window where backend may be a step ahead/behind.
  const activeBucket = useMemo(() => {
    if (!summary) return null;
    const bucket = summary[sportView];
    if (bucket) return bucket;
    if (sportView === 'running') {
      return {
        total_activities: summary.total_activities,
        total_distance_m: summary.total_distance_m,
        total_duration_s: summary.total_duration_s,
        avg_pace_s_per_km: summary.avg_pace_s_per_km,
        race_count: summary.race_count,
      };
    }
    return null;
  }, [summary, sportView]);

  const getTotalDistance = () => {
    if (!activeBucket) return null;
    return formatDistance(activeBucket.total_distance_m, 1);
  };

  const getAveragePace = () => {
    if (sportView !== 'running' || !activeBucket) return null;
    const pace = (activeBucket as ActivitySummaryBucket).avg_pace_s_per_km;
    if (!pace) return null;
    return formatPace(pace);
  };

  const handleFilterChange = (newFilters: Partial<ActivityListParams>) => {
    setFilters((prev) => ({ ...prev, ...newFilters, offset: 0 })); // Reset to first page
  };

  const handlePageChange = (newOffset: number) => {
    setFilters((prev) => ({ ...prev, offset: newOffset }));
  };

  const handleStructuralFilterChange = (next: ActivityFiltersState) => {
    setFilterState(next);
    setFilters((prev) => ({ ...prev, offset: 0 })); // any filter change resets pagination
  };

  const filtersActive = isFiltersActive(filterState);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8 pb-24">
      <div className="max-w-6xl mx-auto px-4">
        
        {/* Selection mode banner */}
        {selectionMode && (
          <Card className="mb-4 bg-orange-900/30 border-orange-700/50">
            <CardContent className="py-3 text-center">
              <p className="text-orange-200 flex items-center justify-center gap-2">
                <BarChart3 className="w-4 h-4" />
                <strong>Compare Mode:</strong> Click activities to select them for comparison (max 10)
              </p>
            </CardContent>
          </Card>
        )}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
              <Activity className="w-6 h-6 text-orange-500" />
            </div>
            <h1 className="text-2xl md:text-3xl font-bold">Activities</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 md:gap-4">
            {/* Compare mode toggle */}
            <button
              onClick={handleToggleSelectionMode}
              className={`px-3 md:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectionMode
                  ? 'bg-orange-600 text-white'
                  : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
              }`}
            >
              {selectionMode 
                ? selectionCount > 0 
                  ? `${selectionCount} Selected` 
                  : 'Select'
                : '📊 Compare'}
            </button>
            {selectionMode && selectionCount > 0 && (
              <button
                onClick={clearSelection}
                className="text-sm text-slate-400 hover:text-white"
              >
                Clear
              </button>
            )}
            <UnitToggle />
            {summary && !selectionMode && (
              <div className="hidden md:block text-sm text-slate-400">
                {summary.total_activities} activities in last {summary.period_days} days
              </div>
            )}
          </div>
        </div>

        {/* Sport view toggle — Running is canonical (default); Other / All
            are explicit alternates so non-running activity is never silently
            mixed into running totals. */}
        {summary && (
          <div className="mb-3 inline-flex rounded-lg border border-slate-700 bg-slate-800/60 p-0.5 text-xs">
            {SPORT_VIEW_OPTIONS.map((opt) => {
              const isActive = sportView === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    setSportView(opt.value);
                    // Sync the list filter so the cards and the list agree.
                    // 'combined' clears the sport filter (show everything).
                    // 'other' clears sport (the sport-pills below are the
                    // drill-down); 'running' pins sport=run.
                    if (opt.value === 'running') handleFilterChange({ sport: 'run' });
                    else handleFilterChange({ sport: undefined });
                  }}
                  aria-pressed={isActive}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? 'bg-orange-500 text-white'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700/60'
                  }`}
                >
                  {opt.icon}
                  {opt.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Summary Stats — sport-aware. Avg Pace is hidden for non-running
            views (not a meaningful aggregate across walks + strength + cycling). */}
        {summary && activeBucket && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Card className="bg-slate-800 border-slate-700">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                  <Activity className="w-3.5 h-3.5 text-orange-500" />
                  {sportView === 'running' ? 'Running Distance' : sportView === 'other' ? 'Other Distance' : 'Total Distance'}
                </p>
                <p className="text-lg font-semibold">{getTotalDistance()}</p>
              </CardContent>
            </Card>
            <Card className="bg-slate-800 border-slate-700">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                  <Clock className="w-3.5 h-3.5 text-blue-500" />
                  Total Time
                </p>
                <p className="text-lg font-semibold">{(activeBucket.total_duration_s / 3600).toFixed(1)} hrs</p>
              </CardContent>
            </Card>
            {sportView === 'running' ? (
              <Card className="bg-slate-800 border-slate-700">
                <CardContent className="pt-4 pb-4">
                  <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                    <Flame className="w-3.5 h-3.5 text-red-500" />
                    Avg Pace
                  </p>
                  <p className="text-lg font-semibold">{getAveragePace() ?? 'N/A'}</p>
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-slate-800 border-slate-700">
                <CardContent className="pt-4 pb-4">
                  <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                    <BarChart3 className="w-3.5 h-3.5 text-emerald-500" />
                    Activities
                  </p>
                  <p className="text-lg font-semibold">{activeBucket.total_activities}</p>
                </CardContent>
              </Card>
            )}
            <Card className="bg-slate-800 border-slate-700">
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                  <Trophy className="w-3.5 h-3.5 text-yellow-500" />
                  {sportView === 'running' ? 'Races' : 'Sports'}
                </p>
                <p className="text-lg font-semibold">
                  {sportView === 'running'
                    ? ((activeBucket as ActivitySummaryBucket).race_count ?? 0)
                    : sportView === 'other'
                      ? Object.keys(summary.other?.by_sport ?? {}).length
                      : Object.keys(summary.activities_by_sport ?? {}).length}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* When viewing "Other", expose a small sport breakdown so the athlete
            can drill from sport into the filtered list in one tap. */}
        {sportView === 'other' && summary?.other?.by_sport && Object.keys(summary.other.by_sport).length > 0 && (
          <div className="mb-6 flex flex-wrap gap-2">
            {Object.entries(summary.other.by_sport).map(([sport, bucket]) => (
              <button
                key={sport}
                type="button"
                onClick={() => handleFilterChange({ sport })}
                className={`text-xs rounded-md border px-2.5 py-1 inline-flex items-center gap-1.5 capitalize ${
                  filters.sport === sport
                    ? 'border-orange-500 bg-orange-500/20 text-white'
                    : 'border-slate-700 bg-slate-800/60 hover:bg-slate-700/60 text-slate-200'
                }`}
                aria-label={`Filter list to ${sport}`}
                aria-pressed={filters.sport === sport}
              >
                <span className="font-semibold">{sport}</span>
                <span className="text-slate-400">·</span>
                <span className="tabular-nums">{bucket.total_activities}</span>
                {bucket.total_distance_m > 0 && (
                  <>
                    <span className="text-slate-400">·</span>
                    <span className="tabular-nums">
                      {formatDistance(bucket.total_distance_m, 1)}
                    </span>
                  </>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Brushable filter panel — see docs/specs/phase1_filters_design.md */}
        <ActivityFilterPanel value={filterState} onChange={handleStructuralFilterChange} />

        {/* Compact secondary controls (sort, race/training scope, page size) */}
        <div className="flex flex-wrap items-end gap-3 mb-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 uppercase tracking-wide">Sort</span>
            <select
              value={filters.sort_by || 'start_time'}
              onChange={(e) =>
                handleFilterChange({
                  sort_by: e.target.value as 'start_time' | 'distance_m' | 'duration_s',
                })
              }
              className="bg-slate-900 border border-slate-700 rounded text-slate-200 px-2 py-1 focus:border-orange-500 focus:outline-none"
            >
              <option value="start_time">Date</option>
              <option value="distance_m">Distance</option>
              <option value="duration_s">Duration</option>
            </select>
            <select
              value={filters.sort_order || 'desc'}
              onChange={(e) =>
                handleFilterChange({ sort_order: e.target.value as 'asc' | 'desc' })
              }
              className="bg-slate-900 border border-slate-700 rounded text-slate-200 px-2 py-1 focus:border-orange-500 focus:outline-none"
            >
              <option value="desc">Newest</option>
              <option value="asc">Oldest</option>
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 uppercase tracking-wide">Show</span>
            <select
              value={filters.is_race === undefined ? 'all' : filters.is_race ? 'races' : 'training'}
              onChange={(e) => {
                const value = e.target.value;
                handleFilterChange({
                  is_race: value === 'all' ? undefined : value === 'races',
                });
              }}
              className="bg-slate-900 border border-slate-700 rounded text-slate-200 px-2 py-1 focus:border-orange-500 focus:outline-none"
            >
              <option value="all">All</option>
              <option value="races">Races</option>
              <option value="training">Training</option>
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 uppercase tracking-wide">Per page</span>
            <select
              value={filters.limit || 20}
              onChange={(e) =>
                handleFilterChange({ limit: parseInt(e.target.value), offset: 0 })
              }
              className="bg-slate-900 border border-slate-700 rounded text-slate-200 px-2 py-1 focus:border-orange-500 focus:outline-none"
            >
              <option value="10">10</option>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
          {filtersActive && activities && (
            <div className="ml-auto text-slate-300 tabular-nums">
              {activities.length}{activities.length === (filters.limit || 20) ? '+' : ''} match
            </div>
          )}
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
          <div className="text-center py-12 text-slate-400">
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
                    name: activity.resolved_title ?? activity.name,
                    date: activity.start_date,
                    workout_type: activity.workout_type || null,
                    distance_m: activity.distance,
                  })}
                />
              ))}
            </div>

            {/* Pagination */}
            <div className="flex justify-center items-center gap-4 mt-8">
              <Button
                variant="outline"
                onClick={() => handlePageChange(Math.max(0, (filters.offset || 0) - (filters.limit || 20)))}
                disabled={(filters.offset || 0) === 0}
                className="border-slate-700 hover:bg-slate-800"
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                Previous
              </Button>
              <Badge variant="outline" className="text-slate-400 border-slate-600 px-3 py-1">
                Page {Math.floor((filters.offset || 0) / (filters.limit || 20)) + 1}
              </Badge>
              <Button
                variant="outline"
                onClick={() => handlePageChange((filters.offset || 0) + (filters.limit || 20))}
                disabled={activities.length < (filters.limit || 20)}
                className="border-slate-700 hover:bg-slate-800"
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
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

