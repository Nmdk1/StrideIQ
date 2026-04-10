/**
 * Unified Report API Service
 */

import { apiClient } from '../client';

export interface HealthDay {
  sleep_score?: number;
  sleep_total_s?: number;
  sleep_deep_s?: number;
  sleep_light_s?: number;
  sleep_rem_s?: number;
  sleep_awake_s?: number;
  sleep_score_qualifier?: string;
  hrv_overnight_avg?: number;
  hrv_5min_high?: number;
  resting_hr?: number;
  min_hr?: number;
  max_hr?: number;
  avg_stress?: number;
  max_stress?: number;
  stress_qualifier?: string;
  steps?: number;
  active_kcal?: number;
  active_time_s?: number;
  moderate_intensity_s?: number;
  vigorous_intensity_s?: number;
  vo2max?: number;
}

export interface ActivityRow {
  id: string;
  name?: string;
  sport?: string;
  start_time?: string;
  workout_type?: string;
  workout_zone?: string;
  duration_s?: number;
  distance_m?: number;
  avg_hr?: number;
  max_hr?: number;
  avg_pace_min_per_km?: number;
  active_kcal?: number;
  intensity_score?: number;
  total_elevation_gain?: number;
  avg_cadence?: number;
  avg_stride_length_m?: number;
  avg_ground_contact_ms?: number;
  avg_vertical_oscillation_cm?: number;
  avg_power_w?: number;
  performance_percentage?: number;
  temperature_f?: number;
  humidity_pct?: number;
  weather_condition?: string;
  shape_sentence?: string;
  moving_time_s?: number;
}

export interface NutritionRow {
  id: string;
  entry_type: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  caffeine_mg?: number;
  fluid_ml?: number;
  notes?: string;
  macro_source?: string;
}

export interface NutritionDayTotals {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  caffeine_mg: number;
  fluid_ml: number;
  entry_count: number;
}

export interface BodyCompDay {
  weight_kg?: number;
  body_fat_pct?: number;
  muscle_mass_kg?: number;
  bmi?: number;
}

export interface ReportDay {
  date: string;
  health?: HealthDay;
  activities?: ActivityRow[];
  nutrition_entries?: NutritionRow[];
  nutrition_totals?: NutritionDayTotals;
  body_composition?: BodyCompDay;
}

export interface PeriodAverages {
  days: number;
  avg_sleep_score?: number;
  avg_sleep_hours?: number;
  avg_hrv?: number;
  avg_resting_hr?: number;
  avg_stress?: number;
  avg_steps?: number;
  total_activities: number;
  total_distance_m: number;
  total_duration_s: number;
  total_active_kcal: number;
  avg_daily_calories?: number;
  avg_daily_protein_g?: number;
  avg_daily_carbs_g?: number;
  avg_daily_fat_g?: number;
  avg_daily_caffeine_mg?: number;
  nutrition_days_logged: number;
  avg_weight_kg?: number;
}

export interface AvailableMetrics {
  health_curated: string[];
  health_extended: string[];
  activity_curated: string[];
  activity_extended: string[];
  nutrition_curated: string[];
  nutrition_extended: string[];
  body_composition: string[];
}

export interface ReportResponse {
  start_date: string;
  end_date: string;
  categories: string[];
  days: ReportDay[];
  period_averages: PeriodAverages;
  available_metrics: AvailableMetrics;
}

export type ReportCategory = 'health' | 'activities' | 'nutrition' | 'body_composition';

export const reportService = {
  async getReport(params: {
    start_date: string;
    end_date: string;
    categories?: ReportCategory[];
  }): Promise<ReportResponse> {
    const qs = new URLSearchParams();
    qs.set('start_date', params.start_date);
    qs.set('end_date', params.end_date);
    if (params.categories) {
      qs.set('categories', params.categories.join(','));
    }
    return apiClient.get<ReportResponse>(`/v1/reports?${qs.toString()}`);
  },

  getExportCsvUrl(params: {
    start_date: string;
    end_date: string;
    categories?: ReportCategory[];
  }): string {
    const qs = new URLSearchParams();
    qs.set('start_date', params.start_date);
    qs.set('end_date', params.end_date);
    if (params.categories) {
      qs.set('categories', params.categories.join(','));
    }
    return `/v1/reports/export/csv?${qs.toString()}`;
  },
};
