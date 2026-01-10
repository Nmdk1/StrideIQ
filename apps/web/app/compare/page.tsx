'use client';

/**
 * Compare Page - Contextual Comparison Hub
 * 
 * The differentiator feature: Compare runs in context, not just by distance.
 * This is what makes StrideIQ unique - no other platform offers this.
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useActivities } from '@/lib/hooks/queries/activities';
import { useQuickScore } from '@/lib/hooks/queries/contextual-compare';
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
    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${getScoreColor(quickScore.score)}`}>
      {Math.round(quickScore.score)}
    </div>
  );
}

// Activity card for comparison selection
function ActivityCard({ 
  activity, 
  formatDistance, 
  formatPace 
}: { 
  activity: any; 
  formatDistance: (m: number, decimals?: number) => string;
  formatPace: (secPerKm: number) => string;
}) {
  const pacePerKm = activity.duration_s && activity.distance_m 
    ? activity.duration_s / (activity.distance_m / 1000) 
    : null;
  
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 hover:border-gray-600 transition-all group">
      <div className="flex justify-between items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="text-sm text-gray-400 mb-1">
            {new Date(activity.start_time).toLocaleDateString('en-US', { 
              weekday: 'short', month: 'short', day: 'numeric' 
            })}
          </div>
          <div className="font-medium truncate mb-2">
            {activity.name || 'Untitled Run'}
          </div>
          <div className="flex gap-4 text-sm text-gray-400">
            <span>{formatDistance(activity.distance_m, 1)}</span>
            {pacePerKm && <span>{formatPace(pacePerKm)}</span>}
            {activity.avg_hr && <span>{activity.avg_hr} bpm</span>}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <QuickScoreBadge activityId={activity.id} />
          <Link
            href={`/compare/context/${activity.id}`}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium rounded-lg transition-colors opacity-80 group-hover:opacity-100"
          >
            Compare
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ComparePage() {
  const [showAll, setShowAll] = useState(false);
  const { data: activities, isLoading } = useActivities({ limit: showAll ? 50 : 10 });
  const { formatDistance, formatPace } = useUnits();
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-4xl mx-auto px-4">
          
          {/* Hero Section */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500/10 border border-orange-500/30 rounded-full text-orange-400 text-sm font-medium mb-4">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
              </span>
              New Feature
            </div>
            
            <h1 className="text-4xl font-bold mb-4">
              Context vs Context
            </h1>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-6">
              Compare runs based on <span className="text-white font-medium">how similar they actually are</span> — 
              not just distance. See your true performance accounting for conditions, intensity, and effort.
            </p>
            
            {/* Feature highlights */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto mb-8">
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                <div className="text-2xl mb-2">👻</div>
                <div className="font-medium mb-1">Ghost Average</div>
                <div className="text-sm text-gray-400">Compare against a baseline from similar runs</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                <div className="text-2xl mb-2">📊</div>
                <div className="font-medium mb-1">Performance Score</div>
                <div className="text-sm text-gray-400">0-100 score showing how you did vs similar efforts</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                <div className="text-2xl mb-2">💡</div>
                <div className="font-medium mb-1">Context Insights</div>
                <div className="text-sm text-gray-400">Explanations for why performance differed</div>
              </div>
            </div>
          </div>
          
          {/* Activity Selection */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <span>Select a run to compare</span>
              <span className="text-sm font-normal text-gray-400">
                (showing {activities?.length || 0} recent runs)
              </span>
            </h2>
            
            {isLoading ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner size="lg" />
              </div>
            ) : activities && activities.length > 0 ? (
              <div className="space-y-3">
                {activities.map((activity: any) => (
                  <ActivityCard
                    key={activity.id}
                    activity={activity}
                    formatDistance={formatDistance}
                    formatPace={formatPace}
                  />
                ))}
                
                {!showAll && activities.length >= 10 && (
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
              </div>
            )}
          </div>
          
          {/* How it works */}
          <div className="bg-gray-800/30 rounded-xl border border-gray-700/50 p-6">
            <h3 className="font-semibold mb-4 text-gray-300">How Contextual Comparison Works</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-400">
              <div>
                <strong className="text-gray-200">1. Smart Similarity</strong>
                <p>We find runs that match your target using duration, intensity, heart rate, workout type, conditions, and elevation.</p>
              </div>
              <div>
                <strong className="text-gray-200">2. Ghost Baseline</strong>
                <p>Your similar runs are averaged to create a &quot;ghost&quot; — what you&apos;d typically do under these conditions.</p>
              </div>
              <div>
                <strong className="text-gray-200">3. Performance Score</strong>
                <p>Your run is scored 0-100 based on how you performed vs the ghost average.</p>
              </div>
              <div>
                <strong className="text-gray-200">4. The &quot;BUT&quot; Insight</strong>
                <p>We explain why performance differed: &quot;You were 5% slower, BUT it was 15°F hotter than usual.&quot;</p>
              </div>
            </div>
          </div>
          
        </div>
      </div>
    </ProtectedRoute>
  );
}
