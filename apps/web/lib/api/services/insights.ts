import { apiClient } from '../client';

// Types
export interface Insight {
  id: string;
  insight_type: string;
  priority: number;
  title: string;
  content: string;
  insight_date: string;
  activity_id?: string;
  data?: Record<string, unknown>;
  is_dismissed: boolean;
}

export interface ActiveInsightsResponse {
  insights: Insight[];
  is_premium: boolean;
  total_available: number;
  premium_locked: number;
}

export interface KPI {
  name: string;
  current_value?: string;
  start_value?: string;
  change?: string;
  trend?: 'up' | 'down' | 'stable';
}

export interface BuildStatusResponse {
  has_active_plan: boolean;
  plan_name?: string;
  current_week?: number;
  total_weeks?: number;
  current_phase?: string;
  phase_focus?: string;
  goal_race_name?: string;
  goal_race_date?: string;
  days_to_race?: number;
  progress_percent?: number;
  kpis: KPI[];
  projected_time?: string;
  confidence?: string;
  week_focus?: string;
  key_session?: string;
}

export interface IntelligenceItem {
  text: string;
  source: 'n1' | 'population';
  confidence?: number;
}

export interface Pattern {
  name: string;
  description: string;
  data?: Record<string, unknown>;
}

export interface AthleteIntelligenceResponse {
  what_works: IntelligenceItem[];
  what_doesnt: IntelligenceItem[];
  patterns: Pattern[];
  injury_patterns: IntelligenceItem[];
  career_prs: Record<string, unknown>;
}

// Service
export const insightsService = {
  async getActiveInsights(limit = 10): Promise<ActiveInsightsResponse> {
    return apiClient.get<ActiveInsightsResponse>(
      `/v1/insights/active?limit=${limit}`
    );
  },

  async getBuildStatus(): Promise<BuildStatusResponse> {
    return apiClient.get<BuildStatusResponse>('/v1/insights/build-status');
  },

  async getAthleteIntelligence(): Promise<AthleteIntelligenceResponse> {
    return apiClient.get<AthleteIntelligenceResponse>('/v1/insights/intelligence');
  },

  async dismissInsight(insightId: string): Promise<void> {
    await apiClient.post(`/v1/insights/${insightId}/dismiss`);
  },

  async saveInsight(insightId: string): Promise<void> {
    await apiClient.post(`/v1/insights/${insightId}/save`);
  },

  async generateInsights(): Promise<{ insights_generated: number; insights_saved: number }> {
    return apiClient.post<{ insights_generated: number; insights_saved: number }>(
      '/v1/insights/generate'
    );
  },
};
