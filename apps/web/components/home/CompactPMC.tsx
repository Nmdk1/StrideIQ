'use client';

/**
 * CompactPMC — home page Training Load snapshot
 *
 * Renders the 30-day Fitness/Fatigue/Form chart below "This Week".
 * Fetches from the existing /v1/training-load/history?days=30 endpoint.
 * Renders nothing if loading or no data (silence > noise on home page).
 *
 * Click model (Codex review requirement):
 *   - Header CTA and chart body → navigate to /training-load
 *   - Legend area → tooltips only, stopPropagation prevents navigation
 *
 * Date formatting: UTC methods throughout — same pattern as commit a4a96d3.
 */

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { TrendingUp, Info } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  Tooltip as UiTooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from '@/components/ui/tooltip';

interface DailyLoad {
  date: string;
  atl: number;
  ctl: number;
  tsb: number;
}

interface LoadHistoryResponse {
  history: DailyLoad[];
}

const LEGEND_ITEMS = [
  {
    key: 'ctl',
    name: 'Fitness',
    color: '#3B82F6',
    tooltip: 'Longer-term training load trend. Higher = more accumulated fitness.',
  },
  {
    key: 'atl',
    name: 'Fatigue',
    color: '#F97316',
    tooltip: 'Short-term training stress trend. Higher = more recent fatigue.',
  },
  {
    key: 'tsb',
    name: 'Form',
    color: '#10B981',
    tooltip: 'Fitness minus Fatigue. Positive = fresh. Negative = fatigued but building.',
  },
] as const;

export function CompactPMC() {
  const { token } = useAuth();
  const router = useRouter();

  const { data } = useQuery<LoadHistoryResponse>({
    queryKey: ['training-load', 30],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/training-load/history?days=30`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error('Failed to fetch training load');
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!token,
  });

  const history = data?.history;
  if (!history || history.length === 0) return null;

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4">

      {/* Section header — CTA link is its own tap target */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-semibold text-slate-300">Training Load</span>
        </div>
        <Link
          href="/training-load"
          className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          View training load →
        </Link>
      </div>

      {/* Legend — excluded from chart click target via stopPropagation */}
      <div
        className="flex flex-wrap gap-x-4 gap-y-1.5 mb-3"
        onClick={(e) => e.stopPropagation()}
      >
        {LEGEND_ITEMS.map((item) => (
          <TooltipProvider key={item.key}>
            <UiTooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1.5 cursor-help select-none">
                  <div
                    className="w-5 h-0.5 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs text-slate-400">{item.name}</span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="top">{item.tooltip}</TooltipContent>
            </UiTooltip>
          </TooltipProvider>
        ))}
      </div>

      {/* Cross-training disclosure */}
      <div className="flex items-center gap-1.5 mb-2">
        <Info className="w-3 h-3 text-slate-600" />
        <span className="text-[10px] text-slate-500">Includes all activities (running, cross-training)</span>
      </div>

      {/* Chart body — tap navigates to /training-load */}
      <div
        className="cursor-pointer"
        onClick={() => router.push('/training-load')}
        role="button"
        aria-label="View full Training Load chart"
      >
        <ResponsiveContainer width="100%" height={168}>
          <ComposedChart data={history} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="date"
              stroke="#9CA3AF"
              tick={{ fontSize: 10 }}
              tickFormatter={(value) => {
                const d = new Date(value);
                return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
              }}
            />
            <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} width={28} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelFormatter={(label) => {
                const d = new Date(label);
                return d.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                  timeZone: 'UTC',
                });
              }}
            />
            {/* TSB — area fill behind lines */}
            <Area
              type="monotone"
              dataKey="tsb"
              name="Form"
              fill="#10B981"
              fillOpacity={0.2}
              stroke="#10B981"
              strokeWidth={2}
              dot={false}
            />
            {/* CTL — Fitness */}
            <Line
              type="monotone"
              dataKey="ctl"
              name="Fitness"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
            />
            {/* ATL — Fatigue */}
            <Line
              type="monotone"
              dataKey="atl"
              name="Fatigue"
              stroke="#F97316"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

    </div>
  );
}
