'use client';

import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, useMap } from 'react-leaflet';
import L, { LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { Maximize2, Minimize2, X } from 'lucide-react';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';

const CARTO_VOYAGER = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
const CARTO_ATTRIBUTION = '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>';

interface MileMarker {
  position: [number, number];
  label: string;
}

interface PaceSegment {
  positions: [number, number][];
  color: string;
}

export interface WeatherData {
  temperature_f: number | null;
  weather_condition: string | null;
  humidity_pct: number | null;
  heat_adjustment_pct: number | null;
}

export interface Props {
  track: [number, number][];
  startCoords?: [number, number] | null;
  accentColor?: string;
  unitSystem?: 'imperial' | 'metric';
  streamPoints?: StreamPoint[];
  weather?: WeatherData | null;
  hoveredIndex?: number | null;
}

/** Leaflet expects [lat, lng]. Some sources store [lng, lat]; detect via first coordinate. */
function normalizeTrackLatLng(track: [number, number][]): [number, number][] {
  if (track.length === 0) return track;
  const [a, b] = track[0];
  if (Math.abs(a) > 90 && Math.abs(b) <= 90) {
    return track.map(([x, y]) => [y, x] as [number, number]);
  }
  return track;
}

function normalizeCoordPair(c: [number, number]): [number, number] {
  const [a, b] = c;
  if (Math.abs(a) > 90 && Math.abs(b) <= 90) return [b, a];
  return c;
}

function haversine([lat1, lon1]: [number, number], [lat2, lon2]: [number, number]): number {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function computeMileMarkers(
  track: [number, number][],
  unitSystem: 'imperial' | 'metric',
): MileMarker[] {
  if (track.length < 2) return [];
  const interval = unitSystem === 'imperial' ? 1609.34 : 1000;
  const markers: MileMarker[] = [];
  let cumulative = 0;
  let nextMark = interval;
  for (let i = 1; i < track.length; i++) {
    const d = haversine(track[i - 1], track[i]);
    cumulative += d;
    if (cumulative >= nextMark) {
      markers.push({ position: track[i], label: String(Math.round(nextMark / interval)) });
      nextMark += interval;
    }
  }
  return markers;
}

function createMileIcon(label: string): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div style="
      background: rgba(15, 23, 42, 0.9);
      border: 1.5px solid rgba(148, 163, 184, 0.5);
      color: #e2e8f0;
      font-size: 11px;
      font-weight: 600;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: system-ui, -apple-system, sans-serif;
    ">${label}</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function paceColor(t: number): string {
  // t: 0 = fastest (red), 1 = slowest (blue)
  if (t < 0.5) {
    const g = Math.round(180 * (t * 2));
    return `rgb(235, ${g}, 50)`;
  }
  const r = Math.round(235 * (1 - (t - 0.5) * 2));
  const b = Math.round(180 * ((t - 0.5) * 2));
  return `rgb(${r}, ${180 - b / 2}, ${50 + b})`;
}

function gradeAdjustedPace(paceSkm: number, gradePct: number): number {
  const adjustment = gradePct > 0 ? gradePct * 12 : gradePct * 7;
  return paceSkm - adjustment;
}

function buildPaceSegments(
  stream: StreamPoint[],
  useEffort: boolean,
): PaceSegment[] {
  const withGps = stream.filter(p => p.lat != null && p.lng != null && p.pace != null);
  if (withGps.length < 2) return [];

  const paces = withGps.map(p =>
    useEffort && p.grade != null
      ? gradeAdjustedPace(p.pace!, p.grade)
      : p.pace!
  );
  const sorted = [...paces].sort((a, b) => a - b);
  const p5 = sorted[Math.floor(sorted.length * 0.05)];
  const p95 = sorted[Math.floor(sorted.length * 0.95)];
  const range = p95 - p5 || 1;

  const segments: PaceSegment[] = [];
  for (let i = 0; i < withGps.length - 1; i++) {
    const p = withGps[i];
    const next = withGps[i + 1];
    const t = Math.max(0, Math.min(1, (paces[i] - p5) / range));
    segments.push({
      positions: [[p.lat!, p.lng!], [next.lat!, next.lng!]],
      color: paceColor(t),
    });
  }
  return segments;
}

function weatherIcon(condition: string | null): string {
  if (!condition) return '🌡️';
  const c = condition.toLowerCase();
  if (c.includes('clear') && !c.includes('mostly')) return '☀️';
  if (c.includes('mostly_clear') || c.includes('partly')) return '🌤️';
  if (c.includes('overcast') || c.includes('cloudy')) return '☁️';
  if (c.includes('rain') || c.includes('drizzle')) return '🌧️';
  if (c.includes('snow')) return '❄️';
  if (c.includes('fog')) return '🌫️';
  return '🌡️';
}

function InvalidateOnResize() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => map.invalidateSize(), 100);
    return () => clearTimeout(timer);
  });
  return null;
}

