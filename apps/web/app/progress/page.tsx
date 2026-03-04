'use client';

import React from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useProgressKnowledge, useProgressNarrative } from '@/lib/hooks/queries/progress';
import { ProgressHero } from '@/components/progress/ProgressHero';
import { CorrelationWeb } from '@/components/progress/CorrelationWeb';
import { WhatDataProved } from '@/components/progress/WhatDataProved';
import { RecoveryFingerprint } from '@/components/progress/RecoveryFingerprint';
import { VerdictSection } from '@/components/progress/VerdictSection';
import { ChapterCard } from '@/components/progress/ChapterCard';
import { LookingAheadSection } from '@/components/progress/LookingAhead';
import { PairedSparkline } from '@/components/progress/PairedSparkline';

const C = {
  bg: '#0d1321',
  card: '#141c2e',
  border: 'rgba(255,255,255,0.07)',
  oFaint: 'rgba(194,101,10,0.11)',
  oBorder: 'rgba(194,101,10,0.27)',
  orange: '#c2650a',
  oL: '#e07b20',
  green: '#2ab87a',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  t25: 'rgba(255,255,255,0.25)',
  t08: 'rgba(255,255,255,0.08)',
  w: '#fff',
};

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: '26px 28px',
      }}
    >
      {children}
    </div>
  );
}

function SkeletonBlock({ height, delay = 0 }: { height: number; delay?: number }) {
  return (
    <div
      style={{
        height,
        background: 'rgba(255,255,255,0.03)',
        borderRadius: 16,
        animation: 'pulse 1.5s ease-in-out infinite',
        animationDelay: `${delay}s`,
      }}
    />
  );
}

const CONFIDENCE_COLORS: Record<string, string> = {
  emerging: C.t40,
  confirmed: C.orange,
  strong: C.green,
};

