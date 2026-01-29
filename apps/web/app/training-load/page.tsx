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

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Tooltip as UiTooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
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

interface PersonalZones {
  mean_tsb: number;
  std_tsb: number;
  threshold_fresh: number;
  threshold_recovering: number;
  threshold_normal_low: number;
  threshold_danger: number;
  sample_days: number;
  is_personalized: boolean;
  current_zone: string;
  zone_description: string;
}

interface LoadHistoryResponse {
  history: DailyLoad[];
  summary: LoadSummary;
  personal_zones?: PersonalZones;
}

function getPeriodEndpoints(history: DailyLoad[]) {
  if (!history || history.length === 0) return null;
  const first = history[0];
  const last = history[history.length - 1];
  const firstDate = new Date(first.date).getTime();
  const lastDate = new Date(last.date).getTime();
  // Defensive: keep "start" as the older date even if backend order changes.
  return firstDate <= lastDate ? { start: first, end: last } : { start: last, end: first };
}

function formatOverPeriod(days: number) {
  if (days === 365) return 'over 1yr';
  return `over ${days}d`;
}

function formatSignedInt(n: number) {
  const rounded = Math.round(n);
  if (rounded > 0) return `+${rounded}`;
  return `${rounded}`;
}

export default function TrainingLoadPage() {
  const { token } = useAuth();
  const [days, setDays] = useState(60);

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

  const endpoints = data?.history ? getPeriodEndpoints(data.history) : null;
  const ctlDelta = endpoints ? endpoints.end.ctl - endpoints.start.ctl : null;
  const atlDelta = endpoints ? endpoints.end.atl - endpoints.start.atl : null;
  const tsbDelta = endpoints ? endpoints.end.tsb - endpoints.start.tsb : null;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-6xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">Training Load</h1>
            <p className="text-slate-400">
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
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white'
              }`}
            >
              {d < 90 ? `${d} days` : d < 365 ? `${d / 30}mo` : '1 year'}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="space-y-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="animate-pulse bg-slate-800/50 rounded-lg h-32"></div>
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
                deltaText={ctlDelta === null ? undefined : `${formatSignedInt(ctlDelta)} ${formatOverPeriod(days)}`}
                deltaTone={ctlDelta === null ? undefined : ctlDelta >= 0 ? 'good' : 'bad'}
                tooltip="CTL (Fitness): 42-day exponential average of training stress. Higher = more accumulated fitness."
              />
              <MetricCard
                label="Fatigue"
                sublabel="ATL (7-day)"
                value={data.summary.atl}
                trend={data.summary.atl_trend}
                color="orange"
                deltaText={atlDelta === null ? undefined : `${formatSignedInt(atlDelta)} ${formatOverPeriod(days)}`}
                deltaTone={atlDelta === null ? undefined : atlDelta >= 0 ? 'bad' : 'good'}
                tooltip="ATL (Fatigue): 7-day exponential average of training stress. Higher = more recent fatigue."
              />
              <MetricCard
                label="Form"
                sublabel="TSB (CTL - ATL)"
                value={data.summary.tsb}
                trend={data.summary.tsb_trend}
                color={data.summary.tsb > 0 ? 'green' : 'red'}
                showSign
                deltaText={tsbDelta === null ? undefined : `${formatSignedInt(tsbDelta)} ${formatOverPeriod(days)}`}
                deltaTone={tsbDelta === null ? undefined : tsbDelta >= 0 ? 'good' : 'bad'}
                tooltip="TSB (Form): Fitness minus Fatigue. Positive = fresher, negative = more fatigued (often while building fitness)."
              />
              <PhaseCard 
                phase={data.summary.training_phase}
                recommendation={data.summary.recommendation}
                tooltip="Training Phase: a high-level read of whether you're building, tapering, recovering, or maintaining based on your recent training load."
              />
            </div>

            {/* Personal Zones Card - N=1 */}
            {data.personal_zones && (
              <PersonalZonesCard zones={data.personal_zones} currentTsb={data.summary.tsb} />
            )}

            {/* Performance Management Chart */}
            <div className="bg-slate-800/50 rounded-lg p-6 mb-8">
              <h2 className="text-xl font-bold text-white mb-4">Performance Management Chart</h2>
              <div className="w-full" style={{ height: 320 }}>
                {data.history.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
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
                ) : (
                  <div className="h-full w-full rounded-lg bg-slate-900/30 border border-slate-700/50 flex items-center justify-center">
                    <p className="text-slate-500 text-sm">No data to display</p>
                  </div>
                )}
              </div>
            </div>

            {/* Daily TSS Chart */}
            <div className="bg-slate-800/50 rounded-lg p-6 mb-8">
              <h2 className="text-xl font-bold text-white mb-4">Daily Training Stress</h2>
              <div className="w-full" style={{ height: 192 }}>
                {data.history.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
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
                ) : (
                  <div className="h-full w-full rounded-lg bg-slate-900/30 border border-slate-700/50 flex items-center justify-center">
                    <p className="text-slate-500 text-sm">No data to display</p>
                  </div>
                )}
              </div>
            </div>

            {/* Education Section */}
            <div className="bg-slate-800/30 rounded-lg p-6 border border-slate-700/50/50">
              <h3 className="text-lg font-medium text-white mb-4">Understanding Your Training Load</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                    <span className="font-medium text-white">Fitness (CTL)</span>
                  </div>
                  <p className="text-slate-400">
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
                  <p className="text-slate-400">
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
                  <p className="text-slate-400">
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
    </ProtectedRoute>
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
  deltaText,
  deltaTone,
  tooltip,
}: {
  label: string;
  sublabel: string;
  value: number;
  trend: string;
  color: 'blue' | 'orange' | 'green' | 'red';
  showSign?: boolean;
  deltaText?: string;
  deltaTone?: 'good' | 'bad' | 'neutral';
  tooltip?: string;
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

  const deltaTextClass =
    deltaTone === 'good'
      ? 'text-green-400'
      : deltaTone === 'bad'
        ? 'text-red-400'
        : 'text-slate-500';

  return (
    <UiTooltip>
      <TooltipTrigger asChild>
        <div className={`rounded-lg p-4 border ${colorClasses[color]} ${tooltip ? 'cursor-help' : ''}`}>
          <p className="text-slate-400 text-sm mb-1">{label}</p>
      <p className="text-slate-500 text-xs mb-2">{sublabel}</p>
      <div className="flex items-baseline gap-2">
        <span className={`text-3xl font-bold ${colorClasses[color].split(' ')[0]}`}>
          {displayValue}
        </span>
        <span className={`text-lg ${colorClasses[color].split(' ')[0]}`}>
          {getTrendArrow()}
        </span>
      </div>
      {deltaText ? (
        <p className={`mt-2 text-xs ${deltaTextClass}`}>
          {deltaText}
        </p>
      ) : null}
        </div>
      </TooltipTrigger>
      {tooltip ? (
        <TooltipContent side="top">
          {tooltip}
        </TooltipContent>
      ) : null}
    </UiTooltip>
  );
}

function PhaseCard({
  phase,
  recommendation,
  tooltip,
}: {
  phase: string;
  recommendation: string;
  tooltip?: string;
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
        return 'border-slate-700/50/50 bg-slate-800/50';
      default:
        return 'border-slate-700/50/50 bg-slate-800/50';
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

  const phaseMeaning = (() => {
    switch (phase) {
      case 'building':
        return 'Building: increasing training load to develop fitness.';
      case 'tapering':
        return 'Tapering: reducing load to shed fatigue and sharpen.';
      case 'recovering':
        return 'Recovering: prioritizing recovery after a hard block or race.';
      case 'maintaining':
        return 'Maintaining: holding fitness steady with balanced load.';
      default:
        return 'Training phase is inferred from your recent training load.';
    }
  })();

  return (
    <UiTooltip>
      <TooltipTrigger asChild>
        <div className={`rounded-lg p-4 border ${getPhaseColor()} ${tooltip ? 'cursor-help' : ''}`}>
      <p className="text-slate-400 text-sm mb-1">Training Phase</p>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">{getPhaseIcon()}</span>
        <span className="text-xl font-bold text-white capitalize">{phase}</span>
      </div>
      <p className="text-slate-400 text-xs">{recommendation}</p>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top">
        {tooltip ? `${tooltip}\n\n${phaseMeaning}` : phaseMeaning}
      </TooltipContent>
    </UiTooltip>
  );
}

function PersonalZonesCard({
  zones,
  currentTsb,
}: {
  zones: PersonalZones;
  currentTsb: number;
}) {
  const formatThreshold = (val: number) => {
    return val >= 0 ? `+${val.toFixed(0)}` : val.toFixed(0);
  };

  // Determine which zone the current TSB falls into for highlighting
  const getZoneHighlight = (zoneName: string) => {
    if (zones.current_zone === zoneName) {
      return 'bg-orange-600/30 border-l-2 border-orange-500';
    }
    return '';
  };

  return (
    <div className="bg-slate-800/50 rounded-lg p-6 mb-8 border border-slate-700/50">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-white">Your Personal Zones</h2>
          <p className="text-slate-400 text-sm">
            {zones.is_personalized 
              ? `Calibrated from ${zones.sample_days} days of your training`
              : 'Using population defaults (need 56+ days for personalization)'
            }
          </p>
        </div>
        {zones.is_personalized && (
          <span className="px-3 py-1 bg-green-900/30 text-green-400 text-xs rounded-full border border-green-700/50">
            N=1 Personalized
          </span>
        )}
      </div>

      {/* Current state */}
      <div className="bg-slate-900/50 rounded-lg p-4 mb-4">
        <p className="text-slate-400 text-sm mb-1">Current State</p>
        <p className="text-white">{zones.zone_description}</p>
      </div>

      {/* Zone thresholds */}
      <div className="space-y-2">
        <div className={`flex justify-between items-center p-2 rounded ${getZoneHighlight('race_ready')}`}>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-slate-300">Race Ready</span>
          </div>
          <span className="text-slate-400 font-mono text-sm">
            TSB &gt; {formatThreshold(zones.threshold_fresh)}
          </span>
        </div>

        <div className={`flex justify-between items-center p-2 rounded ${getZoneHighlight('recovering')}`}>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-slate-300">Recovering</span>
          </div>
          <span className="text-slate-400 font-mono text-sm">
            {formatThreshold(zones.threshold_recovering)} to {formatThreshold(zones.threshold_fresh)}
          </span>
        </div>

        <div className={`flex justify-between items-center p-2 rounded ${getZoneHighlight('optimal_training')}`}>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-slate-400"></div>
            <span className="text-slate-300">Normal Training</span>
          </div>
          <span className="text-slate-400 font-mono text-sm">
            {formatThreshold(zones.threshold_normal_low)} to {formatThreshold(zones.threshold_recovering)}
          </span>
        </div>

        <div className={`flex justify-between items-center p-2 rounded ${getZoneHighlight('overreaching')}`}>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500"></div>
            <span className="text-slate-300">Overreaching</span>
          </div>
          <span className="text-slate-400 font-mono text-sm">
            {formatThreshold(zones.threshold_danger)} to {formatThreshold(zones.threshold_normal_low)}
          </span>
        </div>

        <div className={`flex justify-between items-center p-2 rounded ${getZoneHighlight('overtraining_risk')}`}>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span className="text-slate-300">Overtraining Risk</span>
          </div>
          <span className="text-slate-400 font-mono text-sm">
            TSB &lt; {formatThreshold(zones.threshold_danger)}
          </span>
        </div>
      </div>

      {/* Stats footer */}
      <div className="mt-4 pt-4 border-t border-slate-700/50 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-slate-500">Your typical TSB</span>
          <p className="text-white font-mono">{formatThreshold(zones.mean_tsb)} (mean)</p>
        </div>
        <div>
          <span className="text-slate-500">Your variation</span>
          <p className="text-white font-mono">±{zones.std_tsb.toFixed(1)} (SD)</p>
        </div>
      </div>
    </div>
  );
}

