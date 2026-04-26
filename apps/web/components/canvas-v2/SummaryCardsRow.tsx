'use client';

/**
 * SummaryCardsRow — fixed 5-card strip across the top of Canvas v2.
 *
 * Cards are RUN-LEVEL summary; they NEVER change on scrub. Per-moment values
 * live in the MomentReadout strip below the streams. This split is intentional
 * — it preserves the at-a-glance "what kind of run was this" reading.
 */

import React from 'react';

export interface SummaryCardsRowProps {
  cardiacDriftPct: number | null;
  avgHrBpm: number | null;
  avgCadenceSpm: number | null;
  maxGradePct: number | null;
  totalMovingTimeS: number | null;
}

function formatDriftPct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function formatInt(v: number | null, suffix = ''): string {
  if (v === null || !Number.isFinite(v)) return '—';
  return `${Math.round(v)}${suffix}`;
}

function formatGrade(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m`;
  return `${m}m`;
}

interface CardProps {
  label: string;
  value: string;
  unit?: string;
  tone?: 'default' | 'positive' | 'warning' | 'accent';
}

function SummaryCard({ label, value, unit, tone = 'default' }: CardProps) {
  const valueClass = {
    default: 'text-slate-100',
    positive: 'text-emerald-400',
    warning: 'text-amber-400',
    accent: 'text-rose-400',
  }[tone];

  return (
    <div className="rounded-2xl bg-slate-900/60 backdrop-blur-sm border border-slate-800/70 px-4 py-3 min-w-0 flex-1">
      <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5 truncate">
        {label}
      </p>
      <p className={`text-2xl font-semibold tabular-nums leading-none ${valueClass}`}>
        {value}
        {unit && (
          <span className="text-slate-500 text-sm font-normal ml-1">{unit}</span>
        )}
      </p>
    </div>
  );
}

export function SummaryCardsRow(props: SummaryCardsRowProps) {
  // Cardiac drift tone: negative drift is good (HR held while pace held/improved).
  const driftTone: CardProps['tone'] =
    props.cardiacDriftPct === null
      ? 'default'
      : props.cardiacDriftPct < 0
        ? 'positive'
        : props.cardiacDriftPct > 5
          ? 'warning'
          : 'default';

  return (
    <div className="flex gap-2 sm:gap-3 overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0 pb-1">
      <SummaryCard
        label="Cardiac Drift"
        value={formatDriftPct(props.cardiacDriftPct)}
        tone={driftTone}
      />
      <SummaryCard
        label="Avg HR"
        value={formatInt(props.avgHrBpm)}
        unit="bpm"
        tone="accent"
      />
      <SummaryCard
        label="Avg Cadence"
        value={formatInt(props.avgCadenceSpm)}
        unit="spm"
      />
      <SummaryCard
        label="Max Grade"
        value={formatGrade(props.maxGradePct)}
        tone="warning"
      />
      <SummaryCard label="Total Time" value={formatDuration(props.totalMovingTimeS)} />
    </div>
  );
}
