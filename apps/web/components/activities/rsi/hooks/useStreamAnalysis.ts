/**
 * RSI-Alpha — useStreamAnalysis hook
 *
 * Fetches GET /v1/activities/{id}/stream-analysis via @tanstack/react-query.
 *
 * CANONICAL CONTRACT: Types below match the Python dataclass field names
 * in apps/api/services/run_stream_analysis.py exactly. Backend is the
 * source of truth. Do not rename fields here — if there's a mismatch,
 * the backend wins.
 *
 * Returns:
 *   - Full StreamAnalysisData when stream_fetch_status === 'success'
 *   - { status: 'pending' } when streams are still being fetched
 *     (backend collapses fetching/failed/None into 'pending')
 *   - { status: 'unavailable' } for manual activities without GPS
 *   - null while loading
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

// ── Types (match backend dataclasses exactly) ──

export interface Segment {
  type: 'warmup' | 'work' | 'recovery' | 'cooldown' | 'steady';
  start_index: number;
  end_index: number;
  start_time_s: number;
  end_time_s: number;
  duration_s: number;
  avg_pace_s_km: number | null;
  avg_hr: number | null;
  avg_cadence: number | null;
  avg_grade: number | null;
}

export interface DriftAnalysis {
  cardiac_pct: number | null;
  pace_pct: number | null;
  cadence_trend_bpm_per_km: number | null;
}

export interface PlanComparison {
  planned_duration_min: number | null;
  actual_duration_min: number | null;
  duration_delta_min: number | null;
  planned_distance_km: number | null;
  actual_distance_km: number | null;
  distance_delta_km: number | null;
  planned_pace_s_km: number | null;
  actual_pace_s_km: number | null;
  pace_delta_s_km: number | null;
  planned_interval_count: number | null;
  detected_work_count: number | null;
  interval_count_match: boolean | null;
}

export interface Moment {
  type: string;
  index: number;
  time_s: number;
  value: number | null;
  context: string | null;  // Short enum-level label, not prose
}

/** Per-point stream data for canvas visualization (server-side LTTB ≤500 points) */
export interface StreamPoint {
  time: number;
  hr: number | null;
  pace: number | null;        // seconds per km
  altitude: number | null;
  grade: number | null;
  cadence: number | null;     // SPM (already doubled from Strava half-strides)
  effort: number;             // [0.0, 1.0]
}

export interface StreamAnalysisData {
  // Analysis result (flat — matches backend StreamAnalysisResult dataclass)
  segments: Segment[];
  drift: DriftAnalysis;
  moments: Moment[];
  plan_comparison: PlanComparison | null;
  channels_present: string[];
  channels_missing: string[];
  point_count: number;
  confidence: number;
  tier_used: string;
  estimated_flags: string[];
  cross_run_comparable: boolean;
  effort_intensity: number[];
  // Per-point stream data (added by router, not in dataclass)
  stream: StreamPoint[];
}

/** ADR-063 lifecycle responses (backend collapses fetching/failed/None → 'pending') */
export interface StreamLifecycleResponse {
  status: 'pending' | 'unavailable';
}

export type StreamHookData = StreamAnalysisData | StreamLifecycleResponse | null;

export interface UseStreamAnalysisReturn {
  data: StreamHookData;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

/** Type guard: is the response a full analysis (not a lifecycle status)? */
export function isAnalysisData(data: StreamHookData): data is StreamAnalysisData {
  return data !== null && !('status' in data) && 'segments' in data;
}

/** Type guard: is the response a lifecycle status (pending/unavailable)? */
export function isLifecycleResponse(data: StreamHookData): data is StreamLifecycleResponse {
  return data !== null && 'status' in data;
}

export function useStreamAnalysis(activityId: string): UseStreamAnalysisReturn {
  const { data, isLoading, error, refetch } = useQuery<StreamHookData>({
    queryKey: ['stream-analysis', activityId],
    queryFn: async () => {
      const result = await apiClient.get<Record<string, unknown>>(
        `/v1/activities/${activityId}/stream-analysis`
      );
      // Backend returns { status: 'pending' | 'unavailable' } for lifecycle states
      if ('status' in result && (result.status === 'pending' || result.status === 'unavailable')) {
        return result as unknown as StreamLifecycleResponse;
      }
      // Otherwise it's the full analysis result
      return result as unknown as StreamAnalysisData;
    },
    enabled: !!activityId,
    staleTime: 1000 * 60 * 10, // 10 minutes — analysis doesn't change often
    retry: (failureCount, error) => {
      // Don't retry 404s
      if (error instanceof Error && error.message.includes('404')) return false;
      return failureCount < 2;
    },
  });

  return {
    data: data ?? null,
    isLoading,
    error: error ?? null,
    refetch,
  };
}
