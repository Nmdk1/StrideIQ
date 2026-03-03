'use client';

import React from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useProgressKnowledge } from '@/lib/hooks/queries/progress';
import { ProgressHero } from '@/components/progress/ProgressHero';
import { CorrelationWeb } from '@/components/progress/CorrelationWeb';
import { WhatDataProved } from '@/components/progress/WhatDataProved';
import { RecoveryFingerprint } from '@/components/progress/RecoveryFingerprint';

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

function Card({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
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

export default function ProgressPage() {
  const { data, isLoading, error } = useProgressKnowledge();

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
              <div
                style={{
                  height: 200,
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: 16,
                  animation: 'pulse 1.5s ease-in-out infinite',
                }}
              />
              <div
                style={{
                  height: 340,
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: 16,
                  animation: 'pulse 1.5s ease-in-out infinite',
                  animationDelay: '0.2s',
                }}
              />
              <div
                style={{
                  height: 280,
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: 16,
                  animation: 'pulse 1.5s ease-in-out infinite',
                  animationDelay: '0.4s',
                }}
              />
            </div>
            <p style={{ textAlign: 'center', fontSize: 13, color: C.t40, marginTop: 24 }}>
              Loading your knowledge graph...
            </p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
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
            <p style={{ color: C.t60 }}>Unable to load your progress knowledge.</p>
            <p style={{ fontSize: 13, color: C.t40, marginTop: 4 }}>Try refreshing the page.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const { hero, correlation_web, proved_facts, patterns_forming, recovery_curve, data_coverage } = data;
  const hasFindings = correlation_web.nodes.length > 0;

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

        {/* Hero */}
        <ProgressHero
          dateLabel={hero.date_label}
          headline={hero.headline}
          headlineAccent={hero.headline_accent}
          subtext={hero.subtext}
          stats={hero.stats}
        />

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
          {/* Correlation Web */}
          {hasFindings ? (
            <Card>
              <CorrelationWeb nodes={correlation_web.nodes} edges={correlation_web.edges} />
            </Card>
          ) : patterns_forming ? (
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
                      width: `${patterns_forming.progress_pct}%`,
                      height: '100%',
                      background: C.orange,
                      borderRadius: 3,
                      transition: 'width 1s ease',
                    }}
                  />
                </div>
                <span style={{ fontSize: 12, color: C.t40, whiteSpace: 'nowrap' }}>
                  {patterns_forming.checkin_count}/{patterns_forming.checkins_needed}
                </span>
              </div>
              <p style={{ fontSize: 13, color: C.t60, lineHeight: 1.65 }}>{patterns_forming.message}</p>
            </Card>
          ) : null}

          {/* What the Data Proved */}
          {proved_facts.length > 0 && (
            <Card>
              <WhatDataProved facts={proved_facts} />
            </Card>
          )}

          {/* Recovery Fingerprint */}
          {recovery_curve && (
            <Card>
              <RecoveryFingerprint data={recovery_curve} />
            </Card>
          )}

          {/* Ask Coach CTA */}
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

          {/* Data coverage footer */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              gap: 16,
              fontSize: 11,
              color: C.t25,
              paddingTop: 8,
            }}
          >
            <span>{data_coverage.total_findings} patterns</span>
            <span>·</span>
            <span>{data_coverage.confirmed_findings} confirmed</span>
            <span>·</span>
            <span>{data_coverage.checkin_count} check-ins</span>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
