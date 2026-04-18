'use client';

/**
 * Home Page — ADR-17 Phase 2: Coach-Led Experience
 *
 * Tier 1 (above fold): Coach Noticed + Quick Check-in
 * Tier 2 (below fold): Today's workout, This Week, Race Countdown
 *
 * Removed: Quick Access, Yesterday, Hero Narrative, Welcome card, Import Progress
 */

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useHomeData, useQuickCheckin, useInvalidateHome } from '@/lib/hooks/queries/home';
import { useUnits } from '@/lib/context/UnitsContext';
import { LastRunHero } from '@/components/home/LastRunHero';
import { CompactPMC } from '@/components/home/CompactPMC';
import { RecentCrossTrainingCard } from '@/components/home/RecentCrossTrainingCard';
import FindingCard from '@/components/findings/FindingCard';
import { TrialBanner } from '@/components/home/TrialBanner';
import { FirstInsightsBanner } from '@/components/home/FirstInsightsBanner';
import { AdaptationProposalCard } from '@/components/home/AdaptationProposalCard';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Calendar,
  TrendingUp,
  Activity,
  Zap,
  ArrowRight,
  CheckCircle2,
  Clock,
  Target,
  BarChart3,
  MessageSquare,
  Footprints,
  Flame,
  Sparkles,
  Loader2,
  Heart,
  Moon,
  Info,
  Dumbbell,
  Bike,
  Mountain,
  StretchHorizontal,
  UtensilsCrossed,
} from 'lucide-react';

// --- Workout styling ---

const WORKOUT_CONFIG: Record<string, { color: string; bgColor: string; icon: React.ReactNode }> = {
  rest:         { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Clock className="w-6 h-6" /> },
  recovery:     { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Clock className="w-6 h-6" /> },
  easy:         { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Footprints className="w-6 h-6" /> },
  easy_strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Zap className="w-6 h-6" /> },
  strides:      { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Zap className="w-6 h-6" /> },
  medium_long:  { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <TrendingUp className="w-6 h-6" /> },
  long:         { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <TrendingUp className="w-6 h-6" /> },
  long_mp:      { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <Target className="w-6 h-6" /> },
  threshold:    { color: 'text-orange-400', bgColor: 'bg-orange-500/20', icon: <Flame className="w-6 h-6" /> },
  tempo:        { color: 'text-orange-400', bgColor: 'bg-orange-500/20', icon: <Flame className="w-6 h-6" /> },
  intervals:    { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: <Activity className="w-6 h-6" /> },
  vo2max:       { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: <Activity className="w-6 h-6" /> },
  race:         { color: 'text-pink-400', bgColor: 'bg-pink-500/20', icon: <Target className="w-6 h-6" /> },
};

const DEFAULT_WORKOUT = { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Footprints className="w-6 h-6" /> };

const SPORT_CHIP_ICONS: Record<string, { icon: React.ReactNode; label: string }> = {
  strength:    { icon: <Dumbbell className="w-3.5 h-3.5" />, label: 'Strength' },
  cycling:     { icon: <Bike className="w-3.5 h-3.5" />, label: 'Cycling' },
  hiking:      { icon: <Mountain className="w-3.5 h-3.5" />, label: 'Hiking' },
  walking:     { icon: <Footprints className="w-3.5 h-3.5" />, label: 'Walking' },
  flexibility: { icon: <StretchHorizontal className="w-3.5 h-3.5" />, label: 'Flexibility' },
};

function getWorkoutConfig(type?: string) {
  return type ? (WORKOUT_CONFIG[type] ?? DEFAULT_WORKOUT) : DEFAULT_WORKOUT;
}

function formatWorkoutType(type?: string): string {
  if (!type) return '';
  const labels: Record<string, string> = {
    easy: 'Easy Run', easy_strides: 'Easy + Strides', strides: 'Strides',
    medium_long: 'Medium Long', long: 'Long Run', long_mp: 'Long + MP',
    threshold: 'Threshold', tempo: 'Tempo', intervals: 'Intervals',
    vo2max: 'VO2max', rest: 'Rest Day', recovery: 'Recovery', race: 'Race Day',
  };
  return labels[type] || type.replace(/_/g, ' ');
}

function getStatusBadge(status: string) {
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    ahead:    { cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', icon: <TrendingUp className="w-3 h-3" />, label: 'Ahead' },
    on_track: { cls: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: <CheckCircle2 className="w-3 h-3" />, label: 'On Track' },
    behind:   { cls: 'bg-orange-500/20 text-orange-400 border-orange-500/30', icon: <Clock className="w-3 h-3" />, label: 'Behind' },
  };
  const s = map[status];
  if (!s) return null;
  return <Badge className={`${s.cls} gap-1 text-xs`}>{s.icon} {s.label}</Badge>;
}



