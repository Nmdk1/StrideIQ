/**
 * Plan Generation API Service
 * 
 * Provides access to the plan generation system.
 */

import { apiClient } from '../client';

// =============================================================================
// TYPES
// =============================================================================

export interface PlanPhase {
  name: string;
  phase_type: string;
  weeks: number[];
  focus: string;
}

export interface WorkoutSegment {
  name: string;
  distance_miles?: number;
  duration_minutes?: number;
  pace_description: string;
}

export interface GeneratedWorkout {
  week: number;
  day: number;
  day_name: string;
  date?: string;
  workout_type: string;
  title: string;
  description: string;
  phase: string;
  phase_name: string;
  distance_miles: number;
  duration_minutes: number;
  pace_description: string;
  segments?: WorkoutSegment[];
  option: 'A' | 'B';
  has_option_b: boolean;
}

export interface GeneratedPlan {
  plan_tier: 'standard' | 'semi_custom' | 'custom';
  distance: string;
  duration_weeks: number;
  volume_tier: string;
  days_per_week: number;
  rpi?: number;
  start_date?: string;
  end_date?: string;
  race_date?: string;
  phases: PlanPhase[];
  workouts: GeneratedWorkout[];
  weekly_volumes: number[];
  peak_volume: number;
  total_miles: number;
  total_quality_sessions: number;
}

export interface PlanOptions {
  distances: string[];
  durations: number[];
  volume_tiers: { value: string; label: string; range: string }[];
  days_options: number[];
}

export interface StandardPlanRequest {
  distance: string;
  duration_weeks: number;
  days_per_week: number;
  volume_tier: string;
  start_date?: string;
  race_name?: string;
}

export interface SemiCustomPlanRequest {
  distance: string;
  race_date: string;
  days_per_week: number;
  current_weekly_miles: number;
  recent_race_distance?: string;
  recent_race_time_seconds?: number;  // Seconds, not string
  race_name?: string;
}

export interface CustomPlanRequest {
  distance: string;
  race_date: string;
  race_name?: string;
  days_per_week: number;
  current_weekly_miles?: number;
  current_long_run_miles?: number;
  recent_race_distance?: string;
  recent_race_time_seconds?: number;
  goal_time_seconds?: number;
  preferred_quality_day?: number;  // 0=Mon, 6=Sun
  preferred_long_run_day?: number;
  injury_history?: Record<string, unknown>;
}

// Model-Driven Plan (ADR-022)
export interface ModelDrivenPlanRequest {
  race_date: string;
  race_distance: string;
  goal_time_seconds?: number;
  force_recalibrate?: boolean;
}

// Tune-Up Race
export interface TuneUpRace {
  date: string;
  distance: string;
  name?: string;
  purpose: 'threshold' | 'sharpening' | 'tune_up' | 'fitness_check';
}

// Constraint-Aware Plan (ADR-030, ADR-031)
export interface ConstraintAwarePlanRequest {
  race_date: string;
  race_distance: string;
  goal_time_seconds?: number;
  tune_up_races?: TuneUpRace[];
  race_name?: string;
}

export interface FitnessBank {
  peak: {
    weekly_miles: number;
    monthly_miles: number;
    long_run: number;
    mp_long_run: number;
    ctl: number;
  };
  current: {
    weekly_miles: number;
    ctl: number;
    atl: number;
  };
  best_rpi: number;
  races: Array<{
    date: string;
    distance: string;
    finish_time: number;
    pace_per_mile: number;
    rpi: number;
    conditions: string | null;
  }>;
  tau1: number;
  tau2: number;
  experience: string;
  constraint: {
    type: string;
    details: string | null;
    returning: boolean;
  };
  projections: {
    weeks_to_80pct: number;
    weeks_to_race_ready: number;
    sustainable_peak: number;
  };
}

export interface ConstraintAwarePlanResponse {
  success: boolean;
  plan_id: string;
  race: {
    date: string;
    distance: string;
    name?: string;
  };
  fitness_bank: FitnessBank;
  model: {
    confidence: string;
    tau1: number;
    tau2: number;
    insights: string[];
  };
  prediction: {
    time: string;
    confidence_interval: string;
  };
  personalization: {
    notes: string[];
    tune_up_races: TuneUpRace[];
  };
  summary: {
    total_weeks: number;
    total_miles: number;
    peak_miles: number;
  };
  weeks: Array<{
    week: number;
    theme: string;
    start_date: string;
    days: Array<{
      day_of_week: number;
      workout_type: string;
      name: string;
      description: string;
      target_miles: number;
      intensity: string;
      paces: Record<string, string>;
      notes: string[];
      tss: number;
    }>;
    total_miles: number;
    notes: string[];
  }>;
  generated_at: string;
}

