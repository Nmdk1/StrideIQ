/**
 * RSI-Alpha — Shared Test Fixtures
 *
 * Mock data conforming to the StreamAnalysisResult contract.
 * Used by all rsi-canvas-*.test.tsx files.
 */

// ── Types (will be replaced by imports from components/activities/rsi/types.ts) ──

export interface Segment {
  type: 'warmup' | 'work' | 'recovery' | 'cooldown' | 'steady';
  start_time_s: number;
  end_time_s: number;
  avg_hr: number | null;
  avg_pace_sec_per_km: number | null;
  avg_cadence: number | null;
  avg_grade: number | null;
}

export interface DriftAnalysis {
  cardiac_drift_pct: number | null;
  pace_drift_pct: number | null;
  cadence_trend_bpm_per_km: number | null;
}

export interface PlanComparison {
  planned_duration_s: number;
  actual_duration_s: number;
  planned_distance_m: number | null;
  actual_distance_m: number | null;
  planned_pace_sec_per_km: number | null;
  actual_pace_sec_per_km: number | null;
  interval_count_planned: number | null;
  interval_count_actual: number | null;
}

export interface StreamAnalysisResult {
  segments: Segment[];
  drift: DriftAnalysis;
  moments: Array<Record<string, unknown>>;
  plan_comparison: PlanComparison | null;
  channels_present: string[];
  channels_missing: string[];
  point_count: number;
  confidence: number;
  tier_used: string;
  estimated_flags: string[];
  cross_run_comparable: boolean;
}

export interface StreamPoint {
  time: number;
  hr: number;
  pace: number;
  altitude: number;
  grade: number;
  cadence: number;
  effort: number;
}

// ── Tier 1 analysis result (easy run, 1 hour) ──

export const mockTier1Result: StreamAnalysisResult = {
  segments: [
    { type: 'warmup', start_time_s: 0, end_time_s: 480, avg_hr: 135, avg_pace_sec_per_km: 345, avg_cadence: 170, avg_grade: 0.5 },
    { type: 'work', start_time_s: 480, end_time_s: 720, avg_hr: 172, avg_pace_sec_per_km: 210, avg_cadence: 190, avg_grade: 1.0 },
    { type: 'recovery', start_time_s: 720, end_time_s: 900, avg_hr: 150, avg_pace_sec_per_km: 350, avg_cadence: 172, avg_grade: -0.5 },
    { type: 'work', start_time_s: 900, end_time_s: 1140, avg_hr: 175, avg_pace_sec_per_km: 208, avg_cadence: 192, avg_grade: 0.8 },
    { type: 'cooldown', start_time_s: 1140, end_time_s: 1380, avg_hr: 128, avg_pace_sec_per_km: 370, avg_cadence: 165, avg_grade: -0.3 },
  ],
  drift: {
    cardiac_drift_pct: 4.2,
    pace_drift_pct: 1.8,
    cadence_trend_bpm_per_km: -0.3,
  },
  moments: [],
  plan_comparison: null,
  channels_present: ['hr', 'pace', 'altitude', 'cadence', 'grade'],
  channels_missing: ['power'],
  point_count: 1380,
  confidence: 0.88,
  tier_used: 'tier1_threshold_hr',
  estimated_flags: [],
  cross_run_comparable: true,
};

// ── Tier 4 analysis result (no physiological data) ──

export const mockTier4Result: StreamAnalysisResult = {
  ...mockTier1Result,
  tier_used: 'tier4_stream_relative',
  confidence: 0.42,
  cross_run_comparable: false,
  estimated_flags: ['stream_relative_classification'],
};

// ── Result with plan comparison ──

export const mockResultWithPlan: StreamAnalysisResult = {
  ...mockTier1Result,
  plan_comparison: {
    planned_duration_s: 3600,
    actual_duration_s: 3720,
    planned_distance_m: 10000,
    actual_distance_m: 10250,
    planned_pace_sec_per_km: 360,
    actual_pace_sec_per_km: 363,
    interval_count_planned: 6,
    interval_count_actual: 5,
  },
};

// ── Result with no segments (edge case) ──

export const mockEmptyResult: StreamAnalysisResult = {
  segments: [],
  drift: { cardiac_drift_pct: null, pace_drift_pct: null, cadence_trend_bpm_per_km: null },
  moments: [],
  plan_comparison: null,
  channels_present: ['hr'],
  channels_missing: ['pace', 'altitude', 'cadence', 'grade'],
  point_count: 300,
  confidence: 0.15,
  tier_used: 'tier4_stream_relative',
  estimated_flags: ['minimal_channels'],
  cross_run_comparable: false,
};

// ── Lifecycle status responses ──

export const mockPendingResponse = { status: 'pending' as const };
export const mockUnavailableResponse = { status: 'unavailable' as const };

// ── Synthetic stream data (simplified for tests) ──

export function generateTestStreamData(count: number = 100): StreamPoint[] {
  const points: StreamPoint[] = [];
  for (let i = 0; i < count; i++) {
    const t = i / count;
    points.push({
      time: i,
      hr: 120 + Math.round(60 * t + 5 * Math.sin(i * 0.1)),
      pace: 360 - Math.round(80 * t),
      altitude: 100 + 10 * Math.sin(i * 0.05),
      grade: 2 * Math.sin(i * 0.05),
      cadence: 170 + Math.round(10 * t),
      effort: 0.6 + 0.4 * t,
    });
  }
  return points;
}
