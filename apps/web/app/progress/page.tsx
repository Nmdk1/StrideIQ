'use client';

import React from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useProgressKnowledge } from '@/lib/hooks/queries/progress';
import { ProgressHero } from '@/components/progress/ProgressHero';
import { RecoveryFingerprint } from '@/components/progress/RecoveryFingerprint';
import FindingCard from '@/components/findings/FindingCard';

type DomainGroup = {
  key: string;
  label: string;
  totalConfirmations: number;
  findings: Array<{
    id: string;
    text: string;
    evidence: string;
    implication: string;
    confidenceTier: string;
    domain: string;
    timesConfirmed: number;
  }>;
};

function metricToDomain(metric: string): string {
  const m = metric.toLowerCase();
  if (m.includes('sleep') || m.includes('readiness') || m.includes('hrv')) return 'sleep_recovery';
  if (m.includes('hr') || m.includes('heart') || m.includes('cardiac')) return 'cardiac';
  if (m.includes('pace') || m.includes('efficiency') || m.includes('speed')) return 'pace';
  if (m.includes('temp') || m.includes('weather') || m.includes('heat') || m.includes('dew')) return 'environmental';
  if (m.includes('distance') || m.includes('volume') || m.includes('load') || m.includes('miles')) return 'volume';
  return 'general';
}

function domainLabel(key: string): string {
  if (key === 'sleep_recovery') return 'Sleep and recovery';
  if (key === 'cardiac') return 'Cardiac';
  if (key === 'pace') return 'Pace efficiency';
  if (key === 'environmental') return 'Environmental';
  if (key === 'volume') return 'Volume and load';
  return 'General patterns';
}

function groupFindings(
  provedFacts: Array<{
    input_metric: string;
    output_metric: string;
    headline: string;
    evidence: string;
    implication: string;
    confidence_tier: string;
    times_confirmed: number;
  }>
): DomainGroup[] {
  const bucket = new Map<string, DomainGroup>();
  for (const fact of provedFacts) {
    const domain = metricToDomain(`${fact.input_metric} ${fact.output_metric}`);
    const existing = bucket.get(domain) ?? {
      key: domain,
      label: domainLabel(domain),
      totalConfirmations: 0,
      findings: [],
    };
    existing.findings.push({
      id: `${fact.input_metric}-${fact.output_metric}-${fact.times_confirmed}`,
      text: fact.headline,
      evidence: fact.evidence,
      implication: fact.implication,
      confidenceTier: fact.confidence_tier,
      domain,
      timesConfirmed: fact.times_confirmed,
    });
    existing.totalConfirmations += fact.times_confirmed;
    bucket.set(domain, existing);
  }

  return [...bucket.values()]
    .map((group) => ({
      ...group,
      findings: group.findings.sort((a, b) => b.timesConfirmed - a.timesConfirmed),
    }))
    .sort((a, b) => b.totalConfirmations - a.totalConfirmations);
}

export default function ProgressPage() {
  const { data, isLoading, error } = useProgressKnowledge();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-[#0d1321] text-white">
          <div className="max-w-[920px] mx-auto px-6 py-14 space-y-5">
            <div className="h-[200px] rounded-2xl bg-white/5 animate-pulse" />
            <div className="h-[340px] rounded-2xl bg-white/5 animate-pulse" />
            <div className="h-[280px] rounded-2xl bg-white/5 animate-pulse" />
            <p className="text-center text-xs text-slate-500">Loading your progress patterns...</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-[#0d1321] text-white flex items-center justify-center">
          <div className="text-center">
            <p className="text-slate-300">Unable to load your progress knowledge.</p>
            <p className="text-xs text-slate-500 mt-1">Try refreshing the page.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const { hero, proved_facts, patterns_forming, recovery_curve, data_coverage } = data;
  const grouped = groupFindings(proved_facts);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[#0d1321] text-white">
        {/* Hero */}
        <ProgressHero
          dateLabel={hero.date_label}
          headline={hero.headline}
          headlineAccent={hero.headline_accent}
          subtext={hero.subtext}
          stats={hero.stats}
        />

        <div className="max-w-[920px] mx-auto px-6 pb-20 pt-7 space-y-5">
          {grouped.length > 0 ? (
            grouped.map((group) => (
              <section key={group.key} className="rounded-2xl border border-slate-700/50 bg-[#141c2e] p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-slate-200">{group.label}</h3>
                  <span className="text-xs text-slate-500">{group.totalConfirmations} confirmations</span>
                </div>
                <div className="space-y-3">
                  {group.findings.map((finding) => (
                    <FindingCard
                      key={finding.id}
                      text={finding.text}
                      domain={finding.domain}
                      confidenceTier={finding.confidenceTier}
                      timesConfirmed={finding.timesConfirmed}
                      evidence={finding.evidence}
                      implication={finding.implication}
                      expandable
                    />
                  ))}
                </div>
              </section>
            ))
          ) : (
            <section className="rounded-2xl border border-slate-700/50 bg-[#141c2e] p-5 space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Patterns building</h3>
              {patterns_forming ? (
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden flex-1">
                      <div
                        className="h-full bg-orange-500 rounded-full transition-all duration-700"
                        style={{ width: `${patterns_forming.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500 whitespace-nowrap">
                      {patterns_forming.checkin_count}/{patterns_forming.checkins_needed}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400">{patterns_forming.message}</p>
                </div>
              ) : (
                <FindingCard expandable={false} activityCount={data_coverage.checkin_count} />
              )}
            </section>
          )}

          {recovery_curve ? (
            <section className="rounded-2xl border border-slate-700/50 bg-[#141c2e] p-5">
              <RecoveryFingerprint data={recovery_curve} />
            </section>
          ) : null}

          <div className="text-center pt-3">
            <Link
              href="/coach?q=Walk%20me%20through%20my%20progress%20in%20detail"
              className="inline-flex items-center rounded-lg bg-[#c2650a] hover:bg-[#d0731d] text-white text-sm font-semibold px-7 py-2.5 transition-colors"
            >
              Ask Coach About Your Progress
            </Link>
          </div>

          <div className="rounded-xl border border-slate-700/40 bg-slate-900/35 px-4 py-2.5 flex justify-center gap-4 text-[11px] text-slate-500">
            <span>{data_coverage.total_findings} patterns</span>
            <span>{data_coverage.confirmed_findings} confirmed</span>
            <span>{data_coverage.checkin_count} check-ins</span>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
