'use client';

/**
 * Trends Dashboard
 * 
 * The analytical nerve center - shows:
 * - Efficiency trends over time
 * - Volume trends
 * - Root cause analysis when trends detected
 * - Historical pattern recognition
 */

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';

interface TrendData {
  metric: string;
  direction: string;
  magnitude_percent: number | null;
  confidence: number;
  data_points: number;
  period_days: number;
  is_significant: boolean;
  interpretation?: string;
}

interface RootCauseData {
  status: string;
  message?: string;
  trend?: {
    direction: string;
    magnitude_percent: number | null;
    confidence: number;
  };
  hypotheses: Array<{
    factor: string;
    correlation: number;
    direction: string;
    confidence: number;
    explanation: string;
  }>;
}

export default function TrendsPage() {
  const router = useRouter();
  const { token, isAuthenticated } = useAuth();
  const [days, setDays] = useState(30);

  // Redirect if not authenticated
  React.useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  const { data: efficiencyTrend, isLoading: efficiencyLoading } = useQuery<TrendData>({
    queryKey: ['efficiency-trend', days],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/run-analysis/trends/efficiency?days=${days}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Failed to fetch efficiency trend');
      return res.json();
    },
    enabled: !!token,
    staleTime: 60000,
  });

  const { data: volumeTrend, isLoading: volumeLoading } = useQuery<TrendData>({
    queryKey: ['volume-trend', days],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/run-analysis/trends/volume?days=${days}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Failed to fetch volume trend');
      return res.json();
    },
    enabled: !!token,
    staleTime: 60000,
  });

  const { data: rootCauses, isLoading: causesLoading } = useQuery<RootCauseData>({
    queryKey: ['root-causes', days],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/run-analysis/root-causes?days=${days}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Failed to fetch root causes');
      return res.json();
    },
    enabled: !!token,
    staleTime: 60000,
  });

  if (!isAuthenticated) {
    return null;
  }

  const isLoading = efficiencyLoading || volumeLoading || causesLoading;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Trends</h1>
          <p className="text-gray-400">
            Signal, not noise. Patterns over time, not reactions to single workouts.
          </p>
        </div>

        {/* Time Period Selector */}
        <div className="flex flex-wrap gap-2 mb-8">
          {[14, 30, 60, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-4 py-2 rounded-lg transition-colors ${
                days === d
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
              }`}
            >
              {d < 90 ? `${d} days` : `${d / 30} months`}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="space-y-6">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="animate-pulse bg-gray-800/50 rounded-lg h-48"></div>
            ))}
          </div>
        ) : (
          <div className="space-y-8">
            {/* Main Trends Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Efficiency Trend */}
              <TrendCard
                title="Efficiency"
                subtitle="HR / Pace ratio (lower = better)"
                trend={efficiencyTrend}
                invertGood
              />

              {/* Volume Trend */}
              <TrendCard
                title="Volume"
                subtitle="Weekly mileage progression"
                trend={volumeTrend}
              />
            </div>

            {/* Interpretation */}
            {efficiencyTrend?.interpretation && (
              <div className="bg-gray-800/50 rounded-lg p-6 border-l-4 border-orange-500">
                <h3 className="text-lg font-medium text-white mb-2">What This Means</h3>
                <p className="text-gray-300">{efficiencyTrend.interpretation}</p>
              </div>
            )}

            {/* Root Cause Analysis */}
            {rootCauses && (
              <div className="bg-gray-800/30 rounded-lg p-6">
                <h2 className="text-xl font-bold text-white mb-4">Root Cause Analysis</h2>
                
                {rootCauses.status === 'no_significant_trend' ? (
                  <div className="text-gray-400">
                    <p>{rootCauses.message}</p>
                    <p className="mt-2 text-sm text-gray-500">
                      Root cause analysis activates when significant trends are detected.
                      This is by design — we don&apos;t react to noise.
                    </p>
                  </div>
                ) : rootCauses.hypotheses.length === 0 ? (
                  <div className="text-gray-400">
                    <p>Trend detected but no clear root causes identified.</p>
                    <p className="mt-2 text-sm text-gray-500">
                      Consider logging more input data (sleep, stress, soreness) to improve analysis.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <p className="text-gray-400 text-sm mb-4">
                      Factors potentially contributing to your{' '}
                      <span className={
                        rootCauses.trend?.direction === 'declining' 
                          ? 'text-orange-400' 
                          : 'text-green-400'
                      }>
                        {rootCauses.trend?.direction}
                      </span>{' '}
                      efficiency trend:
                    </p>
                    
                    {rootCauses.hypotheses.map((hypothesis, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-4 p-4 bg-gray-800/50 rounded-lg"
                      >
                        <div
                          className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center ${
                            Math.abs(hypothesis.correlation) > 0.5
                              ? 'bg-orange-600/20 text-orange-400'
                              : 'bg-gray-700/50 text-gray-400'
                          }`}
                        >
                          {getFactorIcon(hypothesis.factor)}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-medium text-white capitalize">
                              {hypothesis.factor}
                            </h4>
                            <CorrelationBadge correlation={hypothesis.correlation} />
                          </div>
                          <p className="text-gray-300 text-sm">{hypothesis.explanation}</p>
                          <p className="text-gray-500 text-xs mt-1">
                            {Math.round(hypothesis.confidence * 100)}% confidence
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Data Quality Notice */}
            <div className="bg-gray-800/20 rounded-lg p-4 border border-gray-700/50">
              <div className="flex items-start gap-3">
                <svg
                  className="w-5 h-5 text-gray-500 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div className="text-sm text-gray-400">
                  <p className="font-medium text-gray-300 mb-1">About This Analysis</p>
                  <p>
                    Trends require data over time. The more consistently you log your runs
                    and daily check-ins, the more accurate this analysis becomes.
                    We need at least 5 data points to detect meaningful patterns.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Sub-Components ============

