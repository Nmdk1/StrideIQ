'use client';

/**
 * Compare Page - Contextual Comparison Hub
 * 
 * Enhanced with shadcn/ui while preserving existing orange accents and hierarchy.
 * 
 * The differentiator feature: Compare runs in context, not just by distance.
 * Supports:
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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Search, 
  CheckSquare, 
  Zap, 
  ArrowRight, 
  Check,
  Heart,
  Activity,
  Calendar,
  X,
  Info,
  Footprints,
  Target,
  Filter
} from 'lucide-react';

// Quick score badge component
function QuickScoreBadge({ activityId }: { activityId: string }) {
  const { data: quickScore, isLoading } = useQuickScore(activityId);
  
  if (isLoading) {
    return <div className="w-10 h-10 bg-slate-700 rounded-full animate-pulse" />;
  }
  
  if (!quickScore?.score) {
    return null;
  }
  
  const getScoreConfig = (score: number) => {
    if (score >= 70) return { bg: 'bg-emerald-500', text: 'text-white', ring: 'ring-emerald-500/30' };
    if (score >= 55) return { bg: 'bg-blue-500', text: 'text-white', ring: 'ring-blue-500/30' };
    if (score >= 45) return { bg: 'bg-slate-500', text: 'text-white', ring: 'ring-slate-500/30' };
    if (score >= 30) return { bg: 'bg-amber-500', text: 'text-slate-900', ring: 'ring-amber-500/30' };
    return { bg: 'bg-red-500', text: 'text-white', ring: 'ring-red-500/30' };
  };
  
  const config = getScoreConfig(quickScore.score);
  
  return (
    <div 
      className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${config.bg} ${config.text} ring-2 ${config.ring} shadow-lg`} 
      title={`Performance Score: ${Math.round(quickScore.score)}`}
    >
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
  const distance = activity.distance ?? activity.distance_m ?? 0;
  const duration = activity.moving_time ?? activity.duration_s ?? 0;
  const avgHr = activity.average_heartrate ?? activity.avg_hr;
  const maxHr = activity.max_hr;
  const startDate = activity.start_date ?? activity.start_time;
  
  const pacePerKm = duration && distance 
    ? duration / (distance / 1000) 
    : null;
  
  return (
    <Card 
      className={`transition-all duration-200 cursor-pointer group ${
        isSelected 
          ? 'border-orange-500 bg-orange-950/30 shadow-lg shadow-orange-500/10' 
          : 'bg-slate-800 border-slate-700 hover:border-slate-600'
      }`}
      onClick={selectionMode ? onToggleSelect : undefined}
    >
      <CardContent className="py-4 px-4">
        <div className="flex items-center gap-4">
          {/* Checkbox for selection mode */}
          {selectionMode && (
            <div className={`w-6 h-6 rounded border-2 flex items-center justify-center transition-all flex-shrink-0 ${
              isSelected 
                ? 'bg-orange-500 border-orange-500' 
                : 'border-slate-500 hover:border-slate-400 group-hover:border-orange-400/50'
            }`}>
              {isSelected && <Check className="w-4 h-4 text-white" strokeWidth={3} />}
            </div>
          )}
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm text-slate-400 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" />
                {startDate ? new Date(startDate).toLocaleDateString('en-US', { 
                  weekday: 'short', month: 'short', day: 'numeric' 
                }) : '-'}
              </span>
              {activity.workout_type && (
                <Badge variant="secondary" className="text-xs bg-slate-700/50 text-slate-300 border-slate-600/50">
                  {activity.workout_type.replace(/_/g, ' ')}
                </Badge>
              )}
            </div>
            <div className="font-medium truncate text-white">
              {activity.name || 'Untitled Run'}
            </div>
          </div>
          
          <div className="flex items-center gap-5 text-sm">
            <div className="text-right">
              <div className="font-semibold text-white flex items-center gap-1.5 justify-end">
                <Footprints className="w-3.5 h-3.5 text-slate-400" />
                {formatDistance(distance, 1)}
              </div>
              <div className="text-slate-400 text-xs">{pacePerKm ? formatPace(pacePerKm) : '-'}</div>
            </div>
            <div className="text-right w-14">
              <div className="font-semibold text-white flex items-center gap-1 justify-end">
                <Heart className="w-3 h-3 text-red-400" />
                {avgHr || '-'}
              </div>
              <div className="text-slate-500 text-[10px] uppercase">avg</div>
            </div>
            <div className="text-right w-14">
              <div className="font-semibold text-white">{maxHr || '-'}</div>
              <div className="text-slate-500 text-[10px] uppercase">max</div>
            </div>
            
            {!selectionMode && (
              <>
                <QuickScoreBadge activityId={activity.id} />
                <Button asChild size="sm" className="bg-orange-600 hover:bg-orange-500 shadow-lg shadow-orange-500/20">
                  <Link
                    href={`/compare/context/${activity.id}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Search className="w-4 h-4 mr-1.5" />
                    Similar
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ComparePage() {
  const router = useRouter();
  const [showAll, setShowAll] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [baselineId, setBaselineId] = useState<string | null>(null);
  
  // Filters
  const [minDistance, setMinDistance] = useState<string>('');
  const [maxDistance, setMaxDistance] = useState<string>('');
  const [minAvgHR, setMinAvgHR] = useState<string>('');
  const [maxAvgHR, setMaxAvgHR] = useState<string>('');
  const [minMaxHR, setMinMaxHR] = useState<string>('');
  const [maxMaxHR, setMaxMaxHR] = useState<string>('');
  
  const { data: activities, isLoading } = useActivities({ limit: showAll ? 100 : 20 });
  const { formatDistance, formatPace, units, setUnits, distanceUnitShort } = useUnits();
  const compareSelectedMutation = useCompareSelected();
  
  const hasDistanceFilter = minDistance || maxDistance;
  const hasAvgHRFilter = minAvgHR || maxAvgHR;
  const hasMaxHRFilter = minMaxHR || maxMaxHR;
  const hasAnyFilter = hasDistanceFilter || hasAvgHRFilter || hasMaxHRFilter;
  
  // Filter activities
  const filteredActivities = useMemo(() => {
    if (!activities) return [];
    
    const parseDistanceToMeters = (value: string): number | null => {
      if (!value) return null;
      const num = parseFloat(value);
      if (isNaN(num)) return null;
      const km = units === 'imperial' ? num * 1.60934 : num;
      return km * 1000;
    };
    
    const minDistanceM = parseDistanceToMeters(minDistance);
    const maxDistanceM = parseDistanceToMeters(maxDistance);
    
    return activities.filter((a: any) => {
      const distance = a.distance ?? a.distance_m ?? 0;
      const avgHr = a.average_heartrate ?? a.avg_hr;
      const maxHr = a.max_hr;
      
      if (hasDistanceFilter) {
        if (!distance) return false;
        if (minDistanceM !== null && distance < minDistanceM) return false;
        if (maxDistanceM !== null && distance > maxDistanceM) return false;
      }
      
      if (hasAvgHRFilter) {
        if (!avgHr) return false;
        if (minAvgHR && avgHr < parseInt(minAvgHR)) return false;
        if (maxAvgHR && avgHr > parseInt(maxAvgHR)) return false;
      }
      
      if (hasMaxHRFilter) {
        if (!maxHr) return false;
        if (minMaxHR && maxHr < parseInt(minMaxHR)) return false;
        if (maxMaxHR && maxHr > parseInt(maxMaxHR)) return false;
      }
      
      return true;
    });
  }, [activities, minDistance, maxDistance, minAvgHR, maxAvgHR, minMaxHR, maxMaxHR, hasDistanceFilter, hasAvgHRFilter, hasMaxHRFilter, units]);
  
  const toggleSelection = (id: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
      if (baselineId === id) setBaselineId(null);
    } else {
      if (newSet.size < 10) newSet.add(id);
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
      sessionStorage.setItem('strideiq_compare_results', JSON.stringify(result));
      router.push('/compare/results');
    } catch (error) {
      console.error('Compare failed:', error);
    }
  };
  
  const handleCompareFiltered = async () => {
    try {
      const ids = filteredActivities.slice(0, 10).map((a: any) => a.id);
      const result = await compareSelectedMutation.mutateAsync({
        activityIds: ids,
        baselineId: undefined,
      });
      sessionStorage.setItem('strideiq_compare_results', JSON.stringify(result));
      router.push('/compare/results');
    } catch (error) {
      console.error('Compare failed:', error);
    }
  };
  
  const selectedCount = selectedIds.size;
  
  const clearFilters = () => {
    setMinDistance('');
    setMaxDistance('');
    setMinAvgHR('');
    setMaxAvgHR('');
    setMinMaxHR('');
    setMaxMaxHR('');
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-5xl mx-auto px-4 py-8">
          
          {/* Header */}
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
              <Activity className="w-6 h-6 text-orange-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Compare Runs</h1>
              <p className="text-sm text-slate-400">
                Find similar runs automatically, or select 2-10 runs to compare directly
              </p>
            </div>
          </div>
          
          {/* Mode Toggle + Filters Card */}
          <Card className="mb-6 bg-slate-800 border-slate-700">
            <CardContent className="pt-5 pb-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                {/* Mode Toggle */}
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => {
                      setSelectionMode(false);
                      clearSelection();
                    }}
                    variant={!selectionMode ? "default" : "secondary"}
                    size="sm"
                    className={!selectionMode ? "bg-orange-600 hover:bg-orange-500" : ""}
                  >
                    <Search className="w-4 h-4 mr-1.5" />
                    Find Similar
                  </Button>
                  <Button
                    onClick={() => setSelectionMode(true)}
                    variant={selectionMode ? "default" : "secondary"}
                    size="sm"
                    className={selectionMode ? "bg-orange-600 hover:bg-orange-500" : ""}
                  >
                    <CheckSquare className="w-4 h-4 mr-1.5" />
                    Select & Compare
                  </Button>
                </div>
                
                {/* Unit Toggle */}
                <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-0.5 ring-1 ring-slate-700">
                  <button
                    onClick={() => setUnits('imperial')}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      units === 'imperial' 
                        ? 'bg-orange-600 text-white shadow-lg' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    mi
                  </button>
                  <button
                    onClick={() => setUnits('metric')}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      units === 'metric' 
                        ? 'bg-orange-600 text-white shadow-lg' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    km
                  </button>
                </div>
              </div>
              
              {/* Filters Row */}
              <div className="flex flex-wrap items-center gap-4 mt-4 pt-4 border-t border-slate-700/50">
                <div className="flex items-center gap-1.5 text-sm text-slate-400">
                  <Filter className="w-4 h-4" />
                  Filters:
                </div>
                
                {/* Distance Filter */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 uppercase tracking-wide">Distance ({distanceUnitShort})</span>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="Min"
                    value={minDistance}
                    onChange={(e) => setMinDistance(e.target.value)}
                    className="w-16 px-2.5 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
                  />
                  <span className="text-slate-600">-</span>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="Max"
                    value={maxDistance}
                    onChange={(e) => setMaxDistance(e.target.value)}
                    className="w-16 px-2.5 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
                  />
                </div>
                
                {/* Avg HR Filter */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1">
                    <Heart className="w-3 h-3 text-red-400" /> Avg
                  </span>
                  <input
                    type="number"
                    placeholder="Min"
                    value={minAvgHR}
                    onChange={(e) => setMinAvgHR(e.target.value)}
                    className="w-16 px-2.5 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
                  />
                  <span className="text-slate-600">-</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxAvgHR}
                    onChange={(e) => setMaxAvgHR(e.target.value)}
                    className="w-16 px-2.5 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
                  />
                </div>
                
                {/* Max HR Filter */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 uppercase tracking-wide">Max HR</span>
                  <input
                    type="number"
                    placeholder="Min"
                    value={minMaxHR}
                    onChange={(e) => setMinMaxHR(e.target.value)}
                    className="w-16 px-2.5 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
                  />
                  <span className="text-slate-600">-</span>
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxMaxHR}
                    onChange={(e) => setMaxMaxHR(e.target.value)}
                    className="w-16 px-2.5 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
                  />
                </div>
                
                {hasAnyFilter && (
                  <Button variant="ghost" size="sm" onClick={clearFilters} className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10">
                    <X className="w-3 h-3 mr-1" /> Clear
                  </Button>
                )}
              </div>
              
              {/* Filter Results Action */}
              {hasAnyFilter && filteredActivities.length >= 2 && filteredActivities.length <= 10 && (
                <div className="mt-4 pt-4 border-t border-slate-700/50 flex items-center justify-between">
                  <div className="text-sm text-slate-400 flex items-center gap-2">
                    <Badge variant="default" className="bg-orange-500">{filteredActivities.length}</Badge>
                    runs match your filters
                  </div>
                  <Button
                    onClick={handleCompareFiltered}
                    disabled={compareSelectedMutation.isPending}
                    className="bg-orange-600 hover:bg-orange-500 shadow-lg shadow-orange-500/20"
                  >
                    {compareSelectedMutation.isPending ? (
                      <>
                        <LoadingSpinner size="sm" />
                        <span className="ml-2">Comparing...</span>
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4 mr-1.5" />
                        Compare All {filteredActivities.length} Filtered
                      </>
                    )}
                  </Button>
                </div>
              )}
              
              {hasAnyFilter && filteredActivities.length > 10 && (
                <div className="mt-4 pt-4 border-t border-slate-700/50 text-sm text-slate-400 flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  <Badge variant="default" className="bg-orange-500">{filteredActivities.length}</Badge>
                  runs match. Select up to 10, or narrow your filter.
                </div>
              )}
              
              {hasAnyFilter && filteredActivities.length === 1 && (
                <div className="mt-4 pt-4 border-t border-slate-700/50 text-sm text-slate-400 flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  Only <Badge variant="default" className="bg-orange-500">1</Badge> run matches. Broaden filter or use &quot;Find Similar&quot;.
                </div>
              )}
              
              {hasAnyFilter && filteredActivities.length === 0 && (
                <div className="mt-4 pt-4 border-t border-slate-700/50 text-sm text-amber-400 flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  No runs match. Try adjusting the ranges.
                </div>
              )}
              
              {/* Selection Mode Instructions */}
              {selectionMode && (
                <div className="mt-4 pt-4 border-t border-slate-700/50">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-slate-400">
                      {selectedCount === 0 && 'Click runs to select (2-10 runs)'}
                      {selectedCount === 1 && 'Select at least one more'}
                      {selectedCount >= 2 && (
                        <span className="text-orange-400 font-medium flex items-center gap-2">
                          <Badge variant="success">{selectedCount}</Badge> runs selected
                          {baselineId && <Badge variant="outline" className="text-slate-400">baseline set</Badge>}
                        </span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {selectedCount > 0 && (
                        <Button variant="ghost" size="sm" onClick={clearSelection} className="text-slate-400 hover:text-white">
                          Clear
                        </Button>
                      )}
                      {selectedCount >= 2 && (
                        <Button
                          onClick={handleCompareSelected}
                          disabled={compareSelectedMutation.isPending}
                          className="bg-orange-600 hover:bg-orange-500 shadow-lg shadow-orange-500/20"
                        >
                          {compareSelectedMutation.isPending ? (
                            <>
                              <LoadingSpinner size="sm" />
                              <span className="ml-2">Comparing...</span>
                            </>
                          ) : (
                            <>Compare {selectedCount} Runs</>
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                  
                  {selectedCount >= 2 && (
                    <div className="mt-3 text-sm flex items-center gap-2">
                      <span className="text-slate-400">Baseline (optional):</span>
                      <select
                        value={baselineId || ''}
                        onChange={(e) => setBaselineId(e.target.value || null)}
                        className="px-3 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:border-orange-500 focus:outline-none"
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
            </CardContent>
          </Card>
          
          {/* Activity List */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Footprints className="w-5 h-5 text-slate-400" />
                {filteredActivities.length} runs
                {hasAnyFilter && <Badge variant="outline" className="text-slate-400 text-xs">filtered</Badge>}
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
                  <Button
                    variant="ghost"
                    onClick={() => setShowAll(true)}
                    className="w-full text-slate-400 hover:text-white"
                  >
                    Show more runs...
                  </Button>
                )}
              </div>
            ) : (
              <Card className="bg-slate-800 border-slate-700">
                <CardContent className="py-12 text-center">
                  {hasAnyFilter ? (
                    <>
                      <Search className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                      <h3 className="text-xl font-semibold mb-2">No runs match your filter</h3>
                      <p className="text-slate-400">
                        Try adjusting the ranges. Runs without HR data are excluded when filtering.
                      </p>
                    </>
                  ) : (
                    <>
                      <Footprints className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                      <h3 className="text-xl font-semibold mb-2">No runs yet</h3>
                      <p className="text-slate-400 mb-4">
                        Sync your Strava account to start comparing your runs
                      </p>
                      <Button asChild className="bg-orange-600 hover:bg-orange-500">
                        <Link href="/settings">Connect Strava</Link>
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
          
          {/* How it works */}
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold text-slate-300 flex items-center gap-2">
                <Info className="w-4 h-4 text-slate-400" />
                Two Ways to Compare
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="bg-slate-700/50 border-slate-600">
                  <CardContent className="pt-4 pb-4">
                    <div className="text-orange-400 font-medium mb-2 flex items-center gap-2">
                      <Search className="w-4 h-4" />
                      Find Similar (Auto)
                    </div>
                    <CardDescription>
                      Click &quot;Similar&quot; on any run. We find your most similar runs 
                      by duration, HR, intensity, conditions. Compare against that baseline.
                    </CardDescription>
                  </CardContent>
                </Card>
                <Card className="bg-slate-700/50 border-slate-600">
                  <CardContent className="pt-4 pb-4">
                    <div className="text-orange-400 font-medium mb-2 flex items-center gap-2">
                      <CheckSquare className="w-4 h-4" />
                      Select & Compare (Manual)
                    </div>
                    <CardDescription>
                      Pick 2-10 specific runs. Set one as baseline, see how others stack up. 
                      Great for comparing specific races or workouts.
                    </CardDescription>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
          
        </div>
        </div>
    </ProtectedRoute>
  );
}
