'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapPin, ChevronDown } from 'lucide-react';
import { useUnits } from '@/lib/context/UnitsContext';
import { useStreamHover } from '@/lib/context/StreamHoverContext';
import ActivityMap from './ActivityMap';
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
}

interface Props {
  activityId: string;
  track: [number, number][];
  startCoords?: [number, number] | null;
  sportType: string;
  startTime: string;
  accentColor?: string;
  streamPoints?: StreamPoint[];
  weather?: WeatherData | null;
  distanceM?: number;
  durationS?: number;
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
  streamPoints,
  weather,
  distanceM,
  durationS,
}: Props) {
  const { units } = useUnits();
  const { hoveredIndex } = useStreamHover();
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

  const siblingCount = siblings?.count ?? 0;
  const conditionsMatch = siblings?.conditions_match_count ?? 0;

  return (
    <div className="space-y-1">
      <ActivityMap
        track={track}
        startCoords={startCoords}
        ghosts={[]}
        accentColor={accentColor}
        unitSystem={units}
        streamPoints={streamPoints}
        weather={weather}
        hoveredIndex={hoveredIndex}
      />

      {/* Route siblings summary */}
      {siblingCount > 0 && (
        <div className="px-1 space-y-1">
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
