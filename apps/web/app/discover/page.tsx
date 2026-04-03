'use client';

/**
 * First-Session Discovery
 *
 * The aha moment: the first time the system tells the athlete
 * something true about their body that they didn't know.
 *
 * Shown after backfill completes. Polls until insights are ready.
 * Once seen, the athlete can navigate to /manual for the full picture
 * or /home for the daily experience.
 */

import React, { useEffect } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useFirstInsights, TopCorrelation, TopInvestigation } from '@/lib/hooks/queries/first-insights';
import {
  Sparkles,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Activity,
  BookOpen,
} from 'lucide-react';

const DISMISSED_KEY = 'strideiq_first_insights_seen';

function formatSpan(days: number): string {
  if (days < 30) return `${days} days`;
  if (days < 365) return `${Math.floor(days / 30)} months`;
  const years = (days / 365).toFixed(1);
  return `${years} years`;
}

function InsightReveal({ correlation, index }: { correlation: TopCorrelation; index: number }) {
  const isPositive = correlation.direction === 'positive';

  return (
    <div
      className="rounded-xl border border-slate-700/40 bg-[#141c2e] p-5 transition-all"
      style={{
        animationDelay: `${(index + 1) * 400}ms`,
        animation: 'fadeSlideIn 0.6s ease-out forwards',
        opacity: 0,
      }}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex-shrink-0">
          {isPositive ? (
            <TrendingUp className="w-5 h-5 text-emerald-400" />
          ) : (
            <TrendingDown className="w-5 h-5 text-amber-400" />
          )}
        </div>
        <div>
          <p className="text-sm text-slate-200 leading-relaxed">{correlation.headline}</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-slate-500">
            <span>{correlation.input} → {correlation.output}</span>
            <span>confirmed {correlation.times_confirmed}x</span>
            {correlation.strength === 'strong' && (
              <span className="text-emerald-500">strong</span>
            )}
          </div>
          {(correlation.threshold_label || correlation.asymmetry_label) && (
            <p className="mt-2 text-xs text-slate-500">
              {[correlation.threshold_label, correlation.asymmetry_label]
                .filter(Boolean)
                .join(' · ')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function InvestigationReveal({ finding, index }: { finding: TopInvestigation; index: number }) {
  return (
    <div
      className="rounded-xl border border-slate-700/40 bg-[#141c2e] p-5 transition-all"
      style={{
        animationDelay: `${(index + 4) * 400}ms`,
        animation: 'fadeSlideIn 0.6s ease-out forwards',
        opacity: 0,
      }}
    >
      <div className="flex items-start gap-3">
        <Activity className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-slate-200 leading-relaxed">{finding.headline}</p>
      </div>
    </div>
  );
}

function AnalyzingState() {
  return (
    <div className="text-center py-20">
      <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-slate-800 flex items-center justify-center">
        <Sparkles className="w-8 h-8 text-orange-400 animate-pulse" />
      </div>
      <h2 className="text-xl font-semibold text-slate-200 mb-3">
        Analyzing your history
      </h2>
      <p className="text-sm text-slate-400 max-w-sm mx-auto leading-relaxed mb-8">
        The system is reading your training data and looking for patterns
        unique to your body. This usually takes a minute or two.
      </p>
      <LoadingSpinner size="sm" />
    </div>
  );
}

export default function DiscoverPage() {
  const { data, isLoading } = useFirstInsights();

  useEffect(() => {
    if (data?.ready) {
      localStorage.setItem(DISMISSED_KEY, '1');
    }
  }, [data?.ready]);

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-[#0d1321]">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  const ready = data?.ready;

  return (
    <ProtectedRoute>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div className="min-h-screen bg-[#0d1321] text-slate-100">
        <div className="max-w-[640px] mx-auto px-6 py-12">

          {!ready ? (
            <AnalyzingState />
          ) : (
            <>
              {/* Header */}
              <header
                className="mb-10"
                style={{ animation: 'fadeSlideIn 0.6s ease-out forwards' }}
              >
                <p className="text-xs uppercase tracking-widest text-orange-400/80 mb-3">
                  First look
                </p>
                <h1 className="text-2xl font-bold text-white mb-3">
                  We analyzed {data.activity_count?.toLocaleString()} activities
                  {data.history_span_days && data.history_span_days > 30
                    ? ` across ${formatSpan(data.history_span_days)}`
                    : ''
                  }
                </h1>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Here&apos;s what the system found about how your body works.
                  {data.correlation_count && data.correlation_count > 3
                    ? ` ${data.correlation_count} patterns detected so far — these are the strongest.`
                    : ''
                  }
                </p>
              </header>

              {/* Findings */}
              <div className="space-y-4 mb-12">
                {data.top_correlations?.map((c, i) => (
                  <InsightReveal key={i} correlation={c} index={i} />
                ))}
                {data.top_investigations?.map((f, i) => (
                  <InvestigationReveal key={`inv-${i}`} finding={f} index={i} />
                ))}
              </div>

              {/* Actions */}
              <div
                className="space-y-3"
                style={{
                  animationDelay: '2.4s',
                  animation: 'fadeSlideIn 0.6s ease-out forwards',
                  opacity: 0,
                }}
              >
                <Link
                  href="/manual"
                  className="flex items-center justify-between w-full rounded-xl border border-slate-700/40 bg-[#141c2e] hover:bg-[#1a2540] px-5 py-4 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <BookOpen className="w-5 h-5 text-slate-400 group-hover:text-slate-200 transition-colors" />
                    <div>
                      <p className="text-sm font-medium text-slate-200">Your Operating Manual</p>
                      <p className="text-xs text-slate-500">Every confirmed pattern, organized by domain</p>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
                </Link>

                <Link
                  href="/home"
                  className="flex items-center justify-center gap-2 w-full rounded-xl px-5 py-3 text-sm text-slate-400 hover:text-slate-200 transition-colors"
                >
                  Go to Home
                </Link>
              </div>

              {/* Footnote */}
              <p className="text-center text-xs text-slate-600 mt-12">
                These patterns strengthen with continued use. New findings appear as the system learns more.
              </p>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
