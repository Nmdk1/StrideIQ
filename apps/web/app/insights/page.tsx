'use client';

/**
 * Insights Page - The "Brain View" of Your Training
 * 
 * Proactive, personalized insights that answer "WHY" not just "WHAT".
 * Three sections:
 * 1. Active Insights - Auto-generated, ranked by importance
 * 2. Build Status - Phase-aware KPIs and trajectory (if active plan)
 * 3. Athlete Intelligence - What works for YOU (Elite)
 */

import React, { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { 
  useInsightFeed,
  useActiveInsights, 
  useBuildStatus, 
  useAthleteIntelligence,
  useDismissInsight,
  useSaveInsight,
  useGenerateInsights,
} from '@/lib/hooks/queries/insights';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { InsightActionLink } from '@/components/insights/InsightActionLink';
import type { Insight, KPI, InsightFeedCard } from '@/lib/api/services/insights';
import { useAuth } from '@/lib/context/AuthContext';

// Insight type styling
const INSIGHT_STYLES: Record<string, { bg: string; border: string; icon: string }> = {
  trend_alert: { 
    bg: 'bg-blue-900/30', 
    border: 'border-blue-700/50',
    icon: '📈'
  },
  breakthrough: { 
    bg: 'bg-emerald-900/30', 
    border: 'border-emerald-700/50',
    icon: '✨'
  },
  pattern_detection: { 
    bg: 'bg-orange-900/30', 
    border: 'border-orange-700/50',
    icon: '🔍'
  },
  fatigue_warning: { 
    bg: 'bg-red-900/30', 
    border: 'border-red-700/50',
    icon: '⚠️'
  },
  comparison: { 
    bg: 'bg-purple-900/30', 
    border: 'border-purple-700/50',
    icon: '🔥'
  },
  phase_specific: { 
    bg: 'bg-cyan-900/30', 
    border: 'border-cyan-700/50',
    icon: '💡'
  },
  injury_risk: { 
    bg: 'bg-red-900/40', 
    border: 'border-red-600/60',
    icon: '🛡️'
  },
  achievement: { 
    bg: 'bg-yellow-900/30', 
    border: 'border-yellow-700/50',
    icon: '🏆'
  },
};

function InsightCard({ 
  insight, 
  onDismiss, 
  onSave,
  isPending,
}: { 
  insight: Insight; 
  onDismiss: () => void;
  onSave: () => void;
  isPending: boolean;
}) {
  const [saved, setSaved] = useState(false);
  const style = INSIGHT_STYLES[insight.insight_type] || INSIGHT_STYLES.trend_alert;
  
  const handleSave = () => {
    setSaved(true);
    onSave();
  };
  
  return (
    <div className={`rounded-lg border p-5 ${style.bg} ${style.border} transition-all`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <div className="text-xl mt-0.5">{style.icon}</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-slate-500 uppercase tracking-wide">
                {insight.insight_type.replace(/_/g, ' ')}
              </span>
              {insight.priority >= 80 && (
                <span className="px-1.5 py-0.5 bg-orange-600 text-white text-xs rounded">
                  HIGH
                </span>
              )}
            </div>
            <h3 className="font-semibold text-white mb-2">{insight.title}</h3>
            <p className="text-slate-300 text-sm leading-relaxed">{insight.content}</p>
            
            {/* Data visualization if available */}
            {insight.data && typeof insight.data.change_percent === 'number' && (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-lg">
                  {insight.data.change_percent > 0 ? '↑' : '↓'}
                </span>
                <span className={`text-sm font-medium ${
                  insight.data.change_percent > 0 ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {Math.abs(insight.data.change_percent)}% {insight.data.change_percent > 0 ? 'improvement' : 'decline'}
                </span>
              </div>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-1">
          <button 
            onClick={handleSave}
            disabled={isPending || saved}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors text-lg"
            title="Save to profile"
          >
            {saved ? '⭐' : '☆'}
          </button>
          <button 
            onClick={onDismiss}
            disabled={isPending}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors text-lg"
            title="Dismiss"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfidenceBadge({ card }: { card: InsightFeedCard }) {
  const label = (card.confidence?.label || 'insufficient').toLowerCase();
  const cls =
    label === 'high'
      ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30'
      : label === 'moderate'
        ? 'bg-yellow-600/20 text-yellow-300 border-yellow-500/30'
        : label === 'low'
          ? 'bg-orange-600/20 text-orange-300 border-orange-500/30'
          : 'bg-slate-700/40 text-slate-300 border-slate-600/40';
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${cls}`}>
      {label} confidence
    </span>
  );
}

function FeedSection() {
  const { data, isLoading, error } = useInsightFeed(5);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-10 text-slate-400">
        Unable to load Insights feed right now.
      </div>
    );
  }

  const cards = data?.cards || [];
  if (!cards.length) {
    return (
      <div className="text-center py-10 bg-slate-800/50 rounded-lg border border-slate-700/50">
        <div className="text-5xl mb-4">🧠</div>
        <h3 className="text-lg font-medium text-slate-300 mb-2">No insights yet</h3>
        <p className="text-slate-500 max-w-md mx-auto">
          Sync a few runs (with heart rate if possible) and we’ll start ranking what matters.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span className="text-2xl">⚡</span>
          Top Insights (Ranked)
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          Engine output → evidence → action
        </p>
      </div>

      <div className="space-y-4">
        {cards.map((card) => (
          <div
            key={card.key}
            className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-5"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-slate-500 uppercase tracking-wide">
                    {card.type.replace(/_/g, ' ')}
                  </span>
                  <ConfidenceBadge card={card} />
                </div>
                <h3 className="font-semibold text-white mb-2">{card.title}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{card.summary}</p>

                {card.evidence?.length ? (
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2">
                    {card.evidence.slice(0, 4).map((e, idx) => (
                      <div key={idx} className="bg-slate-900/40 rounded-lg p-3 border border-slate-800">
                        <div className="text-xs text-slate-500">{e.label}</div>
                        <div className="text-sm text-slate-200 mt-0.5">{e.value}</div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="flex flex-col gap-2">
                {(card.actions || []).slice(0, 2).map((a) => (
                  <InsightActionLink
                    key={a.href}
                    href={a.href}
                    label={a.label}
                    variant="default"
                  />
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function KPICard({ kpi }: { kpi: KPI }) {
  const trendColor = kpi.trend === 'up' ? 'text-emerald-400' : kpi.trend === 'down' ? 'text-red-400' : 'text-slate-400';
  const trendIcon = kpi.trend === 'up' ? '↑' : kpi.trend === 'down' ? '↓' : null;
  
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4">
      <div className="text-sm text-slate-400 mb-1">{kpi.name}</div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold text-white">{kpi.current_value || '—'}</span>
        {trendIcon && <span className={`text-lg ${trendColor} mb-1`}>{trendIcon}</span>}
      </div>
      {kpi.start_value && (
        <div className="text-xs text-slate-500 mt-1">
          from {kpi.start_value} at build start
        </div>
      )}
    </div>
  );
}

function ActiveInsightsSection() {
  const { data, isLoading, error } = useActiveInsights(10);
  const dismissMutation = useDismissInsight();
  const saveMutation = useSaveInsight();
  const generateMutation = useGenerateInsights();
  
  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="text-center py-12 text-red-400">
        Error loading insights. Please try again.
      </div>
    );
  }
  
  const hasInsights = data?.insights && data.insights.length > 0;
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="text-2xl">🔥</span>
            Active Insights
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Auto-generated from your recent training
          </p>
        </div>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          className="px-4 py-2 bg-slate-800 border border-slate-700/50 hover:border-slate-600 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          {generateMutation.isPending ? 'Generating...' : 'Refresh'}
        </button>
      </div>
      
      {hasInsights ? (
        <div className="space-y-4">
          {data.insights.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              onDismiss={() => dismissMutation.mutate(insight.id)}
              onSave={() => saveMutation.mutate(insight.id)}
              isPending={dismissMutation.isPending || saveMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-slate-800/50 rounded-lg border border-slate-700/50">
          <div className="text-5xl mb-4">✨</div>
          <h3 className="text-lg font-medium text-slate-300 mb-2">No active insights yet</h3>
          <p className="text-slate-500 max-w-md mx-auto">
            Insights are generated when you sync activities. 
            Keep training and we&apos;ll surface patterns and trends.
          </p>
        </div>
      )}
    </div>
  );
}

function BuildStatusSection() {
  const { data, isLoading } = useBuildStatus();
  
  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }
  
  if (!data?.has_active_plan) {
    return (
      <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-6 text-center">
        <div className="text-4xl mb-3">📊</div>
        <h3 className="text-lg font-medium text-slate-300 mb-2">No active training plan</h3>
        <p className="text-slate-500 text-sm mb-4">
          Start a training plan to see KPIs, trajectory, and phase context.
        </p>
        <a 
          href="/plans" 
          className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
        >
          Browse Plans
        </a>
      </div>
    );
  }
  
  const progressPercent = data.progress_percent || 0;
  
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span className="text-2xl">📊</span>
          Build Status
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          {data.plan_name}
        </p>
      </div>
      
      {/* Progress bar */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700/50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-slate-400">
            Week {data.current_week} of {data.total_weeks}
          </span>
          {data.days_to_race && (
            <span className="text-sm font-medium text-orange-400">
              {data.days_to_race} days to race
            </span>
          )}
        </div>
        <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        {data.current_phase && (
          <div className="mt-2 text-sm">
            <span className="text-slate-500">Phase:</span>{' '}
            <span className="text-white font-medium">{data.current_phase}</span>
          </div>
        )}
      </div>
      
      {/* KPIs */}
      {data.kpis && data.kpis.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {data.kpis.map((kpi, idx) => (
            <KPICard key={idx} kpi={kpi} />
          ))}
        </div>
      )}
      
      {/* Race projection */}
      {data.projected_time && (
        <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm text-emerald-400 font-medium">Race Projection</span>
            {data.confidence && (
              <span className={`px-2 py-0.5 rounded text-xs ${
                data.confidence === 'high' ? 'bg-emerald-600' :
                data.confidence === 'medium' ? 'bg-yellow-600' : 'bg-slate-600'
              }`}>
                {data.confidence.toUpperCase()}
              </span>
            )}
          </div>
          <div className="text-2xl font-bold text-white">{data.projected_time}</div>
          {data.goal_race_name && (
            <div className="text-sm text-slate-400 mt-1">{data.goal_race_name}</div>
          )}
        </div>
      )}
      
      {/* This week's focus */}
      {data.week_focus && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
          <div className="text-sm text-slate-400 mb-1">This Week&apos;s Focus</div>
          <p className="text-white">{data.week_focus}</p>
          {data.key_session && (
            <div className="mt-2 text-sm">
              <span className="text-slate-500">Key Session:</span>{' '}
              <span className="text-orange-400 font-medium">{data.key_session}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AthleteIntelligenceSection() {
  const { user } = useAuth();
  const hasEliteAccess =
    user?.subscription_tier === 'elite' ||
    (user?.subscription_tier !== undefined &&
      ['pro', 'premium', 'guided', 'subscription'].includes(user.subscription_tier));

  const { data, isLoading, error } = useAthleteIntelligence(hasEliteAccess);
  
  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }
  
  if (error) {
    // If you are Elite and still seeing an error, it's a real failure—not a lock.
    if (hasEliteAccess) {
      const msg = (error as Error)?.message || 'Unable to load Athlete Intelligence.';
      return (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-medium text-white mb-1">Athlete Intelligence</h3>
              <p className="text-slate-400 text-sm">{msg}</p>
              <p className="text-slate-500 text-xs mt-2">
                This is an Elite feature and should load for you—this message indicates a backend/API error.
              </p>
            </div>
            <a
              href="/settings"
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors h-fit"
            >
              Settings
            </a>
          </div>
        </div>
      );
    }

    // Non-elite: show a real preview (not a blank "locked" box).
    return (
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-medium text-white mb-1">Athlete Intelligence</h3>
            <p className="text-slate-400 text-sm">
              Preview of what this will surface once Elite membership is enabled.
            </p>
          </div>
          <a
            href="/settings"
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors h-fit"
          >
            Manage membership
          </a>
        </div>

        <div className="mt-5 grid md:grid-cols-2 gap-4">
          <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-4">
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">What works (preview)</div>
            <ul className="space-y-2 blur-sm select-none">
              <li className="text-slate-200 text-sm">Long runs 90–120 min correlate with better efficiency the following week.</li>
              <li className="text-slate-200 text-sm">2 quality sessions per 14 days is your current sweet spot.</li>
              <li className="text-slate-200 text-sm">Your best weeks follow 1 deliberate cutback week every 3–4 weeks.</li>
            </ul>
          </div>
          <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-4">
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">What hurts (preview)</div>
            <ul className="space-y-2 blur-sm select-none">
              <li className="text-slate-200 text-sm">Hard sessions too close together precede your “harmful” load weeks.</li>
              <li className="text-slate-200 text-sm">Fast “easy” days raise fatigue without improving outcomes.</li>
              <li className="text-slate-200 text-sm">Low sleep weeks coincide with worse HR/pace efficiency.</li>
            </ul>
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Preview items are illustrative; real output will be evidence-backed and personalized.
        </p>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span className="text-2xl">💡</span>
          Athlete Intelligence
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          What we&apos;ve learned about YOU from your data
        </p>
      </div>
      
      <div className="grid md:grid-cols-2 gap-6">
        {/* What Works */}
        <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-5">
          <h3 className="font-semibold text-emerald-400 mb-3 flex items-center gap-2">
            <span className="text-lg">✅</span> What Works For You
          </h3>
          {data?.what_works && data.what_works.length > 0 ? (
            <ul className="space-y-2">
              {data.what_works.map((item, idx) => (
                <li key={idx} className="text-slate-300 text-sm flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">•</span>
                  {item.text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500 text-sm">Still learning...</p>
          )}
        </div>
        
        {/* What Doesn't Work */}
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-5">
          <h3 className="font-semibold text-red-400 mb-3 flex items-center gap-2">
            <span className="text-lg">❌</span> What Doesn&apos;t Work
          </h3>
          {data?.what_doesnt && data.what_doesnt.length > 0 ? (
            <ul className="space-y-2">
              {data.what_doesnt.map((item, idx) => (
                <li key={idx} className="text-slate-300 text-sm flex items-start gap-2">
                  <span className="text-red-500 mt-0.5">•</span>
                  {item.text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500 text-sm">No negative patterns detected yet</p>
          )}
        </div>
      </div>
      
      {/* Injury Patterns */}
      {data?.injury_patterns && data.injury_patterns.length > 0 && (
        <div className="bg-orange-900/20 border border-orange-700/50 rounded-lg p-5">
          <h3 className="font-semibold text-orange-400 mb-3 flex items-center gap-2">
            <span className="text-lg">🛡️</span>
            Injury Risk Patterns
          </h3>
          <ul className="space-y-2">
            {data.injury_patterns.map((item, idx) => (
              <li key={idx} className="text-slate-300 text-sm flex items-start gap-2">
                <span className="text-orange-500 mt-0.5">⚠</span>
                {item.text}
                <span className="text-slate-500 text-xs ml-1">
                  (from {item.source === 'n1' ? 'your history' : 'population data'})
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function InsightsPage() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
        <div className="max-w-6xl mx-auto px-4">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">🧠 Insights</h1>
            <p className="text-slate-400">
              What your training is telling you — personalized, proactive, actionable
            </p>
          </div>
          
          {/* Three sections */}
          <div className="space-y-12">
            {/* Section 0: Ranked feed */}
            <section>
              <FeedSection />
            </section>

            {/* Section 1: Active Insights */}
            <section>
              <ActiveInsightsSection />
            </section>
            
            {/* Section 2: Build Status */}
            <section>
              <BuildStatusSection />
            </section>
            
            {/* Section 3: Athlete Intelligence */}
            <section>
              <AthleteIntelligenceSection />
            </section>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
