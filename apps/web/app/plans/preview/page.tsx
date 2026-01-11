'use client';

/**
 * Plan Preview Page
 * 
 * Browse and preview available training plans.
 * Users can see full plan structure before creating.
 */

import React, { useState } from 'react';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { planService, type GeneratedPlan } from '@/lib/api/services/plans';

const DISTANCES = [
  { value: '5k', label: '5K' },
  { value: '10k', label: '10K' },
  { value: 'half_marathon', label: 'Half Marathon' },
  { value: 'marathon', label: 'Marathon' },
];

const TIERS = [
  { value: 'builder', label: 'Building Up (20-35 mi/wk)' },
  { value: 'low', label: 'Low Volume (35-45 mi/wk)' },
  { value: 'mid', label: 'Mid Volume (45-60 mi/wk)' },
  { value: 'high', label: 'High Volume (60+ mi/wk)' },
];

export default function PlanPreviewPage() {
  const [distance, setDistance] = useState('marathon');
  const [tier, setTier] = useState('mid');
  const [duration, setDuration] = useState(18);
  const [days, setDays] = useState(6);
  const [preview, setPreview] = useState<GeneratedPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'phases' | 'weeks'>('phases');
  
  const fetchPreview = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const data = await planService.previewStandard({
        distance,
        duration_weeks: duration,
        days_per_week: days,
        volume_tier: tier,
      });
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preview');
    } finally {
      setIsLoading(false);
    }
  };
  
  // Workout type colors
  const getWorkoutColor = (type: string) => {
    const colors: Record<string, string> = {
      rest: 'bg-gray-700 text-gray-400',
      easy: 'bg-emerald-900/50 text-emerald-400',
      strides: 'bg-emerald-900/50 text-emerald-400',
      hills: 'bg-emerald-900/50 text-emerald-400',
      medium_long: 'bg-sky-900/50 text-sky-400',
      long: 'bg-blue-900/50 text-blue-400',
      long_mp: 'bg-pink-900/50 text-pink-400',
      threshold_intervals: 'bg-orange-900/50 text-orange-400',
      tempo: 'bg-orange-900/50 text-orange-400',
      intervals: 'bg-red-900/50 text-red-400',
    };
    return colors[type] || 'bg-gray-800 text-gray-400';
  };
  
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Preview Training Plans</h1>
          <p className="text-gray-400">Explore our periodized training plans before you commit</p>
        </div>
        
        {/* Configuration */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Distance</label>
              <select
                value={distance}
                onChange={(e) => setDistance(e.target.value)}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
              >
                {DISTANCES.map(d => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Volume Tier</label>
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
              >
                {TIERS.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Duration</label>
              <select
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
              >
                <option value={8}>8 weeks</option>
                <option value={12}>12 weeks</option>
                <option value={16}>16 weeks</option>
                <option value={18}>18 weeks</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Days/Week</label>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white"
              >
                <option value={5}>5 days</option>
                <option value={6}>6 days</option>
                <option value={7}>7 days</option>
              </select>
            </div>
          </div>
          
          <button
            onClick={fetchPreview}
            disabled={isLoading}
            className="w-full px-6 py-3 bg-gradient-to-r from-pink-600 to-orange-600 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <LoadingSpinner size="sm" />
                Generating Preview...
              </>
            ) : (
              'Generate Preview'
            )}
          </button>
        </div>
        
        {error && (
          <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-400 mb-8">
            {error}
          </div>
        )}
        
        {/* Preview */}
        {preview && (
          <div className="space-y-8">
            {/* Summary */}
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">Plan Summary</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="text-3xl font-bold text-white">{preview.duration_weeks}</div>
                  <div className="text-sm text-gray-400">Weeks</div>
                </div>
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="text-3xl font-bold text-emerald-400">{preview.total_miles.toFixed(0)}</div>
                  <div className="text-sm text-gray-400">Total Miles</div>
                </div>
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="text-3xl font-bold text-blue-400">{preview.peak_volume.toFixed(0)}</div>
                  <div className="text-sm text-gray-400">Peak Miles/Week</div>
                </div>
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="text-3xl font-bold text-orange-400">{preview.total_quality_sessions}</div>
                  <div className="text-sm text-gray-400">Quality Sessions</div>
                </div>
              </div>
            </div>
            
            {/* Phases */}
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">Training Phases</h2>
              <div className="space-y-3">
                {preview.phases.map((phase, i) => (
                  <div key={i} className="flex items-center gap-4 p-4 bg-gray-900 rounded-lg">
                    <div className="w-20 text-sm text-gray-500">
                      Wk {phase.weeks[0]}-{phase.weeks[phase.weeks.length - 1]}
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-white">{phase.name}</div>
                      <div className="text-sm text-gray-400">{phase.focus}</div>
                    </div>
                    <div className="text-sm text-gray-500">{phase.weeks.length} weeks</div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* View Toggle */}
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode('phases')}
                className={`px-4 py-2 rounded-lg font-medium ${
                  viewMode === 'phases' 
                    ? 'bg-pink-600 text-white' 
                    : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                By Phase
              </button>
              <button
                onClick={() => setViewMode('weeks')}
                className={`px-4 py-2 rounded-lg font-medium ${
                  viewMode === 'weeks' 
                    ? 'bg-pink-600 text-white' 
                    : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                Week by Week
              </button>
            </div>
            
            {/* Week by Week */}
            {viewMode === 'weeks' && (
              <div className="space-y-4">
                {Array.from({ length: preview.duration_weeks }, (_, i) => i + 1).map(week => {
                  const weekWorkouts = preview.workouts.filter(w => w.week === week);
                  const phase = preview.phases.find(p => p.weeks.includes(week));
                  const volume = preview.weekly_volumes[week - 1] || 0;
                  
                  return (
                    <div key={week} className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
                      <div className="p-4 bg-gray-900 border-b border-gray-700 flex items-center justify-between">
                        <div>
                          <span className="text-white font-bold">Week {week}</span>
                          <span className="text-gray-500 mx-2">•</span>
                          <span className="text-orange-400">{phase?.name}</span>
                        </div>
                        <span className="text-gray-400">{volume.toFixed(0)} mi</span>
                      </div>
                      <div className="grid grid-cols-7 gap-1 p-2">
                        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, dayIndex) => {
                          const workout = weekWorkouts.find(w => w.day === dayIndex);
                          return (
                            <div 
                              key={day}
                              className="p-2 min-h-[80px]"
                              title={workout?.description}
                            >
                              <div className="text-xs text-gray-500 mb-1">{day}</div>
                              {workout && (
                                <div className={`rounded p-1.5 text-xs ${getWorkoutColor(workout.workout_type)}`}>
                                  <div className="font-semibold truncate uppercase">
                                    {workout.workout_type.replace(/_/g, ' ')}
                                  </div>
                                  {workout.distance_miles && (
                                    <div className="opacity-75">{workout.distance_miles}mi</div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            
            {/* By Phase */}
            {viewMode === 'phases' && (
              <div className="space-y-6">
                {preview.phases.map((phase, phaseIndex) => (
                  <div key={phaseIndex} className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
                    <div className="p-4 bg-gradient-to-r from-orange-900/30 to-gray-800 border-b border-gray-700">
                      <h3 className="text-lg font-bold text-white">{phase.name}</h3>
                      <p className="text-sm text-gray-400">{phase.focus}</p>
                      <p className="text-xs text-gray-500 mt-1">Weeks {phase.weeks.join(', ')}</p>
                    </div>
                    
                    <div className="p-4 space-y-3">
                      {phase.weeks.slice(0, 2).map(week => {
                        const weekWorkouts = preview.workouts.filter(w => w.week === week);
                        return (
                          <div key={week} className="bg-gray-900 rounded-lg p-3">
                            <div className="text-sm text-gray-400 mb-2">Week {week}</div>
                            <div className="flex flex-wrap gap-2">
                              {weekWorkouts.map((w, i) => (
                                <span 
                                  key={i}
                                  className={`px-2 py-1 rounded text-xs ${getWorkoutColor(w.workout_type)}`}
                                >
                                  {w.day_name}: {w.title}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                      {phase.weeks.length > 2 && (
                        <div className="text-center text-sm text-gray-500">
                          +{phase.weeks.length - 2} more weeks
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {/* CTA */}
            <div className="bg-gradient-to-r from-pink-900/30 to-orange-900/30 border border-pink-700/50 rounded-xl p-6 text-center">
              <h3 className="text-xl font-bold text-white mb-2">Ready to Start Training?</h3>
              <p className="text-gray-400 mb-4">
                Create this plan personalized to your fitness and race date.
              </p>
              <a
                href="/plans/create"
                className="inline-block px-8 py-3 bg-gradient-to-r from-pink-600 to-orange-600 rounded-lg font-semibold text-white hover:from-pink-700 hover:to-orange-700 transition-colors"
              >
                Create Your Plan
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
