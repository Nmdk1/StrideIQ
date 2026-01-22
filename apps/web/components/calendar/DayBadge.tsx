'use client';

/**
 * DayBadge Component
 * 
 * Small badge for calendar day cells showing analytics signals.
 * 
 * ADR-016: Calendar Signals - Day Badges + Week Trajectory
 * 
 * DESIGN: Compact, scannable, mobile-friendly
 */

import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  Check,
  Target,
  Zap,
  AlertTriangle,
  AlertCircle,
  Info
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export interface DayBadgeData {
  type: string;
  badge: string;
  color: string;
  icon: string;
  confidence: string;
  tooltip: string;
}

interface DayBadgeProps {
  badge: DayBadgeData;
  compact?: boolean;
}

// Icon mapping
const ICON_MAP: Record<string, React.ReactNode> = {
  trending_up: <TrendingUp className="w-2.5 h-2.5" />,
  trending_down: <TrendingDown className="w-2.5 h-2.5" />,
  check: <Check className="w-2.5 h-2.5" />,
  target: <Target className="w-2.5 h-2.5" />,
  zap: <Zap className="w-2.5 h-2.5" />,
  alert_triangle: <AlertTriangle className="w-2.5 h-2.5" />,
  alert_circle: <AlertCircle className="w-2.5 h-2.5" />,
  info: <Info className="w-2.5 h-2.5" />,
};

// Color mapping
const COLOR_MAP: Record<string, { bg: string; text: string; border: string }> = {
  emerald: {
    bg: 'bg-emerald-500/20',
    text: 'text-emerald-400',
    border: 'border-emerald-500/40',
  },
  green: {
    bg: 'bg-green-500/20',
    text: 'text-green-400',
    border: 'border-green-500/40',
  },
  blue: {
    bg: 'bg-blue-500/20',
    text: 'text-blue-400',
    border: 'border-blue-500/40',
  },
  orange: {
    bg: 'bg-orange-500/20',
    text: 'text-orange-400',
    border: 'border-orange-500/40',
  },
  yellow: {
    bg: 'bg-yellow-500/20',
    text: 'text-yellow-400',
    border: 'border-yellow-500/40',
  },
  purple: {
    bg: 'bg-purple-500/20',
    text: 'text-purple-400',
    border: 'border-purple-500/40',
  },
  slate: {
    bg: 'bg-slate-500/20',
    text: 'text-slate-400',
    border: 'border-slate-500/40',
  },
};

export function DayBadge({ badge, compact = false }: DayBadgeProps) {
  const colors = COLOR_MAP[badge.color] || COLOR_MAP.slate;
  const icon = ICON_MAP[badge.icon] || null;
  
  if (compact) {
    // Ultra-compact for mobile
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`inline-flex items-center justify-center px-1 py-0.5 rounded text-[8px] font-medium ${colors.bg} ${colors.text}`}>
            {badge.badge}
          </div>
        </TooltipTrigger>
        <TooltipContent side="top">
          {badge.tooltip}
        </TooltipContent>
      </Tooltip>
    );
  }
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border ${colors.bg} ${colors.text} ${colors.border} text-[9px] font-medium cursor-default`}>
          {icon}
          <span>{badge.badge}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top">
        {badge.tooltip}
      </TooltipContent>
    </Tooltip>
  );
}

export default DayBadge;
