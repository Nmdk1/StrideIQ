'use client';

/**
 * Single day chip for the home/analytics “This week” row.
 * Primary tap = longest run; +N = extra runs; icons = other sports (separate links).
 */

import Link from 'next/link';
import {
  Activity,
  CheckCircle2,
  Clock,
  Flame,
  Footprints,
  Mountain,
  StretchHorizontal,
  TrendingUp,
  Zap,
  Target,
  Dumbbell,
  Bike,
} from 'lucide-react';
import type { WeekDay } from '@/lib/api/services/home';

const WORKOUT_CONFIG: Record<string, { color: string; bgColor: string; icon: React.ReactNode }> = {
  rest: { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Clock className="w-6 h-6" /> },
  recovery: { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Clock className="w-6 h-6" /> },
  easy: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Footprints className="w-6 h-6" /> },
  easy_strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Zap className="w-6 h-6" /> },
  strides: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: <Zap className="w-6 h-6" /> },
  medium_long: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <TrendingUp className="w-6 h-6" /> },
  long: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <TrendingUp className="w-6 h-6" /> },
  long_mp: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: <Target className="w-6 h-6" /> },
  threshold: { color: 'text-orange-400', bgColor: 'bg-orange-500/20', icon: <Flame className="w-6 h-6" /> },
  tempo: { color: 'text-orange-400', bgColor: 'bg-orange-500/20', icon: <Flame className="w-6 h-6" /> },
  intervals: { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: <Activity className="w-6 h-6" /> },
  vo2max: { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: <Activity className="w-6 h-6" /> },
  race: { color: 'text-pink-400', bgColor: 'bg-pink-500/20', icon: <Target className="w-6 h-6" /> },
};

const DEFAULT_WORKOUT = { color: 'text-slate-400', bgColor: 'bg-slate-500/20', icon: <Footprints className="w-6 h-6" /> };

export function getWorkoutConfig(type?: string) {
  return type ? (WORKOUT_CONFIG[type] ?? DEFAULT_WORKOUT) : DEFAULT_WORKOUT;
}

export const SPORT_CHIP_ICONS: Record<string, { icon: React.ReactNode; label: string }> = {
  strength: { icon: <Dumbbell className="w-3.5 h-3.5" />, label: 'Strength' },
  cycling: { icon: <Bike className="w-3.5 h-3.5" />, label: 'Cycling' },
  hiking: { icon: <Mountain className="w-3.5 h-3.5" />, label: 'Hiking' },
  walking: { icon: <Footprints className="w-3.5 h-3.5" />, label: 'Walking' },
  flexibility: { icon: <StretchHorizontal className="w-3.5 h-3.5" />, label: 'Flexibility' },
};

export interface WeekChipDayProps {
  day: WeekDay;
  formatMilesNoUnit: (mi: number) => string;
}

export function WeekChipDay({ day, formatMilesNoUnit }: WeekChipDayProps) {
  const dayConfig = getWorkoutConfig(day.workout_type);
  const longestRunHref = day.activity_id ? `/activities/${day.activity_id}` : null;
  const dayDetailHref = `/calendar?date=${day.date}`;
  const primaryHref = longestRunHref ?? (day.workout_id ? dayDetailHref : null);
  const runCount = day.run_count ?? 0;
  const others = day.other_activities ?? [];

  const headerEl = (
    <div
      className={`text-[10px] uppercase mb-1 ${day.is_today ? 'text-orange-400 font-semibold' : 'text-slate-500'}`}
    >
      {day.day_abbrev}
    </div>
  );

  const distanceEl = (
    <div className={`text-xs font-semibold ${day.completed ? 'text-emerald-400' : dayConfig.color}`}>
      {day.completed && day.distance_mi ? (
        <span className="flex flex-col items-center gap-0.5">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span className="text-[10px] tabular-nums">{formatMilesNoUnit(day.distance_mi)}</span>
        </span>
      ) : day.workout_type === 'rest' ? (
        <span className="text-slate-600">&mdash;</span>
      ) : day.distance_mi ? (
        <span>{formatMilesNoUnit(day.distance_mi)}</span>
      ) : (
        <span className="text-slate-600">&mdash;</span>
      )}
    </div>
  );

  const cls = `flex-1 text-center py-2.5 px-0.5 rounded-lg transition-all ${
    day.is_today ? 'ring-2 ring-orange-500 bg-orange-500/10' : ''
  } ${day.completed ? 'bg-emerald-500/15 border border-emerald-500/25' : 'bg-slate-700/50 border border-transparent'}`;

  const primaryArea = primaryHref ? (
    <Link
      href={primaryHref}
      aria-label={
        day.completed && day.distance_mi
          ? `${day.day_abbrev}: ${formatMilesNoUnit(day.distance_mi)} of running. Open longest run.`
          : `${day.day_abbrev}: open day`
      }
      className="block hover:opacity-90"
    >
      {headerEl}
      {distanceEl}
    </Link>
  ) : (
    <>
      {headerEl}
      {distanceEl}
    </>
  );

  const extras =
    runCount > 1 || others.length > 0 ? (
      <div className="mt-1 flex items-center justify-center gap-1 flex-wrap">
        {runCount > 1 && (
          <Link
            href={dayDetailHref}
            aria-label={`+${runCount - 1} more run${runCount - 1 === 1 ? '' : 's'} this day`}
            title={`+${runCount - 1} more run${runCount - 1 === 1 ? '' : 's'}`}
            className="text-[10px] font-semibold leading-none px-1 py-0.5 rounded bg-emerald-500/25 text-emerald-200 hover:bg-emerald-500/40"
          >
            +{runCount - 1}
          </Link>
        )}
        {others.map((o) => {
          const sportInfo = SPORT_CHIP_ICONS[o.sport];
          if (!sportInfo) return null;
          const label = o.distance_mi
            ? `${sportInfo.label}: ${formatMilesNoUnit(o.distance_mi)}`
            : o.duration_min
              ? `${sportInfo.label}: ${Math.round(o.duration_min)} min`
              : sportInfo.label;
          return (
            <Link
              key={o.activity_id}
              href={`/activities/${o.activity_id}`}
              aria-label={label}
              title={label}
              className="inline-flex items-center justify-center p-0.5 rounded bg-slate-700/60 text-slate-300 hover:bg-slate-600 hover:text-white"
            >
              {sportInfo.icon}
            </Link>
          );
        })}
      </div>
    ) : null;

  return (
    <div className={cls}>
      {primaryArea}
      {extras}
    </div>
  );
}
