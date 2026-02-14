/**
 * RSI-Alpha — useStreamAnalysis hook (stub)
 *
 * Placeholder hook. Full implementation wires to
 * GET /v1/activities/{id}/stream-analysis via @tanstack/react-query.
 */

/** ADR-063 lifecycle responses */
export interface StreamLifecycleResponse {
  status: 'pending' | 'unavailable';
}

/** Full analysis + stream payload */
export interface StreamAnalysisData {
  analysis: Record<string, unknown>;
  stream: Record<string, number>[];
}

export type StreamHookData = StreamAnalysisData | StreamLifecycleResponse | null;

export interface UseStreamAnalysisReturn {
  data: StreamHookData;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useStreamAnalysis(_activityId: string): UseStreamAnalysisReturn {
  return {
    data: null,
    isLoading: true,
    error: null,
    refetch: () => {},
  };
}
