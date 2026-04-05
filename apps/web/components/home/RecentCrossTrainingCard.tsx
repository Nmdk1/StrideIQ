'use client';

import Link from 'next/link';
import { Dumbbell, Bike, Mountain, Footprints, StretchHorizontal, ChevronRight } from 'lucide-react';

const SPORT_MAP: Record<string, { icon: typeof Dumbbell; label: string; color: string; bg: string }> = {
  strength:    { icon: Dumbbell, label: 'Strength', color: 'text-amber-400', bg: 'bg-amber-500/15 border-amber-500/20' },
  cycling:     { icon: Bike, label: 'Cycling', color: 'text-blue-400', bg: 'bg-blue-500/15 border-blue-500/20' },
  hiking:      { icon: Mountain, label: 'Hiking', color: 'text-emerald-400', bg: 'bg-emerald-500/15 border-emerald-500/20' },
  walking:     { icon: Footprints, label: 'Walking', color: 'text-teal-400', bg: 'bg-teal-500/15 border-teal-500/20' },
  flexibility: { icon: StretchHorizontal, label: 'Flexibility', color: 'text-purple-400', bg: 'bg-purple-500/15 border-purple-500/20' },
};

interface Props {
  data: {
    id: string;
    sport: string;
    name: string | null;
    distance_m: number | null;
    duration_s: number | null;
    avg_hr: number | null;
    steps: number | null;
    active_kcal: number | null;
    start_time: string;
    additional_count: number;
  };
}

function formatDuration(s: number): string {
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  if (hrs > 0) return `${hrs}h ${mins}m`;
  return `${mins} min`;
}

function formatDistance(m: number): string {
  const mi = m / 1609.344;
  return mi < 10 ? `${mi.toFixed(1)} mi` : `${Math.round(mi)} mi`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function getMetrics(data: Props['data']): string {
  const parts: string[] = [];
  const sport = data.sport;

  if (sport === 'walking' && data.steps) {
    parts.push(`${data.steps.toLocaleString()} steps`);
  }

  if (data.distance_m && data.distance_m > 0) {
    parts.push(formatDistance(data.distance_m));
  }

  if (data.duration_s && data.duration_s > 0) {
    parts.push(formatDuration(data.duration_s));
  }

  if (data.avg_hr) {
    parts.push(`${data.avg_hr} bpm`);
  }

  return parts.join(' · ');
}

function getLocationAndTime(data: Props['data']): string {
  const parts: string[] = [];
  if (data.name) {
    const cleanName = data.name
      .replace(/ (Running|Walking|Cycling|Hiking)$/i, '')
      .trim();
    if (cleanName) parts.push(cleanName);
  }
  parts.push(formatTime(data.start_time));
  return parts.join(' · ');
}

export function RecentCrossTrainingCard({ data }: Props) {
  const config = SPORT_MAP[data.sport] ?? SPORT_MAP.walking;
  const Icon = config.icon;
  const metrics = getMetrics(data);
  const subtitle = getLocationAndTime(data);

  return (
    <div className="relative">
      <Link
        href={`/activities/${data.id}`}
        className="block rounded-lg border border-slate-700/30 bg-slate-800/30 hover:bg-slate-800/50 transition-colors px-4 py-3"
      >
        <div className="flex items-start gap-3">
          <div className={`p-1.5 rounded-md border ${config.bg} flex-shrink-0 mt-0.5`}>
            <Icon className={`w-4 h-4 ${config.color}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
              {metrics && (
                <span className="text-sm text-slate-300">{' · '}{metrics}</span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</p>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-600 flex-shrink-0 mt-1" />
        </div>
      </Link>

      {data.additional_count > 0 && (
        <Link
          href="/activities"
          className="absolute right-3 bottom-1.5 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
        >
          +{data.additional_count} more
        </Link>
      )}
    </div>
  );
}
