"use client";

/**
 * Personal Bests Page
 * 
 * Enhanced with shadcn/ui + Lucide.
 * Displays the athlete's personal bests across standard race distances.
 * 
 * TONE: Data speaks. No praise, no motivation.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { apiClient } from '@/lib/api/client';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Trophy, RefreshCw, Clock, Activity, Calendar, Medal } from 'lucide-react';

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
      <Card className="bg-red-900/30 border-red-700">
        <CardContent className="py-8 text-center text-red-400">
          Error loading personal bests.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
              <Trophy className="w-6 h-6 text-orange-500" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">Personal Bests</h1>
              <p className="text-slate-400 mt-1">
                Auto-calculated from your activity history
              </p>
            </div>
          </div>
          <Button
            onClick={handleRecalculate}
            disabled={recalculating}
            className="bg-orange-600 hover:bg-orange-500"
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${recalculating ? 'animate-spin' : ''}`} />
            {recalculating 
              ? (syncMutation.isPending ? 'Syncing...' : 'Recalculating...')
              : 'Recalculate'}
          </Button>
        </div>

        {/* PBs Table */}
        {sortedPbs.length === 0 ? (
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="py-12 text-center">
              <Trophy className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 mb-2">No personal bests found.</p>
              <p className="text-slate-500 text-sm">
                Click &quot;Recalculate&quot; to scan your activity history for PBs.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-slate-800 border-slate-700 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-700/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">
                      <span className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-orange-500" />
                        Distance
                      </span>
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">
                      <span className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-blue-500" />
                        Time
                      </span>
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Pace</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">
                      <span className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-purple-500" />
                        Date
                      </span>
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {sortedPbs.map((pb) => (
                    <tr key={pb.id} className="hover:bg-slate-700/30 transition-colors">
                      <td className="px-4 py-4 font-medium text-white">
                        {DISTANCE_LABELS[pb.distance_category] || pb.distance_category}
                      </td>
                      <td className="px-4 py-4 text-slate-300 font-mono">
                        {formatDuration(pb.time_seconds)}
                      </td>
                      <td className="px-4 py-4 text-slate-300 font-mono">
                        {formatPace(pb.pace_per_mile)}
                      </td>
                      <td className="px-4 py-4 text-slate-400">
                        {new Date(pb.achieved_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-4">
                        {pb.is_race ? (
                          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                            <Medal className="w-3 h-3 mr-1" />
                            Race
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-slate-400 border-slate-600">
                            Training
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Summary */}
        {sortedPbs.length > 0 && (
          <div className="mt-6 text-sm text-slate-500 flex items-center gap-2">
            <Trophy className="w-4 h-4" />
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
