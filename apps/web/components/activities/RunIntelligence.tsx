'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { Loader2, Brain } from 'lucide-react';

interface Highlight {
  label: string;
  value: string;
  color: string;
}

interface IntelligenceResponse {
  headline: string;
  body: string;
  highlights: Highlight[];
}

const COLOR_CLASSES: Record<string, string> = {
  emerald: 'text-emerald-400',
  green: 'text-green-400',
  yellow: 'text-yellow-400',
  orange: 'text-orange-400',
  red: 'text-red-400',
  slate: 'text-slate-300',
};

export function RunIntelligence({ activityId }: { activityId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['run-intelligence', activityId],
    queryFn: () =>
      apiClient.get<IntelligenceResponse>(
        `/v1/activities/${activityId}/intelligence`
      ),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  if (error || (!isLoading && !data)) return null;

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-700/30 bg-slate-800/30 px-4 py-5 flex items-center justify-center">
        <Loader2 className="w-4 h-4 animate-spin text-slate-500" />
      </div>
    );
  }

  if (!data || (!data.headline && !data.body)) return null;

  return (
    <div className="rounded-lg border border-indigo-500/20 bg-gradient-to-br from-slate-800/60 to-indigo-950/20 px-4 py-4">
      <div className="flex items-center gap-2 mb-2">
        <Brain className="w-4 h-4 text-indigo-400" />
        <span className="text-xs font-semibold uppercase tracking-wide text-indigo-400/80">
          Run Intelligence
        </span>
      </div>

      {data.headline && (
        <p className="text-sm font-medium text-slate-200 leading-snug">
          {data.headline}
        </p>
      )}

      {data.body && (
        <p className="text-sm text-slate-400 leading-relaxed mt-1.5">
          {data.body}
        </p>
      )}

      {data.highlights.length > 0 && (
        <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3 pt-3 border-t border-slate-700/30">
          {data.highlights.map((h) => (
            <span key={h.label} className="text-xs text-slate-400">
              <span className="text-slate-500">{h.label}</span>{' '}
              <span className={`font-medium ${COLOR_CLASSES[h.color] ?? 'text-slate-300'}`}>
                {h.value}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