function TrendCard({
  title,
  subtitle,
  trend,
  invertGood = false,
}: {
  title: string;
  subtitle: string;
  trend: TrendData | undefined;
  invertGood?: boolean;
}) {
  if (!trend) {
    return (
      <div className="bg-gray-800/50 rounded-lg p-6">
        <h3 className="text-lg font-medium text-white mb-1">{title}</h3>
        <p className="text-gray-500 text-sm mb-4">{subtitle}</p>
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  const getDirectionColor = () => {
    if (trend.direction === 'insufficient_data') return 'text-gray-500';
    if (trend.direction === 'stable') return 'text-gray-400';
    
    const isGood = invertGood
      ? trend.direction === 'declining'
      : trend.direction === 'improving';
    
    return isGood ? 'text-green-400' : 'text-orange-400';
  };

  const getArrow = () => {
    if (trend.direction === 'improving') return '↑';
    if (trend.direction === 'declining') return '↓';
    if (trend.direction === 'stable') return '→';
    return '—';
  };

  const getBackgroundGradient = () => {
    if (trend.direction === 'insufficient_data') return 'from-gray-800/50 to-gray-800/30';
    if (!trend.is_significant) return 'from-gray-800/50 to-gray-800/30';
    
    const isGood = invertGood
      ? trend.direction === 'declining'
      : trend.direction === 'improving';
    
    return isGood 
      ? 'from-green-900/30 to-gray-800/30' 
      : 'from-orange-900/30 to-gray-800/30';
  };

  return (
    <div className={`bg-gradient-to-br ${getBackgroundGradient()} rounded-lg p-6 border border-gray-700/50`}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-medium text-white mb-1">{title}</h3>
          <p className="text-gray-500 text-sm">{subtitle}</p>
        </div>
        {trend.is_significant && (
          <span className="px-2 py-1 bg-orange-600/20 text-orange-400 text-xs rounded">
            Significant
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-3 mb-4">
        <span className={`text-4xl font-bold ${getDirectionColor()}`}>
          {getArrow()}
        </span>
        <span className={`text-2xl font-medium ${getDirectionColor()}`}>
          {trend.direction.replace('_', ' ')}
        </span>
      </div>

      {trend.direction !== 'insufficient_data' && trend.magnitude_percent !== null && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Change</span>
            <span className="text-white">{Math.abs(trend.magnitude_percent).toFixed(1)}%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Confidence</span>
            <span className="text-white">{Math.round(trend.confidence * 100)}%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Based on</span>
            <span className="text-white">{trend.data_points} data points</span>
          </div>
        </div>
      )}

      {trend.direction === 'insufficient_data' && (
        <p className="text-gray-400 text-sm">
          Need at least 5 runs to calculate trend.
          Currently have {trend.data_points}.
        </p>
      )}
    </div>
  );
}

function CorrelationBadge({ correlation }: { correlation: number }) {
  const abs = Math.abs(correlation);
  let label: string;
  let color: string;

  if (abs > 0.7) {
    label = 'Strong';
    color = 'bg-orange-600/20 text-orange-400';
  } else if (abs > 0.4) {
    label = 'Moderate';
    color = 'bg-yellow-600/20 text-yellow-400';
  } else {
    label = 'Weak';
    color = 'bg-gray-600/20 text-gray-400';
  }

  return (
    <span className={`px-2 py-0.5 rounded text-xs ${color}`}>
      {label} ({correlation > 0 ? '+' : ''}{(correlation * 100).toFixed(0)}%)
    </span>
  );
}

function getFactorIcon(factor: string): React.ReactNode {
  switch (factor) {
    case 'sleep':
      return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      );
    case 'stress':
      return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      );
    case 'soreness':
      return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
        </svg>
      );
    case 'volume':
      return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      );
    default:
      return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
  }
}

