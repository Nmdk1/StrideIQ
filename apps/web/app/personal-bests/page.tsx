"use client";

/**
 * Personal Bests Page
 * 
 * Displays the athlete's personal bests across standard race distances.
 * PBs are auto-calculated from activity history.
 * 
 * TONE: Data speaks. No praise, no motivation.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { apiClient } from '@/lib/api/client';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

interface PersonalBest {
  id: string;
  distance_category: string;
  distance_meters: number;
  time_seconds: number;
  pace_per_mile: number | null;
  achieved_at: string;
  is_race: boolean;
  age_at_achievement: number | null;
}

interface AthleteProfile {
  id: string;
  display_name: string;
}

const DISTANCE_ORDER = [
  '400m', '800m', 'mile', '2mile', '5k', '10k', '15k', 
  'half_marathon', 'marathon', '25k', '30k', '50k', '100k'
];

const DISTANCE_LABELS: Record<string, string> = {
  '400m': '400m',
  '800m': '800m',
  'mile': 'Mile',
  '2mile': '2 Mile',
  '5k': '5K',
  '10k': '10K',
  '15k': '15K',
  '25k': '25K',
  '30k': '30K',
  '50k': '50K',
  '100k': '100K',
  'half_marathon': 'Half Marathon',
  'marathon': 'Marathon',
};

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.round(seconds % 60);
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatPace(pacePerMile: number | null): string {
  if (!pacePerMile) return '--';
  const mins = Math.floor(pacePerMile);
  const secs = Math.round((pacePerMile % 1) * 60);
  return `${mins}:${secs.toString().padStart(2, '0')}/mi`;
}

function PersonalBestsContent() {
  const queryClient = useQueryClient();
  const [recalculating, setRecalculating] = useState(false);

  // Get current user
  const { data: profile } = useQuery<AthleteProfile>({
    queryKey: ['profile'],
    queryFn: () => apiClient.get('/v1/athletes/me'),
  });

  // Get personal bests
  const { data: pbs, isLoading, error } = useQuery<PersonalBest[]>({
    queryKey: ['personal-bests', profile?.id],
    queryFn: () => apiClient.get(`/v1/athletes/${profile?.id}/personal-bests`),
    enabled: !!profile?.id,
  });

  interface RecalculateResponse {
    pbs_created: number;
    efforts_in_db: number;
  }

  // Sync from Strava mutation (fetches best efforts from API - can take 30-60s)
  const syncMutation = useMutation({
    mutationFn: () => apiClient.post(`/v1/athletes/${profile?.id}/sync-best-efforts?limit=100`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personal-bests'] });
      setRecalculating(false);
    },
    onError: () => {
      setRecalculating(false);
    },
  });

  // Quick recalculate mutation (regenerates from stored efforts - instant)
  const recalculateMutation = useMutation<RecalculateResponse, Error, void>({
    mutationFn: () => apiClient.post(`/v1/athletes/${profile?.id}/recalculate-pbs`),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['personal-bests'] });
      // If no PBs created and no efforts stored, we need to sync from Strava first
      if (data.pbs_created === 0 && data.efforts_in_db === 0) {
        syncMutation.mutate();
      } else {
        setRecalculating(false);
      }
    },
    onError: () => {
      setRecalculating(false);
    },
  });

  const handleRecalculate = () => {
    setRecalculating(true);
    recalculateMutation.mutate();
  };

  // Sort PBs by distance order
  const sortedPbs = pbs?.slice().sort((a, b) => {
    const aIdx = DISTANCE_ORDER.indexOf(a.distance_category);
    const bIdx = DISTANCE_ORDER.indexOf(b.distance_category);
    return (aIdx === -1 ? 999 : aIdx) - (bIdx === -1 ? 999 : bIdx);
  }) || [];

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-400">
        Error loading personal bests.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Personal Bests</h1>
            <p className="text-gray-400 mt-1">
              Auto-calculated from your activity history
            </p>
          </div>
          <button
            onClick={handleRecalculate}
            disabled={recalculating}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {recalculating 
              ? (syncMutation.isPending ? 'Syncing from Strava...' : 'Recalculating...')
              : 'Recalculate'}
          </button>
        </div>

        {/* PBs Table */}
        {sortedPbs.length === 0 ? (
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
            <p className="text-gray-400 mb-4">No personal bests found.</p>
            <p className="text-gray-500 text-sm">
              Click &quot;Recalculate&quot; to scan your activity history for PBs.
            </p>
          </div>
        ) : (
          <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-700/50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Distance</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Time</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Pace</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Date</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Race</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {sortedPbs.map((pb) => (
                  <tr key={pb.id} className="hover:bg-gray-700/30">
                    <td className="px-4 py-3 font-medium text-white">
                      {DISTANCE_LABELS[pb.distance_category] || pb.distance_category}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {formatDuration(pb.time_seconds)}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {formatPace(pb.pace_per_mile)}
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {new Date(pb.achieved_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      {pb.is_race ? (
                        <span className="text-emerald-400 text-sm">Race</span>
                      ) : (
                        <span className="text-gray-500 text-sm">Training</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Summary */}
        {sortedPbs.length > 0 && (
          <div className="mt-6 text-sm text-gray-500">
            {sortedPbs.length} personal best{sortedPbs.length !== 1 ? 's' : ''} recorded
          </div>
        )}
      </div>
    </div>
  );
}

export default function PersonalBestsPage() {
  return (
    <ProtectedRoute>
      <PersonalBestsContent />
    </ProtectedRoute>
  );
}
