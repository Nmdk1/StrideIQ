'use client';

/**
 * Compare Page - Contextual Comparison Hub
 * 
 * The differentiator feature: Compare runs in context, not just by distance.
 * Supports both:
 * 1. Auto-find similar runs (click any run)
 * 2. Manual selection (select 2-10 runs to compare)
 * 3. Filter by HR range
 */

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useActivities } from '@/lib/hooks/queries/activities';
import { useQuickScore, useCompareSelected } from '@/lib/hooks/queries/contextual-compare';
import { useUnits } from '@/lib/context/UnitsContext';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

// Quick score badge component
function QuickScoreBadge({ activityId }: { activityId: string }) {
  const { data: quickScore, isLoading } = useQuickScore(activityId);
  
  if (isLoading) {
    return <div className="w-8 h-8 bg-gray-700 rounded-full animate-pulse" />;
  }
  
  if (!quickScore?.score) {
    return null;
  }
  
  const getScoreColor = (score: number) => {
    if (score >= 70) return 'bg-green-500 text-white';
    if (score >= 55) return 'bg-blue-500 text-white';
    if (score >= 45) return 'bg-gray-500 text-white';
    if (score >= 30) return 'bg-yellow-500 text-gray-900';
    return 'bg-red-500 text-white';
  };
  
  return (
    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${getScoreColor(quickScore.score)}`} title={`Performance Score: ${Math.round(quickScore.score)}`}>
      {Math.round(quickScore.score)}
    </div>
  );
}

// Activity row with selection
function ActivityRow({ 
  activity, 
  formatDistance, 
  formatPace,
  isSelected,
  onToggleSelect,
  selectionMode,
}: { 
  activity: any; 
  formatDistance: (m: number, decimals?: number) => string;
  formatPace: (secPerKm: number) => string;
  isSelected: boolean;
  onToggleSelect: () => void;
  selectionMode: boolean;
}) {
  // Handle both API field names (distance vs distance_m, moving_time vs duration_s)
  const distance = activity.distance ?? activity.distance_m ?? 0;
  const duration = activity.moving_time ?? activity.duration_s ?? 0;
  const avgHr = activity.average_heartrate ?? activity.avg_hr;
  const maxHr = activity.max_hr;
  const startDate = activity.start_date ?? activity.start_time;
  
  const pacePerKm = duration && distance 
    ? duration / (distance / 1000) 
    : null;
  
  return (
    <div 
      className={`bg-gray-800 border rounded-xl p-4 transition-all group cursor-pointer ${
        isSelected 
          ? 'border-orange-500 bg-orange-900/20' 
          : 'border-gray-700 hover:border-gray-600'
      }`}
      onClick={selectionMode ? onToggleSelect : undefined}
    >
      <div className="flex items-center gap-4">
        {/* Checkbox for selection mode */}
        {selectionMode && (
          <div className={`w-6 h-6 rounded border-2 flex items-center justify-center transition-all ${
            isSelected 
              ? 'bg-orange-500 border-orange-500' 
              : 'border-gray-500 hover:border-gray-400'
          }`}>
            {isSelected && (
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        )}
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-sm text-gray-400">
              {startDate ? new Date(startDate).toLocaleDateString('en-US', { 
                weekday: 'short', month: 'short', day: 'numeric' 
              }) : '-'}
            </span>
            {activity.workout_type && (
              <span className="text-xs px-2 py-0.5 bg-gray-700 rounded-full text-gray-300">
                {activity.workout_type.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          <div className="font-medium truncate">
            {activity.name || 'Untitled Run'}
          </div>
        </div>
        
        <div className="flex items-center gap-6 text-sm">
          <div className="text-right">
            <div className="font-medium">{formatDistance(distance, 1)}</div>
            <div className="text-gray-400">{pacePerKm ? formatPace(pacePerKm) : '-'}</div>
          </div>
          <div className="text-right w-16">
            <div className="font-medium">{avgHr || '-'}</div>
            <div className="text-gray-400 text-xs">avg bpm</div>
          </div>
          <div className="text-right w-16">
            <div className="font-medium">{maxHr || '-'}</div>
            <div className="text-gray-400 text-xs">max bpm</div>
          </div>
          
          {!selectionMode && (
            <>
              <QuickScoreBadge activityId={activity.id} />
              <Link
                href={`/compare/context/${activity.id}`}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium rounded-lg transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                Find Similar
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ComparePage() {
  const router = useRouter();
  const [showAll, setShowAll] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [baselineId, setBaselineId] = useState<string | null>(null);
  
  // Filters - Average HR
  const [minAvgHR, setMinAvgHR] = useState<string>('');
  const [maxAvgHR, setMaxAvgHR] = useState<string>('');
  // Filters - Max HR
  const [minMaxHR, setMinMaxHR] = useState<string>('');
  const [maxMaxHR, setMaxMaxHR] = useState<string>('');
  
  const { data: activities, isLoading } = useActivities({ limit: showAll ? 100 : 20 });
  const { formatDistance, formatPace } = useUnits();
  const compareSelectedMutation = useCompareSelected();
  
  // Check if any HR filter is active
  const hasAvgHRFilter = minAvgHR || maxAvgHR;
  const hasMaxHRFilter = minMaxHR || maxMaxHR;
  
  // Filter activities by HR
  const filteredActivities = useMemo(() => {
    if (!activities) return [];
    
    return activities.filter((a: any) => {
      const avgHr = a.average_heartrate ?? a.avg_hr;
      const maxHr = a.max_hr;
      
      // If filtering by avg HR, exclude runs without avg HR data
      if (hasAvgHRFilter) {
        if (!avgHr) return false; // No HR data = exclude
        if (minAvgHR && avgHr < parseInt(minAvgHR)) return false;
        if (maxAvgHR && avgHr > parseInt(maxAvgHR)) return false;
      }
      
      // If filtering by max HR, exclude runs without max HR data
      if (hasMaxHRFilter) {
        if (!maxHr) return false; // No max HR data = exclude
        if (minMaxHR && maxHr < parseInt(minMaxHR)) return false;
        if (maxMaxHR && maxHr > parseInt(maxMaxHR)) return false;
      }
      
      return true;
    });
  }, [activities, minAvgHR, maxAvgHR, minMaxHR, maxMaxHR, hasAvgHRFilter, hasMaxHRFilter]);
  
  const toggleSelection = (id: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
      if (baselineId === id) setBaselineId(null);
    } else {
      if (newSet.size < 10) {
        newSet.add(id);
      }
    }
    setSelectedIds(newSet);
  };
  
  const clearSelection = () => {
    setSelectedIds(new Set());
    setBaselineId(null);
  };
  
  const handleCompareSelected = async () => {
    if (selectedIds.size < 2) return;
    
    try {
      const result = await compareSelectedMutation.mutateAsync({
        activityIds: Array.from(selectedIds),
        baselineId: baselineId || undefined,
      });
      
      // Navigate to the first selected activity's context page with the comparison
      const firstId = baselineId || Array.from(selectedIds)[0];
      router.push(`/compare/context/${firstId}?mode=selected`);
    } catch (error) {
      console.error('Compare failed:', error);
    }
  };
  
  const selectedCount = selectedIds.size;
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-5xl mx-auto px-4">
          
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Compare Runs</h1>
            <p className="text-gray-400">
              Find similar runs automatically, or select 2-10 runs to compare directly
            </p>
          </div>
          
          {/* Mode Toggle + Filters */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 mb-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              {/* Mode Toggle */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setSelectionMode(false);
                    clearSelection();
                  }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    !selectionMode 
                      ? 'bg-orange-600 text-white' 
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  🔍 Find Similar
                </button>
                <button
                  onClick={() => setSelectionMode(true)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectionMode 
                      ? 'bg-orange-600 text-white' 
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  ☑️ Select & Compare
                </button>
              </div>
              
              {/* HR Filters */}
              <div className="flex flex-wrap items-center gap-4">
                {/* Avg HR Filter */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Avg HR:</span>
                  <input
                    type="number"
                    placeholder="Min"
                    value={minAvgHR}
                    onChange={(e) => setMinAvgHR(e.target.value)}
                    className="w-16 px-2 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none"
                  />
                  <span className="text-gray-500">-</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxAvgHR}
                    onChange={(e) => setMaxAvgHR(e.target.value)}
                    className="w-16 px-2 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none"
                  />
                </div>
                
                {/* Max HR Filter */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Max HR:</span>
                  <input
                    type="number"
                    placeholder="Min"
                    value={minMaxHR}
                    onChange={(e) => setMinMaxHR(e.target.value)}
                    className="w-16 px-2 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none"
                  />
                  <span className="text-gray-500">-</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxMaxHR}
                    onChange={(e) => setMaxMaxHR(e.target.value)}
                    className="w-16 px-2 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none"
                  />
                </div>
                
                {(hasAvgHRFilter || hasMaxHRFilter) && (
                  <button
                    onClick={() => { 
                      setMinAvgHR(''); 
                      setMaxAvgHR(''); 
                      setMinMaxHR(''); 
                      setMaxMaxHR(''); 
                    }}
                    className="text-xs text-orange-400 hover:text-orange-300"
                  >
                    Clear filters
                  </button>
                )}
              </div>
            </div>
            
            {/* Selection Mode Instructions */}
            {selectionMode && (
              <div className="mt-4 pt-4 border-t border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-400">
                    {selectedCount === 0 && 'Click runs to select them (2-10 runs)'}
                    {selectedCount === 1 && 'Select at least one more run to compare'}
                    {selectedCount >= 2 && (
                      <span className="text-orange-400">
                        {selectedCount} runs selected
                        {baselineId && ' (baseline set)'}
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {selectedCount > 0 && (
                      <button
                        onClick={clearSelection}
                        className="px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors"
                      >
                        Clear Selection
                      </button>
                    )}
                    {selectedCount >= 2 && (
                      <button
                        onClick={handleCompareSelected}
                        disabled={compareSelectedMutation.isPending}
                        className="px-6 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-600 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
                      >
                        {compareSelectedMutation.isPending ? (
                          <>
                            <LoadingSpinner size="sm" />
                            Comparing...
                          </>
                        ) : (
                          <>
                            Compare {selectedCount} Runs
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
                
                {/* Baseline selector */}
                {selectedCount >= 2 && (
                  <div className="mt-3 text-sm">
                    <span className="text-gray-400">Baseline (optional): </span>
                    <select
                      value={baselineId || ''}
                      onChange={(e) => setBaselineId(e.target.value || null)}
                      className="ml-2 px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none"
                    >
                      <option value="">Most recent selected</option>
                      {Array.from(selectedIds).map(id => {
                        const activity = filteredActivities.find((a: any) => a.id === id);
                        return (
                          <option key={id} value={id}>
                            {activity?.name || 'Run'}
                          </option>
                        );
                      })}
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Activity List */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">
                {filteredActivities.length} runs
                {(hasAvgHRFilter || hasMaxHRFilter) && ' (filtered)'}
              </h2>
            </div>
            
            {isLoading ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner size="lg" />
              </div>
            ) : filteredActivities.length > 0 ? (
              <div className="space-y-2">
                {filteredActivities.map((activity: any) => (
                  <ActivityRow
                    key={activity.id}
                    activity={activity}
                    formatDistance={formatDistance}
                    formatPace={formatPace}
                    isSelected={selectedIds.has(activity.id)}
                    onToggleSelect={() => toggleSelection(activity.id)}
                    selectionMode={selectionMode}
                  />
                ))}
                
                {!showAll && activities && activities.length >= 20 && (
                  <button
                    onClick={() => setShowAll(true)}
                    className="w-full py-3 text-gray-400 hover:text-white transition-colors text-sm"
                  >
                    Show more runs...
                  </button>
                )}
              </div>
            ) : (
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-8 text-center">
                {(hasAvgHRFilter || hasMaxHRFilter) ? (
                  <>
                    <div className="text-4xl mb-4">🔍</div>
                    <h3 className="text-xl font-semibold mb-2">No runs match your filter</h3>
                    <p className="text-gray-400">
                      Try adjusting the HR range. Runs without HR data are excluded when filtering.
                    </p>
                  </>
                ) : (
                  <>
                    <div className="text-4xl mb-4">🏃</div>
                    <h3 className="text-xl font-semibold mb-2">No runs yet</h3>
                    <p className="text-gray-400 mb-4">
                      Sync your Strava account to start comparing your runs
                    </p>
                    <Link
                      href="/settings"
                      className="inline-block px-6 py-3 bg-orange-600 hover:bg-orange-700 rounded-lg font-medium transition-colors"
                    >
                      Connect Strava
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>
          
          {/* How it works */}
          <div className="bg-gray-800/30 rounded-xl border border-gray-700/50 p-6">
            <h3 className="font-semibold mb-4 text-gray-300">Two Ways to Compare</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="text-orange-400 font-medium mb-2">🔍 Find Similar (Auto)</div>
                <p className="text-gray-400">
                  Click &quot;Find Similar&quot; on any run. We automatically find your most similar runs 
                  based on duration, HR, intensity, conditions, and more. Then compare against that baseline.
                </p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="text-orange-400 font-medium mb-2">☑️ Select & Compare (Manual)</div>
                <p className="text-gray-400">
                  Pick 2-10 specific runs you want to compare. Set one as the baseline, then see how the 
                  others stack up. Great for comparing specific races or workouts.
                </p>
              </div>
            </div>
          </div>
          
        </div>
      </div>
    </ProtectedRoute>
  );
}
