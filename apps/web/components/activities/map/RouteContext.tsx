'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { MapPin, Ghost } from 'lucide-react';
import { useUnits } from '@/lib/context/UnitsContext';
import ActivityMap from './ActivityMap';

interface RouteSiblingMeta {
  id: string;
  start_time: string;
  distance_m: number;
  duration_s: number;
  temperature_f: number | null;
  dew_point_f: number | null;
  workout_type: string | null;
}

interface SiblingsResponse {
  count: number;
  conditions_match_count: number;
  siblings: RouteSiblingMeta[];
  tracks?: Record<string, [number, number][]>;
}

interface GhostTrace {
  id: string;
  points: [number, number][];
  opacity: number;
}

interface Props {
  activityId: string;
  track: [number, number][];
  startCoords?: [number, number] | null;
  sportType: string;
  startTime: string;
  accentColor?: string;
  mapHeight?: number;
}

function computeGhostOpacity(siblingDate: string, currentDate: string): number {
  const sib = new Date(siblingDate).getTime();
  const cur = new Date(currentDate).getTime();
  const daysAgo = Math.max(0, (cur - sib) / (1000 * 60 * 60 * 24));
  if (daysAgo <= 30) return 0.30;
  if (daysAgo <= 60) return 0.20;
  if (daysAgo <= 90) return 0.14;
  return 0.08;
}

export default function RouteContext({
  activityId,
  track,
  startCoords,
  sportType,
  startTime,
  accentColor = '#3b82f6',
  mapHeight = 300,
}: Props) {
  const { units } = useUnits();
  const [showGhosts, setShowGhosts] = useState(false);
  const [ghostTraces, setGhostTraces] = useState<GhostTrace[]>([]);

  const { data: siblings } = useQuery<SiblingsResponse>({
    queryKey: ['route-siblings', activityId],
    queryFn: async () => {
      const res = await fetch(`/v1/activities/${activityId}/route-siblings`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (!res.ok) return { count: 0, conditions_match_count: 0, siblings: [] };
      return res.json();
    },
    // Siblings/ghosts are run-only for now — walking/cycling get the map but not route history
    enabled: sportType === 'run' && track.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  const ghostMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(
        `/v1/activities/${activityId}/route-siblings?include_tracks=true&limit=30`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } },
      );
      if (!res.ok) throw new Error('Failed to load ghost tracks');
      return res.json() as Promise<SiblingsResponse>;
    },
    onSuccess: (data) => {
      const traces: GhostTrace[] = [];
      for (const sib of data.siblings) {
        const pts = data.tracks?.[sib.id];
        if (!pts || pts.length < 2) continue;
        traces.push({
          id: sib.id,
          points: pts,
          opacity: computeGhostOpacity(sib.start_time, startTime),
        });
      }
      setGhostTraces(traces);
      setShowGhosts(true);
    },
  });

  const siblingCount = siblings?.count ?? 0;
  const conditionsMatch = siblings?.conditions_match_count ?? 0;
  const canShowGhosts = siblingCount >= 6;

  return (
    <div className="space-y-2">
      <ActivityMap
        track={track}
        startCoords={startCoords}
        ghosts={showGhosts ? ghostTraces : []}
        height={mapHeight}
        accentColor={accentColor}
        unitSystem={units}
      />

      {siblingCount > 0 && sportType === 'run' && (
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <MapPin className="w-3 h-3" />
            <span>
              You&apos;ve run from here {siblingCount} time{siblingCount !== 1 ? 's' : ''}
              {conditionsMatch > 0 && (
                <span className="text-slate-500">
                  , {conditionsMatch} in similar conditions
                </span>
              )}
            </span>
          </div>

          {canShowGhosts && !showGhosts && (
            <button
              onClick={() => ghostMutation.mutate()}
              disabled={ghostMutation.isPending}
              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
            >
              <Ghost className="w-3 h-3" />
              {ghostMutation.isPending ? 'Loading...' : 'Show ghost map'}
            </button>
          )}

          {showGhosts && (
            <button
              onClick={() => setShowGhosts(false)}
              className="text-xs text-slate-500 hover:text-slate-400 transition-colors"
            >
              Hide ghosts
            </button>
          )}
        </div>
      )}
    </div>
  );
}
