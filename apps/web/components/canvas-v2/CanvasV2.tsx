'use client';

/**
 * CanvasV2 — top-level orchestrator for the sandbox Run Shape Canvas.
 *
 * Wires together:
 *   - ScrubProvider (shared cursor state across panels)
 *   - SummaryCardsRow (run-level, never changes on scrub)
 *   - StreamsStack (Pace + HR + Elevation, drives scrub by hover)
 *   - MomentReadout (Pace · Grade · HR · Cadence at scrub position)
 *
 * The 3D terrain panel was removed after first-pass review: a path-only
 * heightfield without surrounding DEM is fundamentally a worse map than the
 * existing 2D Leaflet view. Real 3D map work is scoped separately in
 * docs/specs/RUN_3D_MAP.md.
 */

import React, { useMemo } from 'react';
import { useStreamAnalysis, isAnalysisData, isLifecycleResponse } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { useResampledTrack } from './hooks/useResampledTrack';
import { useElementWidth } from './hooks/useElementWidth';
import { ScrubProvider } from './hooks/useScrubState';
import { SummaryCardsRow } from './SummaryCardsRow';
import { StreamsStack } from './StreamsStack';
import { MomentReadout } from './MomentReadout';

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

  const { track } = useResampledTrack(stream, { targetPoints: 500 });
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
      </div>
    </ScrubProvider>
  );
}
