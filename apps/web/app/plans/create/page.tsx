'use client';

/**
 * Plan Creation Page
 * 
 * Questionnaire-based plan creation flow.
 * Collects necessary information to generate personalized training plans.
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { planService } from '@/lib/api/services/plans';
import { ApiClientError } from '@/lib/api/client';
import { useAuth } from '@/lib/context/AuthContext';
import { useUnits } from '@/lib/context/UnitsContext';
import { parseTimeToSeconds } from '@/lib/utils/time';
import { calendarKeys } from '@/lib/hooks/queries/calendar';

const M_PER_MI = 1609.344;

type Step = 'plan-type' | 'distance' | 'race-date' | 'current-fitness' | 'availability' | 'recent-race' | 'experience' | 'review' | 'model-driven-form' | 'model-driven-preview' | 'constraint-aware-form' | 'constraint-aware-tune-up' | 'constraint-aware-preview';

type PlanType = 'template' | 'model-driven' | 'constraint-aware';

interface TuneUpRace {
  date: string;
  distance: string;
  name: string;
  purpose: 'threshold' | 'sharpening' | 'tune_up' | 'fitness_check';
}

interface PlanFormData {
  planType: PlanType;
  distance: string;
  race_date: string;
  race_name: string;
  current_weekly_m: number;
  longest_recent_run_m: number;
  days_per_week: number;
  recent_race_distance?: string;
  recent_race_time?: string;
  experience_level: string;
  injury_history: string;
  goal_time_seconds?: number;
  tune_up_races: TuneUpRace[];
  target_peak_weekly_m?: number;
  target_peak_weekly_min_m?: number;
  target_peak_weekly_max_m?: number;
}

interface ModelDrivenPreview {
  model: {
    confidence: string;
    tau1: number;
    tau2: number;
    insights: string[];
  };
  prediction: {
    prediction: {
      time_seconds: number;
      time_formatted: string;
      confidence: string;
    };
  } | null;
  personalization?: {
    taper_start_week: number;
    notes: string[];
    summary: string;
  };
}

type PlanCreateError = {
  message: string;
  isUpgrade?: boolean;
  safeBoundsMiles?: { min: number; max: number };
  recommendedPeakMiles?: number;
  // Optional debug context (technical reasons) that we keep available but
  // do not render to the athlete unless they expand the details disclosure.
  reasons?: string[];
};

function formatPlanCreateError(err: unknown): PlanCreateError {
  if (err instanceof ApiClientError) {
    if (err.status === 403) {
      return {
        message: 'Personalized training plans are a premium feature. Upgrade to unlock N=1 plan generation built from your actual training data.',
        isUpgrade: true,
      };
    }
    const detail = (err.data as { detail?: unknown } | undefined)?.detail;
    if (detail && typeof detail === 'object') {
      const payload = detail as {
        error_code?: string;
        reasons?: string[];
        next_action?: string;
        display_message?: string;
        suggested_safe_bounds?: { weekly_miles?: { min?: number; max?: number } };
        safe_bounds_km?: { weekly_miles?: { min?: number; max?: number } };
        recommended_peak_weekly_miles?: number;
      };
      if (payload.error_code === 'readiness_gate_blocked') {
        const display = (payload.display_message || '').trim();
        const message = display
          ? display
          : "Your training history doesn't yet support this race distance. Build a longer long-run, then come back, or pick a shorter goal distance.";
        return { message };
      }
      if (payload.error_code === 'quality_gate_failed') {
        const display = (payload.display_message || '').trim();
        const reasons = Array.isArray(payload.reasons) ? payload.reasons : [];
        const message = display
          ? display
          : reasons.length > 0
            ? `We caught a plan quality issue:\n${reasons.map((r, i) => `${i + 1}. ${r}`).join('\n')}`
            : 'We caught a plan quality issue. Please adjust your inputs and try again.';
        const weekly = payload.suggested_safe_bounds?.weekly_miles;
        const safeBoundsMiles =
          typeof weekly?.min === 'number' && typeof weekly?.max === 'number'
            ? { min: weekly.min, max: weekly.max }
            : undefined;
        const recommendedPeakMiles =
          typeof payload.recommended_peak_weekly_miles === 'number'
            ? payload.recommended_peak_weekly_miles
            : safeBoundsMiles
              ? Math.round(((safeBoundsMiles.min + safeBoundsMiles.max) / 2) * 10) / 10
              : undefined;
        return {
          message,
          safeBoundsMiles,
          recommendedPeakMiles,
          reasons,
        };
      }
      return { message: `Request failed (${err.status}).` };
    }
    return { message: err.message };
  }
  return { message: err instanceof Error ? err.message : 'Failed to create plan' };
}

interface PlanCreateErrorBannerProps {
  error: PlanCreateError;
  formatDistance: (meters: number | null | undefined, decimals?: number) => string;
  onAcceptSafeRange?: (recommendedPeakMiles: number) => void;
}

function PlanCreateErrorBanner({ error, formatDistance, onAcceptSafeRange }: PlanCreateErrorBannerProps) {
  if (error.isUpgrade) {
    return (
      <div className="mt-4 p-5 bg-gradient-to-r from-amber-900/40 to-amber-800/20 border border-amber-600/50 rounded-lg">
        <p className="text-amber-200 text-sm font-medium mb-3">{error.message}</p>
        <a
          href="/#pricing"
          className="inline-block px-5 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold rounded-lg text-sm transition-colors"
        >
          View Plans &amp; Upgrade
        </a>
      </div>
    );
  }

  const safe = error.safeBoundsMiles;
  const recommendedMiles = error.recommendedPeakMiles;
  const showSafeRange = !!safe && !!onAcceptSafeRange && typeof recommendedMiles === 'number';

  const formatBoundsLabel = () => {
    if (!safe) return null;
    const minM = safe.min * M_PER_MI;
    const maxM = safe.max * M_PER_MI;
    return `${formatDistance(minM, 0)}-${formatDistance(maxM, 0)}/week`;
  };

  const formatRecommended = () => {
    if (typeof recommendedMiles !== 'number') return null;
    return `${formatDistance(recommendedMiles * M_PER_MI, 0)}/week`;
  };

  return (
    <div className="mt-4 p-4 bg-red-900/40 border border-red-700/60 rounded-lg text-sm">
      <p className="text-red-200 whitespace-pre-line">{error.message}</p>
      {safe && (
        <p className="text-red-100/80 mt-2">
          Safe range from your training history: <span className="font-semibold">{formatBoundsLabel()}</span>
        </p>
      )}
      {showSafeRange && (
        <button
          type="button"
          onClick={() => onAcceptSafeRange!(recommendedMiles!)}
          className="mt-3 inline-block px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold rounded-lg text-sm transition-colors"
        >
          Use safe range ({formatRecommended()})
        </button>
      )}
      {error.reasons && error.reasons.length > 0 && (
        <details className="mt-3 text-xs text-red-200/70">
          <summary className="cursor-pointer hover:text-red-200">Show technical details</summary>
          <ul className="mt-2 ml-4 list-disc space-y-1">
            {error.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

const DISTANCES_BY_UNIT: Record<'metric' | 'imperial', Array<{ value: string; label: string; subtitle: string; icon: string }>> = {
  imperial: [
    { value: 'marathon', label: 'Marathon', subtitle: '26.2 miles', icon: '🏃' },
    { value: 'half_marathon', label: 'Half Marathon', subtitle: '13.1 miles', icon: '🏃' },
    { value: '10k', label: '10K', subtitle: '6.2 miles', icon: '🏃' },
    { value: '5k', label: '5K', subtitle: '3.1 miles', icon: '🏃' },
  ],
  metric: [
    { value: 'marathon', label: 'Marathon', subtitle: '42.2 km', icon: '🏃' },
    { value: 'half_marathon', label: 'Half Marathon', subtitle: '21.1 km', icon: '🏃' },
    { value: '10k', label: '10K', subtitle: '10 km', icon: '🏃' },
    { value: '5k', label: '5K', subtitle: '5 km', icon: '🏃' },
  ],
};

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'New to Racing', description: 'This is my first structured training plan' },
  { value: 'intermediate', label: 'Some Experience', description: 'I have raced this distance before' },
  { value: 'experienced', label: 'Experienced', description: 'I have trained with structured plans' },
];

export default function CreatePlanPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, isAuthenticated: authAuthenticated } = useAuth();
  const { units, formatDistance } = useUnits();
  const isMetric = units === 'metric';
  const distanceUnitShort = isMetric ? 'km' : 'mi';
  const distanceUnitLong = isMetric ? 'kilometers' : 'miles';
  const DISTANCES = DISTANCES_BY_UNIT[units];
  const [step, setStep] = useState<Step>('plan-type');
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [error, setError] = useState<PlanCreateError | null>(null);
  const [modelPreview, setModelPreview] = useState<ModelDrivenPreview | null>(null);
  const [modelPlanResult, setModelPlanResult] = useState<import('@/lib/api/services/plans').ModelDrivenPlanResponse | null>(null);
  
  const [formData, setFormData] = useState<PlanFormData>({
    planType: 'template',
    distance: '',
    race_date: '',
    race_name: '',
    current_weekly_m: 48280,
    longest_recent_run_m: 16093,
    days_per_week: 6,
    experience_level: 'intermediate',
    injury_history: '',
    tune_up_races: [],
    target_peak_weekly_m: undefined,
    target_peak_weekly_min_m: undefined,
    target_peak_weekly_max_m: undefined,
  });
  const [goalTimeDisplay, setGoalTimeDisplay] = useState('');
  const [constraintAwareResult, setConstraintAwareResult] = useState<import('@/lib/api/services/plans').ConstraintAwarePlanResponse | null>(null);
  const [constraintAwarePreview, setConstraintAwarePreview] = useState<import('@/lib/api/services/plans').ConstraintAwarePreview | null>(null);
  
  // Phase 6: paid access is Free vs Pro (Stripe subscription or active trial).
  const rawTier = (user?.subscription_tier || 'free').toLowerCase();
  const hasProAccess = !!(user as any)?.has_active_subscription || rawTier !== 'free';
  
  // Check authentication
  useEffect(() => {
    const token = localStorage.getItem('auth_token');  // Matches AuthContext key
    setIsAuthenticated(!!token);
    // Debug: Log tier info
    console.log('[Plan Create] User tier:', user?.subscription_tier, 'User object:', user);
  }, [user]);
  
  // Calculate weeks until race
  const weeksUntilRace = formData.race_date
    ? Math.ceil((new Date(formData.race_date).getTime() - Date.now()) / (7 * 24 * 60 * 60 * 1000))
    : 0;
  
  // Determine plan duration
  const planDuration = weeksUntilRace >= 18 ? 18 : weeksUntilRace >= 12 ? 12 : Math.max(8, weeksUntilRace);
  
  // Determine volume tier based on current miles
  const getVolumeTier = () => {
    const weeklyMi = formData.current_weekly_m / M_PER_MI;
    if (weeklyMi < 35) return 'builder';
    if (weeklyMi < 45) return 'low';
    if (weeklyMi < 60) return 'mid';
    return 'high';
  };
  
  // Handle model-driven plan creation
  const handleModelDrivenSubmit = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await planService.createModelDriven({
        race_date: formData.race_date,
        race_distance: formData.distance,
        goal_time_seconds: formData.goal_time_seconds,
      });
      
      setModelPlanResult(result);
      setStep('model-driven-preview');
      
    } catch (err) {
      console.error('[Plan Create] Error creating model-driven plan:', err);
      setError(formatPlanCreateError(err));
    } finally {
      setIsLoading(false);
    }
  };

  // Handle constraint-aware plan creation
  const handleConstraintAwareSubmit = async (overrides?: { target_peak_weekly_m?: number }) => {
    setIsLoading(true);
    setError(null);

    try {
      const preview = await planService.previewConstraintAware(
        formData.race_date,
        formData.distance
      );
      setConstraintAwarePreview(preview);

      const peakM = overrides?.target_peak_weekly_m
        ?? formData.target_peak_weekly_m
        ?? undefined;

      const result = await planService.createConstraintAware({
        race_date: formData.race_date,
        race_distance: formData.distance,
        goal_time_seconds: formData.goal_time_seconds,
        race_name: formData.race_name || undefined,
        tune_up_races: formData.tune_up_races.length > 0 ? formData.tune_up_races : undefined,
        target_peak_weekly_m: peakM,
        target_peak_weekly_range:
          formData.target_peak_weekly_min_m && formData.target_peak_weekly_max_m
            ? { min: formData.target_peak_weekly_min_m, max: formData.target_peak_weekly_max_m }
            : undefined,
      });
      
      setConstraintAwareResult(result);
      setStep('constraint-aware-preview');
      
    } catch (err) {
      console.error('[Plan Create] Error creating constraint-aware plan:', err);
      setError(formatPlanCreateError(err));
    } finally {
      setIsLoading(false);
    }
  };

  // Apply constraint-aware plan to calendar
  const applyConstraintAwareToCalendar = async () => {
    if (!constraintAwareResult) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // The plan is already saved on the backend
      // Just invalidate cache and redirect
      await queryClient.invalidateQueries({ queryKey: calendarKeys.all });
      router.push('/calendar');
    } catch (err) {
      console.error('[Plan Create] Error applying to calendar:', err);
      setError({ message: 'Failed to apply plan to calendar' });
    } finally {
      setIsLoading(false);
    }
  };

  // Add a tune-up race
  const addTuneUpRace = () => {
    setFormData({
      ...formData,
      tune_up_races: [
        ...formData.tune_up_races,
        { date: '', distance: '10_mile', name: '', purpose: 'threshold' }
      ]
    });
  };

  // Remove a tune-up race
  const removeTuneUpRace = (index: number) => {
    setFormData({
      ...formData,
      tune_up_races: formData.tune_up_races.filter((_, i) => i !== index)
    });
  };

  // Update a tune-up race
  const updateTuneUpRace = (index: number, field: keyof TuneUpRace, value: string) => {
    const updated = [...formData.tune_up_races];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, tune_up_races: updated });
  };
  
  // Apply model-driven plan to calendar
  const applyModelDrivenToCalendar = async () => {
    if (!modelPlanResult) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // The plan is already saved on the backend
      // Just invalidate cache and redirect
      await queryClient.invalidateQueries({ queryKey: calendarKeys.all });
      router.push('/calendar');
    } catch (err) {
      console.error('[Plan Create] Error applying to calendar:', err);
      setError({ message: 'Failed to apply plan to calendar' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Convert race time to seconds if provided
      const raceTimeSeconds = formData.recent_race_time 
        ? parseTimeToSeconds(formData.recent_race_time) 
        : undefined;
      
      // Check paid access (Stripe subscription or active trial).
      const isProTier = hasProAccess;
      const hasPaceData = formData.recent_race_distance && raceTimeSeconds;
      
      // Use auth state from hook, not local state
      // Note: AuthContext stores token as 'auth_token', not 'token'
      const authValid = !!user && !!localStorage.getItem('auth_token');
      
      // Debug logging
      console.log('[Plan Create] Creating plan:', {
        tier: user?.subscription_tier,
        isProTier,
        hasPaceData,
        authValid,
        localIsAuthenticated: isAuthenticated,
      });
      
      // Route based on tier
      console.log('[Plan Create] Routing decision:', { authValid, isProTier, hasPaceData });
      
      if (authValid && isProTier) {
        // PRO: Fully custom plan (includes model-driven / constraint-aware flows)
        console.log('[Plan Create] >>> TAKING PRO/CUSTOM PATH');
        await planService.createCustom({
          distance: formData.distance,
          race_date: formData.race_date,
          race_name: formData.race_name || undefined,
          days_per_week: formData.days_per_week,
          current_weekly_m: formData.current_weekly_m,
          recent_race_distance: formData.recent_race_distance,
          recent_race_time_seconds: raceTimeSeconds ?? undefined,
        });
      } else if (authValid && hasPaceData) {
        // Personalized paces require Pro now (no one-time checkout paths).
        router.push('/settings');
        return;
      } else {
        // STANDARD: Free plan, effort descriptions only
        console.log('[Plan Create] >>> TAKING STANDARD PATH (fallback)');
        // Calculate start date from race date minus duration
        const raceDate = new Date(formData.race_date);
        const startDate = new Date(raceDate);
        startDate.setDate(startDate.getDate() - (planDuration * 7) + 1);
        const startDateStr = startDate.toISOString().split('T')[0];
        
        await planService.createStandard({
          distance: formData.distance,
          duration_weeks: planDuration,
          days_per_week: formData.days_per_week,
          volume_tier: getVolumeTier(),
          start_date: startDateStr,
          race_name: formData.race_name || undefined,
        });
      }
      
      // Invalidate calendar cache so it fetches fresh data with the new plan
      await queryClient.invalidateQueries({ queryKey: calendarKeys.all });
      
      // Redirect to calendar to see the plan
      router.push('/calendar');
      
    } catch (err) {
      console.error('[Plan Create] Error creating plan:', err);
      setError(formatPlanCreateError(err));
      // Stay on page - don't redirect
      return;
    } finally {
      setIsLoading(false);
    }
  };

  const acceptSafeRangeAndResubmit = (recommendedPeakMiles: number) => {
    const peakM = recommendedPeakMiles * M_PER_MI;
    setFormData((prev) => ({ ...prev, target_peak_weekly_m: peakM }));
    setError(null);
    if (formData.planType === 'constraint-aware') {
      void handleConstraintAwareSubmit({ target_peak_weekly_m: peakM });
    } else if (formData.planType === 'model-driven') {
      void handleModelDrivenSubmit();
    } else {
      void handleSubmit();
    }
  };

  const nextStep = () => {
    // Different flows for each plan type
    if (formData.planType === 'model-driven') {
      const modelSteps: Step[] = ['plan-type', 'model-driven-form'];
      const currentIndex = modelSteps.indexOf(step);
      if (currentIndex < modelSteps.length - 1) {
        setStep(modelSteps[currentIndex + 1]);
      }
    } else if (formData.planType === 'constraint-aware') {
      const caSteps: Step[] = ['plan-type', 'constraint-aware-form', 'constraint-aware-tune-up'];
      const currentIndex = caSteps.indexOf(step);
      if (currentIndex < caSteps.length - 1) {
        setStep(caSteps[currentIndex + 1]);
      }
    } else {
      const templateSteps: Step[] = ['plan-type', 'distance', 'race-date', 'current-fitness', 'availability', 'recent-race', 'experience', 'review'];
      const currentIndex = templateSteps.indexOf(step);
      if (currentIndex < templateSteps.length - 1) {
        setStep(templateSteps[currentIndex + 1]);
      }
    }
  };
  
  const prevStep = () => {
    if (formData.planType === 'model-driven') {
      const modelSteps: Step[] = ['plan-type', 'model-driven-form', 'model-driven-preview'];
      const currentIndex = modelSteps.indexOf(step);
      if (currentIndex > 0) {
        setStep(modelSteps[currentIndex - 1]);
      }
    } else if (formData.planType === 'constraint-aware') {
      const caSteps: Step[] = ['plan-type', 'constraint-aware-form', 'constraint-aware-tune-up', 'constraint-aware-preview'];
      const currentIndex = caSteps.indexOf(step);
      if (currentIndex > 0) {
        setStep(caSteps[currentIndex - 1]);
      }
    } else {
      const templateSteps: Step[] = ['plan-type', 'distance', 'race-date', 'current-fitness', 'availability', 'recent-race', 'experience', 'review'];
      const currentIndex = templateSteps.indexOf(step);
      if (currentIndex > 0) {
        setStep(templateSteps[currentIndex - 1]);
      }
    }
  };
  
  // Step indicator - varies by plan type
  const templateSteps: Step[] = ['plan-type', 'distance', 'race-date', 'current-fitness', 'availability', 'recent-race', 'experience', 'review'];
  const templateLabels = ['Type', 'Distance', 'Race Date', 'Fitness', 'Schedule', 'Recent Race', 'Experience', 'Review'];
  
  const modelSteps: Step[] = ['plan-type', 'model-driven-form', 'model-driven-preview'];
  const modelLabels = ['Type', 'Race Info', 'Your Plan'];

  const constraintAwareSteps: Step[] = ['plan-type', 'constraint-aware-form', 'constraint-aware-tune-up', 'constraint-aware-preview'];
  const constraintAwareLabels = ['Type', 'Goal Race', 'Tune-Up Races', 'Your Plan'];
  
  const steps = formData.planType === 'model-driven' 
    ? modelSteps 
    : formData.planType === 'constraint-aware' 
      ? constraintAwareSteps 
      : templateSteps;
  const stepLabels = formData.planType === 'model-driven' 
    ? modelLabels 
    : formData.planType === 'constraint-aware' 
      ? constraintAwareLabels 
      : templateLabels;
  
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Create Your Training Plan</h1>
          <p className="text-slate-400">Answer a few questions to get a personalized plan</p>
        </div>
        
        {/* Progress */}
        <div className="flex items-center justify-between mb-8">
          {steps.map((s, i) => (
            <React.Fragment key={s}>
              <div className="flex flex-col items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${
                    steps.indexOf(step) >= i
                      ? 'bg-pink-600 text-white'
                      : 'bg-slate-800 text-slate-500'
                  }`}
                >
                  {i + 1}
                </div>
                <div className="text-xs text-slate-500 mt-1 hidden md:block">{stepLabels[i]}</div>
              </div>
              {i < steps.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 ${
                  steps.indexOf(step) > i ? 'bg-pink-600' : 'bg-slate-800'
                }`} />
              )}
            </React.Fragment>
          ))}
        </div>
        
        {/* Step Content */}
        <div className="bg-slate-800 border border-slate-700/50 rounded-xl p-6 mb-6">
          {/* Plan Type Selection */}
          {step === 'plan-type' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">How do you want to create your plan?</h2>
              <div className="space-y-4">
                {/* Template Option */}
                <button
                  onClick={() => setFormData({ ...formData, planType: 'template' })}
                  className={`w-full p-6 rounded-xl border-2 text-left transition-all ${
                    formData.planType === 'template'
                      ? 'border-pink-500 bg-pink-900/20'
                      : 'border-slate-700/50 bg-slate-900 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className="text-3xl">📋</div>
                    <div className="flex-1">
                      <div className="font-bold text-white text-lg">Template Plan</div>
                      <div className="text-sm text-slate-400 mt-1">
                        Standard training structure based on your goals. Good for most runners.
                      </div>
                    </div>
                  </div>
                </button>
                
                {/* Model-Driven Option */}
                <button
                  onClick={() => {
                    if (hasProAccess) {
                      setFormData({ ...formData, planType: 'model-driven' });
                    }
                  }}
                  disabled={!hasProAccess}
                  className={`w-full p-6 rounded-xl border-2 text-left transition-all ${
                    formData.planType === 'model-driven'
                      ? 'border-purple-500 bg-purple-900/20'
                      : hasProAccess
                        ? 'border-slate-700/50 bg-slate-900 hover:border-purple-600'
                        : 'border-slate-800 bg-slate-900/50 opacity-60 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className="text-3xl">🧠</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-lg">Model-Driven Plan</span>
                        <span className="px-2 py-0.5 bg-purple-600 text-purple-100 text-xs rounded-full font-medium">
                          Pro
                        </span>
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Built from YOUR data. Calibrates τ1/τ2 from your training history, predicts race time, calculates optimal taper.
                      </div>
                      {hasProAccess && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <span className="px-2 py-1 bg-purple-900/50 text-purple-300 text-xs rounded">
                            Personal τ values
                          </span>
                          <span className="px-2 py-1 bg-purple-900/50 text-purple-300 text-xs rounded">
                            Race prediction
                          </span>
                          <span className="px-2 py-1 bg-purple-900/50 text-purple-300 text-xs rounded">
                            Counter-conventional insights
                          </span>
                        </div>
                      )}
                      {!hasProAccess && (
                        <div className="mt-3">
                          <a href="/settings" className="text-purple-400 hover:text-purple-300 text-sm underline">
                            Manage membership →
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                </button>

                {/* Constraint-Aware Option - The Premium N=1 Experience */}
                <button
                  onClick={() => {
                    if (hasProAccess) {
                      setFormData({ ...formData, planType: 'constraint-aware' });
                    }
                  }}
                  disabled={!hasProAccess}
                  className={`w-full p-6 rounded-xl border-2 text-left transition-all ${
                    formData.planType === 'constraint-aware'
                      ? 'border-emerald-500 bg-emerald-900/20'
                      : hasProAccess
                        ? 'border-slate-700/50 bg-slate-900 hover:border-emerald-600'
                        : 'border-slate-800 bg-slate-900/50 opacity-60 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className="text-3xl">🏦</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-lg">Fitness Bank Plan</span>
                        <span className="px-2 py-0.5 bg-emerald-600 text-emerald-100 text-xs rounded-full font-medium">
                          Pro
                        </span>
                        <span className="px-2 py-0.5 bg-amber-600 text-amber-100 text-xs rounded-full font-medium">
                          Recommended
                        </span>
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Full N=1 experience. Analyzes your peak capabilities, detects constraints, respects your training patterns. 
                        Supports tune-up races.
                      </div>
                      {hasProAccess && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <span className="px-2 py-1 bg-emerald-900/50 text-emerald-300 text-xs rounded">
                            Peak 71mpw, 22mi long
                          </span>
                          <span className="px-2 py-1 bg-emerald-900/50 text-emerald-300 text-xs rounded">
                            Injury-aware ramp
                          </span>
                          <span className="px-2 py-1 bg-emerald-900/50 text-emerald-300 text-xs rounded">
                            Tune-up race support
                          </span>
                          <span className="px-2 py-1 bg-emerald-900/50 text-emerald-300 text-xs rounded">
                            Specific prescriptions
                          </span>
                        </div>
                      )}
                      {!hasProAccess && (
                        <div className="mt-3">
                          <a href="/settings" className="text-emerald-400 hover:text-emerald-300 text-sm underline">
                            Manage membership →
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              </div>
            </div>
          )}
          
          {/* Model-Driven Form */}
          {step === 'model-driven-form' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Create Your Model-Driven Plan</h2>
              <p className="text-slate-400 text-sm mb-6">
                Just the basics. We calculate everything else from your training data.
              </p>
              
              <div className="space-y-6">
                {/* Race Distance */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Distance</label>
                  <div className="grid grid-cols-2 gap-3">
                    {DISTANCES.map(d => (
                      <button
                        key={d.value}
                        onClick={() => setFormData({ ...formData, distance: d.value })}
                        className={`p-4 rounded-xl border-2 text-left transition-all ${
                          formData.distance === d.value
                            ? 'border-purple-500 bg-purple-900/20'
                            : 'border-slate-700/50 bg-slate-900 hover:border-slate-600'
                        }`}
                      >
                        <div className="font-bold text-white">{d.label}</div>
                        <div className="text-xs text-slate-400">{d.subtitle}</div>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Race Date */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Date</label>
                  <input
                    type="date"
                    value={formData.race_date}
                    onChange={(e) => setFormData({ ...formData, race_date: e.target.value })}
                    min={new Date(Date.now() + 4 * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                    max={new Date(Date.now() + 52 * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white"
                  />
                  {formData.race_date && (
                    <div className="mt-2 text-sm text-slate-400">
                      {Math.ceil((new Date(formData.race_date).getTime() - Date.now()) / (7 * 24 * 60 * 60 * 1000))} weeks out
                    </div>
                  )}
                </div>
                
                {/* Race Name (optional) */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Name (optional)</label>
                  <input
                    type="text"
                    value={formData.race_name}
                    onChange={(e) => setFormData({ ...formData, race_name: e.target.value })}
                    placeholder="e.g., Boston Marathon"
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
              </div>
              
              {error && (
                <PlanCreateErrorBanner
                  error={error}
                  formatDistance={formatDistance}
                  onAcceptSafeRange={acceptSafeRangeAndResubmit}
                />
              )}
            </div>
          )}

          {/* Model-Driven Preview */}
          {step === 'model-driven-preview' && modelPlanResult && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Your Plan is Ready</h2>
              <p className="text-slate-400 text-sm mb-6">
                Built from your data. Not a template.
              </p>
              
              <div className="space-y-4">
                {/* Prediction */}
                <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 rounded-xl p-5 border border-purple-500/30">
                  <div className="text-sm text-purple-300 mb-1">Predicted Finish</div>
                  <div className="text-3xl font-bold text-white">
                    {modelPlanResult.prediction?.prediction?.time_formatted || 'N/A'}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    {modelPlanResult.prediction?.prediction?.confidence_interval_formatted} ({modelPlanResult.prediction?.prediction?.confidence} confidence)
                  </div>
                </div>
                
                {/* Model Parameters */}
                <div className="bg-slate-900 rounded-xl p-5">
                  <div className="text-sm text-slate-400 mb-3">Your Model</div>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <div className="text-2xl font-bold text-purple-400">{modelPlanResult.model.tau1}d</div>
                      <div className="text-xs text-slate-500">τ1 (fitness)</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-pink-400">{modelPlanResult.model.tau2}d</div>
                      <div className="text-xs text-slate-500">τ2 (fatigue)</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-orange-400">{modelPlanResult.personalization.taper_start_week * 7}d</div>
                      <div className="text-xs text-slate-500">taper</div>
                    </div>
                  </div>
                  
                  {/* Insights */}
                  <div className="space-y-2">
                    {modelPlanResult.model.insights.map((insight, i) => (
                      <div key={i} className="text-sm text-slate-300 flex items-start gap-2">
                        <span className="text-purple-400">•</span>
                        {insight}
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Counter-conventional notes */}
                {modelPlanResult.personalization.notes.length > 0 && (
                  <div className="bg-amber-900/30 border border-amber-700/50 rounded-xl p-5">
                    <div className="text-sm text-amber-400 font-medium mb-2">From Your Data</div>
                    {modelPlanResult.personalization.notes.map((note, i) => (
                      <div key={i} className="text-sm text-slate-300 mt-1">
                        &quot;{note}&quot;
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Summary */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-900 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{modelPlanResult.summary.total_weeks}</div>
                    <div className="text-xs text-slate-500">weeks</div>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">
                      {formatDistance(modelPlanResult.summary.total_distance_m, 0)}
                    </div>
                    <div className="text-xs text-slate-500">total</div>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{Math.round(modelPlanResult.summary.total_tss)}</div>
                    <div className="text-xs text-slate-500">total TSS</div>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Constraint-Aware Form */}
          {step === 'constraint-aware-form' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Your Goal Race</h2>
              <p className="text-slate-400 text-sm mb-6">
                We&apos;ll analyze your full training history to build the perfect plan.
              </p>
              
              <div className="space-y-6">
                {/* Race Distance */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Distance</label>
                  <div className="grid grid-cols-2 gap-3">
                    {DISTANCES.map(d => (
                      <button
                        key={d.value}
                        onClick={() => setFormData({ ...formData, distance: d.value })}
                        className={`p-4 rounded-xl border-2 text-left transition-all ${
                          formData.distance === d.value
                            ? 'border-emerald-500 bg-emerald-900/20'
                            : 'border-slate-700/50 bg-slate-900 hover:border-slate-600'
                        }`}
                      >
                        <div className="font-bold text-white">{d.label}</div>
                        <div className="text-xs text-slate-400">{d.subtitle}</div>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Race Date */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Date</label>
                  <input
                    type="date"
                    value={formData.race_date}
                    onChange={(e) => setFormData({ ...formData, race_date: e.target.value })}
                    min={new Date(Date.now() + 4 * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                    max={new Date(Date.now() + 52 * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white"
                  />
                  {formData.race_date && (
                    <div className="mt-2 text-sm text-slate-400">
                      {Math.ceil((new Date(formData.race_date).getTime() - Date.now()) / (7 * 24 * 60 * 60 * 1000))} weeks out
                    </div>
                  )}
                </div>
                
                {/* Race Name */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Name (optional)</label>
                  <input
                    type="text"
                    value={formData.race_name}
                    onChange={(e) => setFormData({ ...formData, race_name: e.target.value })}
                    placeholder="e.g., Boston Marathon"
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                </div>

                {/* Goal Time */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Goal Time (optional)</label>
                  <input
                    type="text"
                    value={goalTimeDisplay}
                    onChange={(e) => {
                      const raw = e.target.value;
                      setGoalTimeDisplay(raw);
                      const secs = parseTimeToSeconds(raw);
                      setFormData({ ...formData, goal_time_seconds: secs ?? undefined });
                    }}
                    placeholder={formData.distance === 'marathon' || formData.distance === 'half_marathon' ? 'e.g. 1:45:00' : 'e.g. 55:00'}
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                  <div className="text-xs text-slate-500 mt-2">
                    {formData.goal_time_seconds
                      ? `${Math.floor(formData.goal_time_seconds / 3600) > 0 ? Math.floor(formData.goal_time_seconds / 3600) + 'h ' : ''}${Math.floor((formData.goal_time_seconds % 3600) / 60)}m ${formData.goal_time_seconds % 60}s — we'll set your training paces from this.`
                      : 'Enter H:MM:SS or MM:SS. Used to calculate your training paces.'}
                  </div>
                </div>

                {/* Athlete peak weekly volume override */}
                {(() => {
                  const peakDisplay =
                    formData.target_peak_weekly_m !== undefined
                      ? formatDistance(formData.target_peak_weekly_m, 0).replace(/[^\d.]/g, '')
                      : '';
                  const peakMin = isMetric ? 25000 : 16093;
                  const peakMax = isMetric ? 515000 : 321869;
                  const peakPlaceholder = isMetric ? 'e.g. 110' : 'e.g. 68';
                  return (
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-2">
                        Peak Weekly Volume Override (optional, {distanceUnitLong})
                      </label>
                      <input
                        type="number"
                        min={isMetric ? 16 : 10}
                        max={isMetric ? 320 : 200}
                        value={peakDisplay}
                        onChange={(e) => {
                          const raw = e.target.value;
                          if (!raw) {
                            setFormData({ ...formData, target_peak_weekly_m: undefined });
                            return;
                          }
                          const display = Number(raw);
                          const meters = isMetric ? display * 1000 : display * M_PER_MI;
                          setFormData({ ...formData, target_peak_weekly_m: meters });
                        }}
                        placeholder={peakPlaceholder}
                        className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                      />
                      <div className="text-xs text-slate-500 mt-2">
                        If outside safety/plausibility bounds, we clamp and show the exact reason.
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Constraint-Aware Tune-Up Races */}
          {step === 'constraint-aware-tune-up' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Tune-Up Races (Optional)</h2>
              <p className="text-slate-400 text-sm mb-6">
                Add any races you&apos;re doing before your goal race. We&apos;ll coordinate your training around them.
              </p>
              
              <div className="space-y-4">
                {formData.tune_up_races.map((race, index) => (
                  <div key={index} className="bg-slate-900 rounded-xl p-4 border border-slate-700/50">
                    <div className="flex justify-between items-start mb-4">
                      <div className="text-sm font-medium text-emerald-400">Tune-Up Race {index + 1}</div>
                      <button
                        onClick={() => removeTuneUpRace(index)}
                        className="text-red-400 hover:text-red-300 text-sm"
                      >
                        Remove
                      </button>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Date</label>
                        <input
                          type="date"
                          value={race.date}
                          onChange={(e) => updateTuneUpRace(index, 'date', e.target.value)}
                          max={formData.race_date}
                          min={new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Distance</label>
                        <select
                          value={race.distance}
                          onChange={(e) => updateTuneUpRace(index, 'distance', e.target.value)}
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-sm"
                        >
                          <option value="5k">5K</option>
                          <option value="10k">10K</option>
                          <option value="10_mile">10 Mile</option>
                          <option value="half_marathon">Half Marathon</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Race Name</label>
                        <input
                          type="text"
                          value={race.name}
                          onChange={(e) => updateTuneUpRace(index, 'name', e.target.value)}
                          placeholder="e.g., Cherry Blossom 10 Mile"
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Purpose</label>
                        <select
                          value={race.purpose}
                          onChange={(e) => updateTuneUpRace(index, 'purpose', e.target.value)}
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-sm"
                        >
                          <option value="threshold">Threshold (race hard)</option>
                          <option value="sharpening">Sharpening (controlled)</option>
                          <option value="tune_up">Tune-up (moderate)</option>
                          <option value="fitness_check">Fitness check</option>
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
                
                <button
                  onClick={addTuneUpRace}
                  className="w-full p-4 rounded-xl border-2 border-dashed border-slate-700/50 text-slate-400 hover:text-emerald-400 hover:border-emerald-600 transition-all"
                >
                  + Add Tune-Up Race
                </button>
                
                {formData.tune_up_races.length === 0 && (
                  <div className="p-4 bg-slate-800/50 rounded-lg text-center text-sm text-slate-400">
                    No tune-up races? No problem. Click &quot;Generate Plan&quot; to continue.
                  </div>
                )}
              </div>
              
              {error && (
                <PlanCreateErrorBanner
                  error={error}
                  formatDistance={formatDistance}
                  onAcceptSafeRange={acceptSafeRangeAndResubmit}
                />
              )}
            </div>
          )}

          {/* Constraint-Aware Preview */}
          {step === 'constraint-aware-preview' && constraintAwareResult && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Your Personalized Plan</h2>
              <p className="text-slate-400 text-sm mb-6">
                Built from your data. Not a template.
              </p>

              <div className="space-y-4">
                {(() => {
                  const warnings = constraintAwareResult.warnings || [];
                  if (warnings.length === 0) return null;
                  const peakM = constraintAwareResult.soft_gate_applied_peak_weekly_m;
                  const requestedM =
                    constraintAwareResult.soft_gate_requested_peak_weekly_m;
                  const fmtPeak = (m: number | null | undefined) =>
                    m == null ? null : `${formatDistance(m, 1)}/wk`;
                  const cappedFromTo = warnings.find((w) =>
                    w.startsWith('capped_requested_peak_to_safe_range:'),
                  );
                  const autoTuned = warnings.find((w) =>
                    w.startsWith('auto_tuned_peak_to_safe_range:'),
                  );
                  const droppedRange = warnings.find((w) =>
                    w.startsWith('dropped_requested_range_to_safe_peak:'),
                  );
                  const safeRangeBreach = warnings.find((w) =>
                    w.startsWith('safe_range_regen_still_outside_band'),
                  );
                  const heading = safeRangeBreach
                    ? 'Your plan is built — here is what we noticed'
                    : 'We adjusted your peak weekly volume';
                  let body: React.ReactNode = null;
                  if (cappedFromTo) {
                    body = (
                      <>
                        You asked for a peak of <strong>{fmtPeak(requestedM)}</strong>.
                        That is higher than your training history supports right now, so
                        we capped this plan at <strong>{fmtPeak(peakM)}</strong>. The
                        plan you are seeing uses that safer peak. If you still want the
                        higher volume, change the peak in the form and re-generate.
                      </>
                    );
                  } else if (droppedRange) {
                    body = (
                      <>
                        You asked for a peak weekly volume range. Your training history
                        does not support the top of that range, so we built this plan at
                        a single safer peak of <strong>{fmtPeak(peakM)}</strong>.
                        Use this plan as-is, or set a specific peak in the form and
                        re-generate.
                      </>
                    );
                  } else if (autoTuned) {
                    body = (
                      <>
                        We picked a peak of <strong>{fmtPeak(peakM)}</strong> based
                        on what your training history supports. You can override this
                        manually from the form if you want a different peak.
                      </>
                    );
                  } else if (safeRangeBreach) {
                    body = (
                      <>
                        {constraintAwareResult.soft_gate_display_message ||
                          "We built this plan, but the math suggests it is pushing the edge of what your training history supports. Use it as-is, or adjust your peak from the form."}
                      </>
                    );
                  } else {
                    return null;
                  }
                  return (
                    <div
                      role="status"
                      data-testid="soft-gate-warning"
                      className="rounded-xl border border-amber-500/40 bg-amber-900/20 p-4"
                    >
                      <div className="text-sm font-semibold text-amber-200">{heading}</div>
                      <p className="mt-1 text-sm text-amber-100/90">{body}</p>
                    </div>
                  );
                })()}
                {/* Fitness Bank Summary */}
                <div className="bg-gradient-to-r from-emerald-900/50 to-teal-900/50 rounded-xl p-5 border border-emerald-500/30">
                  <div className="text-sm text-emerald-300 mb-2">Your Fitness Bank</div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="text-2xl font-bold text-white">
                        {formatDistance(constraintAwareResult.fitness_bank.peak.weekly_m, 0)}
                      </div>
                      <div className="text-xs text-slate-400">peak weekly</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-white">
                        {formatDistance(constraintAwareResult.fitness_bank.peak.long_run_m, 0)}
                      </div>
                      <div className="text-xs text-slate-400">longest run</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-white">
                        {formatDistance(constraintAwareResult.fitness_bank.peak.mp_long_run_m, 0)}
                      </div>
                      <div className="text-xs text-slate-400">proven @MP</div>
                    </div>
                  </div>
                  {constraintAwareResult.fitness_bank.constraint.returning && (
                    <div className="mt-3 text-sm text-amber-400">
                      ⚠️ Detected: {constraintAwareResult.fitness_bank.constraint.type} - plan protects first weeks
                    </div>
                  )}
                </div>
                
                {/* Prediction */}
                <div className="bg-slate-900 rounded-xl p-5">
                  <div className="text-sm text-slate-400 mb-1">Predicted Finish</div>
                  <div className="text-3xl font-bold text-white">
                    {constraintAwareResult.prediction.scenarios?.base?.time || constraintAwareResult.prediction.time || 'N/A'}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    {constraintAwareResult.prediction.confidence_interval}
                  </div>
                  {constraintAwareResult.prediction.uncertainty_reason && (
                    <div className="text-xs text-amber-400 mt-2">
                      {constraintAwareResult.prediction.uncertainty_reason}
                    </div>
                  )}
                  {constraintAwareResult.prediction.rationale_tags?.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {constraintAwareResult.prediction.rationale_tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-1 rounded bg-slate-800 text-slate-300 text-xs"
                        >
                          {tag.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Scenario Predictions */}
                {constraintAwareResult.prediction.scenarios && (
                  <div className="bg-slate-900 rounded-xl p-5">
                    <div className="text-sm text-slate-400 mb-3">Prediction Scenarios</div>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="rounded-lg border border-slate-700/50 p-3">
                        <div className="text-xs text-slate-500">Conservative</div>
                        <div className="text-lg font-bold text-white">{constraintAwareResult.prediction.scenarios.conservative.time}</div>
                        <div className="text-xs text-slate-400">{constraintAwareResult.prediction.scenarios.conservative.confidence}</div>
                      </div>
                      <div className="rounded-lg border border-emerald-700/50 p-3 bg-emerald-900/10">
                        <div className="text-xs text-slate-500">Base</div>
                        <div className="text-lg font-bold text-emerald-300">{constraintAwareResult.prediction.scenarios.base.time}</div>
                        <div className="text-xs text-slate-400">{constraintAwareResult.prediction.scenarios.base.confidence}</div>
                      </div>
                      <div className="rounded-lg border border-slate-700/50 p-3">
                        <div className="text-xs text-slate-500">Aggressive</div>
                        <div className="text-lg font-bold text-white">{constraintAwareResult.prediction.scenarios.aggressive.time}</div>
                        <div className="text-xs text-slate-400">{constraintAwareResult.prediction.scenarios.aggressive.confidence}</div>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Model Parameters */}
                <div className="bg-slate-900 rounded-xl p-5">
                  <div className="text-sm text-slate-400 mb-3">Your Response Model</div>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-2xl font-bold text-emerald-400">{constraintAwareResult.model.tau1}d</div>
                      <div className="text-xs text-slate-500">τ1 (fitness adaptation)</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-teal-400">{constraintAwareResult.model.tau2}d</div>
                      <div className="text-xs text-slate-500">τ2 (fatigue decay)</div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    {constraintAwareResult.model.insights.map((insight, i) => (
                      <div key={i} className="text-sm text-slate-300 flex items-start gap-2">
                        <span className="text-emerald-400">•</span>
                        {insight}
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Plan Summary */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-900 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{constraintAwareResult.summary.total_weeks}</div>
                    <div className="text-xs text-slate-500">weeks</div>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">
                      {formatDistance(constraintAwareResult.summary.total_distance_m, 0)}
                    </div>
                    <div className="text-xs text-slate-500">total</div>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">
                      {formatDistance(constraintAwareResult.summary.peak_distance_m, 0)}
                    </div>
                    <div className="text-xs text-slate-500">peak week</div>
                  </div>
                </div>

                {/* Volume contract */}
                {constraintAwareResult.volume_contract && (
                  <div className="bg-slate-900 rounded-xl p-5">
                    <div className="text-sm text-slate-400 mb-2">Volume Contract</div>
                    <div className="text-sm text-slate-300">
                      Band: {formatDistance(constraintAwareResult.volume_contract.band_min_m, 0)} - {formatDistance(constraintAwareResult.volume_contract.band_max_m, 0)}/wk
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Source: {constraintAwareResult.volume_contract.source.replace('_', ' ')} | Peak confidence: {constraintAwareResult.volume_contract.peak_confidence}
                    </div>
                    {constraintAwareResult.volume_contract.clamped && (
                      <div className="text-xs text-amber-400 mt-2">
                        {constraintAwareResult.volume_contract.clamp_reason || 'Requested override was clamped for safety.'}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Personalized Insights */}
                {constraintAwareResult.personalization.notes.length > 0 && (
                  <div className="bg-amber-900/30 border border-amber-700/50 rounded-xl p-5">
                    <div className="text-sm text-amber-400 font-medium mb-2">From Your Data</div>
                    {constraintAwareResult.personalization.notes.slice(0, 3).map((note, i) => (
                      <div key={i} className="text-sm text-slate-300 mt-2">
                        &quot;{note}&quot;
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Week Themes Preview */}
                <div className="bg-slate-900 rounded-xl p-5">
                  <div className="text-sm text-slate-400 mb-3">Week Themes</div>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {constraintAwareResult.weeks.map((week, i) => (
                      <div key={i} className="flex justify-between text-sm">
                        <span className="text-slate-300">Week {week.week}: {week.theme.replace('_', ' ')}</span>
                        <span className="text-slate-500">
                          {formatDistance(week.total_distance_m, 0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Distance Selection */}
          {step === 'distance' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">What distance are you training for?</h2>
              <div className="grid grid-cols-2 gap-4">
                {DISTANCES.map(d => (
                  <button
                    key={d.value}
                    onClick={() => setFormData({ ...formData, distance: d.value })}
                    className={`p-6 rounded-xl border-2 text-left transition-all ${
                      formData.distance === d.value
                        ? 'border-pink-500 bg-pink-900/20'
                        : 'border-slate-700/50 bg-slate-900 hover:border-slate-600'
                    }`}
                  >
                    <div className="text-3xl mb-2">{d.icon}</div>
                    <div className="font-bold text-white">{d.label}</div>
                    <div className="text-sm text-slate-400">{d.subtitle}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {/* Race Date */}
          {step === 'race-date' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">When is your race?</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Date</label>
                  <input
                    type="date"
                    value={formData.race_date}
                    onChange={(e) => setFormData({ ...formData, race_date: e.target.value })}
                    min={new Date(Date.now() + 8 * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Name (optional)</label>
                  <input
                    type="text"
                    value={formData.race_name}
                    onChange={(e) => setFormData({ ...formData, race_name: e.target.value })}
                    placeholder="e.g., Boston Marathon"
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
                
                {formData.race_date && (
                  <div className="p-4 bg-slate-900 rounded-lg">
                    <div className="text-sm text-slate-400">Training Duration</div>
                    <div className="text-2xl font-bold text-white">
                      {weeksUntilRace} weeks
                      {weeksUntilRace > 18 && (
                        <span className="text-sm font-normal text-slate-400 ml-2">
                          (18-week plan recommended)
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Current Fitness */}
          {step === 'current-fitness' && (() => {
            const mPerUnit = isMetric ? 1000 : M_PER_MI;
            const weeklyDisplay = Math.round(formData.current_weekly_m / mPerUnit);
            const weeklyMin = isMetric ? 16 : 10;
            const weeklyMax = isMetric ? 160 : 100;
            const weeklyStep = 5;
            const weeklyMid = isMetric ? 80 : 50;

            const longRunDisplay = Math.round(formData.longest_recent_run_m / mPerUnit);
            const longMin = isMetric ? 5 : 3;
            const longMax = isMetric ? 35 : 22;
            const longStep = 1;
            const longMid = isMetric ? 20 : 12;

            return (
              <div>
                <h2 className="text-xl font-bold text-white mb-4">What is your current fitness level?</h2>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">
                      Current Weekly Volume: <span className="text-white">{weeklyDisplay} {distanceUnitShort}</span>
                    </label>
                    <input
                      type="range"
                      min={weeklyMin}
                      max={weeklyMax}
                      step={weeklyStep}
                      value={weeklyDisplay}
                      onChange={(e) => {
                        const display = Number(e.target.value);
                        setFormData({ ...formData, current_weekly_m: display * mPerUnit });
                      }}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                      <span>{weeklyMin} {distanceUnitShort}</span>
                      <span>{weeklyMid} {distanceUnitShort}</span>
                      <span>{weeklyMax} {distanceUnitShort}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">
                      Longest Run in Past Month: <span className="text-white">{longRunDisplay} {distanceUnitShort}</span>
                    </label>
                    <input
                      type="range"
                      min={longMin}
                      max={longMax}
                      step={longStep}
                      value={longRunDisplay}
                      onChange={(e) => {
                        const display = Number(e.target.value);
                        setFormData({ ...formData, longest_recent_run_m: display * mPerUnit });
                      }}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                      <span>{longMin} {distanceUnitShort}</span>
                      <span>{longMid} {distanceUnitShort}</span>
                      <span>{longMax} {distanceUnitShort}</span>
                    </div>
                  </div>

                  <div className="p-4 bg-slate-900 rounded-lg">
                    <div className="text-sm text-slate-400">Your Volume Tier</div>
                    <div className="text-xl font-bold text-orange-400 capitalize">
                      {getVolumeTier().replace('_', ' ')}
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}
          
          {/* Availability */}
          {step === 'availability' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">How many days can you run each week?</h2>
              <div className="grid grid-cols-3 gap-4">
                {[5, 6, 7].map(days => (
                  <button
                    key={days}
                    onClick={() => setFormData({ ...formData, days_per_week: days })}
                    className={`p-6 rounded-xl border-2 text-center transition-all ${
                      formData.days_per_week === days
                        ? 'border-pink-500 bg-pink-900/20'
                        : 'border-slate-700/50 bg-slate-900 hover:border-slate-600'
                    }`}
                  >
                    <div className="text-3xl font-bold text-white">{days}</div>
                    <div className="text-sm text-slate-400">days/week</div>
                  </button>
                ))}
              </div>
              
              <div className="mt-6 p-4 bg-slate-900 rounded-lg">
                <p className="text-sm text-slate-400">
                  {formData.days_per_week === 5 && "5 days gives you flexibility with 2 rest days. Quality over quantity."}
                  {formData.days_per_week === 6 && "6 days is ideal for most runners. One rest day for recovery."}
                  {formData.days_per_week === 7 && "7 days maximizes training stimulus. One day should be very easy."}
                </p>
              </div>
            </div>
          )}
          
          {/* Recent Race (for personalized paces) */}
          {step === 'recent-race' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Do you have a recent race time?</h2>
              <p className="text-slate-400 text-sm mb-6">
                A recent race time (within the last 6 months) helps us calculate your personalized training paces.
              </p>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Distance</label>
                  <select
                    value={formData.recent_race_distance || ''}
                    onChange={(e) => setFormData({ ...formData, recent_race_distance: e.target.value || undefined })}
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white"
                  >
                    <option value="">No recent race (skip)</option>
                    <option value="5k">5K</option>
                    <option value="10k">10K</option>
                    <option value="half_marathon">Half Marathon</option>
                    <option value="marathon">Marathon</option>
                  </select>
                </div>
                
                {formData.recent_race_distance && (
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Finish Time</label>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <input
                          type="number"
                          placeholder="Hours"
                          min="0"
                          max="10"
                          className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                          onChange={(e) => {
                            const hours = e.target.value || '0';
                            const [_, mins, secs] = (formData.recent_race_time || '0:00:00').split(':');
                            setFormData({ ...formData, recent_race_time: `${hours}:${mins || '00'}:${secs || '00'}` });
                          }}
                        />
                        <span className="text-xs text-slate-500 mt-1">hours</span>
                      </div>
                      <div>
                        <input
                          type="number"
                          placeholder="Minutes"
                          min="0"
                          max="59"
                          className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                          onChange={(e) => {
                            const mins = e.target.value || '00';
                            const [hours, _, secs] = (formData.recent_race_time || '0:00:00').split(':');
                            setFormData({ ...formData, recent_race_time: `${hours || '0'}:${mins.padStart(2, '0')}:${secs || '00'}` });
                          }}
                        />
                        <span className="text-xs text-slate-500 mt-1">minutes</span>
                      </div>
                      <div>
                        <input
                          type="number"
                          placeholder="Seconds"
                          min="0"
                          max="59"
                          className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                          onChange={(e) => {
                            const secs = e.target.value || '00';
                            const [hours, mins, _] = (formData.recent_race_time || '0:00:00').split(':');
                            setFormData({ ...formData, recent_race_time: `${hours || '0'}:${mins || '00'}:${secs.padStart(2, '0')}` });
                          }}
                        />
                        <span className="text-xs text-slate-500 mt-1">seconds</span>
                      </div>
                    </div>
                  </div>
                )}
                
                {!formData.recent_race_distance && (
                  <div className="p-4 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                    <p className="text-sm text-blue-300">
                      No problem! Your plan will use effort-based descriptions (e.g., &quot;conversational pace&quot;) instead of specific paces.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Experience */}
          {step === 'experience' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">What is your racing experience?</h2>
              <div className="space-y-4">
                {EXPERIENCE_LEVELS.map(level => (
                  <button
                    key={level.value}
                    onClick={() => setFormData({ ...formData, experience_level: level.value })}
                    className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                      formData.experience_level === level.value
                        ? 'border-pink-500 bg-pink-900/20'
                        : 'border-slate-700/50 bg-slate-900 hover:border-slate-600'
                    }`}
                  >
                    <div className="font-bold text-white">{level.label}</div>
                    <div className="text-sm text-slate-400">{level.description}</div>
                  </button>
                ))}
              </div>
              
              <div className="mt-6">
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Any injury concerns? (optional)
                </label>
                <textarea
                  value={formData.injury_history}
                  onChange={(e) => setFormData({ ...formData, injury_history: e.target.value })}
                  placeholder="e.g., Previous IT band issues, currently healthy"
                  rows={3}
                  className="w-full px-4 py-3 bg-slate-900 border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                />
              </div>
            </div>
          )}
          
          {/* Review */}
          {step === 'review' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Review Your Plan</h2>

              {/* Plan Tier Indicator */}
              <div className={`mb-6 p-4 rounded-lg border ${
                hasProAccess
                  ? 'bg-gradient-to-r from-purple-900/50 to-pink-900/50 border-purple-500'
                  : 'bg-slate-800 border-slate-600'
              }`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-slate-400">Plan Type</div>
                    <div className={`text-lg font-bold ${
                      hasProAccess ? 'text-purple-300' : 'text-slate-300'
                    }`}>
                      {hasProAccess ? '✨ Pro Custom Plan' : 
                       formData.recent_race_distance && formData.recent_race_time ? 'Semi-Custom Plan' :
                       'Standard Plan'}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-slate-400">Your Tier</div>
                    <div className={`text-lg font-bold ${
                      hasProAccess ? 'text-purple-300' : 'text-slate-400'
                    }`}>
                      {hasProAccess ? 'pro' : 'free'}
                    </div>
                  </div>
                </div>
                {hasProAccess && (
                  <div className="text-sm text-purple-200 mt-2">
                    ✓ Personalized paces from your Strava data • ✓ Dynamic adaptation
                  </div>
                )}
                {!hasProAccess && !formData.recent_race_time && (
                  <div className="text-sm text-amber-400 mt-2">
                    ⚠️ Add a recent race time for personalized paces
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-sm text-slate-400">Distance</div>
                    <div className="text-lg font-bold text-white capitalize">
                      {formData.distance.replace('_', ' ')}
                    </div>
                  </div>

                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-sm text-slate-400">Duration</div>
                    <div className="text-lg font-bold text-white">{planDuration} weeks</div>
                  </div>

                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-sm text-slate-400">Days/Week</div>
                    <div className="text-lg font-bold text-white">{formData.days_per_week}</div>
                  </div>

                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-sm text-slate-400">Volume Tier</div>
                    <div className="text-lg font-bold text-orange-400 capitalize">
                      {getVolumeTier()}
                    </div>
                  </div>
                </div>
                
                {formData.race_date && (
                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-sm text-slate-400">Race Day</div>
                    <div className="text-lg font-bold text-white">
                      {new Date(formData.race_date).toLocaleDateString('en-US', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </div>
                    {formData.race_name && (
                      <div className="text-sm text-slate-400 mt-1">{formData.race_name}</div>
                    )}
                  </div>
                )}
                
                {!isAuthenticated && (
                  <div className="p-4 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                    <div className="font-semibold text-blue-400 mb-1">Connect Strava for Better Results</div>
                    <p className="text-sm text-slate-400">
                      Logged in users get personalized paces based on actual performance data.
                    </p>
                  </div>
                )}
              </div>
              
              {error && (
                <PlanCreateErrorBanner
                  error={error}
                  formatDistance={formatDistance}
                  onAcceptSafeRange={acceptSafeRangeAndResubmit}
                />
              )}
            </div>
          )}
        </div>
        
        {/* Navigation */}
        <div className="flex justify-between">
          <button
            onClick={prevStep}
            disabled={step === 'plan-type'}
            className="px-6 py-3 bg-slate-800 border border-slate-700/50 rounded-lg font-semibold text-slate-400 disabled:opacity-50 hover:text-white hover:border-slate-600"
          >
            Back
          </button>
          
          {/* Model-driven flow buttons */}
          {step === 'model-driven-form' ? (
            <button
              onClick={handleModelDrivenSubmit}
              disabled={isLoading || !formData.distance || !formData.race_date}
              className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" />
                  Generating...
                </>
              ) : (
                <>🧠 Generate Plan</>
              )}
            </button>
          ) : step === 'model-driven-preview' ? (
            <button
              onClick={applyModelDrivenToCalendar}
              disabled={isLoading}
              className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" />
                  Applying...
                </>
              ) : (
                <>📅 Apply to Calendar</>
              )}
            </button>
          ) : step === 'constraint-aware-tune-up' ? (
            <button
              onClick={() => handleConstraintAwareSubmit()}
              disabled={isLoading || !formData.distance || !formData.race_date}
              className="px-8 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" />
                  Generating...
                </>
              ) : (
                <>🏦 Generate Plan</>
              )}
            </button>
          ) : step === 'constraint-aware-preview' ? (
            <button
              onClick={applyConstraintAwareToCalendar}
              disabled={isLoading}
              className="px-8 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" />
                  Applying...
                </>
              ) : (
                <>📅 Apply to Calendar</>
              )}
            </button>
          ) : step === 'review' ? (
            <button
              onClick={handleSubmit}
              disabled={isLoading || !formData.distance || !formData.race_date}
              className="px-8 py-3 bg-gradient-to-r from-pink-600 to-orange-600 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" />
                  Creating Plan...
                </>
              ) : (
                'Create Plan'
              )}
            </button>
          ) : (
            <button
              onClick={nextStep}
              disabled={
                (step === 'plan-type' && !formData.planType) ||
                (step === 'distance' && !formData.distance) ||
                (step === 'race-date' && !formData.race_date) ||
                (step === 'constraint-aware-form' && (!formData.distance || !formData.race_date))
              }
              className={`px-8 py-3 rounded-lg font-semibold text-white disabled:opacity-50 ${
                formData.planType === 'constraint-aware'
                  ? 'bg-gradient-to-r from-emerald-600 to-teal-600'
                  : 'bg-gradient-to-r from-pink-600 to-orange-600'
              }`}
            >
              Next
            </button>
          )}
        </div>
        
        {/* Preview Link */}
        <div className="text-center mt-8">
          <a
            href="/plans/preview"
            className="text-sm text-slate-400 hover:text-pink-400"
          >
            Want to explore plans first? Browse plan previews →
          </a>
        </div>
      </div>
    </div>
  );
}
