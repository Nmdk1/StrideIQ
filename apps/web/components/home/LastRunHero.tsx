/**
 * RSI Layer 1 — LastRunHero
 *
 * Home page hero component that shows the effort gradient canvas when
 * the most recent run (within 24h) has stream data. Falls back to a
 * clean metrics-only card when streams aren't ready.
 *
 * Design principles (from RSI_WIRING_SPEC):
 *   - The canvas is the product — effort gradient is first thing the athlete sees
 *   - Silent upgrade — metrics card → canvas hero without loading spinners
 *   - No "pending" text, no skeleton, no loading indicators
 *   - Tap anywhere → navigates to /activities/{id}
 */

'use client';

import React, { useEffect, useRef } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { effortToColor } from '@/components/activities/rsi/utils/effortColor';
import { useUnits } from '@/lib/context/UnitsContext';
import type { LastRun } from '@/lib/api/services/home';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return '--';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 1) return 'Just now';
  if (diffHours < 2) return '1h ago';
  if (diffHours < 12) return `${Math.floor(diffHours)}h ago`;

  // Same day
  if (date.toDateString() === now.toDateString()) {
    return `Today ${date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`;
  }

  // Yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday ${date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`;
  }

  return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// MiniEffortCanvas — compact effort gradient for the hero
// ---------------------------------------------------------------------------

function MiniEffortCanvas({
  effortIntensity,
  height = 80,
}: {
  effortIntensity: number[];
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || effortIntensity.length === 0) return;

    // Use parent width
    const parentWidth = canvas.parentElement?.clientWidth ?? 400;
    canvas.width = parentWidth;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const n = effortIntensity.length;
    const pxPerPoint = parentWidth / n;

    for (let i = 0; i < n; i++) {
      ctx.fillStyle = effortToColor(effortIntensity[i]);
      const x = Math.floor(i * pxPerPoint);
      const w = Math.ceil(pxPerPoint) + 1;
      ctx.fillRect(x, 0, w, height);
    }
  }, [effortIntensity, height]);

  return (
    <canvas
      ref={canvasRef}
      data-testid="hero-effort-gradient"
      className="w-full rounded-t-lg"
      style={{ height, display: 'block' }}
    />
  );
}

// ---------------------------------------------------------------------------
// MetricsPill — compact inline metric
// ---------------------------------------------------------------------------

function MetricsPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LastRunHero (main export)
// ---------------------------------------------------------------------------

export interface LastRunHeroProps {
  lastRun: LastRun;
}

export function LastRunHero({ lastRun }: LastRunHeroProps) {
  const { formatDistance, formatPace } = useUnits();
  const hasCanvas = lastRun.stream_status === 'success' && lastRun.effort_intensity && lastRun.effort_intensity.length > 0;

  // Canvas Hero — effort gradient + metrics ribbon
  if (hasCanvas) {
    return (
      <Link
        href={`/activities/${lastRun.activity_id}`}
        data-testid="last-run-hero"
        className="block rounded-lg overflow-hidden bg-slate-800/50 border border-slate-700/50 hover:border-slate-600/70 transition-colors"
      >
        {/* Effort gradient canvas */}
        <MiniEffortCanvas effortIntensity={lastRun.effort_intensity!} height={80} />

        {/* Metrics ribbon */}
        <div className="px-4 py-3 space-y-2">
          {/* Title row */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-white">{lastRun.name}</p>
              <p className="text-xs text-slate-400">{formatRelativeTime(lastRun.start_time)}</p>
            </div>
            {lastRun.tier_used && lastRun.confidence != null && (
              <div className="text-xs text-slate-500">
                {Math.round(lastRun.confidence * 100)}% confidence
              </div>
            )}
          </div>

          {/* Compact metrics row */}
          <div className="flex justify-between items-center">
            <MetricsPill label="Distance" value={formatDistance(lastRun.distance_m)} />
            <MetricsPill label="Duration" value={formatDuration(lastRun.moving_time_s)} />
            <MetricsPill label="Pace" value={formatPace(lastRun.pace_per_km)} />
            {lastRun.average_hr != null && (
              <MetricsPill label="Avg HR" value={`${Math.round(lastRun.average_hr)} bpm`} />
            )}
          </div>

          {/* See Full Analysis link */}
          <div className="flex justify-end pt-1">
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-400">
              See Full Analysis <ArrowRight className="w-3 h-3" />
            </span>
          </div>
        </div>
      </Link>
    );
  }

  // Metrics-only card — silent upgrade path (no loading indicator)
  return (
    <Link
      href={`/activities/${lastRun.activity_id}`}
      data-testid="last-run-hero"
      data-hero-mode="metrics"
      className="block rounded-lg overflow-hidden bg-slate-800/50 border border-slate-700/50 hover:border-slate-600/70 transition-colors"
    >
      <div className="px-4 py-4 space-y-2">
        {/* Title row */}
        <div>
          <p className="text-sm font-semibold text-white">{lastRun.name}</p>
          <p className="text-xs text-slate-400">{formatRelativeTime(lastRun.start_time)}</p>
        </div>

        {/* Compact metrics row */}
        <div className="flex justify-between items-center">
          <MetricsPill label="Distance" value={formatDistance(lastRun.distance_m)} />
          <MetricsPill label="Duration" value={formatDuration(lastRun.moving_time_s)} />
          <MetricsPill label="Pace" value={formatPace(lastRun.pace_per_km)} />
          {lastRun.average_hr != null && (
            <MetricsPill label="Avg HR" value={`${Math.round(lastRun.average_hr)} bpm`} />
          )}
        </div>

        {/* View Run link */}
        <div className="flex justify-end pt-1">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-400">
            View Run <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </div>
    </Link>
  );
}
