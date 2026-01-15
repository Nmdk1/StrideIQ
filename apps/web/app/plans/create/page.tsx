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
import { useAuth } from '@/lib/context/AuthContext';
import { parseTimeToSeconds } from '@/lib/utils/time';
import { calendarKeys } from '@/lib/hooks/queries/calendar';

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
  current_weekly_miles: number;
  longest_recent_run: number;
  days_per_week: number;
  recent_race_distance?: string;
  recent_race_time?: string;
  experience_level: string;
  injury_history: string;
  goal_time_seconds?: number;
  tune_up_races: TuneUpRace[];
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

const DISTANCES = [
  { value: 'marathon', label: 'Marathon', subtitle: '26.2 miles', icon: '🏃' },
  { value: 'half_marathon', label: 'Half Marathon', subtitle: '13.1 miles', icon: '🏃' },
  { value: '10k', label: '10K', subtitle: '6.2 miles', icon: '🏃' },
  { value: '5k', label: '5K', subtitle: '3.1 miles', icon: '🏃' },
];

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'New to Racing', description: 'This is my first structured training plan' },
  { value: 'intermediate', label: 'Some Experience', description: 'I have raced this distance before' },
  { value: 'experienced', label: 'Experienced', description: 'I have trained with structured plans' },
];

export default function CreatePlanPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, isAuthenticated: authAuthenticated } = useAuth();
  const [step, setStep] = useState<Step>('plan-type');
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelPreview, setModelPreview] = useState<ModelDrivenPreview | null>(null);
  const [modelPlanResult, setModelPlanResult] = useState<import('@/lib/api/services/plans').ModelDrivenPlanResponse | null>(null);
  
  const [formData, setFormData] = useState<PlanFormData>({
    planType: 'template',
    distance: '',
    race_date: '',
    race_name: '',
    current_weekly_miles: 30,
    longest_recent_run: 10,
    days_per_week: 6,
    experience_level: 'intermediate',
    injury_history: '',
    tune_up_races: [],
  });
  const [constraintAwareResult, setConstraintAwareResult] = useState<import('@/lib/api/services/plans').ConstraintAwarePlanResponse | null>(null);
  const [constraintAwarePreview, setConstraintAwarePreview] = useState<import('@/lib/api/services/plans').ConstraintAwarePreview | null>(null);
  
  // Check if user is elite tier
  const isEliteTier = user?.subscription_tier === 'elite';
  
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
    if (formData.current_weekly_miles < 35) return 'builder';
    if (formData.current_weekly_miles < 45) return 'low';
    if (formData.current_weekly_miles < 60) return 'mid';
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
      const errorMessage = err instanceof Error ? err.message : 'Failed to create plan';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle constraint-aware plan creation
  const handleConstraintAwareSubmit = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // First get preview to show fitness bank
      const preview = await planService.previewConstraintAware(
        formData.race_date,
        formData.distance
      );
      setConstraintAwarePreview(preview);
      
      // Then create the full plan
      const result = await planService.createConstraintAware({
        race_date: formData.race_date,
        race_distance: formData.distance,
        goal_time_seconds: formData.goal_time_seconds,
        race_name: formData.race_name || undefined,
        tune_up_races: formData.tune_up_races.length > 0 ? formData.tune_up_races : undefined,
      });
      
      setConstraintAwareResult(result);
      setStep('constraint-aware-preview');
      
    } catch (err) {
      console.error('[Plan Create] Error creating constraint-aware plan:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to create plan';
      setError(errorMessage);
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
      setError('Failed to apply plan to calendar');
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
      setError('Failed to apply plan to calendar');
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
      
      // Check user tier
      const isEliteTier = user?.subscription_tier && 
        ['elite'].includes(user.subscription_tier);
      const isPaidTier = user?.subscription_tier && 
        ['elite', 'pro', 'premium', 'guided', 'subscription'].includes(user.subscription_tier);
      const hasPaceData = formData.recent_race_distance && raceTimeSeconds;
      
      // Use auth state from hook, not local state
      // Note: AuthContext stores token as 'auth_token', not 'token'
      const authValid = !!user && !!localStorage.getItem('auth_token');
      
      // Debug logging
      console.log('[Plan Create] Creating plan:', {
        tier: user?.subscription_tier,
        isEliteTier,
        isPaidTier,
        hasPaceData,
        authValid,
        localIsAuthenticated: isAuthenticated,
      });
      
      // Route based on tier
      console.log('[Plan Create] Routing decision:', { authValid, isEliteTier, hasPaceData, isPaidTier });
      
      if (authValid && isEliteTier) {
        // ELITE TIER: Fully custom plan
        console.log('[Plan Create] >>> TAKING ELITE/CUSTOM PATH');
        await planService.createCustom({
          distance: formData.distance,
          race_date: formData.race_date,
          race_name: formData.race_name || undefined,
          days_per_week: formData.days_per_week,
          current_weekly_miles: formData.current_weekly_miles,
          recent_race_distance: formData.recent_race_distance,
          recent_race_time_seconds: raceTimeSeconds ?? undefined,
        });
      } else if (authValid && hasPaceData) {
        // SEMI-CUSTOM: Paid tier or one-time purchase
        console.log('[Plan Create] >>> TAKING SEMI-CUSTOM PATH');
        if (!isPaidTier) {
          // Check if already purchased (via session storage)
          const purchaseData = sessionStorage.getItem('plan_purchased');
          if (!purchaseData) {
            // Redirect to checkout for $5 payment
            const params = new URLSearchParams({
              tier: 'semi_custom',
              distance: formData.distance,
              duration: planDuration.toString(),
              days: formData.days_per_week.toString(),
              volume: getVolumeTier(),
            });
            router.push(`/plans/checkout?${params.toString()}`);
            return;
          }
          sessionStorage.removeItem('plan_purchased');
        }
        
        // Create semi-custom plan with personalized paces
        await planService.createSemiCustom({
          distance: formData.distance,
          race_date: formData.race_date,
          days_per_week: formData.days_per_week,
          current_weekly_miles: formData.current_weekly_miles,
          recent_race_distance: formData.recent_race_distance,
          recent_race_time_seconds: raceTimeSeconds,
          race_name: formData.race_name || undefined,
        });
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
      const errorMessage = err instanceof Error ? err.message : 'Failed to create plan';
      setError(errorMessage);
      // Stay on page - don't redirect
      return;
    } finally {
      setIsLoading(false);
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
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100">
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
                      : 'border-slate-700/50 bg-[#0a0a0f] hover:border-slate-600'
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
                    if (isEliteTier) {
                      setFormData({ ...formData, planType: 'model-driven' });
                    }
                  }}
                  disabled={!isEliteTier}
                  className={`w-full p-6 rounded-xl border-2 text-left transition-all ${
                    formData.planType === 'model-driven'
                      ? 'border-purple-500 bg-purple-900/20'
                      : isEliteTier
                        ? 'border-slate-700/50 bg-[#0a0a0f] hover:border-purple-600'
                        : 'border-slate-800 bg-slate-900/50 opacity-60 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className="text-3xl">🧠</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-lg">Model-Driven Plan</span>
                        <span className="px-2 py-0.5 bg-purple-600 text-purple-100 text-xs rounded-full font-medium">
                          Elite
                        </span>
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Built from YOUR data. Calibrates τ1/τ2 from your training history, predicts race time, calculates optimal taper.
                      </div>
                      {isEliteTier && (
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
                      {!isEliteTier && (
                        <div className="mt-3">
                          <a href="/pricing" className="text-purple-400 hover:text-purple-300 text-sm underline">
                            Upgrade to Elite →
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                </button>

                {/* Constraint-Aware Option - The Premium N=1 Experience */}
                <button
                  onClick={() => {
                    if (isEliteTier) {
                      setFormData({ ...formData, planType: 'constraint-aware' });
                    }
                  }}
                  disabled={!isEliteTier}
                  className={`w-full p-6 rounded-xl border-2 text-left transition-all ${
                    formData.planType === 'constraint-aware'
                      ? 'border-emerald-500 bg-emerald-900/20'
                      : isEliteTier
                        ? 'border-slate-700/50 bg-[#0a0a0f] hover:border-emerald-600'
                        : 'border-slate-800 bg-slate-900/50 opacity-60 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className="text-3xl">🏦</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-lg">Fitness Bank Plan</span>
                        <span className="px-2 py-0.5 bg-emerald-600 text-emerald-100 text-xs rounded-full font-medium">
                          Elite
                        </span>
                        <span className="px-2 py-0.5 bg-amber-600 text-amber-100 text-xs rounded-full font-medium">
                          Recommended
                        </span>
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Full N=1 experience. Analyzes your peak capabilities, detects constraints, respects your training patterns. 
                        Supports tune-up races.
                      </div>
                      {isEliteTier && (
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
                      {!isEliteTier && (
                        <div className="mt-3">
                          <a href="/pricing" className="text-emerald-400 hover:text-emerald-300 text-sm underline">
                            Upgrade to Elite →
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
                            : 'border-slate-700/50 bg-[#0a0a0f] hover:border-slate-600'
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
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white"
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
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
              </div>
              
              {error && (
                <div className="mt-4 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-400">
                  {error}
                </div>
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
                <div className="bg-[#0a0a0f] rounded-xl p-5">
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
                  <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{modelPlanResult.summary.total_weeks}</div>
                    <div className="text-xs text-slate-500">weeks</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{Math.round(modelPlanResult.summary.total_miles)}</div>
                    <div className="text-xs text-slate-500">total miles</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
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
                            : 'border-slate-700/50 bg-[#0a0a0f] hover:border-slate-600'
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
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white"
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
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
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
                  <div key={index} className="bg-[#0a0a0f] rounded-xl p-4 border border-slate-700/50">
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
                <div className="mt-4 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-400">
                  {error}
                </div>
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
                {/* Fitness Bank Summary */}
                <div className="bg-gradient-to-r from-emerald-900/50 to-teal-900/50 rounded-xl p-5 border border-emerald-500/30">
                  <div className="text-sm text-emerald-300 mb-2">Your Fitness Bank</div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="text-2xl font-bold text-white">{constraintAwareResult.fitness_bank.peak.weekly_miles.toFixed(0)}</div>
                      <div className="text-xs text-slate-400">peak mpw</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-white">{constraintAwareResult.fitness_bank.peak.long_run.toFixed(0)}</div>
                      <div className="text-xs text-slate-400">longest run</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-white">{constraintAwareResult.fitness_bank.peak.mp_long_run.toFixed(0)}</div>
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
                <div className="bg-[#0a0a0f] rounded-xl p-5">
                  <div className="text-sm text-slate-400 mb-1">Predicted Finish</div>
                  <div className="text-3xl font-bold text-white">
                    {constraintAwareResult.prediction.time || 'N/A'}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    {constraintAwareResult.prediction.confidence_interval}
                  </div>
                </div>
                
                {/* Model Parameters */}
                <div className="bg-[#0a0a0f] rounded-xl p-5">
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
                  <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{constraintAwareResult.summary.total_weeks}</div>
                    <div className="text-xs text-slate-500">weeks</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{Math.round(constraintAwareResult.summary.total_miles)}</div>
                    <div className="text-xs text-slate-500">total miles</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-white">{Math.round(constraintAwareResult.summary.peak_miles)}</div>
                    <div className="text-xs text-slate-500">peak week</div>
                  </div>
                </div>
                
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
                <div className="bg-[#0a0a0f] rounded-xl p-5">
                  <div className="text-sm text-slate-400 mb-3">Week Themes</div>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {constraintAwareResult.weeks.map((week, i) => (
                      <div key={i} className="flex justify-between text-sm">
                        <span className="text-slate-300">Week {week.week}: {week.theme.replace('_', ' ')}</span>
                        <span className="text-slate-500">{week.total_miles.toFixed(0)}mi</span>
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
                        : 'border-slate-700/50 bg-[#0a0a0f] hover:border-slate-600'
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
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Race Name (optional)</label>
                  <input
                    type="text"
                    value={formData.race_name}
                    onChange={(e) => setFormData({ ...formData, race_name: e.target.value })}
                    placeholder="e.g., Boston Marathon"
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
                
                {formData.race_date && (
                  <div className="p-4 bg-[#0a0a0f] rounded-lg">
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
          {step === 'current-fitness' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">What is your current fitness level?</h2>
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">
                    Current Weekly Mileage: <span className="text-white">{formData.current_weekly_miles} miles</span>
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    step="5"
                    value={formData.current_weekly_miles}
                    onChange={(e) => setFormData({ ...formData, current_weekly_miles: Number(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>10 mi</span>
                    <span>50 mi</span>
                    <span>100 mi</span>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">
                    Longest Run in Past Month: <span className="text-white">{formData.longest_recent_run} miles</span>
                  </label>
                  <input
                    type="range"
                    min="3"
                    max="22"
                    step="1"
                    value={formData.longest_recent_run}
                    onChange={(e) => setFormData({ ...formData, longest_recent_run: Number(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>3 mi</span>
                    <span>12 mi</span>
                    <span>22 mi</span>
                  </div>
                </div>
                
                <div className="p-4 bg-[#0a0a0f] rounded-lg">
                  <div className="text-sm text-slate-400">Your Volume Tier</div>
                  <div className="text-xl font-bold text-orange-400 capitalize">
                    {getVolumeTier().replace('_', ' ')}
                  </div>
                </div>
              </div>
            </div>
          )}
          
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
                        : 'border-slate-700/50 bg-[#0a0a0f] hover:border-slate-600'
                    }`}
                  >
                    <div className="text-3xl font-bold text-white">{days}</div>
                    <div className="text-sm text-slate-400">days/week</div>
                  </button>
                ))}
              </div>
              
              <div className="mt-6 p-4 bg-[#0a0a0f] rounded-lg">
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
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white"
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
                          className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
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
                          className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
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
                          className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
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
                        : 'border-slate-700/50 bg-[#0a0a0f] hover:border-slate-600'
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
                  className="w-full px-4 py-3 bg-[#0a0a0f] border border-slate-700/50 rounded-lg text-white placeholder-slate-500"
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
                user?.subscription_tier === 'elite' 
                  ? 'bg-gradient-to-r from-purple-900/50 to-pink-900/50 border-purple-500'
                  : 'bg-slate-800 border-slate-600'
              }`}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-slate-400">Plan Type</div>
                    <div className={`text-lg font-bold ${
                      user?.subscription_tier === 'elite' ? 'text-purple-300' : 'text-slate-300'
                    }`}>
                      {user?.subscription_tier === 'elite' ? '✨ Elite Custom Plan' : 
                       formData.recent_race_distance && formData.recent_race_time ? 'Semi-Custom Plan' :
                       'Standard Plan'}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-slate-400">Your Tier</div>
                    <div className={`text-lg font-bold ${
                      user?.subscription_tier === 'elite' ? 'text-purple-300' : 'text-slate-400'
                    }`}>
                      {user?.subscription_tier || 'free'}
                    </div>
                  </div>
                </div>
                {user?.subscription_tier === 'elite' && (
                  <div className="text-sm text-purple-200 mt-2">
                    ✓ Personalized paces from your Strava data • ✓ Dynamic adaptation
                  </div>
                )}
                {user?.subscription_tier !== 'elite' && !formData.recent_race_time && (
                  <div className="text-sm text-amber-400 mt-2">
                    ⚠️ Add a recent race time for personalized paces
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-[#0a0a0f] rounded-lg p-4">
                    <div className="text-sm text-slate-400">Distance</div>
                    <div className="text-lg font-bold text-white capitalize">
                      {formData.distance.replace('_', ' ')}
                    </div>
                  </div>

                  <div className="bg-[#0a0a0f] rounded-lg p-4">
                    <div className="text-sm text-slate-400">Duration</div>
                    <div className="text-lg font-bold text-white">{planDuration} weeks</div>
                  </div>

                  <div className="bg-[#0a0a0f] rounded-lg p-4">
                    <div className="text-sm text-slate-400">Days/Week</div>
                    <div className="text-lg font-bold text-white">{formData.days_per_week}</div>
                  </div>

                  <div className="bg-[#0a0a0f] rounded-lg p-4">
                    <div className="text-sm text-slate-400">Volume Tier</div>
                    <div className="text-lg font-bold text-orange-400 capitalize">
                      {getVolumeTier()}
                    </div>
                  </div>
                </div>
                
                {formData.race_date && (
                  <div className="bg-[#0a0a0f] rounded-lg p-4">
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
                <div className="mt-4 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-400">
                  {error}
                </div>
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
              onClick={handleConstraintAwareSubmit}
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
