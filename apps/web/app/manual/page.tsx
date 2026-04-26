'use client';

/**
 * Personal Operating Manual V2
 *
 * Leads with understanding, not listing.
 * 1. Race Character — who you are on race day
 * 2. Cascade Stories — how your body propagates signals
 * 3. Highlighted Findings — interestingness-ranked, human language
 * 4. What Changed — since last visit
 * 5. Full Record — V1 domain sections, collapsed
 */

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useUnits } from '@/lib/context/UnitsContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import {
  useOperatingManual,
  ManualEntry,
  ManualSection,
  RaceCharacter,
  CascadeStory,
} from '@/lib/hooks/queries/manual';
import {
  Moon, Heart, Zap, Sun, TrendingUp, Target, Brain, Repeat,
  Activity, ChevronDown, ChevronRight, MessageSquare, Footprints,
  Trophy, GitBranch, Sparkles, Clock,
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

const STORAGE_KEY = 'strideiq_manual_last_visit';

function daysSince(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
    if (days < 1) return 'today';
    if (days === 1) return 'yesterday';
    if (days < 30) return `${days}d ago`;
    if (days < 365) return `${Math.floor(days / 30)}mo ago`;
    return `${(days / 365).toFixed(1)}y ago`;
  } catch {
    return '';
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  } catch {
    return '';
  }
}

// ─── Race Character ─────────────────────────────────────────────────────