// ── HRV Tooltip ─────────────────────────────────────────────────────

function HrvTooltip({ recoveryHrv, overnightHrv }: { recoveryHrv?: number; overnightHrv?: number }) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="ml-1 text-slate-500 hover:text-slate-300 transition-colors"
        aria-label="HRV explanation"
      >
        <Info className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 rounded-lg bg-slate-700 border border-slate-600 shadow-xl p-3 z-50 text-left">
          <p className="text-xs font-semibold text-white mb-2">Two HRV numbers — why?</p>
          <div className="space-y-2 text-xs text-slate-300 leading-relaxed">
            <div>
              <span className="text-emerald-400 font-medium">Recovery HRV{recoveryHrv != null ? ` (${Math.round(recoveryHrv)} ms)` : ''}</span>
              <p className="mt-0.5">
                The highest 5-minute HRV window during sleep. Reflects your peak
                parasympathetic recovery — when your nervous system was most relaxed.
                This is what StrideIQ uses for correlations and your Operating Manual.
              </p>
            </div>
            <div>
              <span className="text-blue-400 font-medium">Overnight Avg HRV{overnightHrv != null ? ` (${Math.round(overnightHrv)} ms)` : ''}</span>
              <p className="mt-0.5">
                The average across your entire sleep. This is the number your
                Garmin watch displays on the sleep screen. It&apos;s always lower because it
                includes light sleep and brief awakenings that pull the average down.
              </p>
            </div>
            <p className="text-slate-400 mt-1 pt-1 border-t border-slate-600">
              Both are valid — they measure different things. Recovery HRV is more
              predictive of next-day performance.
            </p>
          </div>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-slate-700" />
        </div>
      )}
    </span>
  );
}


// ── Wellness Row ────────────────────────────────────────────────────

