/**
 * RSI-Alpha — Shared Test Fixtures
 *
 * Mock data conforming to the REAL backend StreamAnalysisResult contract.
 * Field names match Python dataclass in apps/api/services/run_stream_analysis.py EXACTLY.
 *
 * CANONICAL CONTRACT — do not rename fields here without verifying backend.
 * See also: rsi-contract.test.ts for contract enforcement tests.
 */

// ── Types (match backend dataclasses exactly) ──

export interface Segment {
  type: 'warmup' | 'work' | 'recovery' | 'cooldown' | 'steady';
  start_index: number;
  end_index: number;
  start_time_s: number;
  end_time_s: number;
  duration_s: number;
  avg_pace_s_km: number | null;       // Backend: avg_pace_s_km (NOT avg_pace_sec_per_km)
  avg_hr: number | null;
  avg_cadence: number | null;
  avg_grade: number | null;
}

export interface DriftAnalysis {
  cardiac_pct: number | null;          // Backend: cardiac_pct (NOT cardiac_drift_pct)
  pace_pct: number | null;             // Backend: pace_pct (NOT pace_drift_pct)
  cadence_trend_bpm_per_km: number | null;
}

export interface PlanComparison {
  planned_duration_min: number | null;  // Backend: minutes (NOT seconds)
  actual_duration_min: number | null;
  duration_delta_min: number | null;
  planned_distance_km: number | null;   // Backend: km (NOT meters)
  actual_distance_km: number | null;
  distance_delta_km: number | null;
  planned_pace_s_km: number | null;     // Backend: s/km (NOT sec_per_km)
  actual_pace_s_km: number | null;
  pace_delta_s_km: number | null;
  planned_interval_count: number | null; // Backend: planned_interval_count
  detected_work_count: number | null;    // Backend: detected_work_count (NOT interval_count_actual)
  interval_count_match: boolean | null;
}

export interface Moment {
  type: string;
  index: number;
  time_s: number;
  value: number | null;
  context: string | null;               // Backend: context (NOT label)
}

export interface StreamAnalysisResult {
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
}

export interface StreamPoint {
  time: number;
  hr: number | null;
  pace: number | null;
  altitude: number | null;
  grade: number | null;
  cadence: number | null;
  effort: number;
}

// ── Tier 1 analysis result (easy run, 1 hour) ──

export const mockTier1Result: StreamAnalysisResult = {
  segments: [
    { type: 'warmup', start_index: 0, end_index: 480, start_time_s: 0, end_time_s: 480, duration_s: 480, avg_hr: 135, avg_pace_s_km: 345, avg_cadence: 170, avg_grade: 0.5 },
    { type: 'work', start_index: 480, end_index: 720, start_time_s: 480, end_time_s: 720, duration_s: 240, avg_hr: 172, avg_pace_s_km: 210, avg_cadence: 190, avg_grade: 1.0 },
    { type: 'recovery', start_index: 720, end_index: 900, start_time_s: 720, end_time_s: 900, duration_s: 180, avg_hr: 150, avg_pace_s_km: 350, avg_cadence: 172, avg_grade: -0.5 },
    { type: 'work', start_index: 900, end_index: 1140, start_time_s: 900, end_time_s: 1140, duration_s: 240, avg_hr: 175, avg_pace_s_km: 208, avg_cadence: 192, avg_grade: 0.8 },
    { type: 'cooldown', start_index: 1140, end_index: 1380, start_time_s: 1140, end_time_s: 1380, duration_s: 240, avg_hr: 128, avg_pace_s_km: 370, avg_cadence: 165, avg_grade: -0.3 },
  ],
  drift: {
    cardiac_pct: 4.2,
    pace_pct: 1.8,
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
  effort_intensity: [],
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
    planned_duration_min: 60.0,
    actual_duration_min: 62.0,
    duration_delta_min: 2.0,
    planned_distance_km: 10.0,
    actual_distance_km: 10.25,
    distance_delta_km: 0.25,
    planned_pace_s_km: 360,
    actual_pace_s_km: 363,
    pace_delta_s_km: 3,
    planned_interval_count: 6,
    detected_work_count: 5,
    interval_count_match: false,
  },
};

// ── Result with no segments (edge case) ──

export const mockEmptyResult: StreamAnalysisResult = {
  segments: [],
  drift: { cardiac_pct: null, pace_pct: null, cadence_trend_bpm_per_km: null },
  moments: [],
  plan_comparison: null,
  channels_present: ['hr'],
  channels_missing: ['pace', 'altitude', 'cadence', 'grade'],
  point_count: 300,
  confidence: 0.15,
  tier_used: 'tier4_stream_relative',
  estimated_flags: ['minimal_channels'],
  cross_run_comparable: false,
  effort_intensity: [],
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
