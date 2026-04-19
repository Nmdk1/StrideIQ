'use client';

/**
 * CanvasV2 — top-level orchestrator for the sandbox Run Shape Canvas.
 *
 * Wires together:
 *   - ScrubProvider (shared cursor state across panels)
 *   - SummaryCardsRow (run-level, never changes on scrub)
 *   - StreamsStack (Pace + Elevation + HR, drives scrub by hover)
 *   - MomentReadout (Pace · Grade · HR · Cadence at scrub position)
 *   - TerrainMap3D (Mapbox GL spike — gated on NEXT_PUBLIC_MAPBOX_TOKEN)
 *
 * The 3D map is lazy-loaded so mapbox-gl (~700kB gz) doesn't ship in the
 * main bundle. The token-missing path also avoids loading the SDK at all.
 */

import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useStreamAnalysis, isAnalysisData, isLifecycleResponse } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { useResampledTrack } from './hooks/useResampledTrack';
import { useElementWidth } from './hooks/useElementWidth';
import { ScrubProvider } from './hooks/useScrubState';
import { SummaryCardsRow } from './SummaryCardsRow';
import { StreamsStack } from './StreamsStack';
import { MomentReadout } from './MomentReadout';

const TerrainMap3D = dynamic(
  () => import('./TerrainMap3D').then((m) => m.TerrainMap3D),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-2xl border border-slate-800/60 bg-slate-900/30 h-[480px] flex items-center justify-center text-sm text-slate-500">
        Loading 3D map…
      </div>
    ),
  },
);

export interface CanvasV2Props {
  activityId: string;
  /** Activity-level summary fields the cards display (never change on scrub). */
  summary: {
    cardiacDriftPct: number | null;
    avgHrBpm: number | null;
    avgCadenceSpm: number | null;
    maxGradePct: number | null;
    totalMovingTimeS: number | null;
  };
  title: string;
  subtitle: string;
}

export function CanvasV2({ activityId, summary, title, subtitle }: CanvasV2Props) {
  const streamQuery = useStreamAnalysis(activityId);
  const stream = isAnalysisData(streamQuery.data) ? streamQuery.data.stream : null;

  const { track, bounds, hasGps } = useResampledTrack(stream, { targetPoints: 500 });
  const { ref: streamsContainerRef, width: streamsWidth } = useElementWidth<HTMLDivElement>();

  const lifecycleStatus = useMemo(() => {
    if (isLifecycleResponse(streamQuery.data)) return streamQuery.data.status;
    return null;
  }, [streamQuery.data]);

  return (
    <ScrubProvider>
      <div className="space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-amber-500/70">Sandbox · Canvas v2</p>
          <h1 className="text-xl font-semibold mt-1">{title}</h1>
          <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
        </div>

        <SummaryCardsRow {...summary} />

        <div ref={streamsContainerRef}>
          {streamQuery.isLoading || lifecycleStatus === 'pending' ? (
            <div className="rounded-xl border border-slate-800/60 bg-slate-900/30 h-[300px] flex items-center justify-center text-sm text-slate-500 animate-pulse">
              Loading streams…
            </div>
          ) : (
            <StreamsStack track={track} width={Math.max(streamsWidth, 300)} />
          )}
        </div>

        <MomentReadout track={track} />

        {hasGps && bounds ? (
          <TerrainMap3D track={track} bounds={bounds} />
        ) : (
          <div className="rounded-2xl border border-slate-800/60 bg-slate-900/30 p-6 text-center text-sm text-slate-500">
            {lifecycleStatus === 'unavailable'
              ? 'No GPS for this activity — 3D map hidden.'
              : '3D map unavailable — streams only.'}
          </div>
        )}
      </div>
    </ScrubProvider>
  );
}
