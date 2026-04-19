'use client';

/**
 * TerrainMap3D — engine spike for the real 3D run map.
 *
 * Mapbox GL JS + mapbox-dem for actual surrounding terrain (lakes, hills,
 * road network, place identity), with the run's route overlaid as a glowing
 * line and a position marker that follows the shared scrub state.
 *
 * Spike scope (binding for v0):
 *   - outdoors-v12 style + setTerrain('mapbox-dem', exaggeration 2.5)
 *   - boost the BUILT-IN hillshade layer's paint properties (don't add
 *     a second one — outdoors-v12 ships with id 'hillshade' already)
 *   - camera starts pitched (62°) and bearing'd (-20°) directly in the
 *     constructor — no race between fitBounds and a deferred easeTo
 *   - emerald route line + glow (high contrast on warm topo, doesn't
 *     blend with lakes the way blue would)
 *   - position marker bound to useScrubState
 *
 * Token: reads NEXT_PUBLIC_MAPBOX_TOKEN. If absent, renders a clear
 * guidance card and skips Mapbox mount entirely (no console errors, no
 * partial UI).
 *
 * See docs/specs/RUN_3D_MAP.md for the full spec this is exploring.
 */

import React, { useEffect, useRef, useState } from 'react';
import type mapboxgl from 'mapbox-gl';
// Static CSS import: Next.js extracts this into a CSS chunk that ships
// with the dynamic JS chunk. Importing CSS inside a useEffect via
// dynamic import does NOT get extracted — the canvas mounts but the
// styles never apply, so the map is invisible.
import 'mapbox-gl/dist/mapbox-gl.css';
import { useScrubState } from './hooks/useScrubState';
import type { TrackPoint, TrackBounds } from './hooks/useResampledTrack';

export interface TerrainMap3DProps {
  track: TrackPoint[];
  bounds: TrackBounds;
}

function NoTokenState() {
  return (
    <div className="rounded-2xl border border-amber-700/40 bg-amber-950/20 p-6">
      <p className="text-amber-300 font-semibold mb-2 text-sm uppercase tracking-wider">
        Terrain · 3D Map · spike
      </p>
      <p className="text-slate-300 text-sm mb-3">Mapbox token required.</p>
      <p className="text-slate-400 text-sm leading-relaxed">
        Set <code className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-200 text-xs">NEXT_PUBLIC_MAPBOX_TOKEN</code>{' '}
        on the server (free tier at{' '}
        <a
          href="https://account.mapbox.com/access-tokens/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline text-amber-400 hover:text-amber-300"
        >
          account.mapbox.com/access-tokens
        </a>
        ) and restart the web container.
      </p>
    </div>
  );
}

function pickAt(track: TrackPoint[], t: number): TrackPoint | null {
  if (track.length === 0) return null;
  const target = Math.max(0, Math.min(1, t));
  let lo = 0;
  let hi = track.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (track[mid].t < target) lo = mid + 1;
    else hi = mid;
  }
  return track[lo] ?? null;
}