export interface ConstraintAwarePreview {
  fitness_bank: FitnessBank;
  race: {
    date: string;
    distance: string;
    weeks_out: number;
  };
  model: {
    tau1: number;
    tau2: number;
    experience: string;
    insights: string[];
  };
  constraint: {
    type: string;
    details: string | null;
    returning: boolean;
  };
  projections: {
    weeks_to_race_ready: number;
    sustainable_peak: number;
  };
  patterns: {
    long_run_day: string | null;
    quality_day: string | null;
  };
}

export interface ModelDrivenPlanResponse {
  plan_id: string;
  race: {
    date: string;
    distance: string;
    distance_m: number;
  };
  prediction: {
    prediction: {
      time_seconds: number;
      time_formatted: string;
      confidence_interval_seconds: number;
      confidence_interval_formatted: string;
      confidence: string;
    };
    projections: {
      rpi: number;
      ctl: number;
      tsb: number;
    };
    factors: string[];
    notes: string[];
  };
  model: {
    confidence: string;
    tau1: number;
    tau2: number;
    insights: string[];
  };
  personalization: {
    taper_start_week: number;
    notes: string[];
    summary: string;
  };
  weeks: Array<{
    week_number: number;
    start_date: string;
    end_date: string;
    phase: string;
    target_tss: number;
    target_miles: number;
    is_cutback: boolean;
    notes: string[];
    days: Array<{
      date: string;
      day_of_week: string;
      workout_type: string;
      name: string;
      description: string;
      target_tss: number;
      target_miles: number | null;
      target_pace: string | null;
      intensity: string;
      notes: string[];
    }>;
  }>;
  summary: {
    total_weeks: number;
    total_miles: number;
    total_tss: number;
  };
  generated_at: string;
}

// =============================================================================
// API METHODS
// =============================================================================

export const planService = {
  /**
   * Get available plan options
   */
  async getOptions(): Promise<PlanOptions> {
    return apiClient.get<PlanOptions>('/v2/plans/options');
  },

  /**
   * Get volume tier classification for current weekly miles
   */
  async classifyTier(weeklyMiles: number, distance: string = 'marathon') {
    return apiClient.get<{ tier: string; label: string; range: string }>(
      `/v2/plans/classify-tier?weekly_miles=${weeklyMiles}&distance=${distance}`
    );
  },

  /**
   * Preview a standard plan (without creating it)
   */
  async previewStandard(request: StandardPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/standard/preview', request);
  },

  /**
   * Create a standard (free) plan
   */
  async createStandard(request: StandardPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/standard', request);
  },

  /**
   * Create a semi-custom plan ($5 or included with paid tier)
   * Uses user-provided race time for pace calculation.
   */
  async createSemiCustom(request: SemiCustomPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/semi-custom', request);
  },

  /**
   * Create a fully custom plan (Elite tier)
   * Uses user-provided race time OR Strava data for pace calculation.
   */
  async createCustom(request: CustomPlanRequest): Promise<GeneratedPlan> {
    return apiClient.post<GeneratedPlan>('/v2/plans/custom', request);
  },

  /**
   * Create a model-driven plan (Elite tier only)
   * Uses Individual Performance Model (τ1/τ2) calibrated from YOUR data.
   * ADR-022, ADR-025
   */
  async createModelDriven(request: ModelDrivenPlanRequest): Promise<ModelDrivenPlanResponse> {
    return apiClient.post<ModelDrivenPlanResponse>('/v2/plans/model-driven', request);
  },

  /**
   * Preview model insights without generating full plan
   */
  async previewModelDriven(raceDate: string, raceDistance: string): Promise<{
    model: {
      confidence: string;
      tau1: number;
      tau2: number;
      insights: string[];
      can_calibrate: boolean;
    };
    prediction: {
      prediction: {
        time_seconds: number;
        time_formatted: string;
        confidence: string;
      };
    } | null;
    race_date: string;
    race_distance: string;
  }> {
    return apiClient.get(`/v2/plans/model-driven/preview?race_date=${raceDate}&race_distance=${raceDistance}`);
  },

  /**
   * Create a constraint-aware plan (Elite tier only)
   * Uses the Fitness Bank Framework (ADR-030, ADR-031):
   * - Analyzes full training history
   * - Detects constraints (injury, reduced volume)
   * - Generates week themes with alternation
   * - Prescribes specific workouts with personal paces
   * - Handles tune-up races
   */
  async createConstraintAware(request: ConstraintAwarePlanRequest): Promise<ConstraintAwarePlanResponse> {
    return apiClient.post<ConstraintAwarePlanResponse>('/v2/plans/constraint-aware', request);
  },

  /**
   * Preview Fitness Bank insights without generating full plan
   * Shows what we know about the athlete's capabilities and constraints
   */
  async previewConstraintAware(raceDate: string, raceDistance: string): Promise<ConstraintAwarePreview> {
    return apiClient.get<ConstraintAwarePreview>(
      `/v2/plans/constraint-aware/preview?race_date=${raceDate}&race_distance=${raceDistance}`
    );
  },
};
