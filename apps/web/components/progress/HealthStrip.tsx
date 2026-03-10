'use client';

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface Indicator {
  label: string;
  value: string;
  status: 'green' | 'amber' | 'red';
  trend?: 'up' | 'down' | 'stable';
}

interface HealthStripProps {
  indicators: Indicator[];
}

const STATUS_STYLES = {
  green: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
  amber: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
  red: 'bg-red-500/15 border-red-500/30 text-red-400',
};

const TrendIcon = ({ trend }: { trend?: string }) => {
  if (trend === 'up') return <TrendingUp className="w-3 h-3" />;
  if (trend === 'down') return <TrendingDown className="w-3 h-3" />;
  return <Minus className="w-3 h-3 text-slate-500" />;
};

export function HealthStrip({ indicators }: HealthStripProps) {
  if (!indicators.length) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {indicators.map((ind, i) => (
        <div
          key={i}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border ${STATUS_STYLES[ind.status]}`}
        >
          <span className="text-xs font-medium text-slate-400">{ind.label}</span>
          <span className="text-sm font-bold">{ind.value}</span>
          <TrendIcon trend={ind.trend} />
        </div>
      ))}
    </div>
  );
}