export function TerrainMap3D({ track, bounds }: TerrainMap3DProps) {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  const [mountError, setMountError] = useState<string | null>(null);
  const { position } = useScrubState();

  useEffect(() => {
    if (!token) return;
    if (!containerRef.current) return;
    if (track.length < 2) return;

    let cancelled = false;

    (async () => {
      let mapboxgl: typeof import('mapbox-gl').default;
      try {
        const mapboxModule = await import('mapbox-gl');
        mapboxgl = mapboxModule.default;
      } catch (e) {
        if (!cancelled) setMountError(`Failed to load mapbox-gl: ${(e as Error).message}`);
        return;
      }
      if (cancelled || !containerRef.current) return;

      mapboxgl.accessToken = token;

      let map: mapboxgl.Map;
      try {
        map = new mapboxgl.Map({
          container: containerRef.current,
          style: 'mapbox://styles/mapbox/outdoors-v12',
          bounds: [
            [bounds.minLng, bounds.minLat],
            [bounds.maxLng, bounds.maxLat],
          ],
          // Pitch/bearing in the constructor (not deferred easeTo) so they
          // commit alongside the initial bounds fit. Previous spike used
          // easeTo on style.load and the camera stayed flat.
          fitBoundsOptions: { padding: 60, pitch: 62, bearing: -20 },
          attributionControl: true,
          cooperativeGestures: false,
        });
      } catch (e) {
        setMountError(`Failed to initialize Mapbox: ${(e as Error).message}`);
        return;
      }

      mapRef.current = map;

      map.on('error', (ev) => {
        const msg = ev?.error?.message ?? String(ev?.error ?? 'unknown error');
        // eslint-disable-next-line no-console
        console.error('[TerrainMap3D] mapbox error:', msg);
        setMountError((prev) => prev ?? `Mapbox: ${msg}`);
      });

      map.on('style.load', () => {
        if (cancelled) return;

        map.addSource('mapbox-dem', {
          type: 'raster-dem',
          url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
          tileSize: 512,
          maxzoom: 14,
        });
        // 2.5 exaggeration — Bonita has ~550ft of relief over 4.6mi with
        // 15% pitches and is rolling-hills terrain (not Colorado, but
        // genuinely hilly for southeast running). 1.4 was flat, 2.0 was
        // shy, 2.5 makes the climbs actually read at this zoom.
        map.setTerrain({ source: 'mapbox-dem', exaggeration: 2.5 });

        // Outdoors-v12 already ships with a hillshade layer (id 'hillshade'
        // and source 'mapbox-dem'). Adding our own caused a duplicate-id
        // collision and silently fell back to the default mild styling —
        // a chunk of the missing topographic drama. Boost the existing
        // layer's paint instead of adding a competing one.
        if (map.getLayer('hillshade')) {
          map.setPaintProperty('hillshade', 'hillshade-exaggeration', 0.85);
          map.setPaintProperty('hillshade', 'hillshade-shadow-color', '#0f172a');
          map.setPaintProperty('hillshade', 'hillshade-highlight-color', '#fef3c7');
          map.setPaintProperty('hillshade', 'hillshade-accent-color', '#78350f');
        }

        const coordinates = track.map((p) => [p.lng, p.lat] as [number, number]);
        map.addSource('route', {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates },
          },
        });
        map.addLayer({
          id: 'route-glow',
          type: 'line',
          source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#10b981',
            'line-width': 11,
            'line-opacity': 0.35,
            'line-blur': 5,
          },
        });
        map.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#34d399',
            'line-width': 3.5,
          },
        });

        const el = document.createElement('div');
        el.style.width = '14px';
        el.style.height = '14px';
        el.style.borderRadius = '50%';
        el.style.background = '#fbbf24';
        el.style.border = '2px solid #fef3c7';
        el.style.boxShadow = '0 0 12px rgba(251,191,36,0.7)';
        const marker = new mapboxgl.Marker({ element: el, anchor: 'center' })
          .setLngLat([track[0].lng, track[0].lat])
          .addTo(map);
        markerRef.current = marker;
      });
    })();

    return () => {
      cancelled = true;
      markerRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [token, bounds, track]);

  useEffect(() => {
    if (!markerRef.current || track.length === 0) return;
    if (position === null) {
      markerRef.current.setLngLat([track[0].lng, track[0].lat]);
      return;
    }
    const point = pickAt(track, position);
    if (point) {
      markerRef.current.setLngLat([point.lng, point.lat]);
    }
  }, [position, track]);

  if (!token) {
    return <NoTokenState />;
  }

  return (
    <div className="rounded-2xl overflow-hidden border border-slate-800/60 bg-slate-900/30">
      <div className="flex items-center justify-between px-4 py-2 text-xs uppercase tracking-wider text-slate-500 border-b border-slate-800/60">
        <span>Terrain · 3D Map · spike</span>
        <span className={mountError ? 'text-rose-400' : 'text-amber-500/70'}>
          {mountError ? `error: ${mountError.slice(0, 80)}` : 'Mapbox · drag to orbit'}
        </span>
      </div>
      <div ref={containerRef} className="h-[480px] w-full" />
    </div>
  );
}
