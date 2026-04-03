'use client';

/**
 * Personal Operating Manual
 *
 * Everything the system has learned about this athlete, assembled as a
 * structured, readable document organized by physiological domain.
 *
 * Design intent: this is a document, not a dashboard. Long-form, readable,
 * evidence-weighted. The kind of thing you'd read on a rest day and think
 * "so this is what my body does."
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useOperatingManual, ManualEntry, ManualSection } from '@/lib/hooks/queries/manual';
import {
  Moon,
  Heart,
  Zap,
  Sun,
  TrendingUp,
  Target,
  Brain,
  Repeat,
  Activity,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Footprints,
} from 'lucide-react';

const DOMAIN_ICONS: Record<string, React.ReactNode> = {
  recovery: <Zap className="w-5 h-5" />,
  sleep: <Moon className="w-5 h-5" />,
  cardiac: <Heart className="w-5 h-5" />,
  training_load: <TrendingUp className="w-5 h-5" />,
  environmental: <Sun className="w-5 h-5" />,
  pace: <Footprints className="w-5 h-5" />,
  race: <Target className="w-5 h-5" />,
  subjective: <Brain className="w-5 h-5" />,
  training_pattern: <Repeat className="w-5 h-5" />,
};

const DOMAIN_COLORS: Record<string, string> = {
  recovery: '#60a5fa',
  sleep: '#818cf8',
  cardiac: '#f87171',
  training_load: '#34d399',
  environmental: '#fbbf24',
  pace: '#2dd4bf',
  race: '#f472b6',
  subjective: '#a78bfa',
  training_pattern: '#fb923c',
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  } catch {
    return '';
  }
}

function daysSince(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
    if (days < 30) return `${days}d ago`;
    if (days < 365) return `${Math.floor(days / 30)}mo ago`;
    return `${(days / 365).toFixed(1)}y ago`;
  } catch {
    return '';
  }
}

function ConfidenceArc({ tier, confirmed }: { tier?: string; confirmed?: number }) {
  const n = confirmed ?? 0;
  const maxArc = 12;
  const pct = Math.min(n / maxArc, 1);
  const r = 14;
  const circumference = 2 * Math.PI * r;
  const dashLen = circumference * 0.75 * pct;

  let color = '#64748b';
  if (tier === 'strong') color = '#22c55e';
  else if (tier === 'confirmed') color = '#3b82f6';
  else if (tier === 'emerging') color = '#94a3b8';

  return (
    <div className="relative w-9 h-9 flex-shrink-0" title={`${n} confirmations`}>
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" stroke="#1e293b" strokeWidth="3" />
        <circle
          cx="18" cy="18" r={r} fill="none"
          stroke={color} strokeWidth="3"
          strokeDasharray={`${dashLen} ${circumference}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-slate-300">
        {n}
      </span>
    </div>
  );
}

function EntryCard({ entry, domainColor }: { entry: ManualEntry; domainColor: string }) {
  const [expanded, setExpanded] = useState(false);
  const isCorrelation = entry.source === 'correlation';

  const hasDetails = !!(entry.threshold || entry.asymmetry || entry.timing || entry.cascade);

  return (
    <div className="group border-l-2 pl-5 py-4" style={{ borderColor: domainColor + '40' }}>
      <div className="flex items-start gap-3">
        {isCorrelation && (
          <ConfidenceArc tier={entry.confidence_tier} confirmed={entry.times_confirmed} />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 leading-relaxed">{entry.headline}</p>

          {isCorrelation && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
              {entry.input && entry.output && (
                <span>{entry.input} → {entry.output}</span>
              )}
              {entry.r != null && (
                <span>r = {entry.r.toFixed(2)}</span>
              )}
              {entry.confidence_tier && (
                <span className={
                  entry.confidence_tier === 'strong' ? 'text-green-500' :
                  entry.confidence_tier === 'confirmed' ? 'text-blue-400' :
                  'text-slate-500'
                }>
                  {entry.confidence_tier}
                </span>
              )}
              {entry.last_confirmed && (
                <span>last seen {daysSince(entry.last_confirmed)}</span>
              )}
            </div>
          )}

          {!isCorrelation && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
              {entry.confidence && (
                <span className={
                  entry.confidence === 'table_stakes' ? 'text-green-500' :
                  entry.confidence === 'genuine' ? 'text-blue-400' :
                  'text-slate-500'
                }>
                  {entry.confidence === 'table_stakes' ? 'definitive' : entry.confidence}
                </span>
              )}
              {entry.last_confirmed && (
                <span>last seen {daysSince(entry.last_confirmed)}</span>
              )}
            </div>
          )}

          {hasDetails && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-2 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {expanded ? 'Less' : 'Details'}
            </button>
          )}

          {expanded && (
            <div className="mt-3 space-y-2 text-xs text-slate-400 bg-slate-900/60 rounded-lg px-4 py-3">
              {entry.threshold && (
                <div>
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Threshold</span>
                  <p className="mt-0.5">{entry.threshold.label}</p>
                </div>
              )}
              {entry.asymmetry && (
                <div>
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Asymmetry</span>
                  <p className="mt-0.5">{entry.asymmetry.label}</p>
                </div>
              )}
              {entry.timing && (
                <div>
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Timing</span>
                  <p className="mt-0.5">
                    {entry.timing.half_life_days != null && `Half-life: ${entry.timing.half_life_days} days (${entry.timing.decay_type})`}
                    {entry.timing.lag_days != null && entry.timing.half_life_days != null && ' · '}
                    {entry.timing.lag_days != null && `Delayed effect: ${entry.timing.lag_days} day${entry.timing.lag_days !== 1 ? 's' : ''}`}
                  </p>
                </div>
              )}
              {entry.cascade && entry.cascade.length > 0 && (
                <div>
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Cascade chain</span>
                  {entry.cascade.map((c, i) => (
                    <p key={i} className="mt-0.5">
                      via {c.mediator}
                      {c.mediation_ratio != null && ` (${Math.round(c.mediation_ratio * 100)}% mediated)`}
                      {c.is_full_mediation && ' — full mediation'}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DomainSection({ section }: { section: ManualSection }) {
  const [collapsed, setCollapsed] = useState(false);
  const color = DOMAIN_COLORS[section.domain] || '#94a3b8';
  const icon = DOMAIN_ICONS[section.domain] || <Activity className="w-5 h-5" />;
  const confirmed = section.entries.filter(e => (e.times_confirmed ?? 0) >= 3 || e.confidence === 'table_stakes' || e.confidence === 'genuine').length;

  return (
    <section className="mb-10">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-3 mb-1 group"
      >
        <span style={{ color }}>{icon}</span>
        <h2 className="text-lg font-semibold text-slate-100 flex-1 text-left">{section.label}</h2>
        <span className="text-xs text-slate-500 mr-2">
          {confirmed} confirmed · {section.entry_count} total
        </span>
        {collapsed
          ? <ChevronRight className="w-4 h-4 text-slate-500" />
          : <ChevronDown className="w-4 h-4 text-slate-500" />
        }
      </button>
      {section.description && !collapsed && (
        <p className="text-xs text-slate-500 mb-4 ml-8">{section.description}</p>
      )}
      {!collapsed && (
        <div className="ml-2">
          {section.entries.map((entry) => (
            <EntryCard key={entry.id} entry={entry} domainColor={color} />
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyManual() {
  return (
    <div className="text-center py-20 px-6">
      <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-slate-800 flex items-center justify-center">
        <Footprints className="w-8 h-8 text-slate-500" />
      </div>
      <h2 className="text-xl font-semibold text-slate-200 mb-3">
        Your manual is being written
      </h2>
      <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed mb-8">
        Every run, every night of sleep, every check-in teaches the system something about
        your body. As patterns confirm, they&apos;ll appear here — organized by what they mean,
        not where they came from.
      </p>
      <div className="flex flex-col items-center gap-3 text-xs text-slate-500">
        <p>First findings typically appear after 2-3 weeks of consistent data.</p>
        <Link
          href="/home"
          className="text-orange-400 hover:text-orange-300 transition-colors"
        >
          Back to Home
        </Link>
      </div>
    </div>
  );
}

export default function ManualPage() {
  const { data, isLoading, error } = useOperatingManual();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <p className="text-slate-400">Could not load your manual. Try again.</p>
        </div>
      </ProtectedRoute>
    );
  }

  const { summary, sections } = data;
  const isEmpty = sections.length === 0;

  const learningSince = summary.learning_since
    ? formatDate(summary.learning_since)
    : null;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[#0d1321] text-slate-100">
        <div className="max-w-[780px] mx-auto px-6 py-10">

          {/* Header */}
          <header className="mb-12">
            <h1 className="text-2xl font-bold text-white mb-2">
              Personal Operating Manual
            </h1>
            <p className="text-sm text-slate-400 leading-relaxed max-w-lg">
              Everything the system has confirmed about how your body works.
              {learningSince && <> Learning since {learningSince}.</>}
            </p>
          </header>

          {isEmpty ? (
            <EmptyManual />
          ) : (
            <>
              {/* Summary strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-12">
                <SummaryStat label="Confirmed" value={summary.confirmed_findings} accent="#3b82f6" />
                <SummaryStat label="Strong" value={summary.strong_findings} accent="#22c55e" />
                <SummaryStat label="Domains" value={summary.domains_covered} accent="#a78bfa" />
                <SummaryStat label="Total entries" value={summary.total_entries} accent="#64748b" />
              </div>

              {/* Domain sections */}
              {sections.map((section) => (
                <DomainSection key={section.domain} section={section} />
              ))}

              {/* Footer */}
              <footer className="mt-16 pt-6 border-t border-slate-800/50">
                <div className="flex items-center justify-between text-xs text-slate-600">
                  <span>
                    {summary.correlation_findings} correlations · {summary.investigation_findings} investigations
                  </span>
                  <Link
                    href="/coach?q=What%20are%20the%20most%20important%20patterns%20in%20my%20operating%20manual?"
                    className="flex items-center gap-1 text-orange-500/60 hover:text-orange-400 transition-colors"
                  >
                    <MessageSquare className="w-3 h-3" /> Ask coach about these
                  </Link>
                </div>
              </footer>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

function SummaryStat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="rounded-xl border border-slate-700/40 bg-[#141c2e] px-4 py-3">
      <p className="text-2xl font-bold" style={{ color: accent }}>{value}</p>
      <p className="text-xs text-slate-500 mt-0.5">{label}</p>
    </div>
  );
}