export default function ProgressPage() {
  const {
    data: knowledge,
    isLoading: kLoading,
    error: kError,
  } = useProgressKnowledge();

  const {
    data: narrative,
    isLoading: nLoading,
    error: nError,
  } = useProgressNarrative();

  const isLoading = kLoading && nLoading;
  const bothFailed = (kError && nError) || (!kLoading && !nLoading && !knowledge && !narrative);

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div
          style={{
            minHeight: '100vh',
            background: C.bg,
            fontFamily: "-apple-system, 'Segoe UI', sans-serif",
            color: C.w,
          }}
        >
          <div style={{ maxWidth: 900, margin: '0 auto', padding: '60px 24px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <SkeletonBlock height={200} />
              <SkeletonBlock height={120} delay={0.2} />
              <SkeletonBlock height={280} delay={0.3} />
              <SkeletonBlock height={200} delay={0.4} />
            </div>
            <p style={{ textAlign: 'center', fontSize: 13, color: C.t40, marginTop: 24 }}>
              Building your progress story...
            </p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (bothFailed) {
    return (
      <ProtectedRoute>
        <div
          style={{
            minHeight: '100vh',
            background: C.bg,
            fontFamily: "-apple-system, 'Segoe UI', sans-serif",
            color: C.w,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: C.t60 }}>Unable to load your progress data.</p>
            <p style={{ fontSize: 13, color: C.t40, marginTop: 4 }}>Try refreshing the page.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const hero = knowledge?.hero;
  const correlationWeb = knowledge?.correlation_web;
  const provedFacts = knowledge?.proved_facts ?? [];
  const knowledgePatternsForming = knowledge?.patterns_forming;
  const recoveryCurve = knowledge?.recovery_curve;
  const knowledgeCoverage = knowledge?.data_coverage;

  const verdict = narrative?.verdict;
  const chapters = (narrative?.chapters ?? []).filter(
    (ch) => ch.observation || ch.interpretation,
  );
  const personalPatterns = narrative?.personal_patterns ?? [];
  const narrativePatternsForming = narrative?.patterns_forming;
  const lookingAhead = narrative?.looking_ahead;
  const narrativeCoverage = narrative?.data_coverage;

  const hasFindings = (correlationWeb?.nodes?.length ?? 0) > 0;
  const patternsForming = knowledgePatternsForming ?? narrativePatternsForming;

  const activityDays = narrativeCoverage?.activity_days ?? 0;
  const totalFindings = knowledgeCoverage?.total_findings ?? 0;
  const confirmedFindings = knowledgeCoverage?.confirmed_findings ?? 0;
  const checkinCount = knowledgeCoverage?.checkin_count ?? narrativeCoverage?.checkin_days ?? 0;

  return (
    <ProtectedRoute>
      <div
        style={{
          minHeight: '100vh',
          background: C.bg,
          fontFamily: "-apple-system, 'Segoe UI', sans-serif",
          color: C.w,
        }}
      >
        <style>{`
          @keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }
          @keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
        `}</style>

        {/* 1. Hero (from knowledge) */}
        {hero && (
          <ProgressHero
            dateLabel={hero.date_label}
            headline={hero.headline}
            headlineAccent={hero.headline_accent}
            subtext={hero.subtext}
            stats={hero.stats}
          />
        )}

        <div
          style={{
            maxWidth: 900,
            margin: '0 auto',
            padding: '28px 24px 80px',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          {/* 2. Verdict Sparkline (from narrative) */}
          {verdict && (
            <VerdictSection
              sparklineData={verdict.sparkline_data}
              sparklineDirection={verdict.sparkline_direction}
              currentValue={verdict.current_value}
              text={verdict.text}
              grounding={verdict.grounding}
              confidence={verdict.confidence}
            />
          )}

          {/* Loading placeholder if narrative still loading but knowledge rendered */}
          {nLoading && !narrative && (
            <SkeletonBlock height={160} />
          )}

          {/* 3. Chapters (from narrative) */}
          {chapters.map((ch, i) => (
            <ChapterCard
              key={`${ch.topic}-${i}`}
              title={ch.title}
              visualType={ch.visual_type}
              visualData={ch.visual_data}
              observation={ch.observation}
              interpretation={ch.interpretation || undefined}
              action={ch.action || undefined}
            />
          ))}

          {/* 4. Correlation Web (from knowledge) — below chapters */}
          {hasFindings ? (
            <Card>
              <CorrelationWeb nodes={correlationWeb!.nodes} edges={correlationWeb!.edges} />
            </Card>
          ) : patternsForming ? (
            <Card>
              <p
                style={{
                  color: C.t40,
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.16em',
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                N=1 Patterns
              </p>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  marginBottom: 8,
                }}
              >
                <div
                  style={{
                    flex: 1,
                    height: 6,
                    background: C.t08,
                    borderRadius: 3,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${patternsForming.progress_pct}%`,
                      height: '100%',
                      background: C.orange,
                      borderRadius: 3,
                      transition: 'width 1s ease',
                    }}
                  />
                </div>
                <span style={{ fontSize: 12, color: C.t40, whiteSpace: 'nowrap' }}>
                  {patternsForming.checkin_count}/{patternsForming.checkins_needed}
                </span>
              </div>
              <p style={{ fontSize: 13, color: C.t60, lineHeight: 1.65 }}>
                {patternsForming.message}
              </p>
            </Card>
          ) : null}

          {/* 5. What the Data Proved (from knowledge) */}
          {provedFacts.length > 0 && (
            <Card>
              <WhatDataProved facts={provedFacts} />
            </Card>
          )}

          {/* 6. Recovery Fingerprint (from knowledge) */}
          {recoveryCurve && (
            <Card>
              <RecoveryFingerprint data={recoveryCurve} />
            </Card>
          )}

          {/* 7. Personal Patterns (from narrative) */}
          {personalPatterns.length > 0 && (
            <Card>
              <p
                style={{
                  color: C.t40,
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.16em',
                  fontWeight: 600,
                  marginBottom: 16,
                }}
              >
                Personal Patterns
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {personalPatterns.map((pat, i) => (
                  <div key={`pat-${i}`}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: '0.1em',
                          color: CONFIDENCE_COLORS[pat.confidence] ?? C.t40,
                        }}
                      >
                        {pat.confidence}
                      </span>
                      {pat.current_relevance && (
                        <span style={{ fontSize: 11, color: C.t40 }}>
                          · {pat.current_relevance}
                        </span>
                      )}
                    </div>
                    <PairedSparkline
                      inputSeries={pat.visual_data.input_series}
                      outputSeries={pat.visual_data.output_series}
                      inputLabel={pat.visual_data.input_label}
                      outputLabel={pat.visual_data.output_label}
                    />
                    <p style={{ fontSize: 13, color: C.t60, lineHeight: 1.65, marginTop: 10 }}>
                      {pat.narrative}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 8. Looking Ahead (from narrative) */}
          {lookingAhead && (
            <LookingAheadSection data={lookingAhead} />
          )}

          {/* 9. Ask Coach CTA */}
          <div style={{ textAlign: 'center', paddingTop: 12 }}>
            <Link
              href="/coach?q=Walk%20me%20through%20my%20progress%20in%20detail"
              style={{
                display: 'inline-block',
                background: C.orange,
                border: 'none',
                color: '#fff',
                padding: '11px 28px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Ask Coach About Your Progress
            </Link>
          </div>

          {/* 10. Data Coverage Footer (merged) */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              flexWrap: 'wrap',
              gap: 16,
              fontSize: 11,
              color: C.t25,
              paddingTop: 8,
            }}
          >
            {activityDays > 0 && (
              <>
                <span>{activityDays} activities</span>
                <span>·</span>
              </>
            )}
            <span>{totalFindings} patterns</span>
            <span>·</span>
            <span>{confirmedFindings} confirmed</span>
            <span>·</span>
            <span>{checkinCount} check-ins</span>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
