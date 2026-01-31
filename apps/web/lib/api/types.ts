/**
 * Shared TypeScript Types
 * 
 * These types mirror the backend Pydantic schemas.
 * When backend schemas change, update these types accordingly.
 * 
 * This allows for:
 * - Type safety across frontend/backend boundary
 * - Easy refactoring
 * - Single source of truth for API contracts
 */

export type UUID = string;

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Activity {
  id: UUID;
  strava_id?: number;
  name: string;
  distance: number; // meters
  moving_time: number; // seconds
  start_date: string; // ISO format
  average_speed: number; // m/s
  max_hr?: number;
  average_heartrate?: number;
  average_cadence?: number;
  total_elevation_gain?: number;
  pace_per_mile?: string; // Formatted as "MM:SS/mi"
  duration_formatted?: string; // Formatted as "HH:MM:SS" or "MM:SS"
  splits?: Array<{
    split: number;
    distance: number;
    elapsed_time: number;
    moving_time: number;
    average_heartrate?: number;
    max_heartrate?: number;
    average_cadence?: number;
    pace_per_mile?: string;
  }>;
  performance_percentage?: number;
  performance_percentage_national?: number;
  is_race_candidate?: boolean;
  race_confidence?: number;
  // Workout classification
  workout_type?: string;           // The type/structure of the workout (easy_run, tempo_run, etc.)
  workout_zone?: string;           // INTERNAL USE ONLY - not shown to athletes. See 01_INTENSITY_PHILOSOPHY.md
  workout_confidence?: number;     // 0-1 confidence in the classification
  intensity_score?: number;        // 0-100 continuous intensity spectrum
}

export interface ActivityAnalysis {
  has_meaningful_insight: boolean;
  insights: string[];
  metrics: {
    pace_per_mile?: number;
    avg_heart_rate?: number;
    efficiency_score?: number;
  };
  comparisons: Array<{
    baseline_type: string;
    baseline_pace: number;
    baseline_hr: number;
    improvement_pct: number;
    is_meaningful: boolean;
    is_confirmed_trend: boolean;
    trend_avg_improvement?: number;
    sample_size: number;
  }>;
  decoupling?: {
    decoupling_percent?: number;
    decoupling_status?: 'green' | 'yellow' | 'red';
    first_half_ef?: number;
    second_half_ef?: number;
    efficiency_factor?: number;
  };
  perception_prompt: {
    should_prompt: boolean;
    prompt_text: string | null;
    required_fields: string[];
    optional_fields: string[];
    has_feedback: boolean;
    run_type: string | null;
  };
}

export interface RunDelivery {
  activity_id: UUID;
  has_meaningful_insight: boolean;
  insights: string[];
  insight_tone: 'irreverent' | 'sparse';
  show_insights: boolean;
  metrics: {
    pace_per_mile?: number;
    avg_heart_rate?: number;
    efficiency_score?: number;
  };
  perception_prompt: {
    should_prompt: boolean;
    prompt_text: string | null;
    required_fields: string[];
    optional_fields: string[];
    has_feedback: boolean;
    run_type: string | null;
  };
  delivery_timestamp: string;
}

export interface ActivityFeedback {
  id: UUID;
  activity_id: UUID;
  athlete_id: UUID;
  perceived_effort?: number; // 1-10
  leg_feel?: 'fresh' | 'normal' | 'tired' | 'heavy' | 'sore' | 'injured';
  mood_pre?: string;
  mood_post?: string;
  energy_pre?: number; // 1-10
  energy_post?: number; // 1-10
  notes?: string;
  submitted_at: string;
  created_at: string;
  updated_at: string;
}

export interface ActivityFeedbackCreate {
  activity_id: UUID;
  perceived_effort?: number;
  leg_feel?: 'fresh' | 'normal' | 'tired' | 'heavy' | 'sore' | 'injured';
  mood_pre?: string;
  mood_post?: string;
  energy_pre?: number;
  energy_post?: number;
  notes?: string;
}

export interface TrainingAvailability {
  id: UUID;
  athlete_id: UUID;
  day_of_week: number; // 0-6 (Sunday-Saturday)
  time_block: 'morning' | 'afternoon' | 'evening';
  status: 'available' | 'preferred' | 'unavailable';
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface TrainingAvailabilityGrid {
  athlete_id: UUID;
  grid: TrainingAvailability[];
  summary: {
    total_slots: number;
    available_slots: number;
    preferred_slots: number;
    unavailable_slots: number;
    total_available_slots: number;
    available_percentage: number;
    preferred_percentage: number;
    total_available_percentage: number;
  };
}

export interface Athlete {
  id: UUID;
  email?: string;
  display_name?: string;
  birthdate?: string;
  sex?: string;
  height_cm?: number;
  subscription_tier: string;
  stripe_customer_id?: string | null;
  trial_started_at?: string | null;
  trial_ends_at?: string | null;
  trial_source?: string | null;
  has_active_subscription?: boolean;
  onboarding_stage?: string;
  onboarding_completed: boolean;
  role?: 'athlete' | 'coach' | 'admin' | 'owner';
  age_category?: string;
  durability_index?: number;
  recovery_half_life_hours?: number;
  consistency_index?: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
  race_code?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  athlete: Athlete;
}

