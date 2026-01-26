/**
 * Calendar API Service
 * 
 * The calendar is the central UI hub. Everything flows through it.
 * 
 * Provides:
 * - Merged plan + actual view
 * - Day details with notes and insights
 * - Coach chat integration
 */

import { apiClient } from '../client';

// =============================================================================
// TYPES
// =============================================================================

export interface CalendarNote {
  id: string;
  note_date: string;
  note_type: 'pre_workout' | 'post_workout' | 'free_text' | 'voice_memo';
  structured_data?: {
    sleep_hours?: number;
    energy?: string;
    stress?: string;
    weather?: string;
    feel?: string;
    pain?: string;
    fueling?: string;
    mental?: string;
  };
  text_content?: string;
  activity_id?: string;
  created_at: string;
}

export interface CalendarInsight {
  id: string;
  insight_type: 'workout_comparison' | 'efficiency_trend' | 'pattern_detected' | 'achievement' | 'warning';
  priority: number;
  title: string;
  content: string;
  activity_id?: string;
}

export interface PlannedWorkout {
  id: string;
  plan_id: string;
  scheduled_date: string;
  workout_type: string;
  workout_subtype?: string;
  title: string;
  description?: string;
  phase: string;
  week_number: number;  // Required for week summary grouping
  target_distance_km?: number;
  target_duration_minutes?: number;
  segments?: any;
  completed: boolean;
  skipped: boolean;
  coach_notes?: string;
  
  // Option A/B support
  has_option_b?: boolean;
  option_b_title?: string;
  option_b_description?: string;
  option_b_segments?: any;
  selected_option?: 'A' | 'B';
}

export interface ActivitySummary {
  id: string;
  name?: string;
  start_time: string;
  distance_m?: number;
  duration_s?: number;
  avg_hr?: number;
  workout_type?: string;
  intensity_score?: number;
}

export interface InlineInsight {
  metric: 'efficiency' | 'hr' | 'pace' | 'drift' | 'consistency' | 'distance';
  value: string;
  delta?: number;
  sentiment: 'positive' | 'negative' | 'neutral';
}

export interface CalendarDay {
  date: string;
  day_of_week: number;  // 0=Monday, 6=Sunday
  day_name: string;
  planned_workout?: PlannedWorkout;
  activities: ActivitySummary[];
  status: 'future' | 'completed' | 'modified' | 'missed' | 'rest';
  notes: CalendarNote[];
  insights: CalendarInsight[];
  inline_insight?: InlineInsight;  // Single key metric for calendar cell display
  total_distance_m: number;
  total_duration_s: number;
}

export interface WeekSummary {
  week_number: number;
  phase?: string;
  phase_week?: number;
  planned_miles: number;
  completed_miles: number;
  quality_sessions_planned: number;
  quality_sessions_completed: number;
  long_run_planned_miles?: number;
  long_run_completed_miles?: number;
  focus?: string;
  days: CalendarDay[];
}

export interface ActivePlan {
  id: string;
  name: string;
  goal_race_name?: string;
  goal_race_date?: string;
  total_weeks: number;
}

export interface CalendarRangeResponse {
  start_date: string;
  end_date: string;
  active_plan?: ActivePlan;
  current_week?: number;
  current_phase?: string;
  days: CalendarDay[];
  week_summaries: WeekSummary[];
}

export interface CoachMessageRequest {
  message: string;
  context_type: 'day' | 'week' | 'build' | 'open';
  context_date?: string;
  context_week?: number;
  chat_id?: string;
}

export interface CoachMessageResponse {
  chat_id: string;
  response: string;
  context_type: string;
}

export interface CreateNoteRequest {
  note_type: 'pre_workout' | 'post_workout' | 'free_text' | 'voice_memo';
  structured_data?: Record<string, any>;
  text_content?: string;
  activity_id?: string;
}

// =============================================================================
// SERVICE
// =============================================================================

export const calendarService = {
  /**
   * Get calendar data for a date range
   */
  async getCalendar(startDate?: string, endDate?: string): Promise<CalendarRangeResponse> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const queryString = params.toString();
    const url = queryString ? `/v1/calendar?${queryString}` : '/v1/calendar';
    
    return apiClient.get(url);
  },

  /**
   * Get full details for a specific day
   */
  async getDay(date: string): Promise<CalendarDay> {
    return apiClient.get(`/v1/calendar/${date}`);
  },

  /**
   * Get detailed view of a specific training week
   */
  async getWeek(weekNumber: number): Promise<WeekSummary> {
    return apiClient.get(`/v1/calendar/week/${weekNumber}`);
  },

  /**
   * Add a note to a calendar day
   */
  async addNote(date: string, note: CreateNoteRequest): Promise<CalendarNote> {
    return apiClient.post(`/v1/calendar/${date}/notes`, note);
  },

  /**
   * Delete a note
   */
  async deleteNote(date: string, noteId: string): Promise<void> {
    return apiClient.delete(`/v1/calendar/${date}/notes/${noteId}`);
  },

  /**
   * Send a message to the coach
   */
  async sendCoachMessage(
    request: CoachMessageRequest,
    options?: { signal?: AbortSignal; timeoutMs?: number }
  ): Promise<CoachMessageResponse> {
    // Coach can legitimately take longer (tool calls + run)
    return apiClient.post('/v1/calendar/coach', request, {
      signal: options?.signal,
      timeoutMs: options?.timeoutMs ?? 120000,
      // Never retry chat POSTs: retries can multiply perceived latency and can duplicate messages.
      retries: 0,
    });
  },
};
