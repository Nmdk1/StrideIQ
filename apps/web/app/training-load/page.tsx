'use client';

/**
 * Training Load Dashboard
 * 
 * Visualizes:
 * - ATL (Acute Training Load / Fatigue) - 7-day
 * - CTL (Chronic Training Load / Fitness) - 42-day
 * - TSB (Training Stress Balance / Form) = CTL - ATL
 * 
 * The Performance Management Chart (PMC) for runners.
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart
} from 'recharts';

interface DailyLoad {
  date: string;
  total_tss: number;
  workout_count: number;
  atl: number;
  ctl: number;
  tsb: number;
}

interface LoadSummary {
  atl: number;
  ctl: number;
  tsb: number;
  atl_trend: string;
  ctl_trend: string;
  tsb_trend: string;
  training_phase: string;
  recommendation: string;
}

interface LoadHistoryResponse {
  history: DailyLoad[];
  summary: LoadSummary;
}

export default function TrainingLoadPage() {
  const router = useRouter();
  const { token, isAuthenticated } = useAuth();
  const [days, setDays] = useState(60);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  const { data, isLoading, error } = useQuery<LoadHistoryResponse>({
    queryKey: ['training-load', days],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/training-load/history?days=${days}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Failed to fetch training load');
      return res.json();
    },
    enabled: !!token,
    staleTime: 60000,
  });

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Training Load</h1>
          <p className="text-gray-400">
            Fitness, Fatigue, and Form — the complete picture.
          </p>
        </div>

        {/* Period Selector */}
        <div className="flex flex-wrap gap-2 mb-8">
          {[30, 60, 90, 180, 365].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-4 py-2 rounded-lg transition-colors ${
                days === d
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
              }`}
            >
              {d < 90 ? `${d} days` : d < 365 ? `${d / 30}mo` : '1 year'}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="space-y-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="animate-pulse bg-gray-800/50 rounded-lg h-32"></div>
            ))}
          </div>
        ) : error ? (
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-6">
            <p className="text-red-400">Failed to load training data</p>
          </div>
        ) : data ? (
          <>
            {/* Current Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <MetricCard
                label="Fitness"
                sublabel="CTL (42-day)"
                value={data.summary.ctl}
                trend={data.summary.ctl_trend}
                color="blue"
              />
              <MetricCard
                label="Fatigue"
                sublabel="ATL (7-day)"
                value={data.summary.atl}
                trend={data.summary.atl_trend}
                color="orange"
              />
              <MetricCard
                label="Form"
                sublabel="TSB (CTL - ATL)"
                value={data.summary.tsb}
                trend={data.summary.tsb_trend}
                color={data.summary.tsb > 0 ? 'green' : 'red'}
                showSign
              />
              <PhaseCard 
                phase={data.summary.training_phase}
                recommendation={data.summary.recommendation}
              />
            </div>

            {/* Performance Management Chart */}
            <div className="bg-gray-800/50 rounded-lg p-6 mb-8">
              <h2 className="text-xl font-bold text-white mb-4">Performance Management Chart</h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={data.history} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis 
                      dataKey="date" 
                      stroke="#9CA3AF"
                      tickFormatter={(value) => {
                        const d = new Date(value);
                        return `${d.getMonth() + 1}/${d.getDate()}`;
                      }}
                    />
                    <YAxis stroke="#9CA3AF" />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#1F2937', 
                        border: '1px solid #374151',
                        borderRadius: '8px'
                      }}
                      labelFormatter={(label) => {
                        const d = new Date(label);
                        return d.toLocaleDateString('en-US', { 
                          month: 'short', 
                          day: 'numeric',
                          year: 'numeric'
                        });
                      }}
                    />
                    <Legend />
                    
                    {/* TSB area (form) */}
                    <Area
                      type="monotone"
                      dataKey="tsb"
                      name="Form (TSB)"
                      fill="#10B981"
                      fillOpacity={0.2}
                      stroke="#10B981"
                      strokeWidth={0}
                    />
                    
                    {/* Zero line for TSB reference */}
                    <ReferenceLine y={0} stroke="#4B5563" strokeDasharray="3 3" />
                    
                    {/* CTL line (fitness) */}
                    <Line
                      type="monotone"
                      dataKey="ctl"
                      name="Fitness (CTL)"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={false}
                    />
                    
                    {/* ATL line (fatigue) */}
                    <Line
                      type="monotone"
                      dataKey="atl"
                      name="Fatigue (ATL)"
                      stroke="#F97316"
                      strokeWidth={2}
                      dot={false}
                    />
                    
                    {/* TSB line (form) */}
                    <Line
                      type="monotone"
                      dataKey="tsb"
                      name="Form (TSB)"
                      stroke="#10B981"
                      strokeWidth={2}
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Daily TSS Chart */}
            <div className="bg-gray-800/50 rounded-lg p-6 mb-8">
              <h2 className="text-xl font-bold text-white mb-4">Daily Training Stress</h2>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={data.history} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis 
                      dataKey="date" 
                      stroke="#9CA3AF"
                      tickFormatter={(value) => {
                        const d = new Date(value);
                        return `${d.getMonth() + 1}/${d.getDate()}`;
                      }}
                    />
                    <YAxis stroke="#9CA3AF" />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#1F2937', 
                        border: '1px solid #374151',
                        borderRadius: '8px'
                      }}
                      labelFormatter={(label) => {
                        const d = new Date(label);
                        return d.toLocaleDateString('en-US', { 
                          month: 'short', 
                          day: 'numeric'
                        });
                      }}
                      formatter={(value) => [typeof value === 'number' ? value.toFixed(1) : '0', 'TSS']}
                    />
                    
                    <Area
                      type="monotone"
                      dataKey="total_tss"
                      name="Daily TSS"
                      fill="#6366F1"
                      fillOpacity={0.4}
                      stroke="#6366F1"
                      strokeWidth={1}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Education Section */}
            <div className="bg-gray-800/30 rounded-lg p-6 border border-gray-700/50">
              <h3 className="text-lg font-medium text-white mb-4">Understanding Your Training Load</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                    <span className="font-medium text-white">Fitness (CTL)</span>
                  </div>
                  <p className="text-gray-400">
                    Your 42-day exponential average of training stress. 
                    Represents accumulated fitness from consistent training.
                    Higher = more fit.
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                    <span className="font-medium text-white">Fatigue (ATL)</span>
                  </div>
                  <p className="text-gray-400">
                    Your 7-day exponential average of training stress.
                    Represents recent accumulated fatigue.
                    Higher = more tired.
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    <span className="font-medium text-white">Form (TSB)</span>
                  </div>
                  <p className="text-gray-400">
                    Fitness minus Fatigue. Positive = fresh and ready.
                    Negative = fatigued but potentially building fitness.
                    Target +5 to +25 for races.
                  </p>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

// ============ Sub-Components ============

function MetricCard({
  label,
  sublabel,
  value,
  trend,
  color,
  showSign = false,
}: {
  label: string;
  sublabel: string;
  value: number;
  trend: string;
  color: 'blue' | 'orange' | 'green' | 'red';
  showSign?: boolean;
}) {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-900/20 border-blue-700/50',
    orange: 'text-orange-400 bg-orange-900/20 border-orange-700/50',
    green: 'text-green-400 bg-green-900/20 border-green-700/50',
    red: 'text-red-400 bg-red-900/20 border-red-700/50',
  };

  const getTrendArrow = () => {
    if (trend === 'rising') return '↑';
    if (trend === 'falling') return '↓';
    return '→';
  };

  const displayValue = showSign && value > 0 ? `+${value.toFixed(0)}` : value.toFixed(0);

  return (
    <div className={`rounded-lg p-4 border ${colorClasses[color]}`}>
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className="text-gray-500 text-xs mb-2">{sublabel}</p>
      <div className="flex items-baseline gap-2">
        <span className={`text-3xl font-bold ${colorClasses[color].split(' ')[0]}`}>
          {displayValue}
        </span>
        <span className={`text-lg ${colorClasses[color].split(' ')[0]}`}>
          {getTrendArrow()}
        </span>
      </div>
    </div>
  );
}

function PhaseCard({
  phase,
  recommendation,
}: {
  phase: string;
  recommendation: string;
}) {
  const getPhaseColor = () => {
    switch (phase) {
      case 'building':
        return 'border-purple-700/50 bg-purple-900/20';
      case 'tapering':
        return 'border-green-700/50 bg-green-900/20';
      case 'recovering':
        return 'border-blue-700/50 bg-blue-900/20';
      case 'maintaining':
        return 'border-gray-700/50 bg-gray-800/50';
      default:
        return 'border-gray-700/50 bg-gray-800/50';
    }
  };

  const getPhaseIcon = () => {
    switch (phase) {
      case 'building':
        return '📈';
      case 'tapering':
        return '🎯';
      case 'recovering':
        return '🔄';
      case 'maintaining':
        return '⚖️';
      default:
        return '📊';
    }
  };

  return (
    <div className={`rounded-lg p-4 border ${getPhaseColor()}`}>
      <p className="text-gray-400 text-sm mb-1">Training Phase</p>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">{getPhaseIcon()}</span>
        <span className="text-xl font-bold text-white capitalize">{phase}</span>
      </div>
      <p className="text-gray-400 text-xs">{recommendation}</p>
    </div>
  );
}

