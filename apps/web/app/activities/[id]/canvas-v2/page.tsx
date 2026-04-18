'use client';

/**
 * Run Shape Canvas v2 — sandbox route.
 *
 * Lives at /activities/[id]/canvas-v2 in parallel with the existing
 * /activities/[id] page. The existing page is NEVER touched by this branch.
 *
 * Access is gated by `lib/canvasV2/featureGate.ts` to the founder's email
 * in production. Anyone else hitting this URL gets a 404 via Next.js
 * `notFound()`. Override via NEXT_PUBLIC_CANVAS_V2_ALLOWLIST for staging.
 *
 * One-click rollback: delete this directory + redeploy.
 */

import { useEffect, useMemo } from 'react';
import { useParams, notFound } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { isCanvasV2Allowed } from '@/lib/canvasV2/featureGate';
import { API_CONFIG } from '@/lib/api/config';
import { useStreamAnalysis, isAnalysisData } from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { CanvasV2 } from '@/components/canvas-v2/CanvasV2';

interface ActivitySummary {
  id: string;
  name: string | null;
  start_time: string;
  distance_m: number;
  moving_time_s: number;
  elapsed_time_s: number;
  average_hr: number | null;
  average_cadence: number | null;
}

function normalizeCadenceToSpm(raw: number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const v = Number(raw);
  if (!Number.isFinite(v) || v <= 0) return null;
  return v < 120 ? v * 2 : v;
}

function formatDateLine(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export default function CanvasV2Page() {
  const params = useParams();
  const activityId = params.id as string;
  const { user, token, isLoading: authLoading, isAuthenticated } = useAuth();

  const allowed = isAuthenticated && isCanvasV2Allowed(user?.email);

  useEffect(() => {
    if (authLoading) return;
    if (!allowed) notFound();
  }, [authLoading, allowed]);

  const activityQuery = useQuery<ActivitySummary>({
    queryKey: ['activity', activityId],
    queryFn: async () => {
      const res = await fetch(`${API_CONFIG.baseURL}/v1/activities/${activityId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to fetch activity');
      return res.json();
    },
    enabled: allowed && !!token && !!activityId,
  });

  const streamQuery = useStreamAnalysis(allowed ? activityId : '');

  const summary = useMemo(() => {
    const a = activityQuery.data;
    const sa = isAnalysisData(streamQuery.data) ? streamQuery.data : null;
    return {
      cardiacDriftPct: sa?.drift?.cardiac_pct ?? null,
      avgHrBpm: a?.average_hr ?? null,
      avgCadenceSpm: normalizeCadenceToSpm(a?.average_cadence ?? null),
      maxGradePct: maxGrade(sa?.stream),
      totalMovingTimeS: a?.moving_time_s ?? a?.elapsed_time_s ?? null,
    };
  }, [activityQuery.data, streamQuery.data]);

  if (authLoading || !allowed) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="text-slate-500 text-sm">Loading…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 py-6">
        <CanvasV2
          activityId={activityId}
          summary={summary}
          title={activityQuery.data?.name ?? 'Run'}
          subtitle={
            activityQuery.data
              ? `${formatDateLine(activityQuery.data.start_time)} · sandbox`
              : 'Sandbox preview'
          }
        />
      </div>
    </div>
  );
}

function maxGrade(stream: { grade: number | null }[] | null | undefined): number | null {
  if (!stream || stream.length === 0) return null;
  let max: number | null = null;
  for (const p of stream) {
    if (p.grade !== null && Number.isFinite(p.grade)) {
      if (max === null || p.grade > max) max = p.grade;
    }
  }
  return max;
}