function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap();
  const didFit = useRef(false);
  useEffect(() => {
    if (!didFit.current) {
      didFit.current = true;
      const timer = setTimeout(() => {
        map.invalidateSize();
        map.fitBounds(bounds, { padding: [12, 12] });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [map, bounds]);
  return null;
}

export default function ActivityMapInner({
  track,
  startCoords,
  accentColor = '#3b82f6',
  unitSystem = 'imperial',
  streamPoints,
  weather,
  hoveredIndex,
}: Props) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showEffort, setShowEffort] = useState(false);

  const trackLatLng = useMemo(() => normalizeTrackLatLng(track), [track]);
  const startLatLng = useMemo((): [number, number] | null => {
    if (!startCoords) return null;
    return normalizeCoordPair(startCoords);
  }, [startCoords]);

  const hasPaceData = useMemo(
    () => streamPoints && streamPoints.some(p => p.lat != null && p.pace != null),
    [streamPoints],
  );

  const paceSegments = useMemo(
    () => hasPaceData && streamPoints ? buildPaceSegments(streamPoints, showEffort) : [],
    [streamPoints, hasPaceData, showEffort],
  );

  const bounds = useMemo(() => {
    if (trackLatLng.length === 0 && startLatLng) return [startLatLng, startLatLng] as LatLngBoundsExpression;
    if (trackLatLng.length === 0) return [[0, 0], [0, 0]] as LatLngBoundsExpression;
    let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
    for (const [lat, lng] of trackLatLng) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    }
    return [[minLat, minLng], [maxLat, maxLng]] as LatLngBoundsExpression;
  }, [trackLatLng, startLatLng]);

  const mileMarkersAll = useMemo(() => computeMileMarkers(trackLatLng, unitSystem), [trackLatLng, unitSystem]);
  const mileMarkers = useMemo(() => {
    const total = mileMarkersAll.length;
    if (total <= 5) return mileMarkersAll;
    const interval = total <= 15 ? 2 : 5;
    return mileMarkersAll.filter((_, i) => {
      const mile = i + 1;
      return mile === 1 || mile === total || mile % interval === 0;
    });
  }, [mileMarkersAll]);
  const isPin = trackLatLng.length === 0 && startLatLng;
  const isLoop =
    trackLatLng.length > 1 && haversine(trackLatLng[0], trackLatLng[trackLatLng.length - 1]) < 50;

  const hoveredCoord = useMemo(() => {
    if (hoveredIndex == null || !streamPoints) return null;
    const p = streamPoints[hoveredIndex];
    if (!p || p.lat == null || p.lng == null) return null;
    return [p.lat, p.lng] as [number, number];
  }, [hoveredIndex, streamPoints]);

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isFullscreen) setIsFullscreen(false);
  }, [isFullscreen]);

  useEffect(() => {
    if (isFullscreen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isFullscreen, handleEscape]);

  const usePaceColoring = paceSegments.length > 0;

  // High-res coordinate array from stream data (for glow + bounds when available)
  const hiResTrack = useMemo<[number, number][]>(() => {
    if (!streamPoints) return [];
    const pts: [number, number][] = [];
    for (const p of streamPoints) {
      if (p.lat != null && p.lng != null) pts.push([p.lat, p.lng]);
    }
    return pts;
  }, [streamPoints]);

  // Use hi-res track for glow when available, fallback to coarse gps_track
  const glowTrack = hiResTrack.length > 1 ? hiResTrack : trackLatLng;

  return (
    <div>
      <div
        className={
          isFullscreen
            ? 'fixed inset-0 z-50 bg-slate-900'
            : 'relative rounded-lg overflow-hidden border border-slate-700/30'
        }
        style={isFullscreen ? undefined : { aspectRatio: '4 / 3' }}
      >
        {/* Fullscreen toggle */}
        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          className="absolute top-3 right-3 z-[1000] p-1.5 rounded-md bg-slate-900/80 border border-slate-600/50 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>

        {isFullscreen && (
          <button
            onClick={() => setIsFullscreen(false)}
            className="absolute top-3 left-3 z-[1000] p-1.5 rounded-md bg-slate-900/80 border border-slate-600/50 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            aria-label="Close fullscreen"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        {/* Weather badge */}
        {weather?.temperature_f != null && (
          <div className="absolute top-3 right-14 z-[1000] px-2 py-1 rounded-md bg-slate-900/80 border border-slate-600/40 text-[11px] text-slate-300 flex items-center gap-1.5">
            <span>{weatherIcon(weather.weather_condition)}</span>
            <span className="font-medium">{Math.round(weather.temperature_f)}°F</span>
            {weather.humidity_pct != null && (
              <span className="text-slate-500">{weather.humidity_pct}%</span>
            )}
          </div>
        )}

        <div
          style={{
            height: '100%',
            width: '100%',
            filter: 'brightness(0.75) contrast(1.1) saturate(0.5)',
          }}
        >
          <MapContainer
            center={isPin ? startLatLng! : trackLatLng[0] || [0, 0]}
            zoom={14}
            scrollWheelZoom={true}
            zoomControl={true}
            attributionControl={true}
            dragging={true}
            style={{ height: '100%', width: '100%', background: '#0f172a' }}
          >
            <TileLayer url={CARTO_VOYAGER} attribution={CARTO_ATTRIBUTION} />
            <FitBounds bounds={bounds} />
            <InvalidateOnResize />

            {/* Route glow layer — uses hi-res stream coords to avoid angular artifacts */}
            {glowTrack.length > 1 && (
              <Polyline
                positions={glowTrack}
                pathOptions={{ color: accentColor, weight: 8, opacity: 0.15, lineCap: 'round', lineJoin: 'round' }}
              />
            )}

            {/* Route: pace-colored segments OR flat color fallback */}
            {usePaceColoring ? (
              paceSegments.map((seg, i) => (
                <Polyline
                  key={i}
                  positions={seg.positions}
                  pathOptions={{ color: seg.color, weight: 4, opacity: 1, lineCap: 'round', lineJoin: 'round' }}
                />
              ))
            ) : (
              trackLatLng.length > 1 && (
                <Polyline
                  positions={trackLatLng}
                  pathOptions={{ color: accentColor, weight: 4, opacity: 1, lineCap: 'round', lineJoin: 'round' }}
                />
              )
            )}

            {/* Mile/km markers */}
            {mileMarkers.map((m) => (
              <Marker key={m.label} position={m.position} icon={createMileIcon(m.label)} />
            ))}

            {/* Start/end markers — combined for loops, separate otherwise */}
            {trackLatLng.length > 0 && isLoop ? (
              <CircleMarker
                center={trackLatLng[0]}
                radius={8}
                pathOptions={{ color: '#fff', weight: 2, fillColor: '#22c55e', fillOpacity: 1 }}
              />
            ) : (
              <>
                {trackLatLng.length > 0 && (
                  <CircleMarker
                    center={trackLatLng[0]}
                    radius={7}
                    pathOptions={{ color: '#fff', weight: 2, fillColor: '#22c55e', fillOpacity: 1 }}
                  />
                )}
                {trackLatLng.length > 1 && (
                  <CircleMarker
                    center={trackLatLng[trackLatLng.length - 1]}
                    radius={7}
                    pathOptions={{ color: '#fff', weight: 2, fillColor: '#ef4444', fillOpacity: 1 }}
                  />
                )}
              </>
            )}

            {/* Hover marker from chart cross-reference */}
            {hoveredCoord && (
              <CircleMarker
                center={hoveredCoord}
                radius={6}
                pathOptions={{ color: '#fff', weight: 2, fillColor: '#f59e0b', fillOpacity: 1 }}
              />
            )}

            {/* Pin marker (no track) */}
            {isPin && startLatLng && (
              <CircleMarker
                center={startLatLng}
                radius={7}
                pathOptions={{ color: accentColor, fillColor: accentColor, fillOpacity: 0.8, weight: 2 }}
              />
            )}
          </MapContainer>
        </div>
      </div>

      {/* Pace legend + effort toggle (runs with stream data only) */}
      {usePaceColoring && (
        <div className="flex items-center gap-2 mt-1.5 px-1">
          <span className="text-[10px] text-slate-500">Slower</span>
          <div
            className="flex-1 h-1 rounded-full"
            style={{ background: 'linear-gradient(to right, #3b82f6, #eab308, #ef4444)' }}
          />
          <span className="text-[10px] text-slate-500">Faster</span>
          {streamPoints && streamPoints.some(p => p.grade != null) && (
            <button
              onClick={() => setShowEffort(!showEffort)}
              className={`ml-2 text-[10px] px-1.5 py-0.5 rounded border transition-colors ${
                showEffort
                  ? 'border-amber-500/50 text-amber-400 bg-amber-500/10'
                  : 'border-slate-600/50 text-slate-500 hover:text-slate-300'
              }`}
            >
              {showEffort ? 'Effort' : 'Pace'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
