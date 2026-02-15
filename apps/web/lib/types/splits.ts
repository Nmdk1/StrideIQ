/**
 * Shared Split type — used by activity page, SplitsTable, and RunShapeCanvas SplitsModePanel.
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
}
