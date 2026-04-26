'use client';

/**
 * Training Blocks index — Phase 7
 *
 * Lists all detected training blocks for the athlete with weekly volume
 * sparklines. Clicking a block navigates to /blocks/[id] which renders
 * the block-over-block comparison.
 *
 * Backend: GET /v1/blocks
 * Detection: services/blocks/block_detector.py
 */

import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useUnits } from '@/lib/context/UnitsContext';

interface BlockSummary {
  id: string;
  start_date: string;
  end_date: string;
  weeks: number;
  phase: string;
  total_distance_m: number;
  total_duration_s: number;
  run_count: number;
  peak_week_distance_m: number;
  longest_run_m: number | null;
  quality_pct: number;
  workout_type_counts: Record<string, number>;
  dominant_workout_types: string[];
  goal_event_name: string | null;
}

const PHASE_COLORS: Record<string, string> = {
  base: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
  build: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  peak: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  taper: 'bg-violet-500/20 text-violet-300 border-violet-500/40',
  race: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
  recovery: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
  off: 'bg-slate-700/40 text-slate-400 border-slate-600/40',
};

export default function BlocksPage() {
  return (
    <ProtectedRoute>
      <BlocksPageInner />
    </ProtectedRoute>
  );
}

function BlocksPageInner() {
  const { token } = useAuth();
  const { formatDistance } = useUnits();

  const { data, isLoading, error } = useQuery<{ blocks: BlockSummary[] }>({
    queryKey: ['blocks-list'],
    queryFn: async () => {
      const res = await fetch(`${API_CONFIG.baseURL}/v1/blocks?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to fetch blocks');
      return res.json();
    },
    enabled: !!token,
  });

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <header className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">Training blocks</h1>
          <p className="text-sm text-slate-400 mt-1.5 max-w-2xl">
            Detected periods of consistent training. Each block is labeled by its
            character — base, build, peak, taper, race — and aggregates weekly
            volume, run count, and quality percentage.
          </p>
        </header>

        {isLoading && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-28 bg-slate-800/40 rounded-lg animate-pulse" />
            ))}
          </div>
        )}

        {error && (
          <div className="px-4 py-6 bg-rose-900/20 border border-rose-700/30 rounded-lg text-sm text-rose-300">
            Could not load training blocks.
          </div>
        )}

        {data && data.blocks.length === 0 && (
          <div className="px-4 py-8 bg-slate-800/30 rounded-lg text-sm text-slate-400">
            No training blocks detected yet. Blocks emerge from at least 2 weeks
            of consistent training; once you have a steady run history, your
            base/build/peak/taper periods will appear here automatically.
          </div>
        )}

        {data && data.blocks.length > 0 && (
          <div className="space-y-3">
            {data.blocks.map((block) => (
              <BlockRow key={block.id} block={block} formatDistance={formatDistance} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BlockRow({
  block,
  formatDistance,
}: {
  block: BlockSummary;
  formatDistance: (m: number) => string;
}) {
  const phaseClass =
    PHASE_COLORS[block.phase] || 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  const dateRange = `${formatShortDate(block.start_date)} → ${formatShortDate(block.end_date)}`;
  const dominant = block.dominant_workout_types.slice(0, 3);

  return (
    <Link
      href={`/blocks/${block.id}`}
      className="block px-5 py-4 bg-slate-800/30 hover:bg-slate-800/60 border border-slate-700/30 rounded-lg transition-colors"
    >
      <div className="flex items-start gap-4">
        <span
          className={`inline-block px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold rounded border ${phaseClass}`}
        >
          {block.phase}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium text-white">{dateRange}</span>
            <span className="text-[11px] text-slate-500 tabular-nums whitespace-nowrap">
              {block.weeks}w · {block.run_count} runs
            </span>
          </div>
          <div className="flex items-center gap-5 mt-2 text-xs text-slate-300 tabular-nums">
            <span>
              <span className="text-slate-500">Total </span>
              {formatDistance(block.total_distance_m)}
            </span>
            <span>
              <span className="text-slate-500">Peak week </span>
              {formatDistance(block.peak_week_distance_m)}
            </span>
            <span>
              <span className="text-slate-500">Quality </span>
              {block.quality_pct}%
            </span>
            {block.longest_run_m && (
              <span>
                <span className="text-slate-500">Longest </span>
                {formatDistance(block.longest_run_m)}
              </span>
            )}
          </div>
          {dominant.length > 0 && (
            <p className="text-[11px] text-slate-500 mt-1.5">
              {dominant.map((d) => d.replace(/_/g, ' ')).join(' · ')}
              {block.goal_event_name && ` → ${block.goal_event_name}`}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}

function formatShortDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
