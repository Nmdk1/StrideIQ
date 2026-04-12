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
