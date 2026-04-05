'use client';

import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, useMap } from 'react-leaflet';
import L, { LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo, useState, useCallback } from 'react';
import { Maximize2, Minimize2, X } from 'lucide-react';

const CARTO_VOYAGER = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
const CARTO_ATTRIBUTION = '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>';

interface GhostTrace {
  id: string;
  points: [number, number][];
  opacity: number;
}

interface MileMarker {
  position: [number, number];
  label: string;
}

interface Props {
  track: [number, number][];
  startCoords?: [number, number] | null;
  ghosts?: GhostTrace[];
  height?: number;
  accentColor?: string;
  unitSystem?: 'imperial' | 'metric';
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
      markers.push({
        position: track[i],
        label: String(Math.round(nextMark / interval)),
      });
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
  useEffect(() => {
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [map, bounds]);
  return null;
}

export default function ActivityMapInner({
  track,
  startCoords,
  ghosts = [],
  height = 300,
  accentColor = '#3b82f6',
  unitSystem = 'imperial',
}: Props) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const bounds = useMemo(() => {
    const all = [...track];
    ghosts.forEach((g) => all.push(...g.points));
    if (all.length === 0 && startCoords) return [startCoords, startCoords] as LatLngBoundsExpression;
    if (all.length === 0) return [[0, 0], [0, 0]] as LatLngBoundsExpression;
    let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
    for (const [lat, lng] of all) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    }
    const pad = 0.002;
    return [[minLat - pad, minLng - pad], [maxLat + pad, maxLng + pad]] as LatLngBoundsExpression;
  }, [track, ghosts, startCoords]);

  const mileMarkers = useMemo(
    () => computeMileMarkers(track, unitSystem),
    [track, unitSystem],
  );

  const isPin = track.length === 0 && startCoords;

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

  return (
    <div
      className={
        isFullscreen
          ? 'fixed inset-0 z-50 bg-slate-900'
          : 'relative rounded-lg overflow-hidden border border-slate-700/30'
      }
      style={isFullscreen ? undefined : { height }}
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

      <div
        style={{
          height: '100%',
          width: '100%',
          filter: 'brightness(0.75) contrast(1.1) saturate(0.5)',
        }}
      >
        <MapContainer
          center={isPin ? startCoords! : track[0] || [0, 0]}
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

          {/* Ghost traces (behind everything) */}
          {ghosts.map((g) => (
            <Polyline
              key={g.id}
              positions={g.points}
              pathOptions={{ color: '#94a3b8', weight: 2, opacity: g.opacity }}
            />
          ))}

          {/* Route glow layer */}
          {track.length > 1 && (
            <Polyline
              positions={track}
              pathOptions={{
                color: accentColor,
                weight: 8,
                opacity: 0.25,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          )}

          {/* Route main layer */}
          {track.length > 1 && (
            <Polyline
              positions={track}
              pathOptions={{
                color: accentColor,
                weight: 4,
                opacity: 1,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          )}

          {/* Mile/km markers */}
          {mileMarkers.map((m) => (
            <Marker
              key={m.label}
              position={m.position}
              icon={createMileIcon(m.label)}
            />
          ))}

          {/* Start marker — green */}
          {track.length > 0 && (
            <CircleMarker
              center={track[0]}
              radius={7}
              pathOptions={{
                color: '#fff',
                weight: 2,
                fillColor: '#22c55e',
                fillOpacity: 1,
              }}
            />
          )}

          {/* End marker — red */}
          {track.length > 1 && (
            <CircleMarker
              center={track[track.length - 1]}
              radius={7}
              pathOptions={{
                color: '#fff',
                weight: 2,
                fillColor: '#ef4444',
                fillOpacity: 1,
              }}
            />
          )}

          {/* Pin marker (no track, just a point) */}
          {isPin && startCoords && (
            <CircleMarker
              center={startCoords}
              radius={7}
              pathOptions={{ color: accentColor, fillColor: accentColor, fillOpacity: 0.8, weight: 2 }}
            />
          )}
        </MapContainer>
      </div>
    </div>
  );
}
