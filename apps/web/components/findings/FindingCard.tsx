'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';

export interface FindingCardProps {
  text?: string | null;
  domain?: string | null;
  confidenceTier?: string | null;
  timesConfirmed?: number | null;
  evidence?: string | null;
  implication?: string | null;
  expandable?: boolean;
  activityCount?: number;
}

type DomainVisual = {
  key: 'sleep' | 'cardiac' | 'pace' | 'environmental' | 'volume' | 'general';
  color: string;
  icon: string;
  label: string;
};

const DOMAIN_VISUALS: Record<DomainVisual['key'], DomainVisual> = {
  sleep: { key: 'sleep', color: '#818cf8', icon: '☾', label: 'Sleep' },
  cardiac: { key: 'cardiac', color: '#f87171', icon: '♥', label: 'Cardiac' },
  pace: { key: 'pace', color: '#2dd4bf', icon: '↗', label: 'Pace efficiency' },
  environmental: { key: 'environmental', color: '#fbbf24', icon: '☀', label: 'Environmental' },
  volume: { key: 'volume', color: '#60a5fa', icon: '▲', label: 'Volume' },
  general: { key: 'general', color: '#94a3b8', icon: '◆', label: 'Pattern' },
};

const ARC_RADIUS = 22;
const ARC_CIRCUMFERENCE = 2 * Math.PI * ARC_RADIUS;

export function getDomainVisual(domain?: string | null): DomainVisual {
  const d = (domain || '').toLowerCase();
  if (d.includes('sleep') || d.includes('hrv')) return DOMAIN_VISUALS.sleep;
  if (d.includes('hr') || d.includes('cardiac') || d.includes('heart')) return DOMAIN_VISUALS.cardiac;
  if (d.includes('pace') || d.includes('efficiency') || d.includes('speed')) return DOMAIN_VISUALS.pace;
  if (d.includes('heat') || d.includes('weather') || d.includes('temp') || d.includes('dew')) return DOMAIN_VISUALS.environmental;
  if (d.includes('volume') || d.includes('load') || d.includes('distance')) return DOMAIN_VISUALS.volume;
  return DOMAIN_VISUALS.general;
}

function getColdStartText(activityCount?: number): string {
  if (!activityCount || activityCount < 10) return 'Keep logging runs and check-ins to unlock your first confirmed pattern.';
  if (activityCount < 30) return 'Patterns are forming now. A little more data sharpens what the system can prove.';
  return 'Confirmed findings will appear here soon as evidence stabilizes.';
}

function hasRawStatsJargon(text?: string | null): boolean {
  const t = (text || '').toLowerCase();
  return t.includes('r=') || t.includes('p-value') || t.includes('correlation coefficient');
}

export default function FindingCard({
  text,
  domain,
  confidenceTier,
  timesConfirmed,
  evidence,
  implication,
  expandable = false,
  activityCount,
}: FindingCardProps) {
  const [open, setOpen] = useState(false);
  const visual = useMemo(() => getDomainVisual(domain), [domain]);
  const isColdStart = !text;
  const safeText = hasRawStatsJargon(text) ? 'Pattern details are being prepared.' : text;
  const safeEvidence = hasRawStatsJargon(evidence) ? 'Evidence details are available in coach context.' : evidence;
  const safeImplication = hasRawStatsJargon(implication) ? 'Action guidance is available in coach context.' : implication;

  const confirmations = Math.max(0, timesConfirmed || 0);
  const arcRatio = Math.min(confirmations / 60, 0.95);
  const dash = arcRatio * ARC_CIRCUMFERENCE;
  const showExpansion = expandable && !isColdStart;
  const askCoachHref = `/coach?q=${encodeURIComponent(safeText || '')}`;

  return (
    <div
      className="relative rounded-xl border border-slate-700/60 bg-slate-900/40 px-4 py-4 overflow-hidden"
      data-testid="finding-card"
      data-domain-key={visual.key}
    >
      <div
        data-testid="finding-card-glow"
        className="absolute left-0 top-0 h-[3px] w-full"
        style={{ background: `linear-gradient(90deg, ${visual.color}, transparent)` }}
      />

      <div className="flex items-start gap-3">
        <div className="relative h-[52px] w-[52px] shrink-0">
          <svg width="52" height="52" viewBox="0 0 52 52" data-testid="finding-arc">
            <circle
              cx="26"
              cy="26"
              r={ARC_RADIUS}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="3"
            />
            {!isColdStart && (
              <circle
                cx="26"
                cy="26"
                r={ARC_RADIUS}
                fill="none"
                stroke={visual.color}
                strokeWidth="3"
                strokeLinecap="round"
                strokeDasharray={`${dash} ${ARC_CIRCUMFERENCE}`}
                transform="rotate(-90 26 26)"
                data-testid="finding-arc-fill"
              />
            )}
          </svg>
          <span
            className="absolute inset-0 flex items-center justify-center text-sm font-semibold"
            style={{ color: visual.color }}
            aria-hidden="true"
            data-testid="finding-icon"
          >
            {visual.icon}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          {isColdStart ? (
            <>
              <p className="text-sm font-medium text-slate-200">Learning your patterns...</p>
              <p className="text-sm text-slate-400 mt-1">{getColdStartText(activityCount)}</p>
            </>
          ) : (
            <>
              <p className="text-sm text-slate-100 leading-relaxed">{safeText}</p>
              <p className="text-xs mt-1.5">
                <span style={{ color: visual.color }}>{visual.label}</span>
                <span className="text-slate-500">{` · ${confirmations} confirmations`}</span>
                {confidenceTier ? (
                  <span className="text-slate-500">{` · ${confidenceTier === 'strong' ? 'Strong pattern' : 'Confirmed pattern'}`}</span>
                ) : null}
              </p>
            </>
          )}
        </div>
      </div>

      {showExpansion && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="text-xs font-semibold text-slate-300 hover:text-white transition-colors"
            data-testid="finding-expand-toggle"
          >
            {open ? 'Hide evidence' : 'Show evidence'}
          </button>

          {open && (
            <div className="mt-2 rounded-lg border border-slate-700/60 bg-slate-800/30 p-3 space-y-2" data-testid="finding-expanded">
              {safeEvidence ? <p className="text-xs text-slate-300">{safeEvidence}</p> : null}
              {safeImplication ? <p className="text-xs text-slate-400">{safeImplication}</p> : null}
              <Link
                href={askCoachHref}
                className="inline-flex items-center text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors"
                data-testid="finding-ask-coach-link"
              >
                Ask Coach about this
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

