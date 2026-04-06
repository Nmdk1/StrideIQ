'use client';

import { useQuery } from '@tanstack/react-query';
import { useUnits } from '@/lib/context/UnitsContext';
import { useStreamHover } from '@/lib/context/StreamHoverContext';
import ActivityMap from './ActivityMap';
import RouteHistory from './RouteHistory';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import type { WeatherData } from './ActivityMapInner';

interface RouteSiblingMeta {
  id: string;
  start_time: string;
  distance_m: number;
  duration_s: number;
  temperature_f: number | null;
  dew_point_f: number | null;
  heat_adjustment_pct: number | null;
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
  heatAdjustmentPct?: number | null;
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
  heatAdjustmentPct,
}: Props) {
  const { units } = useUnits();
  const { hoveredIndex } = useStreamHover();

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

  return (
    <div className="space-y-1">
      <ActivityMap
        track={track}
        startCoords={startCoords}
        accentColor={accentColor}
        unitSystem={units}
        streamPoints={streamPoints}
        weather={weather}
        hoveredIndex={hoveredIndex}
      />

      {/* Route History — summary always visible when siblings exist, expands to pace chart */}
      {siblingCount > 0 && siblings && distanceM != null && durationS != null && (
        <RouteHistory
          activityId={activityId}
          siblings={siblings.siblings}
          currentDistanceM={distanceM}
          currentDurationS={durationS}
          currentHeatAdjPct={heatAdjustmentPct ?? null}
          unitSystem={units}
        />
      )}
    </div>
  );
}
