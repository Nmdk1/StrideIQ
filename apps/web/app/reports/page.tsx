'use client';

import { useState, useMemo, useCallback } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { useReport } from '@/lib/hooks/queries/reports';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import type {
  ReportCategory,
  ReportDay,
  HealthDay,
  ActivityRow,
  NutritionDayTotals,
  BodyCompDay,
  PeriodAverages,
} from '@/lib/api/services/reports';

// ── Helpers ──────────────────────────────────────────────────────────

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
}

function formatDateShort(iso: string): string {
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function formatDayOfWeek(iso: string): string {
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

function secondsToHM(s: number | undefined | null): string {
  if (!s) return '-';
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function metersToMiles(m: number | undefined | null): string {
  if (!m) return '-';
  return (m / 1609.34).toFixed(1);
}

function paceKmToMile(paceKm: number | undefined | null): string {
  if (!paceKm) return '-';
  const paceMi = paceKm * 1.60934;
  const min = Math.floor(paceMi);
  const sec = Math.round((paceMi - min) * 60);
  return `${min}:${sec.toString().padStart(2, '0')}/mi`;
}

function kgToLbs(kg: number | undefined | null): string {
  if (!kg) return '-';
  return (kg * 2.20462).toFixed(1);
}

function round1(n: number | undefined | null): string {
  if (n == null) return '-';
  return Math.round(n).toString();
}

type DatePreset = '7d' | '14d' | '30d' | '90d' | 'custom';

const CATEGORY_LABELS: Record<ReportCategory, string> = {
  health: 'Health',
  activities: 'Activities',
  nutrition: 'Nutrition',
  body_composition: 'Body Comp',
};

const HEALTH_METRIC_LABELS: Record<string, string> = {
  sleep_score: 'Sleep Score',
  sleep_total_s: 'Sleep Duration',
  sleep_deep_s: 'Deep Sleep',
  sleep_light_s: 'Light Sleep',
  sleep_rem_s: 'REM Sleep',
  sleep_awake_s: 'Awake Time',
  sleep_score_qualifier: 'Sleep Quality',
  hrv_overnight_avg: 'HRV (Overnight)',
  hrv_5min_high: 'HRV (5min High)',
  resting_hr: 'Resting HR',
  min_hr: 'Min HR',
  max_hr: 'Max HR',
  avg_stress: 'Avg Stress',
  max_stress: 'Max Stress',
  stress_qualifier: 'Stress Level',
  steps: 'Steps',
  active_kcal: 'Active Cal',
  active_time_s: 'Active Time',
  moderate_intensity_s: 'Moderate Intensity',
  vigorous_intensity_s: 'Vigorous Intensity',
  vo2max: 'VO2max',
};

const ACTIVITY_METRIC_LABELS: Record<string, string> = {
  name: 'Name',
  sport: 'Sport',
  workout_type: 'Type',
  duration_s: 'Duration',
  distance_m: 'Distance',
  avg_hr: 'Avg HR',
  max_hr: 'Max HR',
  avg_pace_min_per_km: 'Pace',
  active_kcal: 'Calories',
  intensity_score: 'Intensity',
  total_elevation_gain: 'Elevation',
  avg_cadence: 'Cadence',
  avg_stride_length_m: 'Stride',
  avg_ground_contact_ms: 'GCT',
  avg_vertical_oscillation_cm: 'Vert Osc',
  avg_power_w: 'Power',
  performance_percentage: 'Age-Graded',
  temperature_f: 'Temp',
  humidity_pct: 'Humidity',
  weather_condition: 'Weather',
  shape_sentence: 'Shape',
  moving_time_s: 'Moving Time',
  workout_zone: 'Zone',
};

const CURATED_HEALTH = ['sleep_score', 'sleep_total_s', 'hrv_overnight_avg', 'resting_hr', 'avg_stress', 'steps', 'active_kcal'];
const EXTENDED_HEALTH = ['sleep_deep_s', 'sleep_light_s', 'sleep_rem_s', 'sleep_awake_s', 'hrv_5min_high', 'min_hr', 'max_hr', 'max_stress', 'vo2max', 'active_time_s', 'moderate_intensity_s', 'vigorous_intensity_s'];

// ── Metric rendering ─────────────────────────────────────────────────

function renderHealthMetric(key: string, h: HealthDay): string {
  const val = h[key as keyof HealthDay];
  if (val == null) return '-';
  if (key === 'sleep_total_s' || key === 'sleep_deep_s' || key === 'sleep_light_s' || key === 'sleep_rem_s' || key === 'sleep_awake_s' || key === 'active_time_s' || key === 'moderate_intensity_s' || key === 'vigorous_intensity_s') {
    return secondsToHM(val as number);
  }
  if (key === 'vo2max') return (val as number).toFixed(1);
  return val.toString();
}

// ── Day detail component ─────────────────────────────────────────────

function DayDetail({ day, healthMetrics, showActivities, showNutrition, showBodyComp }: {
  day: ReportDay;
  healthMetrics: string[];
  showActivities: boolean;
  showNutrition: boolean;
  showBodyComp: boolean;
}) {
  return (
    <div className="space-y-3 pt-2">
      {day.health && healthMetrics.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {healthMetrics.map((key) => {
            const val = renderHealthMetric(key, day.health!);
            if (val === '-') return null;
            return (
              <div key={key} className="bg-slate-700/40 rounded-lg px-2 py-1.5">
                <div className="text-[10px] text-slate-500">{HEALTH_METRIC_LABELS[key] || key}</div>
                <div className="text-sm font-medium text-white">{val}</div>
              </div>
            );
          })}
        </div>
      )}

      {showActivities && day.activities && day.activities.length > 0 && (
        <div className="space-y-1.5">
          {day.activities.map((a) => (
            <div key={a.id} className="bg-slate-700/40 rounded-lg px-3 py-2">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-white">{a.name || a.sport || 'Activity'}</p>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-400 mt-0.5">
                    {a.workout_type && <span className="capitalize">{a.workout_type.replace(/_/g, ' ')}</span>}
                    {a.duration_s && <span>{secondsToHM(a.duration_s)}</span>}
                    {a.distance_m && <span>{metersToMiles(a.distance_m)} mi</span>}
                    {a.avg_pace_min_per_km && <span>{paceKmToMile(a.avg_pace_min_per_km)}</span>}
                  </div>
                </div>
                <div className="text-right text-xs text-slate-400">
                  {a.avg_hr && <div>{a.avg_hr} bpm</div>}
                  {a.active_kcal && <div>{a.active_kcal} cal</div>}
                  {a.intensity_score && <div>Int: {a.intensity_score.toFixed(0)}</div>}
                </div>
              </div>
              <div className="flex flex-wrap gap-x-3 mt-1 text-[10px] text-slate-500">
                {a.total_elevation_gain && <span>{Math.round(a.total_elevation_gain * 3.28084)}ft gain</span>}
                {a.avg_cadence && <span>{a.avg_cadence} spm</span>}
                {a.avg_power_w && <span>{a.avg_power_w}W</span>}
                {a.performance_percentage && <span>AG: {a.performance_percentage.toFixed(1)}%</span>}
                {a.temperature_f != null && <span>{Math.round(a.temperature_f)}°F</span>}
                {a.weather_condition && <span className="capitalize">{a.weather_condition}</span>}
              </div>
              {a.shape_sentence && <p className="text-[10px] text-slate-500 mt-1 italic">{a.shape_sentence}</p>}
            </div>
          ))}
        </div>
      )}

      {showNutrition && day.nutrition_entries && day.nutrition_entries.length > 0 && (
        <div className="space-y-1">
          {day.nutrition_entries.map((ne) => (
            <div key={ne.id} className="flex justify-between items-center bg-slate-700/40 rounded-lg px-3 py-1.5">
              <div className="min-w-0 flex-1">
                <p className="text-xs text-white truncate">{ne.notes || ne.entry_type.replace(/_/g, ' ')}</p>
                <span className="text-[10px] text-slate-500 capitalize">{ne.entry_type.replace(/_/g, ' ')}</span>
              </div>
              <div className="text-xs text-slate-400 text-right flex-shrink-0 ml-2">
                {ne.calories != null && <span>{Math.round(ne.calories)} cal </span>}
                <span className="text-slate-500">
                  {ne.protein_g != null ? `${Math.round(ne.protein_g)}P ` : ''}
                  {ne.carbs_g != null ? `${Math.round(ne.carbs_g)}C ` : ''}
                  {ne.fat_g != null ? `${Math.round(ne.fat_g)}F` : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showBodyComp && day.body_composition && (
        <div className="flex gap-3 text-xs">
          {day.body_composition.weight_kg && (
            <div className="bg-slate-700/40 rounded-lg px-3 py-1.5">
              <span className="text-slate-500">Weight: </span>
              <span className="text-white font-medium">{kgToLbs(day.body_composition.weight_kg)} lbs</span>
            </div>
          )}
          {day.body_composition.body_fat_pct && (
            <div className="bg-slate-700/40 rounded-lg px-3 py-1.5">
              <span className="text-slate-500">BF: </span>
              <span className="text-white font-medium">{day.body_composition.body_fat_pct}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Trend chart (mini sparkline) ─────────────────────────────────────

function TrendSpark({ values, label, unit, color = '#60a5fa' }: {
  values: { date: string; value: number }[];
  label: string;
  unit?: string;
  color?: string;
}) {
  if (values.length < 2) return null;
  const width = 200;
  const height = 48;
  const px = 4;
  const py = 6;
  const plotW = width - 2 * px;
  const plotH = height - 2 * py;

  const vals = values.map((v) => v.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;

  const points = values.map((v, i) => ({
    x: px + (i / (values.length - 1)) * plotW,
    y: py + plotH - ((v.value - min) / range) * plotH,
  }));

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  return (
    <div className="bg-slate-700/40 rounded-lg p-2">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-[10px] text-slate-500">{label}</span>
        <span className="text-xs font-medium text-slate-300">avg {Math.round(avg)}{unit || ''}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
        {points.length <= 30 && points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={2} fill={color} />
        ))}
      </svg>
    </div>
  );
}

// ── Period averages card ─────────────────────────────────────────────

function AveragesCard({ avgs, cats }: { avgs: PeriodAverages; cats: Set<ReportCategory> }) {
  const items: { label: string; value: string }[] = [];

  if (cats.has('health')) {
    if (avgs.avg_sleep_score != null) items.push({ label: 'Avg Sleep Score', value: avgs.avg_sleep_score.toString() });
    if (avgs.avg_sleep_hours != null) items.push({ label: 'Avg Sleep', value: `${avgs.avg_sleep_hours}h` });
    if (avgs.avg_hrv != null) items.push({ label: 'Avg HRV', value: `${avgs.avg_hrv} ms` });
    if (avgs.avg_resting_hr != null) items.push({ label: 'Avg Resting HR', value: `${avgs.avg_resting_hr} bpm` });
    if (avgs.avg_stress != null) items.push({ label: 'Avg Stress', value: avgs.avg_stress.toString() });
    if (avgs.avg_steps != null) items.push({ label: 'Avg Steps', value: Math.round(avgs.avg_steps).toLocaleString() });
  }
  if (cats.has('activities')) {
    items.push({ label: 'Activities', value: avgs.total_activities.toString() });
    if (avgs.total_distance_m > 0) items.push({ label: 'Total Distance', value: `${(avgs.total_distance_m / 1609.34).toFixed(1)} mi` });
    if (avgs.total_duration_s > 0) items.push({ label: 'Total Time', value: secondsToHM(avgs.total_duration_s) });
    if (avgs.total_active_kcal > 0) items.push({ label: 'Activity Cal', value: Math.round(avgs.total_active_kcal).toLocaleString() });
  }
  if (cats.has('nutrition')) {
    if (avgs.avg_daily_calories != null) items.push({ label: 'Avg Cal/Day', value: Math.round(avgs.avg_daily_calories).toLocaleString() });
    if (avgs.avg_daily_protein_g != null) items.push({ label: 'Avg Protein/Day', value: `${Math.round(avgs.avg_daily_protein_g)}g` });
    if (avgs.avg_daily_carbs_g != null) items.push({ label: 'Avg Carbs/Day', value: `${Math.round(avgs.avg_daily_carbs_g)}g` });
    if (avgs.avg_daily_fat_g != null) items.push({ label: 'Avg Fat/Day', value: `${Math.round(avgs.avg_daily_fat_g)}g` });
    if (avgs.avg_daily_caffeine_mg != null && avgs.avg_daily_caffeine_mg > 0) items.push({ label: 'Avg Caffeine/Day', value: `${Math.round(avgs.avg_daily_caffeine_mg)}mg` });
    items.push({ label: 'Days Logged', value: `${avgs.nutrition_days_logged}/${avgs.days}` });
  }
  if (cats.has('body_composition') && avgs.avg_weight_kg != null) {
    items.push({ label: 'Avg Weight', value: `${kgToLbs(avgs.avg_weight_kg)} lbs` });
  }

  if (items.length === 0) return null;

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">Period Averages</h2>
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
        {items.map((item) => (
          <div key={item.label}>
            <div className="text-[10px] text-slate-500">{item.label}</div>
            <div className="text-sm font-medium text-white">{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


// ── Main page ────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { user } = useAuth();
  const today = new Date().toISOString().split('T')[0];

  const [preset, setPreset] = useState<DatePreset>('14d');
  const [customStart, setCustomStart] = useState(shiftDate(today, -14));
  const [customEnd, setCustomEnd] = useState(today);
  const [categories, setCategories] = useState<Set<ReportCategory>>(
    new Set<ReportCategory>(['health', 'activities', 'nutrition', 'body_composition'])
  );
  const [expandedDay, setExpandedDay] = useState<string | null>(null);
  const [showMetricPicker, setShowMetricPicker] = useState(false);
  const [selectedHealthMetrics, setSelectedHealthMetrics] = useState<Set<string>>(
    new Set(CURATED_HEALTH)
  );
  const [showTrends, setShowTrends] = useState(true);
  const [exporting, setExporting] = useState(false);

  const dateRange = useMemo(() => {
    if (preset === 'custom') return { start: customStart, end: customEnd };
    const days = preset === '7d' ? 7 : preset === '14d' ? 14 : preset === '30d' ? 30 : 90;
    return { start: shiftDate(today, -days + 1), end: today };
  }, [preset, customStart, customEnd, today]);

  const catsArray = useMemo(() => Array.from(categories) as ReportCategory[], [categories]);

  const { data: report, isLoading } = useReport({
    start_date: dateRange.start,
    end_date: dateRange.end,
    categories: catsArray,
  });

  const toggleCategory = useCallback((cat: ReportCategory) => {
    setCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        if (next.size <= 1) return prev;
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  }, []);

  const toggleHealthMetric = useCallback((key: string) => {
    setSelectedHealthMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const healthMetricsArray = useMemo(() => Array.from(selectedHealthMetrics), [selectedHealthMetrics]);

  // Build trend data from report
  const trends = useMemo(() => {
    if (!report) return null;
    const sleepScores: { date: string; value: number }[] = [];
    const hrvs: { date: string; value: number }[] = [];
    const restingHrs: { date: string; value: number }[] = [];
    const dailyCals: { date: string; value: number }[] = [];
    const weights: { date: string; value: number }[] = [];
    const steps: { date: string; value: number }[] = [];

    for (const day of report.days) {
      if (day.health) {
        if (day.health.sleep_score != null) sleepScores.push({ date: day.date, value: day.health.sleep_score });
        if (day.health.hrv_overnight_avg != null) hrvs.push({ date: day.date, value: day.health.hrv_overnight_avg });
        if (day.health.resting_hr != null) restingHrs.push({ date: day.date, value: day.health.resting_hr });
        if (day.health.steps != null) steps.push({ date: day.date, value: day.health.steps });
      }
      if (day.nutrition_totals && day.nutrition_totals.calories > 0) {
        dailyCals.push({ date: day.date, value: day.nutrition_totals.calories });
      }
      if (day.body_composition?.weight_kg) {
        weights.push({ date: day.date, value: day.body_composition.weight_kg * 2.20462 });
      }
    }

    return { sleepScores, hrvs, restingHrs, dailyCals, weights, steps };
  }, [report]);

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
      const { API_CONFIG } = await import('@/lib/api/config');
      const catStr = catsArray.join(',');
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/reports/export/csv?start_date=${dateRange.start}&end_date=${dateRange.end}&categories=${catStr}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `strideiq_report_${dateRange.start}_${dateRange.end}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // silently fail
    } finally {
      setExporting(false);
    }
  };

  if (!user) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center bg-slate-900">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">

          {/* Header */}
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold">Reports</h1>
            <button
              onClick={handleExportCsv}
              disabled={exporting || !report}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700/50 rounded-lg text-xs font-medium text-slate-300 min-h-[36px] transition-colors"
            >
              {exporting ? 'Exporting...' : 'CSV'}
            </button>
          </div>

          {/* Date Range Presets */}
          <div className="flex gap-1.5 bg-slate-800 rounded-xl border border-slate-700/50 p-1">
            {(['7d', '14d', '30d', '90d', 'custom'] as DatePreset[]).map((p) => (
              <button
                key={p}
                onClick={() => setPreset(p)}
                className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors min-h-[36px] ${
                  preset === p ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {p === 'custom' ? 'Custom' : p}
              </button>
            ))}
          </div>

          {/* Custom date inputs */}
          {preset === 'custom' && (
            <div className="flex gap-2">
              <input
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
              />
              <span className="flex items-center text-slate-500 text-sm">to</span>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-sm min-h-[44px]"
              />
            </div>
          )}

          {/* Category Toggles */}
          <div className="flex gap-2">
            {(Object.entries(CATEGORY_LABELS) as [ReportCategory, string][]).map(([cat, label]) => (
              <button
                key={cat}
                onClick={() => toggleCategory(cat)}
                className={`flex-1 py-2 text-xs font-medium rounded-lg border transition-colors min-h-[36px] ${
                  categories.has(cat)
                    ? 'bg-slate-700 border-blue-500/50 text-white'
                    : 'bg-slate-800 border-slate-700/50 text-slate-500'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Metric Picker Toggle */}
          {categories.has('health') && (
            <button
              onClick={() => setShowMetricPicker(!showMetricPicker)}
              className="w-full flex items-center justify-between px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-xs text-slate-400 hover:text-white transition-colors min-h-[36px]"
            >
              <span>Health metrics: {selectedHealthMetrics.size} selected</span>
              <svg className={`w-4 h-4 transition-transform ${showMetricPicker ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}

          {/* Metric Picker Panel */}
          {showMetricPicker && (
            <div className="bg-slate-800 border border-slate-700/50 rounded-xl p-3 space-y-2">
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5">Core</p>
                <div className="flex flex-wrap gap-1.5">
                  {CURATED_HEALTH.map((key) => (
                    <button
                      key={key}
                      onClick={() => toggleHealthMetric(key)}
                      className={`px-2 py-1 text-[11px] rounded border transition-colors ${
                        selectedHealthMetrics.has(key)
                          ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                          : 'bg-slate-700/40 border-slate-600/50 text-slate-500'
                      }`}
                    >
                      {HEALTH_METRIC_LABELS[key]}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5">Extended</p>
                <div className="flex flex-wrap gap-1.5">
                  {EXTENDED_HEALTH.map((key) => (
                    <button
                      key={key}
                      onClick={() => toggleHealthMetric(key)}
                      className={`px-2 py-1 text-[11px] rounded border transition-colors ${
                        selectedHealthMetrics.has(key)
                          ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                          : 'bg-slate-700/40 border-slate-600/50 text-slate-500'
                      }`}
                    >
                      {HEALTH_METRIC_LABELS[key]}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Loading */}
          {isLoading && (
            <div className="flex justify-center py-12">
              <LoadingSpinner size="lg" />
            </div>
          )}

          {report && !isLoading && (
            <>
              {/* Period Averages */}
              <AveragesCard avgs={report.period_averages} cats={categories} />

              {/* Trend Charts */}
              {showTrends && trends && (
                <div className="bg-slate-800 rounded-xl border border-slate-700/50 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-slate-300">Trends</h2>
                    <button onClick={() => setShowTrends(false)} className="text-xs text-slate-500 hover:text-slate-300">Hide</button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {categories.has('health') && (
                      <>
                        <TrendSpark values={trends.sleepScores} label="Sleep Score" color="#a78bfa" />
                        <TrendSpark values={trends.hrvs} label="HRV" unit=" ms" color="#34d399" />
                        <TrendSpark values={trends.restingHrs} label="Resting HR" unit=" bpm" color="#f87171" />
                        <TrendSpark values={trends.steps} label="Steps" color="#fbbf24" />
                      </>
                    )}
                    {categories.has('nutrition') && (
                      <TrendSpark values={trends.dailyCals} label="Calories" unit=" cal" color="#60a5fa" />
                    )}
                    {categories.has('body_composition') && (
                      <TrendSpark values={trends.weights} label="Weight" unit=" lbs" color="#f472b6" />
                    )}
                  </div>
                </div>
              )}

              {!showTrends && (
                <button onClick={() => setShowTrends(true)} className="w-full py-2 text-xs text-slate-500 hover:text-slate-300">Show Trends</button>
              )}

              {/* Day-by-Day Log */}
              <div className="space-y-1">
                <h2 className="text-sm font-semibold text-slate-400 px-1">Daily Log</h2>
                {[...report.days].reverse().map((day) => {
                  const isExpanded = expandedDay === day.date;
                  const hasData = !!(day.health || (day.activities && day.activities.length > 0) || (day.nutrition_entries && day.nutrition_entries.length > 0) || day.body_composition);

                  return (
                    <div
                      key={day.date}
                      className={`bg-slate-800 rounded-xl border transition-colors ${
                        isExpanded ? 'border-blue-500/30' : 'border-slate-700/50'
                      } ${hasData ? '' : 'opacity-40'}`}
                    >
                      <button
                        onClick={() => setExpandedDay(isExpanded ? null : day.date)}
                        className="w-full px-3 py-2.5 text-left"
                        disabled={!hasData}
                      >
                        <div className="flex items-center gap-3">
                          {/* Date column */}
                          <div className="w-16 flex-shrink-0">
                            <div className="text-xs font-semibold text-white">{formatDayOfWeek(day.date)}</div>
                            <div className="text-[10px] text-slate-500">{day.date.slice(5)}</div>
                          </div>

                          {/* Health summary line */}
                          {day.health && categories.has('health') && (
                            <div className="flex gap-2 text-[10px] text-slate-400 flex-shrink-0">
                              {day.health.sleep_score != null && (
                                <span title="Sleep">
                                  <span className="text-slate-600">S:</span>{day.health.sleep_score}
                                </span>
                              )}
                              {day.health.hrv_overnight_avg != null && (
                                <span title="HRV">
                                  <span className="text-slate-600">H:</span>{day.health.hrv_overnight_avg}
                                </span>
                              )}
                              {day.health.resting_hr != null && (
                                <span title="RHR">
                                  <span className="text-slate-600">R:</span>{day.health.resting_hr}
                                </span>
                              )}
                            </div>
                          )}

                          {/* Activity summary */}
                          {day.activities && day.activities.length > 0 && categories.has('activities') && (
                            <div className="text-[10px] text-slate-400 truncate min-w-0">
                              {day.activities.map((a) => {
                                const dist = a.distance_m ? `${metersToMiles(a.distance_m)}mi` : secondsToHM(a.duration_s);
                                return `${(a.workout_type || a.sport || '').replace(/_/g, ' ')} ${dist}`;
                              }).join(' + ')}
                            </div>
                          )}

                          {/* Nutrition totals */}
                          {day.nutrition_totals && day.nutrition_totals.calories > 0 && categories.has('nutrition') && (
                            <div className="text-[10px] text-slate-400 flex-shrink-0 ml-auto">
                              {round1(day.nutrition_totals.calories)} cal
                            </div>
                          )}

                          {/* Weight */}
                          {day.body_composition?.weight_kg && categories.has('body_composition') && (
                            <div className="text-[10px] text-slate-400 flex-shrink-0">
                              {kgToLbs(day.body_composition.weight_kg)}lb
                            </div>
                          )}

                          {/* Expand arrow */}
                          {hasData && (
                            <svg className={`w-3.5 h-3.5 text-slate-600 flex-shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                            </svg>
                          )}
                        </div>
                      </button>

                      {isExpanded && hasData && (
                        <div className="px-3 pb-3">
                          <DayDetail
                            day={day}
                            healthMetrics={healthMetricsArray}
                            showActivities={categories.has('activities')}
                            showNutrition={categories.has('nutrition')}
                            showBodyComp={categories.has('body_composition')}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Date range info */}
              <div className="text-center text-xs text-slate-600 py-2">
                {report.start_date} — {report.end_date} · {report.days.length} days
              </div>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
