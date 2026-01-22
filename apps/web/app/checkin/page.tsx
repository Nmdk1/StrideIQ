/**
 * Morning Check-in Page
 * 
 * Ultra-fast daily check-in. Must complete in <5 seconds.
 * 3 sliders + 1 number field. Done.
 * 
 * Tone: No pressure. Just data when convenient.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';

export default function CheckinPage() {
  const router = useRouter();
  const { user } = useAuth();
  
  const [sleep, setSleep] = useState(7);
  const [stress, setStress] = useState(3);
  const [soreness, setSoreness] = useState(2);
  const [hrv, setHrv] = useState<string>('');
  const [restingHr, setRestingHr] = useState<string>('');
  // Coach-inspired additions
  const [enjoyment, setEnjoyment] = useState<number | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [motivation, setMotivation] = useState<number | null>(null);
  const [showMindset, setShowMindset] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);

    try {
      const token = localStorage.getItem('auth_token');
      const today = new Date().toISOString().split('T')[0];
      
      const resp = await fetch(
        `${API_CONFIG.baseURL}/v1/daily-checkin`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            date: today,
            sleep_h: sleep,
            stress_1_5: stress,
            soreness_1_5: soreness,
            hrv_rmssd: hrv ? parseFloat(hrv) : null,
            resting_hr: restingHr ? parseInt(restingHr) : null,
            // Coach-inspired mindset tracking
            enjoyment_1_5: enjoyment,
            confidence_1_5: confidence,
            motivation_1_5: motivation,
          }),
        }
      );

      if (!resp.ok) {
        const detail = await resp.text().catch(() => '');
        throw new Error(detail || `HTTP ${resp.status}`);
      }
      
      setSubmitted(true);
      setTimeout(() => router.push('/dashboard'), 1000);
    } catch (err) {
      console.error('Check-in failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center">
          <div className="text-center">
            <div className="text-4xl mb-4">✓</div>
            <p className="text-xl font-medium">Logged.</p>
            <p className="text-sm text-slate-400 mt-2 max-w-sm">
              We’ll use this to look for patterns (sleep/stress/soreness ↔ training efficiency) as your data builds.
            </p>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-6 px-4">
        <div className="max-w-md mx-auto">
          {/* Header - minimal */}
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-bold">Check-in</h1>
            <p className="text-sm text-slate-500 mt-1">
              {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
            </p>
          </div>

          {/* Sleep Slider */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium">Sleep</label>
              <span className="text-lg font-bold text-blue-400">{sleep}h</span>
            </div>
            <input
              type="range"
              min="0"
              max="12"
              step="0.5"
              value={sleep}
              onChange={(e) => setSleep(parseFloat(e.target.value))}
              className="w-full h-3 bg-slate-700 rounded-lg appearance-none cursor-pointer slider-thumb"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>0h</span>
              <span>12h</span>
            </div>
          </div>

          {/* Stress Slider */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium">Stress</label>
              <span className="text-lg font-bold text-yellow-400">{stress}/5</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={stress}
              onChange={(e) => setStress(parseInt(e.target.value))}
              className="w-full h-3 bg-slate-700 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Low</span>
              <span>High</span>
            </div>
          </div>

          {/* Soreness Slider */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium">Soreness</label>
              <span className="text-lg font-bold text-orange-400">{soreness}/5</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={soreness}
              onChange={(e) => setSoreness(parseInt(e.target.value))}
              className="w-full h-3 bg-slate-700 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Fresh</span>
              <span>Very sore</span>
            </div>
          </div>

          {/* HRV & Resting HR - Optional, side by side */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <label className="text-sm font-medium mb-2 block">HRV</label>
              <input
                type="number"
                value={hrv}
                onChange={(e) => setHrv(e.target.value)}
                placeholder="--"
                className="w-full px-3 py-3 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-center text-lg font-medium"
              />
              <p className="text-xs text-slate-500 mt-1 text-center">Optional</p>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Resting HR</label>
              <input
                type="number"
                value={restingHr}
                onChange={(e) => setRestingHr(e.target.value)}
                placeholder="--"
                className="w-full px-3 py-3 bg-slate-800 border border-slate-700/50 rounded-lg text-white text-center text-lg font-medium"
              />
              <p className="text-xs text-slate-500 mt-1 text-center">Optional</p>
            </div>
          </div>

          {/* Mindset Section - Collapsible */}
          <div className="mb-8">
            <button
              type="button"
              onClick={() => setShowMindset(!showMindset)}
              className="flex items-center justify-between w-full py-2 text-sm text-slate-400 hover:text-slate-300"
            >
              <span>🧠 Mindset check (optional)</span>
              <span>{showMindset ? '−' : '+'}</span>
            </button>
            
            {showMindset && (
              <div className="mt-4 space-y-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                {/* Enjoyment */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Enjoying training?</label>
                    <span className="text-sm text-green-400">
                      {enjoyment ? ['😞', '😕', '😐', '🙂', '😊'][enjoyment - 1] : '--'}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setEnjoyment(enjoyment === n ? null : n)}
                        className={`flex-1 py-2 rounded ${
                          enjoyment === n 
                            ? 'bg-green-600 text-white' 
                            : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>Dreading</span>
                    <span>Loving it</span>
                  </div>
                </div>

                {/* Confidence */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Confidence level?</label>
                    <span className="text-sm text-purple-400">
                      {confidence ? ['😰', '😟', '😐', '😌', '💪'][confidence - 1] : '--'}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setConfidence(confidence === n ? null : n)}
                        className={`flex-1 py-2 rounded ${
                          confidence === n 
                            ? 'bg-purple-600 text-white' 
                            : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>Doubtful</span>
                    <span>Unstoppable</span>
                  </div>
                </div>

                {/* Motivation */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Motivation?</label>
                    <span className="text-sm text-orange-400">
                      {motivation ? ['😴', '😑', '😐', '😤', '🔥'][motivation - 1] : '--'}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setMotivation(motivation === n ? null : n)}
                        className={`flex-1 py-2 rounded ${
                          motivation === n 
                            ? 'bg-orange-600 text-white' 
                            : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>Forcing it</span>
                    <span>Fired up</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Submit Button - Big, obvious */}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full py-4 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded-lg text-white text-lg font-bold transition-colors"
          >
            {submitting ? 'Saving...' : 'Done'}
          </button>

          {/* Skip link */}
          <button
            onClick={() => router.push('/dashboard')}
            className="w-full mt-4 py-2 text-slate-500 hover:text-slate-400 text-sm"
          >
            Skip for today
          </button>
        </div>
      </div>
    </ProtectedRoute>
  );
}

