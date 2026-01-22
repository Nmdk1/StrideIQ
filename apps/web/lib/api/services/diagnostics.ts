import { apiClient } from '../client';

export type DiagnosticsOverallStatus = 'ready' | 'degraded' | 'blocked';

export interface ProviderHealth {
  provider: 'strava' | 'garmin';
  connected: boolean;
  last_sync_at?: string | null;
  detail?: string | null;
}

export interface IngestionStatus {
  provider: string;
  coverage_pct: number;
  total_activities: number;
  activities_processed: number;
  remaining_activities: number;
  last_provider_sync_at?: string | null;
  last_task_status?: string | null;
  last_task_error?: string | null;
  last_task_retry_after_s?: number | null;
}

export interface CompletenessCounts {
  activities_total: number;
  activities_with_hr: number;
  activities_with_splits: number;
  splits_total: number;
  splits_with_gap: number;
  checkins_total: number;
  checkins_with_hrv: number;
  personal_bests: number;
}

export interface ModelReadiness {
  efficiency_trend_ready: boolean;
  load_response_ready: boolean;
  trend_attribution_ready: boolean;
  personal_bests_ready: boolean;
  notes: string[];
}

export type ActionSeverity = 'critical' | 'recommended' | 'optional';

export interface RecommendedAction {
  id: string;
  severity: ActionSeverity;
  title: string;
  detail: string;
  href: string;
}

export interface DiagnosticsSummaryResponse {
  generated_at: string;
  overall_status: DiagnosticsOverallStatus;
  provider_health: ProviderHealth[];
  ingestion?: IngestionStatus | null;
  completeness: CompletenessCounts;
  model_readiness: ModelReadiness;
  actions: RecommendedAction[];
}

export const diagnosticsService = {
  async getSummary(): Promise<DiagnosticsSummaryResponse> {
    return apiClient.get<DiagnosticsSummaryResponse>('/v1/admin/diagnostics/summary');
  },
};

