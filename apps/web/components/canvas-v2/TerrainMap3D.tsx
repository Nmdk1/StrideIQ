'use client';

/**
 * TerrainMap3D — engine spike for the real 3D run map.
 *
 * Mapbox GL JS + mapbox-dem for actual surrounding terrain (lakes, hills,
 * road network, place identity), with the run's route overlaid as a glowing
 * line and a position marker that follows the shared scrub state.
 *
 * Spike scope (binding for v0):
 *   - outdoors-v12 style + setTerrain('mapbox-dem', exaggeration 3.0)
 *   - DON'T touch the built-in 'hillshade' layer — setPaintProperty on
 *     it threw a hard JS exception in style.load that broke route +
 *     marker setup. Relief comes from setTerrain alone.
 *   - camera tilt forced THREE ways (constructor pitch/bearing,
 *     fitBoundsOptions pitch/bearing, jumpTo on style.load) so something
 *     has to win
 *   - three-layer route: white casing under, emerald glow around,
 *     emerald line on top — readable on every basemap color
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
          // Set initial pitch/bearing on the constructor itself.
          pitch: 62,
          bearing: -20,
          bounds: [
            [bounds.minLng, bounds.minLat],
            [bounds.maxLng, bounds.maxLat],
          ],
          // Repeat pitch/bearing in fitBoundsOptions so the camera-for-bounds
          // calculation accounts for the tilted view (otherwise fit assumes
          // pitch=0 and the bounds shift after we tilt).
          fitBoundsOptions: { padding: 60, pitch: 62, bearing: -20 },
          attributionControl: true,
          cooperativeGestures: false,
        });
      } catch (e) {
        setMountError(`Failed to initialize Mapbox: ${(e as Error).message}`);
        return;
      }

      mapRef.current = map;

      // Compass + pitch indicator. Click compass to reset bearing/pitch
      // to north-flat. Drag the compass (or right-click+drag the map,
      // or two-finger drag on touch) to rotate. Mapbox's built-in
      // dragRotate is on by default.
      map.addControl(
        new mapboxgl.NavigationControl({
          showCompass: true,
          showZoom: true,
          visualizePitch: true,
        }),
        'top-right',
      );

      map.on('error', (ev) => {
        const msg = ev?.error?.message ?? String(ev?.error ?? 'unknown error');
        // eslint-disable-next-line no-console
        console.error('[TerrainMap3D] mapbox error:', msg);
        setMountError((prev) => prev ?? `Mapbox: ${msg}`);
      });

      map.on('style.load', () => {
        if (cancelled) return;

        // Force the camera tilt explicitly. fitBoundsOptions pitch was
        // not engaging on the initial constructor fit for reasons we
        // haven't pinned down. jumpTo is instant, no animation race.
        map.jumpTo({ pitch: 62, bearing: -20 });

        map.addSource('mapbox-dem', {
          type: 'raster-dem',
          url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
          tileSize: 512,
          maxzoom: 14,
        });
        // 3.0 exaggeration — Bonita has ~550ft of relief over 4.6mi with
        // 15% pitches. 1.4 flat, 2.0 shy, 2.5 still mild on this zoom,
        // 3.0 should finally read as the rolling-hills terrain it is.
        // Outdoors-v12's built-in hillshade does the shading; we just
        // drive the geometry harder via setTerrain.
        map.setTerrain({ source: 'mapbox-dem', exaggeration: 3.0 });

        const coordinates = track.map((p) => [p.lng, p.lat] as [number, number]);
        map.addSource('route', {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates },
          },
        });
        // Three layers, bottom to top:
        //   1. white casing — sharp edge for contrast against any color
        //   2. emerald glow — wide blurred halo, makes route findable
        //   3. emerald line — saturated stroke on top
        // Stroke widths chosen so the trail is unmissable at the default
        // bounds zoom (~14) without being cartoonish.
        map.addLayer({
          id: 'route-casing',
          type: 'line',
          source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#ffffff',
            'line-width': 8,
            'line-opacity': 0.7,
          },
        });
        map.addLayer({
          id: 'route-glow',
          type: 'line',
          source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#10b981',
            'line-width': 14,
            'line-opacity': 0.45,
            'line-blur': 6,
          },
        });
        map.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#059669',
            'line-width': 4,
          },
        });

        const el = document.createElement('div');
        el.style.width = '20px';
        el.style.height = '20px';
        el.style.borderRadius = '50%';
        el.style.background = '#fbbf24';
        el.style.border = '3px solid #ffffff';
        el.style.boxShadow = '0 0 18px rgba(251,191,36,0.9), 0 0 4px rgba(0,0,0,0.6)';
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
          {mountError
            ? `error: ${mountError.slice(0, 80)}`
            : 'Mapbox · right-click drag to rotate · click compass to reset'}
        </span>
      </div>
      <div ref={containerRef} className="h-[480px] w-full" />
    </div>
  );
}