function RaceCharacterSection({ data }: { data: RaceCharacter }) {
  const { formatDistance } = useUnits();
  const [expanded, setExpanded] = useState(false);

  if (!data.has_gap_data && data.race_count === 0) return null;

  return (
    <section className="mb-12">
      <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-[#1a1c2e] to-[#141c2e] overflow-hidden">
        <div className="px-6 py-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
              <Trophy className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Race Character</h2>
              <p className="text-xs text-slate-500">{data.race_count} races analyzed</p>
            </div>
          </div>

          {data.narrative && (
            <p className="text-sm text-slate-200 leading-relaxed mb-4">
              {data.narrative}
            </p>
          )}

          {data.has_gap_data && data.avg_gap_pct != null && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
              <div className="rounded-xl bg-[#0d1321]/60 px-4 py-3">
                <p className="text-2xl font-bold text-amber-400">
                  +{data.avg_gap_pct.toFixed(0)}%
                </p>
                <p className="text-xs text-slate-500 mt-0.5">faster on race day</p>
              </div>
              <div className="rounded-xl bg-[#0d1321]/60 px-4 py-3">
                <p className="text-2xl font-bold text-amber-400">{data.race_count}</p>
                <p className="text-xs text-slate-500 mt-0.5">races</p>
              </div>
              {data.pb_count != null && (
                <div className="rounded-xl bg-[#0d1321]/60 px-4 py-3">
                  <p className="text-2xl font-bold text-amber-400">{data.pb_count}</p>
                  <p className="text-xs text-slate-500 mt-0.5">personal bests</p>
                </div>
              )}
            </div>
          )}

          {data.races.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {expanded ? 'Hide race details' : 'Show race details'}
            </button>
          )}

          {expanded && (
            <div className="mt-4 space-y-2">
              {data.races.map((race) => (
                <div
                  key={race.date}
                  className="flex items-center justify-between text-xs bg-[#0d1321]/40 rounded-lg px-4 py-2.5"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500 w-20">{race.date}</span>
                    <span className="text-slate-300">
                      {formatDistance(race.distance_m)} at {race.race_pace}
                    </span>
                    {race.name && (
                      <span className="text-slate-600 truncate max-w-[120px]">{race.name}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {race.gap_pct != null && (
                      <span className="text-amber-400 font-medium">
                        +{race.gap_pct.toFixed(0)}% vs training
                      </span>
                    )}
                    {race.is_pb && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-500/70">
                        PB
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {data.counterevidence && data.counterevidence.length > 0 && (
            <div className="mt-5 pt-5 border-t border-amber-500/10">
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-500/70 mb-3">
                You override your own patterns
              </p>
              <div className="space-y-2">
                {data.counterevidence.slice(0, 5).map((c, i) => (
                  <div
                    key={i}
                    className="text-sm text-slate-200 leading-relaxed bg-[#0d1321]/40 rounded-lg px-4 py-3 border-l-2 border-amber-500/30"
                  >
                    {c.text}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ─── Cascade Stories ─────────────────────────────────────────────────────

function CascadeChainVisual({ chain, mediators }: {
  chain: string[];
  mediators: { name: string; mediation_pct: number }[];
}) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto py-2">
      {chain.map((node, i) => (
        <React.Fragment key={i}>
          <div className="flex-shrink-0 rounded-lg bg-slate-800/80 border border-slate-700/50 px-3 py-1.5">
            <span className="text-xs font-medium text-slate-200 whitespace-nowrap">{node}</span>
          </div>
          {i < chain.length - 1 && (
            <div className="flex-shrink-0 flex items-center gap-0.5 text-slate-600">
              <div className="w-4 h-px bg-slate-600" />
              {mediators[i] && mediators[i].mediation_pct > 0 && (
                <span className="text-[9px] text-slate-500 whitespace-nowrap">
                  {mediators[i].mediation_pct}%
                </span>
              )}
              <div className="w-4 h-px bg-slate-600" />
              <ChevronRight className="w-3 h-3" />
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function CascadeStoryCard({ story }: { story: CascadeStory }) {
  return (
    <div className="rounded-xl border border-indigo-500/15 bg-[#141c2e] p-5 mb-3">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
          <GitBranch className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="flex-1 min-w-0">
          {story.title && (
            <p className="text-sm font-medium text-slate-100 mb-1">{story.title}</p>
          )}
          <p className="text-sm text-slate-300 leading-relaxed">{story.narrative}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
            <span>{story.finding_count} connected findings</span>
            <span>confirmed {story.times_confirmed}x</span>
          </div>
        </div>
      </div>
      <CascadeChainVisual chain={story.chain} mediators={story.mediators} />
      <div className="mt-3 flex justify-end">
        <Link
          href={`/coach?q=How does my ${story.input} affect my running through ${story.mediators[0]?.name || 'other factors'}?`}
          className="flex items-center gap-1 text-xs text-orange-500/60 hover:text-orange-400 transition-colors"
        >
          <MessageSquare className="w-3 h-3" /> Discuss with coach
        </Link>
      </div>
    </div>
  );
}

// ─── Highlighted Findings ────────────────────────────────────────────────

function HighlightedFindingCard({ entry }: { entry: ManualEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = !!(entry.threshold || entry.asymmetry || entry.timing);

  const coachQuestion = entry.threshold
    ? `Tell me about my ${entry.input} threshold and how it affects my ${entry.output}`
    : `How does ${entry.input} affect my ${entry.output}?`;

  return (
    <div className="rounded-xl border border-slate-700/30 bg-[#141c2e] px-5 py-4 mb-2">
      <div className="flex items-start gap-3">
        {entry.direction_counterintuitive && (
          <div className="w-6 h-6 rounded-full bg-rose-500/10 flex items-center justify-center flex-shrink-0 mt-0.5" title="Non-obvious pattern">
            <Sparkles className="w-3 h-3 text-rose-400" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 leading-relaxed">{entry.headline}</p>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
            {entry.input && entry.output && (
              <span>{entry.input} → {entry.output}</span>
            )}
            {entry.times_confirmed != null && (
              <span>confirmed {entry.times_confirmed}x</span>
            )}
            {entry.last_confirmed && (
              <span>last seen {daysSince(entry.last_confirmed)}</span>
            )}
            {entry.direction_counterintuitive && (
              <span className="text-rose-400">non-obvious</span>
            )}
          </div>

          {entry.threshold && (
            <div className="mt-2 text-xs text-blue-400/80 bg-blue-500/5 rounded-lg px-3 py-2">
              {entry.threshold.label}
            </div>
          )}

          {entry.asymmetry && entry.asymmetry.ratio < 0.5 && (
            <div className="mt-2 text-xs text-purple-400/80 bg-purple-500/5 rounded-lg px-3 py-2">
              {entry.asymmetry.label}
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
              {entry.timing && (
                <div>
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Timing</span>
                  <p className="mt-0.5">
                    {entry.timing.half_life_days != null &&
                      `Effect half-life: ${entry.timing.half_life_days} days`}
                    {entry.timing.lag_days != null && entry.timing.half_life_days != null && ' · '}
                    {entry.timing.lag_days != null &&
                      `Delayed by ${entry.timing.lag_days} day${entry.timing.lag_days !== 1 ? 's' : ''}`}
                  </p>
                </div>
              )}
              {entry.asymmetry && (
                <div>
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Asymmetry</span>
                  <p className="mt-0.5">{entry.asymmetry.label}</p>
                </div>
              )}
            </div>
          )}

          <div className="mt-2 flex justify-end">
            <Link
              href={`/coach?q=${encodeURIComponent(coachQuestion)}`}
              className="flex items-center gap-1 text-xs text-orange-500/60 hover:text-orange-400 transition-colors"
            >
              <MessageSquare className="w-3 h-3" /> Ask coach
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── What Changed ────────────────────────────────────────────────────────

function WhatsChangedSection({ entries, lastVisit }: {
  entries: ManualEntry[];
  lastVisit: string | null;
}) {
  const newFindings = useMemo(() => {
    if (!lastVisit) return [];
    return entries.filter((e) => {
      const detected = e.first_detected;
      return detected && detected > lastVisit;
    });
  }, [entries, lastVisit]);

  if (!lastVisit || newFindings.length === 0) return null;

  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center">
          <Clock className="w-4 h-4 text-green-400" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">
            What&apos;s new
          </h2>
          <p className="text-xs text-slate-500">
            {newFindings.length} finding{newFindings.length !== 1 ? 's' : ''} since your last visit
          </p>
        </div>
      </div>
      <div className="space-y-1">
        {newFindings.slice(0, 8).map((e) => (
          <div key={e.id} className="flex items-center gap-3 text-sm text-slate-300 bg-green-500/5 rounded-lg px-4 py-2.5 border border-green-500/10">
            <Sparkles className="w-3 h-3 text-green-400 flex-shrink-0" />
            <span className="flex-1">{e.headline}</span>
            <span className="text-xs text-slate-500 flex-shrink-0">{daysSince(e.first_detected)}</span>
          </div>
        ))}
        {newFindings.length > 8 && (
          <p className="text-xs text-slate-500 pl-4 pt-1">
            and {newFindings.length - 8} more
          </p>
        )}
      </div>
    </section>
  );
}

// ─── Full Record (V1 sections, collapsed) ────────────────────────────────

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

function RecordEntryCard({ entry, domainColor }: { entry: ManualEntry; domainColor: string }) {
  const [expanded, setExpanded] = useState(false);
  const isCorrelation = entry.source === 'correlation';
  const hasDetails = !!(entry.threshold || entry.asymmetry || entry.timing || entry.cascade);

  return (
    <div className="group border-l-2 pl-5 py-3" style={{ borderColor: domainColor + '40' }}>
      <div className="flex items-start gap-3">
        {isCorrelation && (
          <ConfidenceArc tier={entry.confidence_tier} confirmed={entry.times_confirmed} />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-300 leading-relaxed">{entry.headline}</p>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-xs text-slate-600">
            {isCorrelation && entry.input && entry.output && (
              <span>{entry.input} → {entry.output}</span>
            )}
            {entry.r != null && <span>r = {entry.r.toFixed(2)}</span>}
            {entry.last_confirmed && <span>last seen {daysSince(entry.last_confirmed)}</span>}
          </div>

          {hasDetails && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {expanded ? 'Less' : 'Details'}
            </button>
          )}

          {expanded && (
            <div className="mt-2 space-y-2 text-xs text-slate-400 bg-slate-900/60 rounded-lg px-4 py-3">
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
                  <span className="text-slate-500 uppercase tracking-wider text-[10px]">Cascade</span>
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
  const [open, setOpen] = useState(false);
  const color = DOMAIN_COLORS[section.domain] || '#94a3b8';
  const icon = DOMAIN_ICONS[section.domain] || <Activity className="w-5 h-5" />;

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 py-2.5 px-1 group"
      >
        <span style={{ color }}>{icon}</span>
        <span className="text-sm font-medium text-slate-300 flex-1 text-left">{section.label}</span>
        <span className="text-xs text-slate-600 mr-2">{section.entry_count}</span>
        {open
          ? <ChevronDown className="w-4 h-4 text-slate-600" />
          : <ChevronRight className="w-4 h-4 text-slate-600" />
        }
      </button>
      {open && (
        <div className="ml-2 mb-4">
          {section.description && (
            <p className="text-xs text-slate-500 mb-3 ml-8">{section.description}</p>
          )}
          {section.entries.map((entry) => (
            <RecordEntryCard key={entry.id} entry={entry} domainColor={color} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────

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
        <Link href="/home" className="text-orange-400 hover:text-orange-300 transition-colors">
          Back to Home
        </Link>
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────

export default function ManualPage() {
  const { data, isLoading, error } = useOperatingManual();
  const [lastVisit, setLastVisit] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) setLastVisit(stored);
      localStorage.setItem(STORAGE_KEY, new Date().toISOString());
    } catch { /* SSR / private browsing */ }
  }, []);

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

  const { summary, race_character, cascade_stories, highlighted_findings, sections } = data;
  const isEmpty = sections.length === 0 && !race_character && cascade_stories.length === 0;

  const allEntries = sections.flatMap((s) => s.entries);

  const learningSince = summary.learning_since ? formatDate(summary.learning_since) : null;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[#0d1321] text-slate-100">
        <div className="max-w-[780px] mx-auto px-6 py-10">

          {/* Header */}
          <header className="mb-10">
            <h1 className="text-2xl font-bold text-white mb-2">
              Personal Operating Manual
            </h1>
            <p className="text-sm text-slate-400 leading-relaxed max-w-lg">
              What the system understands about how your body works.
              {learningSince && <> Learning since {learningSince}.</>}
            </p>
          </header>

          {isEmpty ? (
            <EmptyManual />
          ) : (
            <>
              {/* Summary strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
                <SummaryStat label="Confirmed" value={summary.confirmed_findings} accent="#3b82f6" />
                <SummaryStat label="Strong" value={summary.strong_findings} accent="#22c55e" />
                <SummaryStat label="Stories" value={summary.cascade_story_count ?? cascade_stories.length} accent="#818cf8" />
                <SummaryStat label="Domains" value={summary.domains_covered} accent="#a78bfa" />
              </div>

              {/* 1. Race Character */}
              {race_character && <RaceCharacterSection data={race_character} />}

              {/* 2. Cascade Stories */}
              {cascade_stories.length > 0 && (
                <section className="mb-10">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center">
                      <GitBranch className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-white">How your body connects</h2>
                      <p className="text-xs text-slate-500">
                        Multi-step chains — how a signal propagates through your physiology
                      </p>
                    </div>
                  </div>
                  {cascade_stories.map((story) => (
                    <CascadeStoryCard key={story.id} story={story} />
                  ))}
                </section>
              )}

              {/* 3. What Changed */}
              <WhatsChangedSection entries={allEntries} lastVisit={lastVisit} />

              {/* 4. Highlighted Findings */}
              {highlighted_findings.length > 0 && (
                <section className="mb-10">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center">
                      <Sparkles className="w-4 h-4 text-blue-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-white">Notable patterns</h2>
                      <p className="text-xs text-slate-500">
                        Ranked by insight, not frequency — thresholds, non-obvious patterns, timing
                      </p>
                    </div>
                  </div>
                  {highlighted_findings.map((entry) => (
                    <HighlightedFindingCard key={entry.id} entry={entry} />
                  ))}
                </section>
              )}

              {/* 5. Full Record */}
              <section className="mb-10">
                <div className="flex items-center gap-3 mb-3">
                  <h2 className="text-sm font-semibold text-slate-400">Full record</h2>
                  <span className="text-xs text-slate-600">
                    {summary.total_entries} entries across {summary.domains_covered} domains
                  </span>
                </div>
                <div className="rounded-xl border border-slate-800/50 bg-[#0d1321]/50 px-4 py-2">
                  {sections.map((section) => (
                    <DomainSection key={section.domain} section={section} />
                  ))}
                </div>
              </section>

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
