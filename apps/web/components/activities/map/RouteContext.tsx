'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { MapPin, Ghost, ChevronDown } from 'lucide-react';
import { useUnits } from '@/lib/context/UnitsContext';
import { useStreamHover } from '@/lib/context/StreamHoverContext';
import ActivityMap from './ActivityMap';
import ElevationProfile from './ElevationProfile';
import RoutePerformancePanel from './RoutePerformancePanel';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import type { WeatherData } from './ActivityMapInner';

interface RouteSiblingMeta {
  id: string;
  start_time: string;
  distance_m: number;
  duration_s: number;
  temperature_f: number | null;
  dew_point_f: number | null;
  workout_type: string | null;
  avg_hr: number | null;
  name: string | null;
  total_elevation_gain: number | null;
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
  streamPoints?: StreamPoint[];
  weather?: WeatherData | null;
  distanceM?: number;
  durationS?: number;
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

function sportVerb(sport: string): string {
  switch (sport) {
    case 'run': return 'run';
    case 'walking': return 'walked';
    case 'hiking': return 'hiked';
    case 'cycling': return 'cycled';
    default: return 'been';
  }
}

export default function RouteContext({
  activityId,
  track,
  startCoords,
  sportType,
  startTime,
  accentColor = '#3b82f6',
  mapHeight = 300,
  streamPoints,
  weather,
  distanceM,
  durationS,
}: Props) {
  const { units } = useUnits();
  const { hoveredIndex } = useStreamHover();
  const [showGhosts, setShowGhosts] = useState(false);
  const [ghostTraces, setGhostTraces] = useState<GhostTrace[]>([]);
  const [showRouteHistory, setShowRouteHistory] = useState(false);

  const { data: siblings } = useQuery<SiblingsResponse>({
    queryKey: ['route-siblings', activityId],
    queryFn: async () => {
      const res = await fetch(`/v1/activities/${activityId}/route-siblings`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (!res.ok) return { count: 0, conditions_match_count: 0, siblings: [] };
      return res.json();
    },
    enabled: track.length > 0,
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
    <div className="space-y-1">
      <ActivityMap
        track={track}
        startCoords={startCoords}
        ghosts={showGhosts ? ghostTraces : []}
        height={mapHeight}
        accentColor={accentColor}
        unitSystem={units}
        streamPoints={streamPoints}
        weather={weather}
        hoveredIndex={hoveredIndex}
      />

      {/* Elevation profile */}
      {streamPoints && streamPoints.some(p => p.altitude != null) && (
        <ElevationProfile
          points={streamPoints}
          accentColor={accentColor}
          height={48}
          unitSystem={units}
        />
      )}

      {/* Route siblings / ghost controls */}
      {siblingCount > 0 && (
        <div className="px-1 space-y-1">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowRouteHistory(!showRouteHistory)}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              <MapPin className="w-3 h-3" />
              <span>
                You&apos;ve {sportVerb(sportType)} from here {siblingCount} time{siblingCount !== 1 ? 's' : ''}
                {conditionsMatch > 0 && (
                  <span className="text-slate-500">
                    {' '}· {conditionsMatch} in similar conditions
                  </span>
                )}
              </span>
              <ChevronDown className={`w-3 h-3 transition-transform ${showRouteHistory ? 'rotate-180' : ''}`} />
            </button>

            <div className="flex items-center gap-2">
              {canShowGhosts && !showGhosts && (
                <button
                  onClick={() => ghostMutation.mutate()}
                  disabled={ghostMutation.isPending}
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
                >
                  <Ghost className="w-3 h-3" />
                  {ghostMutation.isPending ? 'Loading...' : 'Show ghosts'}
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
          </div>

          {showRouteHistory && siblings && distanceM != null && durationS != null && (
            <RoutePerformancePanel
              siblings={siblings.siblings}
              currentActivityId={activityId}
              currentDistanceM={distanceM}
              currentDurationS={durationS}
              sportType={sportType}
              unitSystem={units}
            />
          )}
        </div>
      )}
    </div>
  );
}
