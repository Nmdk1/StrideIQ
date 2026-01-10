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
import { API_CONFIG } from '@/lib/api/config';

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
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-2xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Welcome</h1>
            <p className="text-gray-400">Let&apos;s get you set up. Everything is optional except basics.</p>
          </div>

          {/* Progress Indicator */}
          <div className="mb-8">
            <div className="flex items-center justify-between text-sm text-gray-400">
              <span className={currentStage !== 'initial' ? 'text-white' : ''}>Basics</span>
              <span className={['basic_profile', 'goals', 'connect_strava', 'nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Profile</span>
              <span className={['goals', 'connect_strava', 'nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Goals</span>
              <span className={['connect_strava', 'nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Connect</span>
              <span className={['nutrition_setup', 'work_setup', 'complete'].includes(currentStage) ? 'text-white' : ''}>Optional</span>
            </div>
            <div className="h-1 bg-gray-800 rounded-full mt-2">
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
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 className="text-xl font-semibold mb-4">Let&apos;s Start</h2>
      <p className="text-gray-400 mb-6">What should we call you?</p>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Display Name (Optional)</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
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
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
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
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 className="text-xl font-semibold mb-4">Basic Profile</h2>
      <p className="text-gray-400 mb-6">Help us calculate age-graded performance. (Optional)</p>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Birthdate</label>
          <input
            type="date"
            value={formData.birthdate}
            onChange={(e) => setFormData({ ...formData, birthdate: e.target.value })}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Sex</label>
          <select
            value={formData.sex}
            onChange={(e) => setFormData({ ...formData, sex: e.target.value })}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
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
            className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
            placeholder="e.g., 175.0"
          />
          <p className="text-xs text-gray-500 mt-1">Required for BMI calculation</p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => onNext(formData)}
            disabled={saving}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded text-white font-medium"
          >
            {saving ? <LoadingSpinner size="sm" /> : 'Next'}
          </button>
          <button
            onClick={onSkip}
            disabled={saving}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-700 disabled:cursor-not-allowed rounded text-gray-300 font-medium"
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  );
}

function GoalsStage({ data, onNext, onSkip }: { data: OnboardingData; onNext: (d: OnboardingData) => void; onSkip: () => void }) {
  const [goals, setGoals] = useState<string[]>(data.goals || []);

  const goalOptions = [
    'Improve efficiency',
    'Run faster',
    'Lose weight',
    'Build endurance',
    'Race performance',
    'General fitness',
  ];

  const toggleGoal = (goal: string) => {
    if (goals.includes(goal)) {
      setGoals(goals.filter(g => g !== goal));
    } else {
      setGoals([...goals, goal]);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 className="text-xl font-semibold mb-4">Goals</h2>
      <p className="text-gray-400 mb-6">What are you working toward? (Optional)</p>
      
      <div className="space-y-3 mb-6">
        {goalOptions.map((goal) => (
          <label key={goal} className="flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={goals.includes(goal)}
              onChange={() => toggleGoal(goal)}
              className="w-4 h-4 text-blue-600 bg-gray-900 border-gray-700 rounded"
            />
            <span className="ml-3 text-gray-300">{goal}</span>
          </label>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onNext({ goals })}
          className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"
        >
          Next
        </button>
        <button
          onClick={onSkip}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
        >
          Skip
        </button>
      </div>
    </div>
  );
}

function NutritionSetupStage({ data, onNext, onSkip }: { data: OnboardingData; onNext: (d: OnboardingData) => void; onSkip: () => void }) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 className="text-xl font-semibold mb-4">Nutrition</h2>
      <p className="text-gray-400 mb-6">
        Optional. Helps spot patterns when you log.
      </p>
      
      <div className="space-y-4 mb-6">
        <p className="text-sm text-gray-300">
          Pre-run fuel, post-run recovery, daily intake — log what you want, when convenient.
        </p>
        <p className="text-xs text-gray-500">
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
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
        >
          Skip
        </button>
      </div>
    </div>
  );
}

function ConnectStravaStage({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const handleConnect = () => {
    // Redirect to Strava OAuth
    window.location.href = `${API_CONFIG.baseURL}/v1/strava/auth`;
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 className="text-xl font-semibold mb-4">Connect Strava</h2>
      <p className="text-gray-400 mb-6">
        Import your activities automatically.
      </p>
      
      <div className="space-y-4 mb-6">
        <div className="bg-gray-900 rounded p-4">
          <div className="flex items-center gap-3 mb-3">
            <svg className="w-8 h-8 text-orange-500" viewBox="0 0 24 24" fill="currentColor">
              <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"/>
            </svg>
            <div>
              <p className="font-medium text-white">Strava</p>
              <p className="text-sm text-gray-400">Sync activities, analyze efficiency</p>
            </div>
          </div>
          <button
            onClick={handleConnect}
            className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded text-white font-medium transition-colors"
          >
            Connect Strava
          </button>
        </div>
        <p className="text-xs text-gray-500">
          You can connect anytime from Settings.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={onNext}
          className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white font-medium"
        >
          Continue Without Connecting
        </button>
        <button
          onClick={onSkip}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
        >
          Skip
        </button>
      </div>
    </div>
  );
}

function WorkSetupStage({ data, onComplete, onSkip }: { data: OnboardingData; onComplete: () => void; onSkip: () => void }) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 className="text-xl font-semibold mb-4">Work Patterns</h2>
      <p className="text-gray-400 mb-6">
        Optional. Helps identify work-performance correlations.
      </p>
      
      <div className="space-y-4 mb-6">
        <p className="text-sm text-gray-300">
          Log work hours and stress levels to see how they affect your running.
        </p>
        <p className="text-xs text-gray-500">
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
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
        >
          Skip to Dashboard
        </button>
      </div>
    </div>
  );
}

