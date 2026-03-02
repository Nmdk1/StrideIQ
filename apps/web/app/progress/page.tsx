'use client';

/**
 * Progress Page — Spec V1: Visual-First Progress Narrative
 *
 * Five acts flowing as one continuous scroll:
 *   Act 1: The Verdict (fitness arc sparkline + coach voice)
 *   Act 2: Progress Chapters (visual + narrative per topic)
 *   Act 3: What Your Data Has Learned About You (N=1 patterns)
 *   Act 4: Looking Ahead (race readiness or capability trajectory)
 *   Act 5: Athlete Controls (feedback footer)
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import {
  useProgressNarrative,
  useNarrativeFeedback,
  type NarrativeChapter,
} from '@/lib/hooks/queries/progress';
import {
  SparklineChart,
  BarChart,
  HealthStrip,
  FormGauge,
  PairedSparkline,
  CapabilityBars,
  CompletionRing,
  StatHighlight,
} from '@/components/progress';
import {
  TrendingUp,
  Sparkles,
  MessageCircle,
  ThumbsUp,
  AlertCircle,
  ArrowRight,
  Target,
  Zap,
} from 'lucide-react';

function ChapterVisual({ chapter }: { chapter: NarrativeChapter }) {
  const vd = chapter.visual_data;

  switch (chapter.visual_type) {
    case 'bar_chart':
      return (
        <BarChart
          labels={(vd.labels as string[]) || []}
          values={(vd.values as number[]) || []}
          highlightIndex={vd.highlight_index as number | undefined}
          unit={(vd.unit as string) || 'mi'}
        />
      );

    case 'sparkline':
      return (
        <SparklineChart
          data={(vd.values as number[]) || []}
          direction={(vd.direction as 'rising' | 'stable' | 'declining') || 'stable'}
          currentValue={vd.current as number | undefined}
        />
      );

    case 'health_strip':
      return (
        <HealthStrip
          indicators={
            (vd.indicators as Array<{ label: string; value: string; status: 'green' | 'amber' | 'red'; trend?: 'up' | 'down' | 'stable' }>) || []
          }
        />
      );

    case 'gauge':
      return (
        <FormGauge
          value={(vd.value as number) || 0}
          zoneLabel={(vd.zone_label as string) || ''}
          zones={(vd.zones as string[]) || undefined}
        />
      );

    case 'completion_ring':
      return (
        <div className="flex justify-center py-2">
          <CompletionRing pct={(vd.pct as number) || 0} />
        </div>
      );

    case 'stat_highlight':
      return (
        <StatHighlight
          distance={(vd.distance as string) || ''}
          time={(vd.time as string) || ''}
          dateAchieved={(vd.date_achieved as string) || undefined}
        />
      );

    default:
      return null;
  }
}

export default function ProgressPage() {
  const { data, isLoading, error } = useProgressNarrative();
  const feedbackMutation = useNarrativeFeedback();
  const [feedbackSent, setFeedbackSent] = useState(false);

  const sendFeedback = (type: string, detail?: string) => {
    if (feedbackSent) return;
    feedbackMutation.mutate({ feedback_type: type, feedback_detail: detail });
    setFeedbackSent(true);
  };

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 text-slate-100">
          <div className="max-w-2xl mx-auto px-4 py-12">
            {/* Skeleton: visual-first loading */}
            <div className="space-y-8 animate-pulse">
              <div className="h-12 bg-slate-800/50 rounded-lg" />
              <div className="h-16 bg-slate-800/50 rounded-lg" />
              <div className="space-y-4">
                <div className="h-32 bg-slate-800/50 rounded-lg" />
                <div className="h-8 bg-slate-800/40 rounded-lg w-3/4" />
                <div className="h-6 bg-slate-800/30 rounded-lg w-1/2" />
              </div>
              <div className="h-24 bg-slate-800/50 rounded-lg" />
            </div>
            <p className="text-center text-sm text-slate-500 mt-6">Building your progress report...</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (error || !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center">
          <div className="text-center">
            <p className="text-slate-400">Unable to load your progress report.</p>
            <p className="text-sm text-slate-500 mt-1">Try refreshing the page.</p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const { verdict, chapters, personal_patterns, patterns_forming, looking_ahead, athlete_controls, data_coverage } = data;

  // Minimal data state
  const isMinimalData = data_coverage.activity_days < 7;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-2xl mx-auto px-4 py-6 pb-24 md:pb-8 space-y-10">

          {/* ═══ ACT 1: THE VERDICT ═══ */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="w-5 h-5 text-orange-500" />
              <h1 className="text-lg font-bold text-white">Your Progress</h1>
            </div>

            {/* Sparkline visual */}
            {verdict.sparkline_data.length > 0 && (
              <div className="mb-4">
                <SparklineChart
                  data={verdict.sparkline_data}
                  direction={verdict.sparkline_direction as 'rising' | 'stable' | 'declining'}
                  currentValue={verdict.current_value}
                  height={56}
                />
              </div>
            )}

            {/* Verdict narrative */}
            <div className="bg-gradient-to-br from-orange-500/8 via-slate-800/60 to-slate-800/40 border border-orange-500/15 rounded-xl p-5">
              <p className="text-base text-slate-200 leading-relaxed font-medium">
                {verdict.text}
              </p>
              {verdict.grounding.length > 0 && (
                <p className="text-xs text-slate-500 mt-2">
                  {verdict.grounding.join(' · ')}
                </p>
              )}
            </div>

            {isMinimalData && (
              <div className="mt-4 bg-slate-800/40 border border-slate-700/40 rounded-lg p-4 text-center">
                <p className="text-sm text-slate-300">Your progress story is just beginning.</p>
                <p className="text-xs text-slate-500 mt-1">
                  Run a few more times, do your daily check-ins, and we&apos;ll start telling it.
                </p>
              </div>
            )}
          </section>

          {/* ═══ ACT 2: PROGRESS CHAPTERS ═══ */}
          {chapters.length > 0 && (
            <section className="space-y-8">
              {chapters.map((chapter, i) => (
                <article key={`${chapter.topic}-${i}`} className="space-y-3">
                  {/* Visual anchor */}
                  <ChapterVisual chapter={chapter} />

                  {/* Narrative bridge */}
                  <div className="space-y-2">
                    <h2 className="text-sm font-semibold text-white">{chapter.title}</h2>

                    {chapter.observation && (
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {chapter.observation}
                      </p>
                    )}

                    {chapter.evidence && (
                      <p className="text-xs text-slate-500 font-mono">
                        {chapter.evidence}
                      </p>
                    )}

                    {chapter.interpretation && (
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {chapter.interpretation}
                      </p>
                    )}

                    {chapter.action && (
                      <p className="text-sm text-orange-400 font-medium">
                        {chapter.action}
                      </p>
                    )}
                  </div>
                </article>
              ))}
            </section>
          )}

          {/* ═══ ACT 3: WHAT YOUR DATA HAS LEARNED ABOUT YOU ═══ */}
          {(personal_patterns.length > 0 || patterns_forming) && (
            <section className="space-y-4">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-white">What Your Data Has Learned About You</h2>
              </div>

              {personal_patterns.map((pattern, i) => (
                <div key={i} className="space-y-3">
                  {/* Paired sparkline visual */}
                  {pattern.visual_data.input_series?.length > 0 && (
                    <PairedSparkline
                      inputSeries={pattern.visual_data.input_series}
                      outputSeries={pattern.visual_data.output_series}
                      inputLabel={pattern.visual_data.input_label}
                      outputLabel={pattern.visual_data.output_label}
                    />
                  )}

                  {/* N=1 callout */}
                  <div className="bg-slate-800/40 border border-amber-500/15 rounded-lg p-4">
                    <div className="flex items-start gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-sm text-slate-200 leading-relaxed">
                          {pattern.narrative}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            pattern.confidence === 'strong'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : pattern.confidence === 'confirmed'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-slate-600/30 text-slate-400'
                          }`}>
                            {pattern.confidence === 'strong' ? 'Strong signal' :
                             pattern.confidence === 'confirmed' ? 'Becoming reliable' :
                             'Early signal'}
                          </span>
                          <span className="text-xs text-slate-500">
                            Confirmed {pattern.times_confirmed}×
                          </span>
                        </div>
                        {pattern.current_relevance && (
                          <p className="text-xs text-slate-400 mt-1.5">{pattern.current_relevance}</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {/* Patterns forming */}
              {patterns_forming && personal_patterns.length === 0 && (
                <div className="bg-slate-800/40 border border-slate-700/40 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-orange-400" />
                    <span className="text-xs font-semibold text-slate-300">N=1 Patterns</span>
                  </div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-orange-500 rounded-full transition-all"
                        style={{ width: `${patterns_forming.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500 whitespace-nowrap">
                      {patterns_forming.checkin_count}/{patterns_forming.checkins_needed}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{patterns_forming.message}</p>
                </div>
              )}
            </section>
          )}

          {/* ═══ ACT 4: LOOKING AHEAD ═══ */}
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold text-white">Looking Ahead</h2>
            </div>

            {looking_ahead.variant === 'race' && looking_ahead.race && (
              <div className="space-y-4">
                {/* Readiness gauge */}
                <div className="flex items-center justify-center">
                  <FormGauge
                    value={looking_ahead.race.readiness_score}
                    zoneLabel={looking_ahead.race.readiness_label}
                    zones={looking_ahead.race.gauge_zones}
                  />
                </div>

                {/* Race header */}
                <div className="text-center">
                  <p className="text-base font-bold text-white">{looking_ahead.race.race_name}</p>
                  <p className="text-sm text-purple-400 font-medium">{looking_ahead.race.days_remaining} days</p>
                </div>

                {/* Scenarios */}
                {looking_ahead.race.scenarios.map((s, i) => (
                  <div key={i} className="bg-slate-800/40 border border-slate-700/40 rounded-lg p-4">
                    <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">{s.label}</p>
                    <p className="text-sm text-slate-200 leading-relaxed">{s.narrative}</p>
                    {s.estimated_finish && (
                      <p className="text-sm text-white font-bold mt-1">Est. finish: {s.estimated_finish}</p>
                    )}
                    {s.key_action && (
                      <p className="text-sm text-orange-400 font-medium mt-1">{s.key_action}</p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {looking_ahead.variant === 'trajectory' && looking_ahead.trajectory && (
              <div className="space-y-4">
                {/* Capability bars */}
                {looking_ahead.trajectory.capabilities.length > 0 && (
                  <div>
                    <p className="text-xs text-slate-500 mb-3">Where your fitness is pointing</p>
                    <CapabilityBars capabilities={looking_ahead.trajectory.capabilities} />
                  </div>
                )}

                {/* Trajectory narrative */}
                {looking_ahead.trajectory.narrative && (
                  <div className="bg-slate-800/40 border border-slate-700/40 rounded-lg p-4">
                    <p className="text-sm text-slate-200 leading-relaxed">{looking_ahead.trajectory.narrative}</p>
                    {looking_ahead.trajectory.trend_driver && (
                      <p className="text-xs text-slate-400 mt-2">{looking_ahead.trajectory.trend_driver}</p>
                    )}
                    {looking_ahead.trajectory.milestone_hint && (
                      <p className="text-sm text-orange-400 font-medium mt-2">{looking_ahead.trajectory.milestone_hint}</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* ═══ ACT 5: ATHLETE CONTROLS ═══ */}
          <section className="border-t border-slate-800 pt-6">
            <p className="text-xs text-slate-500 text-center mb-3">How does this feel?</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => sendFeedback('positive')}
                disabled={feedbackSent}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  feedbackSent
                    ? 'bg-emerald-500/20 text-emerald-400 cursor-default'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
                }`}
              >
                <ThumbsUp className="w-3.5 h-3.5" />
                This feels right
              </button>

              <button
                onClick={() => sendFeedback('negative')}
                disabled={feedbackSent}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 transition-colors disabled:opacity-50"
              >
                <AlertCircle className="w-3.5 h-3.5" />
                Something&apos;s off
              </button>

              <Link
                href={`/coach?q=${encodeURIComponent(athlete_controls.coach_query)}`}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-orange-600/20 text-orange-400 hover:bg-orange-600/30 border border-orange-500/20 transition-colors"
              >
                <MessageCircle className="w-3.5 h-3.5" />
                Ask Coach
              </Link>
            </div>

            {feedbackSent && (
              <p className="text-xs text-emerald-400 text-center mt-2">Thanks — logged for calibration.</p>
            )}

            {/* Data coverage */}
            <div className="flex items-center justify-center gap-4 mt-4 text-xs text-slate-600">
              <span>{data_coverage.activity_days} activities</span>
              <span>·</span>
              <span>{data_coverage.checkin_days} check-ins</span>
              {data_coverage.correlation_findings > 0 && (
                <>
                  <span>·</span>
                  <span>{data_coverage.correlation_findings} patterns</span>
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </ProtectedRoute>
  );
}
