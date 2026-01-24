/**
 * Onboarding Flow Page
 * 
 * Multi-step wizard for new users following waterfall intake approach.
 * Stages: initial -> basic_profile -> goals -> nutrition_setup -> work_setup -> complete
 * 
 * Tone: Sparse, non-guilt-inducing, everything optional except basics.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { authService } from '@/lib/api/services/auth';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { stravaService } from '@/lib/api/services/strava';
import { onboardingService } from '@/lib/api/services/onboarding';
import { useBootstrapOnboarding, useOnboardingStatus } from '@/lib/hooks/queries/onboarding';

type OnboardingStage = 'initial' | 'basic_profile' | 'goals' | 'connect_strava' | 'nutrition_setup' | 'work_setup' | 'complete';

interface OnboardingData {
  display_name?: string;
  birthdate?: string;
  sex?: string;
  height_cm?: number;
  goals?: string[];
  nutrition_setup?: boolean;
  work_setup?: boolean;
}

export default function OnboardingPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [currentStage, setCurrentStage] = useState<OnboardingStage>('initial');
  const [data, setData] = useState<OnboardingData>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (user) {
      if (user.onboarding_completed) {
        router.push('/dashboard');
        return;
      }
      setCurrentStage((user.onboarding_stage as OnboardingStage) || 'initial');
    }
  }, [user, router]);


  const handleNext = async (stageData: Partial<OnboardingData>, nextStage: OnboardingStage) => {
    const newData = { ...data, ...stageData };
    setData(newData);

    setSaving(true);
    setError(null);
    try {
      // Update profile data if provided
      const profileUpdates: any = {};
      if (stageData.display_name !== undefined) profileUpdates.display_name = stageData.display_name || null;
      if (stageData.birthdate !== undefined) profileUpdates.birthdate = stageData.birthdate || null;
      if (stageData.sex !== undefined) profileUpdates.sex = stageData.sex || null;
      if (stageData.height_cm !== undefined) profileUpdates.height_cm = stageData.height_cm || null;
      
      // Update onboarding stage
      profileUpdates.onboarding_stage = nextStage;
      profileUpdates.onboarding_completed = nextStage === 'complete';

      await authService.updateProfile(profileUpdates);
      await refreshUser();
      setCurrentStage(nextStage);
    } catch (err) {
      setError(err as Error);
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = async (nextStage: OnboardingStage) => {
    await handleNext({}, nextStage);
  };

  const handleComplete = async () => {
    await handleNext({}, 'complete');
    router.push('/dashboard');
  };

  if (!user) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
        <div className="max-w-2xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Welcome</h1>
            <p className="text-slate-400">Let&apos;s get you set up. Everything is optional except basics.</p>
          </div>

          {/* Progress Indicator */}
          <div className="mb-8">
            <div className="flex items-center justify-between text-sm text-slate-400">
              <span className={currentStage !== 'initial' ? 'text-white' : ''}>Basics</span>
              <span className={['basic_profile', 'goals', 'connect_strava', 'nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Profile</span>
              <span className={['goals', 'connect_strava', 'nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Goals</span>
              <span className={['connect_strava', 'nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Connect</span>
              <span className={['nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Optional</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full mt-2">
              <div 
                className="h-1 bg-blue-600 rounded-full transition-all"
                style={{ width: `${(['initial', 'basic_profile', 'goals', 'connect_strava', 'nutrition_setup', 'work_setup', 'complete'].indexOf(currentStage) + 1) * 16.67}%` }}
              />
            </div>
          </div>

          {error && <ErrorMessage error={error} className="mb-6" />}

          {/* Stage Components */}
          {currentStage === 'initial' && (
            <InitialStage 
              data={data}
              onNext={(d) => handleNext(d, 'basic_profile')}
              onSkip={() => handleSkip('basic_profile')}
            />
          )}

          {currentStage === 'basic_profile' && (
            <BasicProfileStage
              data={data}
              user={user}
              onNext={(d) => handleNext(d, 'goals')}
              onSkip={() => handleSkip('goals')}
              saving={saving}
            />
          )}

          {currentStage === 'goals' && (
            <GoalsStage
              data={data}
              onNext={(d) => handleNext(d, 'connect_strava')}
              onSkip={() => handleSkip('connect_strava')}
            />
          )}

          {currentStage === 'connect_strava' && (
            <ConnectStravaStage
              onNext={() => handleNext({}, 'nutrition_setup')}
              onSkip={() => handleSkip('nutrition_setup')}
            />
          )}

          {currentStage === 'nutrition_setup' && (
            <NutritionSetupStage
              data={data}
              onNext={(d) => handleNext(d, 'work_setup')}
              onSkip={() => handleSkip('work_setup')}
            />
          )}

          {currentStage === 'work_setup' && (
            <WorkSetupStage
              data={data}
              onComplete={handleComplete}
              onSkip={handleComplete}
            />
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

// Stage Components

function InitialStage({ data, onNext, onSkip }: { data: OnboardingData; onNext: (d: OnboardingData) => void; onSkip: () => void }) {
  const [displayName, setDisplayName] = useState(data.display_name || '');

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold mb-4">Let&apos;s Start</h2>
      <p className="text-slate-400 mb-6">What should we call you?</p>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Display Name (Optional)</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
            placeholder="Your name"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => onNext({ display_name: displayName })}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"
          >
            Next
          </button>
          <button
            onClick={onSkip}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 font-medium"
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  );
}

function BasicProfileStage({ 
  data, 
  user, 
  onNext, 
  onSkip, 
  saving 
}: { 
  data: OnboardingData; 
  user: any;
  onNext: (d: OnboardingData) => void; 
  onSkip: () => void;
  saving: boolean;
}) {
  const [formData, setFormData] = useState({
    birthdate: data.birthdate || (user?.birthdate ? user.birthdate.split('T')[0] : ''),
    sex: data.sex || user?.sex || '',
    height_cm: data.height_cm || user?.height_cm || '',
  });

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold mb-4">Basic Profile</h2>
      <p className="text-slate-400 mb-6">Help us calculate age-graded performance. (Optional)</p>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Birthdate</label>
          <input
            type="date"
            value={formData.birthdate}
            onChange={(e) => setFormData({ ...formData, birthdate: e.target.value })}
            className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Sex</label>
          <select
            value={formData.sex}
            onChange={(e) => setFormData({ ...formData, sex: e.target.value })}
            className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
          >
            <option value="">Select...</option>
            <option value="M">Male</option>
            <option value="F">Female</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Height (cm)</label>
          <input
            type="number"
            step="0.1"
            value={formData.height_cm}
            onChange={(e) => setFormData({ ...formData, height_cm: parseFloat(e.target.value) || undefined })}
            className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
            placeholder="e.g., 175.0"
          />
          <p className="text-xs text-slate-500 mt-1">Required for BMI calculation</p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => onNext(formData)}
            disabled={saving}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-white font-medium"
          >
            {saving ? <LoadingSpinner size="sm" /> : 'Next'}
          </button>
          <button
            onClick={onSkip}
            disabled={saving}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-slate-300 font-medium"
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  );
}

function GoalsStage({ data, onNext, onSkip }: { data: OnboardingData; onNext: (d: OnboardingData) => void; onSkip: () => void }) {
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const [form, setForm] = useState({
    goal_event_type: 'none',
    goal_event_date: '',
    goal_priority: 'fitness',
    goal_target_time: '',

    policy_stance: 'durability_first',
    days_per_week: 5,
    time_available_min: 60,
    weekly_mileage_target: '',

    pain_flag: 'none',
    injury_context: '',

    limiter_primary: 'not_sure',
    output_metric_priorities: [] as string[],

    // Optional deep-dive (kept light; can be expanded later)
    year_lookback_notes: '',
    biometrics: {
      trains_with_hr: 'sometimes', // always | sometimes | never
      hr_reliability: 'unknown', // reliable | unreliable | unknown
      has_power: 'no', // yes | no
      sleep_source: 'none', // garmin | oura | apple | other | none
    },
    shoe_rotation: '',
    favorite_workouts: '',
  });

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await onboardingService.getIntake('goals');
        if (!mounted) return;
        if (resp?.responses && typeof resp.responses === 'object') {
          setForm((prev) => ({ ...prev, ...resp.responses }));
        }
      } catch (e: any) {
        if (!mounted) return;
        setLoadErr(e?.message || 'Could not load saved answers.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const setField = (key: string, value: any) => setForm((f) => ({ ...f, [key]: value }));

  const togglePriority = (key: string) => {
    setForm((f) => {
      const set = new Set(f.output_metric_priorities || []);
      if (set.has(key)) {
        set.delete(key);
      } else {
        // Keep this fast: cap at 3 priorities.
        if (set.size >= 3) return f;
        set.add(key);
      }
      return { ...f, output_metric_priorities: Array.from(set) };
    });
  };

  const handleContinue = async () => {
    setSaving(true);
    try {
      const payload = {
        ...form,
        days_per_week: Number(form.days_per_week) || null,
        time_available_min: Number(form.time_available_min) || null,
        weekly_mileage_target:
          form.weekly_mileage_target === '' ? null : Number(form.weekly_mileage_target) || null,
      };
      await onboardingService.saveIntake('goals', payload, true);
      onNext({ goals: payload.output_metric_priorities || [] });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold mb-2">Interview</h2>
      <p className="text-slate-400 mb-6">
        Race goal first. Output metrics under the hood. Everything optional.
      </p>

      {loading ? (
        <div className="py-8 flex justify-center">
          <LoadingSpinner size="sm" />
        </div>
      ) : (
        <div className="space-y-6">
          {loadErr ? <p className="text-sm text-slate-400">{loadErr}</p> : null}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Primary event</label>
              <select
                value={form.goal_event_type}
                onChange={(e) => setField('goal_event_type', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
              >
                <option value="none">None / just get faster</option>
                <option value="5k">5K</option>
                <option value="10k">10K</option>
                <option value="half_marathon">Half Marathon</option>
                <option value="marathon">Marathon</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Event date</label>
              <input
                type="date"
                value={form.goal_event_date || ''}
                onChange={(e) => setField('goal_event_date', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Priority</label>
              <select
                value={form.goal_priority}
                onChange={(e) => setField('goal_priority', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
              >
                <option value="fitness">Fitness block</option>
                <option value="b_race">B race</option>
                <option value="a_race">A race</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Target time</label>
              <input
                type="text"
                value={form.goal_target_time || ''}
                onChange={(e) => setField('goal_target_time', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                placeholder="e.g. 19:30 or 3:10:00"
              />
              <p className="text-xs text-slate-500 mt-1">Optional. Format is flexible.</p>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Policy stance</label>
            <select
              value={form.policy_stance}
              onChange={(e) => setField('policy_stance', e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
            >
              <option value="performance_maximal">Performance maximal (accept volatility)</option>
              <option value="durability_first">Durability first (protect consistency)</option>
              <option value="re_entry">Re-entry (prove repeatability first)</option>
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Days/week you can run</label>
              <input
                type="number"
                min={1}
                max={7}
                value={form.days_per_week as any}
                onChange={(e) => setField('days_per_week', parseInt(e.target.value || '0', 10) || 0)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Typical time available (min)</label>
              <input
                type="number"
                min={10}
                max={240}
                value={form.time_available_min as any}
                onChange={(e) => setField('time_available_min', parseInt(e.target.value || '0', 10) || 0)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Weekly mileage target</label>
              <input
                type="number"
                min={0}
                step={1}
                value={form.weekly_mileage_target}
                onChange={(e) => setField('weekly_mileage_target', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                placeholder="Optional"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Pain right now</label>
              <select
                value={form.pain_flag}
                onChange={(e) => setField('pain_flag', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
              >
                <option value="none">None</option>
                <option value="niggle">Niggle</option>
                <option value="pain">Pain</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Context</label>
              <input
                type="text"
                value={form.injury_context || ''}
                onChange={(e) => setField('injury_context', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                placeholder="Optional. e.g. calf flare-up, returning from stress fracture"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">What’s the limiter right now?</label>
            <select
              value={form.limiter_primary}
              onChange={(e) => setField('limiter_primary', e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
            >
              <option value="not_sure">Not sure</option>
              <option value="endurance">Endurance</option>
              <option value="speed">Speed</option>
              <option value="hills">Hills</option>
              <option value="consistency">Consistency</option>
              <option value="recovery">Recovery</option>
              <option value="body_comp">Body composition</option>
              <option value="life_stress">Life stress / time</option>
            </select>
          </div>

          <div>
            <p className="text-sm font-medium mb-2">Pick up to 3 outputs to optimize first</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {[
                ['race_time', 'Race time'],
                ['efficiency_pace_hr', 'Pace @ HR (efficiency)'],
                ['efficiency_hr_pace', 'HR @ pace (efficiency)'],
                ['durability', 'Durability (hold quality across days)'],
                ['stability', 'Stability (less variance session-to-session)'],
                ['body_comp', 'Body comp / BMI'],
                ['lower_rpe', 'Lower RPE at same work'],
                ['age_graded', 'Age-graded % slope'],
              ].map(([key, label]) => {
                const selected = (form.output_metric_priorities || []).includes(key);
                const atCap = (form.output_metric_priorities || []).length >= 3;
                const disabled = !selected && atCap;
                return (
                  <label key={key} className={`flex items-center gap-3 p-2 rounded border ${selected ? 'border-blue-600/60 bg-slate-900/60' : 'border-slate-700/50 bg-slate-900/30'} ${disabled ? 'opacity-60' : 'cursor-pointer'}`}>
                    <input
                      type="checkbox"
                      checked={selected}
                      disabled={disabled}
                      onChange={() => togglePriority(key)}
                      className="w-4 h-4 text-blue-600 bg-slate-900 border-slate-700/50 rounded"
                    />
                    <span className="text-slate-200 text-sm">{label}</span>
                  </label>
                );
              })}
            </div>
            <p className="text-xs text-slate-500 mt-2">
              This sets what we emphasize early. You can change it later.
            </p>
          </div>

          <details className="bg-slate-900/30 border border-slate-700/50 rounded p-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-200">
              More context (optional)
            </summary>
            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">One-year lookback (high-level)</label>
                <textarea
                  value={form.year_lookback_notes || ''}
                  onChange={(e) => setField('year_lookback_notes', e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white min-h-[88px]"
                  placeholder="Best block, worst block, interruptions, what worked / what broke."
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Train with HR?</label>
                  <select
                    value={form.biometrics.trains_with_hr}
                    onChange={(e) => setField('biometrics', { ...form.biometrics, trains_with_hr: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                  >
                    <option value="always">Always</option>
                    <option value="sometimes">Sometimes</option>
                    <option value="never">Never</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">HR reliability</label>
                  <select
                    value={form.biometrics.hr_reliability}
                    onChange={(e) => setField('biometrics', { ...form.biometrics, hr_reliability: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                  >
                    <option value="unknown">Unknown</option>
                    <option value="reliable">Reliable</option>
                    <option value="unreliable">Unreliable</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Have power?</label>
                  <select
                    value={form.biometrics.has_power}
                    onChange={(e) => setField('biometrics', { ...form.biometrics, has_power: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Sleep source</label>
                  <select
                    value={form.biometrics.sleep_source}
                    onChange={(e) => setField('biometrics', { ...form.biometrics, sleep_source: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                  >
                    <option value="none">None</option>
                    <option value="garmin">Garmin</option>
                    <option value="oura">Oura</option>
                    <option value="apple">Apple</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Shoe rotation</label>
                  <input
                    type="text"
                    value={form.shoe_rotation || ''}
                    onChange={(e) => setField('shoe_rotation', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                    placeholder="Optional"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Favorite workouts</label>
                  <input
                    type="text"
                    value={form.favorite_workouts || ''}
                    onChange={(e) => setField('favorite_workouts', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded text-white"
                    placeholder="Optional. What reliably works for you?"
                  />
                </div>
              </div>
            </div>
          </details>

          <div className="flex gap-2">
            <button
              onClick={handleContinue}
              disabled={saving}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-white font-medium"
            >
              {saving ? <LoadingSpinner size="sm" /> : 'Next'}
            </button>
            <button
              onClick={onSkip}
              disabled={saving}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-slate-300 font-medium"
            >
              Skip
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function NutritionSetupStage({ data, onNext, onSkip }: { data: OnboardingData; onNext: (d: OnboardingData) => void; onSkip: () => void }) {
  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold mb-4">Nutrition</h2>
      <p className="text-slate-400 mb-6">
        Optional. Helps spot patterns when you log.
      </p>
      
      <div className="space-y-4 mb-6">
        <p className="text-sm text-slate-300">
          Pre-run fuel, post-run recovery, daily intake — log what you want, when convenient.
        </p>
        <p className="text-xs text-slate-500">
          You can set this up anytime from the Nutrition page.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onNext({ nutrition_setup: true })}
          className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"
        >
          Continue
        </button>
        <button
          onClick={onSkip}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 font-medium"
        >
          Skip
        </button>
      </div>
    </div>
  );
}

function ConnectStravaStage({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const { data: status } = useOnboardingStatus(true);
  const bootstrap = useBootstrapOnboarding();
  const isConnected = !!status?.strava_connected;
  const lastIndexStatus = status?.ingestion_state?.last_index_status || null;

  const handleConnect = async () => {
    try {
      const { auth_url } = await stravaService.getAuthUrl('/onboarding');
      window.location.href = auth_url;
    } catch (e) {
      // Keep UI quiet; user can retry.
    }
  };

  const handleBootstrap = async () => {
    if (!isConnected) return;
    try {
      await bootstrap.mutateAsync();
    } catch (e) {
      // Best-effort; status will still show connected.
    }
  };

  // If we just returned from OAuth, the URL contains ?strava=connected.
  // Trigger a bootstrap once to start ingesting deterministically.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get('strava') === 'connected') {
      handleBootstrap();
      // Clean URL for aesthetics.
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold mb-4">Connect Strava</h2>
      <p className="text-slate-400 mb-6">
        Import your activities automatically.
      </p>
      
      <div className="space-y-4 mb-6">
        <div className="bg-slate-900 rounded p-4">
          <div className="flex items-center gap-3 mb-3">
            <svg className="w-8 h-8 text-orange-500" viewBox="0 0 24 24" fill="currentColor">
              <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"/>
            </svg>
            <div>
              <p className="font-medium text-white">Strava</p>
              <p className="text-sm text-slate-400">Sync activities, analyze efficiency</p>
            </div>
          </div>
          <button
            onClick={handleConnect}
            disabled={isConnected}
            className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded text-white font-medium transition-colors"
          >
            {isConnected ? 'Connected' : 'Connect Strava'}
          </button>
          {isConnected && (
            <div className="mt-3 text-xs text-slate-400">
              {lastIndexStatus === 'running'
                ? 'Import in progress.'
                : lastIndexStatus === 'success'
                  ? 'Import started.'
                  : 'Connected. Import will start in the background.'}
              {bootstrap.isPending ? ' (queueing...)' : null}
            </div>
          )}
          {isConnected && !bootstrap.isPending && lastIndexStatus !== 'running' && (
            <button
              type="button"
              onClick={handleBootstrap}
              className="mt-3 w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-white font-medium transition-colors"
            >
              Start Import
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500">
          You can connect anytime from Settings.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={onNext}
          className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-white font-medium"
        >
          {isConnected ? 'Continue' : 'Continue Without Connecting'}
        </button>
        <button
          onClick={onSkip}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 font-medium"
        >
          Skip
        </button>
      </div>
    </div>
  );
}

function WorkSetupStage({ data, onComplete, onSkip }: { data: OnboardingData; onComplete: () => void; onSkip: () => void }) {
  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold mb-4">Work Patterns</h2>
      <p className="text-slate-400 mb-6">
        Optional. Helps identify work-performance correlations.
      </p>
      
      <div className="space-y-4 mb-6">
        <p className="text-sm text-slate-300">
          Log work hours and stress levels to see how they affect your running.
        </p>
        <p className="text-xs text-slate-500">
          Set up anytime from Settings.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onComplete()}
          className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium"
        >
          Complete Setup
        </button>
        <button
          onClick={onSkip}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 font-medium"
        >
          Skip to Dashboard
        </button>
      </div>
    </div>
  );
}

