/**
 * Shared Split type — used by activity page Splits tab, SplitsTable, and RunShapeCanvas (split boundary math).
 *
 * Matches the backend /v1/activities/{id}/splits response shape.
 */
export interface Split {
  split_number: number;
  distance: number | null;       // meters
  elapsed_time: number | null;   // seconds
  moving_time: number | null;    // seconds
  average_heartrate: number | null;
  max_heartrate: number | null;
  average_cadence: number | null;
  gap_seconds_per_mile: number | null;
  lap_type: string | null;       // warm_up, work, rest, cool_down
  interval_number: number | null;

  // FIT-derived per-lap metrics (Phase 1 / fit_run_001).
  // All nullable: only populated when a FIT file landed and the athlete
  // wears a sensor that records the metric (e.g., HRM-Pro for running
  // dynamics, Stryd / Forerunner Pro for power).
  total_ascent_m?: number | null;
  total_descent_m?: number | null;
  avg_power_w?: number | null;
  max_power_w?: number | null;
  avg_stride_length_m?: number | null;
  avg_ground_contact_ms?: number | null;
  avg_vertical_oscillation_cm?: number | null;
  avg_vertical_ratio_pct?: number | null;
  // Long-tail metrics — GCT balance, normalized power, max cadence,
  // per-lap kcal/temp/lap-trigger. Bag of name->number.
  extras?: Record<string, number | string | null> | null;
}

export interface IntervalSummary {
  is_structured: boolean;
  workout_description: string | null;
  num_work_intervals: number;
  avg_work_pace_sec_per_km: number | null;
  avg_work_hr: number | null;
  avg_rest_duration_s: number | null;
  avg_rest_hr: number | null;
  fastest_interval: number | null;
  slowest_interval: number | null;
}

export interface SplitsResponse {
  splits: Split[];
  interval_summary: IntervalSummary | null;
}
