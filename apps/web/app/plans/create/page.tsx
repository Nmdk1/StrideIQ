'use client';

/**
 * Plan Creation Page
 * 
 * Questionnaire-based plan creation flow.
 * Collects necessary information to generate personalized training plans.
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { planService } from '@/lib/api/services/plans';

type Step = 'distance' | 'race-date' | 'current-fitness' | 'availability' | 'recent-race' | 'experience' | 'review';

interface PlanFormData {
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
  const [step, setStep] = useState<Step>('distance');
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<PlanFormData>({
    distance: '',
    race_date: '',
    race_name: '',
    current_weekly_miles: 30,
    longest_recent_run: 10,
    days_per_week: 6,
    experience_level: 'intermediate',
    injury_history: '',
  });
  
  // Check authentication
  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsAuthenticated(!!token);
  }, []);
  
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
  
  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Build request body
      const requestBody = {
        distance: formData.distance,
        duration_weeks: planDuration,
        days_per_week: formData.days_per_week,
        volume_tier: getVolumeTier(),
        race_date: formData.race_date,
        race_name: formData.race_name || undefined,
      };
      
      // For authenticated users with race time, create semi-custom plan
      // Check if they have a recent race for pace calculation
      const hasPaceData = formData.recent_race_distance && formData.recent_race_time;
      
      if (isAuthenticated && hasPaceData) {
        // Semi-custom plan - requires $5 payment
        // Check if already purchased (via session storage)
        const purchaseData = sessionStorage.getItem('plan_purchased');
        if (!purchaseData) {
          // Redirect to checkout
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
        
        // Purchase confirmed, create the plan
        await planService.createSemiCustom({
          ...requestBody,
          recent_race_distance: formData.recent_race_distance,
          recent_race_time: formData.recent_race_time,
        });
        
        // Clear purchase data
        sessionStorage.removeItem('plan_purchased');
      } else {
        // Standard (free) plan
        await planService.createStandard(requestBody);
      }
      
      // Redirect to calendar to see the plan
      router.push('/calendar');
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create plan');
    } finally {
      setIsLoading(false);
    }
  };
  
  const nextStep = () => {
    const steps: Step[] = ['distance', 'race-date', 'current-fitness', 'availability', 'recent-race', 'experience', 'review'];
    const currentIndex = steps.indexOf(step);
    if (currentIndex < steps.length - 1) {
      setStep(steps[currentIndex + 1]);
    }
  };
  
  const prevStep = () => {
    const steps: Step[] = ['distance', 'race-date', 'current-fitness', 'availability', 'recent-race', 'experience', 'review'];
    const currentIndex = steps.indexOf(step);
    if (currentIndex > 0) {
      setStep(steps[currentIndex - 1]);
    }
  };
  
  // Step indicator
  const steps: Step[] = ['distance', 'race-date', 'current-fitness', 'availability', 'recent-race', 'experience', 'review'];
  const stepLabels = ['Distance', 'Race Date', 'Fitness', 'Schedule', 'Recent Race', 'Experience', 'Review'];
  
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Create Your Training Plan</h1>
          <p className="text-gray-400">Answer a few questions to get a personalized plan</p>
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
                      : 'bg-gray-800 text-gray-500'
                  }`}
                >
                  {i + 1}
                </div>
                <div className="text-xs text-gray-500 mt-1 hidden md:block">{stepLabels[i]}</div>
              </div>
              {i < steps.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 ${
                  steps.indexOf(step) > i ? 'bg-pink-600' : 'bg-gray-800'
                }`} />
              )}
            </React.Fragment>
          ))}
        </div>
        
        {/* Step Content */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
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
                        : 'border-gray-700 bg-gray-900 hover:border-gray-600'
                    }`}
                  >
                    <div className="text-3xl mb-2">{d.icon}</div>
                    <div className="font-bold text-white">{d.label}</div>
                    <div className="text-sm text-gray-400">{d.subtitle}</div>
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
                  <label className="block text-sm font-medium text-gray-400 mb-2">Race Date</label>
                  <input
                    type="date"
                    value={formData.race_date}
                    onChange={(e) => setFormData({ ...formData, race_date: e.target.value })}
                    min={new Date(Date.now() + 8 * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Race Name (optional)</label>
                  <input
                    type="text"
                    value={formData.race_name}
                    onChange={(e) => setFormData({ ...formData, race_name: e.target.value })}
                    placeholder="e.g., Boston Marathon"
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500"
                  />
                </div>
                
                {formData.race_date && (
                  <div className="p-4 bg-gray-900 rounded-lg">
                    <div className="text-sm text-gray-400">Training Duration</div>
                    <div className="text-2xl font-bold text-white">
                      {weeksUntilRace} weeks
                      {weeksUntilRace > 18 && (
                        <span className="text-sm font-normal text-gray-400 ml-2">
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
                  <label className="block text-sm font-medium text-gray-400 mb-2">
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
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>10 mi</span>
                    <span>50 mi</span>
                    <span>100 mi</span>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
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
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>3 mi</span>
                    <span>12 mi</span>
                    <span>22 mi</span>
                  </div>
                </div>
                
                <div className="p-4 bg-gray-900 rounded-lg">
                  <div className="text-sm text-gray-400">Your Volume Tier</div>
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
                        : 'border-gray-700 bg-gray-900 hover:border-gray-600'
                    }`}
                  >
                    <div className="text-3xl font-bold text-white">{days}</div>
                    <div className="text-sm text-gray-400">days/week</div>
                  </button>
                ))}
              </div>
              
              <div className="mt-6 p-4 bg-gray-900 rounded-lg">
                <p className="text-sm text-gray-400">
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
              <p className="text-gray-400 text-sm mb-6">
                A recent race time (within the last 6 months) helps us calculate your personalized training paces.
              </p>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Race Distance</label>
                  <select
                    value={formData.recent_race_distance || ''}
                    onChange={(e) => setFormData({ ...formData, recent_race_distance: e.target.value || undefined })}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white"
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
                    <label className="block text-sm font-medium text-gray-400 mb-2">Finish Time</label>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <input
                          type="number"
                          placeholder="Hours"
                          min="0"
                          max="10"
                          className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500"
                          onChange={(e) => {
                            const hours = e.target.value || '0';
                            const [_, mins, secs] = (formData.recent_race_time || '0:00:00').split(':');
                            setFormData({ ...formData, recent_race_time: `${hours}:${mins || '00'}:${secs || '00'}` });
                          }}
                        />
                        <span className="text-xs text-gray-500 mt-1">hours</span>
                      </div>
                      <div>
                        <input
                          type="number"
                          placeholder="Minutes"
                          min="0"
                          max="59"
                          className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500"
                          onChange={(e) => {
                            const mins = e.target.value || '00';
                            const [hours, _, secs] = (formData.recent_race_time || '0:00:00').split(':');
                            setFormData({ ...formData, recent_race_time: `${hours || '0'}:${mins.padStart(2, '0')}:${secs || '00'}` });
                          }}
                        />
                        <span className="text-xs text-gray-500 mt-1">minutes</span>
                      </div>
                      <div>
                        <input
                          type="number"
                          placeholder="Seconds"
                          min="0"
                          max="59"
                          className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500"
                          onChange={(e) => {
                            const secs = e.target.value || '00';
                            const [hours, mins, _] = (formData.recent_race_time || '0:00:00').split(':');
                            setFormData({ ...formData, recent_race_time: `${hours || '0'}:${mins || '00'}:${secs.padStart(2, '0')}` });
                          }}
                        />
                        <span className="text-xs text-gray-500 mt-1">seconds</span>
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
                        : 'border-gray-700 bg-gray-900 hover:border-gray-600'
                    }`}
                  >
                    <div className="font-bold text-white">{level.label}</div>
                    <div className="text-sm text-gray-400">{level.description}</div>
                  </button>
                ))}
              </div>
              
              <div className="mt-6">
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Any injury concerns? (optional)
                </label>
                <textarea
                  value={formData.injury_history}
                  onChange={(e) => setFormData({ ...formData, injury_history: e.target.value })}
                  placeholder="e.g., Previous IT band issues, currently healthy"
                  rows={3}
                  className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500"
                />
              </div>
            </div>
          )}
          
          {/* Review */}
          {step === 'review' && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Review Your Plan</h2>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-400">Distance</div>
                    <div className="text-lg font-bold text-white capitalize">
                      {formData.distance.replace('_', ' ')}
                    </div>
                  </div>
                  
                  <div className="bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-400">Duration</div>
                    <div className="text-lg font-bold text-white">{planDuration} weeks</div>
                  </div>
                  
                  <div className="bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-400">Days/Week</div>
                    <div className="text-lg font-bold text-white">{formData.days_per_week}</div>
                  </div>
                  
                  <div className="bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-400">Volume Tier</div>
                    <div className="text-lg font-bold text-orange-400 capitalize">
                      {getVolumeTier()}
                    </div>
                  </div>
                </div>
                
                {formData.race_date && (
                  <div className="bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-400">Race Day</div>
                    <div className="text-lg font-bold text-white">
                      {new Date(formData.race_date).toLocaleDateString('en-US', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </div>
                    {formData.race_name && (
                      <div className="text-sm text-gray-400 mt-1">{formData.race_name}</div>
                    )}
                  </div>
                )}
                
                {!isAuthenticated && (
                  <div className="p-4 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                    <div className="font-semibold text-blue-400 mb-1">Connect Strava for Better Results</div>
                    <p className="text-sm text-gray-400">
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
            disabled={step === 'distance'}
            className="px-6 py-3 bg-gray-800 border border-gray-700 rounded-lg font-semibold text-gray-400 disabled:opacity-50 hover:text-white hover:border-gray-600"
          >
            Back
          </button>
          
          {step === 'review' ? (
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
                (step === 'distance' && !formData.distance) ||
                (step === 'race-date' && !formData.race_date)
              }
              className="px-8 py-3 bg-gradient-to-r from-pink-600 to-orange-600 rounded-lg font-semibold text-white disabled:opacity-50"
            >
              Next
            </button>
          )}
        </div>
        
        {/* Preview Link */}
        <div className="text-center mt-8">
          <a
            href="/plans/preview"
            className="text-sm text-gray-400 hover:text-pink-400"
          >
            Want to explore plans first? Browse plan previews →
          </a>
        </div>
      </div>
    </div>
  );
}