function WellnessRow({ wellness }: { wellness: any }) {
  if (!wellness) return null;

  const statusColor = (s?: string) => {
    if (s === 'high') return 'text-emerald-400';
    if (s === 'low') return 'text-amber-400';
    return 'text-slate-300';
  };

  const statusLabel = (s?: string, metric?: string) => {
    if (!s) return null;
    if (metric === 'rhr') {
      if (s === 'low') return 'Good';
      if (s === 'high') return 'Elevated';
    }
    if (s === 'low') return 'Low for you';
    if (s === 'high') return 'Strong';
    return 'Normal';
  };

  const rangeText = (range?: { low: number; high: number }) => {
    if (!range) return null;
    return `${range.low}–${range.high}`;
  };

  const hasHrv = wellness.recovery_hrv != null;
  const hasRhr = wellness.resting_hr != null;
  const hasSleep = wellness.sleep_h != null;

  if (!hasHrv && !hasRhr && !hasSleep) return null;

  return (
    <div className="flex items-stretch gap-3 px-1">
      {/* Recovery HRV */}
      {hasHrv && (
        <div className="flex-1 rounded-lg bg-slate-800/60 border border-slate-700/50 px-3 py-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Activity className="w-3.5 h-3.5 text-emerald-500" />
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
              Recovery HRV
            </span>
            <HrvTooltip
              recoveryHrv={wellness.recovery_hrv}
              overnightHrv={wellness.overnight_hrv}
            />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className={`text-xl font-bold ${statusColor(wellness.recovery_hrv_status)}`}>
              {Math.round(wellness.recovery_hrv)}
            </span>
            <span className="text-xs text-slate-500">ms</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {statusLabel(wellness.recovery_hrv_status) && (
              <span className={`text-[11px] font-medium ${statusColor(wellness.recovery_hrv_status)}`}>
                {statusLabel(wellness.recovery_hrv_status)}
              </span>
            )}
            {wellness.recovery_hrv_range && (
              <span className="text-[10px] text-slate-500">
                range: {rangeText(wellness.recovery_hrv_range)}
              </span>
            )}
          </div>
          {wellness.overnight_hrv != null && (
            <div className="mt-1.5 pt-1.5 border-t border-slate-700/50">
              <div className="flex items-baseline gap-1.5">
                <span className="text-[11px] text-slate-500">Garmin overnight avg</span>
                <span className="text-sm font-medium text-blue-400">
                  {Math.round(wellness.overnight_hrv)}
                </span>
                <span className="text-[10px] text-slate-500">ms</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Right column: RHR + Sleep stacked */}
      <div className="flex-1 flex flex-col gap-2">
        {/* Resting HR */}
        {hasRhr && (
          <div className="flex-1 rounded-lg bg-slate-800/60 border border-slate-700/50 px-3 py-2">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Heart className="w-3.5 h-3.5 text-red-400" />
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Resting HR</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className={`text-lg font-bold ${statusColor(wellness.resting_hr_status === 'low' ? 'high' : wellness.resting_hr_status === 'high' ? 'low' : wellness.resting_hr_status)}`}>
                {wellness.resting_hr}
              </span>
              <span className="text-[10px] text-slate-500">bpm</span>
              {statusLabel(wellness.resting_hr_status, 'rhr') && (
                <span className={`text-[11px] font-medium ${statusColor(wellness.resting_hr_status === 'low' ? 'high' : wellness.resting_hr_status === 'high' ? 'low' : wellness.resting_hr_status)}`}>
                  {statusLabel(wellness.resting_hr_status, 'rhr')}
                </span>
              )}
              {wellness.resting_hr_range && (
                <span className="text-[10px] text-slate-500">
                  ({rangeText(wellness.resting_hr_range)})
                </span>
              )}
            </div>
          </div>
        )}

        {/* Sleep */}
        {hasSleep && (
          <div className="flex-1 rounded-lg bg-slate-800/60 border border-slate-700/50 px-3 py-2">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Moon className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Sleep</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-bold text-slate-300">
                {wellness.sleep_h}
              </span>
              <span className="text-[10px] text-slate-500">hours</span>
              {wellness.sleep_score != null && (
                <span className="text-[11px] text-slate-400 ml-1">
                  Score: {wellness.sleep_score}
                  {wellness.sleep_score_qualifier ? ` (${wellness.sleep_score_qualifier})` : ''}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// ── Quick Check-in ──────────────────────────────────────────────────

const FEEL_OPTIONS = [
  { label: 'Great', value: 5, emoji: '💪' },
  { label: 'Fine',  value: 4, emoji: '👍' },
  { label: 'Tired', value: 2, emoji: '😴' },
  { label: 'Rough', value: 1, emoji: '😓' },
];

const SLEEP_QUALITY_OPTIONS = [
  { label: 'Great', value: 5, emoji: '🌙' },
  { label: 'OK',    value: 3, emoji: '😐' },
  { label: 'Poor',  value: 1, emoji: '😵' },
];

const SORENESS_OPTIONS = [
  { label: 'No',   value: 1, emoji: '✅' },
  { label: 'Mild', value: 2, emoji: '🤏' },
  { label: 'Yes',  value: 4, emoji: '🔥' },
];

const ENJOYMENT_OPTIONS = [
  { label: 'Dreading', value: 1, emoji: '😞' },
  { label: 'Meh',      value: 3, emoji: '😐' },
  { label: 'Loving it', value: 5, emoji: '😊' },
];

const CONFIDENCE_OPTIONS = [
  { label: 'Doubtful', value: 1, emoji: '😰' },
  { label: 'Steady',   value: 3, emoji: '😐' },
  { label: 'Strong',   value: 5, emoji: '💪' },
];

function QuickCheckin() {
  const [feel, setFeel] = useState<number | null>(null);
  const [sleepQuality, setSleepQuality] = useState<number | null>(null);
  const [sleepHours, setSleepHours] = useState<number | null>(null);
  const [soreness, setSoreness] = useState<number | null>(null);
  const [showMindset, setShowMindset] = useState(false);
  const [enjoyment, setEnjoyment] = useState<number | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const checkin = useQuickCheckin();

  const handleSubmit = () => {
    if (feel === null || sleepQuality === null || soreness === null) return;
    const today = new Date().toISOString().split('T')[0];
    checkin.mutate({
      date: today,
      readiness_1_5: feel,
      sleep_quality_1_5: sleepQuality,
      sleep_h: sleepHours ?? undefined,
      soreness_1_5: soreness,
      enjoyment_1_5: enjoyment ?? undefined,
      confidence_1_5: confidence ?? undefined,
    });
  };

  const allSelected = feel !== null && sleepQuality !== null && soreness !== null;

  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardContent className="pt-4 pb-4 px-5 space-y-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Quick check-in
        </p>

        {/* Feel */}
        <div>
          <p className="text-sm text-slate-300 mb-2">How do you feel today?</p>
          <div className="flex gap-2">
            {FEEL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFeel(opt.value)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                  feel === opt.value
                    ? 'bg-orange-600/30 text-orange-300 ring-1 ring-orange-500/50'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <span className="block text-base mb-0.5">{opt.emoji}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sleep Quality */}
        <div>
          <p className="text-sm text-slate-300 mb-2">How did you sleep?</p>
          <div className="flex gap-2">
            {SLEEP_QUALITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSleepQuality(opt.value)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                  sleepQuality === opt.value
                    ? 'bg-orange-600/30 text-orange-300 ring-1 ring-orange-500/50'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <span className="block text-base mb-0.5">{opt.emoji}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sleep Hours */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <p className="text-sm text-slate-300">Hours slept</p>
            <span className="text-sm font-semibold text-blue-400">
              {sleepHours != null ? `${sleepHours}h` : '--'}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="12"
            step="0.5"
            value={sleepHours ?? 0}
            onChange={(e) => setSleepHours(parseFloat(e.target.value))}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-0.5">
            <span>0h</span>
            <span>12h</span>
          </div>
        </div>

        {/* Soreness */}
        <div>
          <p className="text-sm text-slate-300 mb-2">Any soreness?</p>
          <div className="flex gap-2">
            {SORENESS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSoreness(opt.value)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                  soreness === opt.value
                    ? 'bg-orange-600/30 text-orange-300 ring-1 ring-orange-500/50'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <span className="block text-base mb-0.5">{opt.emoji}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Mindset (optional, collapsible) */}
        <div>
          <button
            type="button"
            onClick={() => setShowMindset(!showMindset)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-400 transition-colors"
          >
            <span>🧠</span>
            <span>Mindset</span>
            <span className="text-[10px]">{showMindset ? '▲' : '▼'}</span>
          </button>

          {showMindset && (
            <div className="mt-3 space-y-3">
              <div>
                <p className="text-sm text-slate-300 mb-2">Enjoying training?</p>
                <div className="flex gap-2">
                  {ENJOYMENT_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setEnjoyment(enjoyment === opt.value ? null : opt.value)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                        enjoyment === opt.value
                          ? 'bg-green-600/30 text-green-300 ring-1 ring-green-500/50'
                          : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                      }`}
                    >
                      <span className="block text-base mb-0.5">{opt.emoji}</span>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm text-slate-300 mb-2">Confidence?</p>
                <div className="flex gap-2">
                  {CONFIDENCE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setConfidence(confidence === opt.value ? null : opt.value)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                        confidence === opt.value
                          ? 'bg-purple-600/30 text-purple-300 ring-1 ring-purple-500/50'
                          : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                      }`}
                    >
                      <span className="block text-base mb-0.5">{opt.emoji}</span>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Submit */}
        {allSelected && (
          <Button
            onClick={handleSubmit}
            disabled={checkin.isPending}
            className="w-full bg-orange-600 hover:bg-orange-700 text-white"
            size="sm"
          >
            {checkin.isPending ? 'Saving...' : 'Save check-in'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}


// ── Check-in Summary (shown after check-in) ────────────────────────

function CheckinSummary({ readiness, sleep, soreness, coachReaction }: {
  readiness?: string | null; sleep?: string | null; soreness?: string | null; coachReaction?: string;
}) {
  const items = [
    { label: 'Readiness', value: readiness, emoji: readiness === 'High' ? '🔥' : readiness === 'Good' ? '💪' : readiness === 'Neutral' ? '😐' : readiness === 'Low' ? '😑' : '😴' },
    { label: 'Sleep', value: sleep, emoji: sleep === 'Great' ? '🌙' : sleep === 'OK' ? '😐' : '😵' },
    { label: 'Soreness', value: soreness, emoji: soreness === 'None' ? '✅' : soreness === 'Mild' ? '🤏' : '🔥' },
  ].filter((i) => i.value);

  if (items.length === 0) return null;

  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardContent className="py-3 px-5">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Today&apos;s check-in
          </p>
        </div>
        <div className="flex gap-4 mb-2">
          {items.map((item) => (
            <div key={item.label} className="flex items-center gap-1.5 text-sm">
              <span>{item.emoji}</span>
              <span className="text-slate-400 text-xs">{item.label}:</span>
              <span className="text-slate-200 text-xs font-medium">{item.value}</span>
            </div>
          ))}
        </div>
        {coachReaction && (
          <div className="bg-slate-700/40 rounded-lg p-3 border border-slate-600/40 mt-1">
            <div className="flex gap-2">
              <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-slate-300 leading-relaxed">{coachReaction}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}


// ── Race Countdown Card ─────────────────────────────────────────────

function RaceCountdownCard({
  raceName, raceDate, daysRemaining, goalTime, goalPace, predictedTime, coachAssessment,
}: {
  raceName?: string; raceDate: string; daysRemaining: number;
  goalTime?: string; goalPace?: string; predictedTime?: string; coachAssessment?: string;
}) {
  return (
    <Card className="bg-slate-800/50 border-slate-700/50">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-pink-400" />
          <CardTitle className="text-sm text-slate-300">Race Countdown</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="pb-4 space-y-2">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">{daysRemaining}</span>
          <span className="text-sm text-slate-400">days to go</span>
        </div>
        {raceName && (
          <p className="text-sm text-slate-300">{raceName}</p>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          {goalTime && <span>Goal: <span className="text-white font-medium">{goalTime}</span></span>}
          {goalPace && <span>Pace: <span className="text-white font-medium">{goalPace}</span></span>}
          {predictedTime && <span>Predicted: <span className="text-white font-medium">{predictedTime}</span></span>}
        </div>
        {coachAssessment && (
          <div className="bg-slate-700/40 rounded-lg p-3 border border-slate-600/40 mt-1">
            <div className="flex gap-2">
              <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-slate-300 leading-relaxed">{coachAssessment}</p>
            </div>
          </div>
        )}
        <Link
          href={`/coach?q=${encodeURIComponent(`Am I on track for my ${raceName || 'race'} in ${daysRemaining} days?`)}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors pt-1"
        >
          Ask Coach <ArrowRight className="w-3 h-3" />
        </Link>
      </CardContent>
    </Card>
  );
}


// ── Briefing Pending Placeholder ────────────────────────────────────

const BRIEFING_TIMEOUT_MS = 30_000;

function BriefingPendingPlaceholder({
  onRetry,
  timedOut,
}: {
  onRetry: () => void;
  timedOut: boolean;
}) {
  if (timedOut) {
    return (
      <div
        data-testid="briefing-timeout-fallback"
        className="px-1 py-2 flex items-start gap-2"
      >
        <Sparkles className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm text-slate-500 leading-relaxed">
            Your coach is taking a moment — check back shortly.
          </p>
          <button
            onClick={onRetry}
            className="text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors"
          >
            Retry now
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="briefing-thinking"
      className="px-1 py-2 flex items-center gap-2"
    >
      <Sparkles className="w-4 h-4 text-slate-500 animate-pulse flex-shrink-0" />
      <p className="text-sm text-slate-500 italic">Coach is thinking...</p>
    </div>
  );
}


// ── Main Page ───────────────────────────────────────────────────────

export default function HomePage() {
  const invalidateHome = useInvalidateHome();
  const { data, isLoading, error } = useHomeData();
  const { units, formatDistance } = useUnits();
  const MI_TO_M = 1609.344;
  const formatMiles = (mi: number | null | undefined, decimals: number = 1) =>
    mi === null || mi === undefined ? '-' : formatDistance(mi * MI_TO_M, decimals);
  const formatMilesNoUnit = (mi: number | null | undefined, decimals: number = 1) =>
    mi === null || mi === undefined
      ? '-'
      : (units === 'metric' ? mi * 1.60934 : mi).toFixed(decimals);
  const rewriteImperialToMetric = (text: string | null | undefined): string | null | undefined => {
    if (!text || units !== 'metric') return text;
    let out = text.replace(/(\d+):(\d{2})\s*\/\s*mi\b/gi, (_match, mm, ss) => {
      const totalSecPerMi = parseInt(mm, 10) * 60 + parseInt(ss, 10);
      const secPerKm = Math.round(totalSecPerMi / 1.60934);
      const m = Math.floor(secPerKm / 60);
      const s = secPerKm % 60;
      return `${m}:${s.toString().padStart(2, '0')}/km`;
    });
    out = out.replace(/(\d+(?:\.\d+)?)\s*mi\b/gi, (_match, mi) => {
      const km = parseFloat(mi) * 1.60934;
      return `${km.toFixed(km < 10 ? 1 : 0)} km`;
    });
    return out;
  };

  // Briefing pending state + 30s timeout fallback
  const briefingState = data?.briefing_state;
  const isInterimBriefing = Boolean(data?.briefing_is_interim);
  const isBriefingPending =
    briefingState === 'stale' ||
    briefingState === 'missing' ||
    briefingState === 'refreshing' ||
    isInterimBriefing;

  const [briefingTimedOut, setBriefingTimedOut] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isBriefingPending && !briefingTimedOut) {
      timeoutRef.current = setTimeout(() => setBriefingTimedOut(true), BRIEFING_TIMEOUT_MS);
    } else if (!isBriefingPending) {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setBriefingTimedOut(false);
    }
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isBriefingPending, briefingTimedOut]);

  const handleBriefingRetry = () => {
    setBriefingTimedOut(false);
    invalidateHome();
  };

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
        <div className="min-h-screen p-4">
          <div className="max-w-xl mx-auto pt-12">
            <Card className="bg-slate-800 border-red-700/50">
              <CardContent className="pt-6">
                <p className="text-slate-400">Could not load data. Try again.</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  const {
    today,
    week,
    strava_connected,
    garmin_connected,
    has_any_activities,
    total_activities,
    race_countdown,
    checkin_needed,
    today_checkin,
    coach_briefing,
    coach_noticed: coachNoticedStructured,
    last_run,
    briefing_last_updated_at,
    garmin_wellness,
    recent_cross_training,
  } = data;

  const formattedBriefingUpdatedAt = briefing_last_updated_at
    ? new Date(briefing_last_updated_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : null;

  const isConnected = strava_connected || garmin_connected;
  const hasAnyData = has_any_activities || week.completed_mi > 0;
  const workoutConfig = getWorkoutConfig(today.workout_type);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">
                {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
              </h1>
            </div>
            <Link
              href="/coach"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-orange-600/20 text-orange-400 hover:bg-orange-600/30 transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" /> Coach
            </Link>
          </div>

          {/* Trial / subscription status banner */}
          <TrialBanner />
          <FirstInsightsBanner />

          {/* ═══ ABOVE THE FOLD: Three things ═══ */}

          {/* 1. Full-bleed hero (last run canvas) */}
          {last_run && <LastRunHero lastRun={last_run} />}

          {/* Cross-training acknowledgment — secondary to the run hero */}
          {recent_cross_training && <RecentCrossTrainingCard data={recent_cross_training} />}

          {/* Training Load — compact PMC (paired visually with LastRunHero) */}
          <CompactPMC />

          {/* 2. The Voice — single paragraph only (morning_voice primary) */}
          {(coach_briefing?.morning_voice || coach_briefing?.coach_noticed) ? (
            <div data-testid="morning-voice" className="px-1 py-2 space-y-2">
              {isInterimBriefing ? (
                <div
                  data-testid="briefing-interim-banner"
                  className="rounded-md border border-blue-500/30 bg-blue-500/10 px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 text-blue-300 animate-spin" />
                    <p className="text-xs text-blue-200">
                      Updating your morning insight from newly synced sleep/HRV data...
                    </p>
                  </div>
                </div>
              ) : null}
              {coach_briefing.morning_voice ? (
                <p
                  className={`text-base leading-relaxed ${
                    isInterimBriefing ? 'text-slate-400 italic' : 'text-slate-300'
                  }`}
                  data-testid="morning-voice-primary"
                >
                  {coach_briefing.morning_voice}
                </p>
              ) : coach_briefing.coach_noticed ? (
                coachNoticedStructured?.finding_id ? (
                  <Link
                    href={`/coach?finding_id=${coachNoticedStructured.finding_id}&q=${encodeURIComponent(coachNoticedStructured.ask_coach_query)}`}
                    className={`block text-base leading-relaxed hover:text-orange-300 transition-colors cursor-pointer ${
                      isInterimBriefing ? 'text-slate-400 italic' : 'text-orange-400/80'
                    }`}
                    data-testid="morning-voice-primary"
                  >
                    {coach_briefing.coach_noticed}
                    <span className="ml-1.5 text-xs text-orange-500/60">&rarr; Ask coach</span>
                  </Link>
                ) : (
                  <p
                    className={`text-base leading-relaxed ${
                      isInterimBriefing ? 'text-slate-400 italic' : 'text-slate-300'
                    }`}
                    data-testid="morning-voice-primary"
                  >
                    {coach_briefing.coach_noticed}
                  </p>
                )
              ) : null}
              {formattedBriefingUpdatedAt ? (
                <p className="text-[11px] text-slate-500" data-testid="briefing-last-updated">
                  Last updated: {formattedBriefingUpdatedAt}
                </p>
              ) : null}
              {coach_briefing.morning_voice && coach_briefing.coach_noticed ? (
                coachNoticedStructured?.finding_id ? (
                  <Link
                    href={`/coach?finding_id=${coachNoticedStructured.finding_id}&q=${encodeURIComponent(coachNoticedStructured.ask_coach_query)}`}
                    className="block text-sm text-orange-400/80 leading-relaxed hover:text-orange-300 transition-colors cursor-pointer"
                    data-testid="coach-noticed-secondary"
                  >
                    {coach_briefing.coach_noticed}
                    <span className="ml-1.5 text-xs text-orange-500/60">&rarr; Ask coach</span>
                  </Link>
                ) : (
                  <p className="text-sm text-slate-500 leading-relaxed" data-testid="coach-noticed-secondary">
                    {coach_briefing.coach_noticed}
                  </p>
                )
              ) : null}
            </div>
          ) : isBriefingPending ? (
            <BriefingPendingPlaceholder
              onRetry={handleBriefingRetry}
              timedOut={briefingTimedOut}
            />
          ) : null}

          {/* 2b. Daily wellness (Garmin HRV, RHR, sleep) */}
          {garmin_wellness && <WellnessRow wellness={garmin_wellness} />}

          {/* 2c. Adaptation proposal (if pending) */}
          <AdaptationProposalCard />

          {/* 3. Today's workout — plain text, no card chrome */}
          {today.has_workout ? (
            <div data-testid="today-workout" className="px-1 pt-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">Today</span>
              <h2 className={`text-xl font-bold mt-1 ${workoutConfig.color}`}>
                {today.title || formatWorkoutType(today.workout_type)}
              </h2>
              {coach_briefing?.workout_why && (
                <p data-testid="workout-why" className="text-sm text-slate-400 mt-1 leading-relaxed">
                  {coach_briefing.workout_why}
                </p>
              )}
              {!coach_briefing?.workout_why && (coach_briefing?.today_context || today.why_context) && (
                <p className="text-sm text-slate-400 mt-1 leading-relaxed">
                  {coach_briefing?.today_context || today.why_context}
                </p>
              )}
              <p className="text-xs text-slate-500 mt-1.5">
                {today.distance_mi && <span>{formatMiles(today.distance_mi)}</span>}
                {today.distance_mi && today.pace_guidance && <span> · </span>}
                {today.pace_guidance && <span>{rewriteImperialToMetric(today.pace_guidance)}</span>}
                {today.week_number && <span> · Week {today.week_number}</span>}
                {today.phase && <span> · {today.phase}</span>}
              </p>
            </div>
          ) : (
            <div data-testid="today-workout" className="px-1 pt-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Today</span>
              <p className="text-sm text-slate-400 mt-1">
                {hasAnyData
                  ? 'Recovery day.'
                  : isConnected
                    ? 'Create a plan to see workouts.'
                    : 'Connect your watch to get started.'}
              </p>
            </div>
          )}

          {/* ═══ BELOW THE FOLD ═══ */}

          {/* Check-in (moved below workout — intentional) */}
          <div data-testid="checkin-section">
            {checkin_needed && hasAnyData ? (
              <QuickCheckin />
            ) : today_checkin ? (
              <CheckinSummary
                readiness={today_checkin.readiness_label}
                sleep={today_checkin.sleep_label}
                soreness={today_checkin.soreness_label}
                coachReaction={coach_briefing?.checkin_reaction}
              />
            ) : null}
          </div>

          {/* Nutrition — daily-use shortcut */}
          <Link
            href="/nutrition"
            className="block group"
          >
            <div className="flex items-center gap-3 bg-slate-800/50 border border-slate-700/50 rounded-xl px-4 py-3 transition-colors group-hover:border-emerald-600/40 group-active:bg-slate-700/50">
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-emerald-500/20 flex-shrink-0">
                <UtensilsCrossed className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white">Log Nutrition</p>
                <p className="text-xs text-slate-500">Photo, scan, or type what you ate</p>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-emerald-400 transition-colors flex-shrink-0" />
            </div>
          </Link>

          {/* Finding or Cold-Start */}
          {data.finding ? (
            <Link href="/progress" className="block transition-transform hover:translate-y-[-1px]">
              <FindingCard
                text={data.finding.text}
                domain={data.finding.domain}
                confidenceTier={data.finding.confidence_tier}
                timesConfirmed={data.finding.times_confirmed}
                evidence={data.finding.evidence_summary}
                implication={data.finding.implication_summary}
                expandable={false}
              />
            </Link>
          ) : !data.has_correlations && has_any_activities ? (
            <FindingCard expandable={false} activityCount={total_activities} />
          ) : null}

          {/* This Week */}
          <Card className="bg-slate-800/50 border-slate-700/50">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-semibold text-slate-300">This Week</span>
                </div>
                {week.week_number && week.total_weeks ? (
                  <span className="text-xs text-slate-500">
                    Week {week.week_number}/{week.total_weeks}
                  </span>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="pb-4 space-y-3">
              {/* Day chips */}
              <div className="flex justify-between gap-1">
                {week.days.map((day) => {
                  const dayConfig = getWorkoutConfig(day.workout_type);
                  const linkHref = day.activity_id
                    ? `/activities/${day.activity_id}`
                    : day.workout_id
                      ? `/calendar?date=${day.date}`
                      : null;

                  const sportInfo = day.sport && day.sport !== 'run' ? SPORT_CHIP_ICONS[day.sport] : null;

                  const chip = (
                    <>
                      <div className={`text-[10px] uppercase mb-1 ${day.is_today ? 'text-orange-400 font-semibold' : 'text-slate-500'}`}>
                        {day.day_abbrev}
                      </div>
                      <div className={`text-xs font-semibold ${day.completed ? 'text-emerald-400' : dayConfig.color}`}>
                        {day.completed && sportInfo ? (
                          <span className="flex flex-col items-center gap-0.5">
                            {sportInfo.icon}
                          </span>
                        ) : day.completed && day.distance_mi ? (
                          <span className="flex flex-col items-center gap-0.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span className="text-[10px]">{formatMilesNoUnit(day.distance_mi)}</span>
                          </span>
                        ) : day.workout_type === 'rest' ? (
                          <span className="text-slate-600">&mdash;</span>
                        ) : day.distance_mi ? (
                          <span>{formatMilesNoUnit(day.distance_mi)}</span>
                        ) : (
                          <span className="text-slate-600">&mdash;</span>
                        )}
                      </div>
                    </>
                  );

                  const cls = `flex-1 text-center py-2.5 px-0.5 rounded-lg transition-all ${
                    day.is_today ? 'ring-2 ring-orange-500 bg-orange-500/10' : ''
                  } ${day.completed ? 'bg-emerald-500/15 border border-emerald-500/25' : 'bg-slate-700/50 border border-transparent'
                  } ${linkHref ? 'cursor-pointer hover:bg-slate-600/50' : ''}`;

                  return linkHref ? (
                    <Link key={day.date} href={linkHref} className={cls}>{chip}</Link>
                  ) : (
                    <div key={day.date} className={cls}>{chip}</div>
                  );
                })}
              </div>

              {/* Progress / Volume */}
              {week.status === 'no_plan' ? (
                <div className="text-center py-1">
                  {week.completed_mi > 0 ? (
                    <>
                      <div className="flex items-center justify-center gap-2 mb-1">
                        <Footprints className="w-4 h-4 text-orange-500" />
                        <span className="text-lg font-bold text-white">{formatMiles(week.completed_mi)}</span>
                        <span className="text-xs text-slate-500">logged</span>
                      </div>
                      {week.trajectory_sentence && (
                        <p className="text-xs text-slate-400">{rewriteImperialToMetric(week.trajectory_sentence)}</p>
                      )}
                    </>
                  ) : (
                    <p className="text-sm text-slate-500">
                      {isConnected
                        ? total_activities > 0 ? 'No runs this week yet.' : 'Waiting for sync.'
                        : 'Connect your watch to track.'}
                    </p>
                  )}
                </div>
              ) : (
                <>
                  {week.planned_mi > 0 && (
                    <Progress
                      value={Math.min(100, week.progress_pct)}
                      className="h-2"
                      indicatorClassName={
                        week.status === 'ahead' ? 'bg-emerald-500'
                          : week.status === 'on_track' ? 'bg-blue-500'
                            : 'bg-orange-500'
                      }
                    />
                  )}
                  <div className="flex items-center justify-between">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-lg font-bold text-white">{formatMilesNoUnit(week.completed_mi)}</span>
                      <span className="text-sm text-slate-500">/ {formatMiles(week.planned_mi)}</span>
                    </div>
                    {getStatusBadge(week.status)}
                  </div>
                  {(coach_briefing?.week_assessment || week.trajectory_sentence) && (
                    <div className="pt-1 border-t border-slate-700/50">
                      {coach_briefing?.week_assessment ? (
                        <div className="flex gap-2">
                          <Sparkles className="w-3.5 h-3.5 text-orange-400 flex-shrink-0 mt-0.5" />
                          <p className="text-xs text-slate-300">{rewriteImperialToMetric(coach_briefing.week_assessment)}</p>
                        </div>
                      ) : (
                        <p className="text-xs text-slate-400">{rewriteImperialToMetric(week.trajectory_sentence)}</p>
                      )}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Race Countdown */}
          {race_countdown && (
            <RaceCountdownCard
              raceName={race_countdown.race_name ?? undefined}
              raceDate={race_countdown.race_date}
              daysRemaining={race_countdown.days_remaining}
              goalTime={race_countdown.goal_time ?? undefined}
              goalPace={race_countdown.goal_pace ?? undefined}
              predictedTime={race_countdown.predicted_time ?? undefined}
              coachAssessment={coach_briefing?.race_assessment}
            />
          )}

          {/* Runtoon teaser — shown only if athlete has a last run */}
          {last_run && (
            <div className="rounded-lg border border-slate-700/40 bg-slate-800/20 p-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl flex-shrink-0" aria-hidden="true">🎨</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-200 leading-snug">
                    Your Runtoon is on your last run
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                    AI-generated caricature from your actual run data.
                  </p>
                  <Link
                    href={`/activities/${last_run.activity_id}`}
                    className="inline-block mt-2 text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors"
                  >
                    See it →
                  </Link>
                </div>
              </div>
            </div>
          )}

          {/* Brand subline */}
          <p className="text-center text-xs text-slate-600 py-2">
            Your body. Your data. Your voice.
          </p>

        </div>
      </div>
    </ProtectedRoute>
  );
}
