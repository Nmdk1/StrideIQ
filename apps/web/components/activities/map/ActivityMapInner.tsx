'use client';

import { MapContainer, TileLayer, Polyline, CircleMarker, useMap } from 'react-leaflet';
import { LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';

const CARTO_DARK = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const CARTO_ATTRIBUTION = '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>';

interface GhostTrace {
  id: string;
  points: [number, number][];
  opacity: number;
}

interface Props {
  track: [number, number][];
  startCoords?: [number, number] | null;
  ghosts?: GhostTrace[];
  height?: number;
  accentColor?: string;
}

function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(bounds, { padding: [30, 30] });
  }, [map, bounds]);
  return null;
}

export default function ActivityMapInner({
  track,
  startCoords,
  ghosts = [],
  height = 300,
  accentColor = '#3b82f6',
}: Props) {
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
    const pad = 0.001;
    return [[minLat - pad, minLng - pad], [maxLat + pad, maxLng + pad]] as LatLngBoundsExpression;
  }, [track, ghosts, startCoords]);

  const isPin = track.length === 0 && startCoords;

  return (
    <div className="rounded-lg overflow-hidden border border-slate-700/30" style={{ height }}>
      <MapContainer
        center={isPin ? startCoords! : track[0] || [0, 0]}
        zoom={14}
        scrollWheelZoom={false}
        zoomControl={false}
        attributionControl={false}
        style={{ height: '100%', width: '100%', background: '#0f172a' }}
      >
        <TileLayer url={CARTO_DARK} attribution={CARTO_ATTRIBUTION} />
        <FitBounds bounds={bounds} />

        {ghosts.map((g) => (
          <Polyline
            key={g.id}
            positions={g.points}
            pathOptions={{ color: '#94a3b8', weight: 2, opacity: g.opacity }}
          />
        ))}

        {track.length > 1 && (
          <Polyline
            positions={track}
            pathOptions={{ color: accentColor, weight: 3, opacity: 0.9 }}
          />
        )}

        {isPin && startCoords && (
          <CircleMarker
            center={startCoords}
            radius={6}
            pathOptions={{ color: accentColor, fillColor: accentColor, fillOpacity: 0.8, weight: 2 }}
          />
        )}
      </MapContainer>
    </div>
  );
}
