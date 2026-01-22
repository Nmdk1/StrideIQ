/**
 * Decoupling Badge Component
 * 
 * Displays aerobic decoupling with traffic light badge + exact percentage.
 * 
 * Green: <5% decoupling (excellent durability)
 * Yellow: 5-8% decoupling (moderate cardiac drift)
 * Red: >8% decoupling (significant cardiac drift)
 */

'use client';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface DecouplingBadgeProps {
  decouplingPercent?: number;
  decouplingStatus?: 'green' | 'yellow' | 'red';
  className?: string;
}

export function DecouplingBadge({ 
  decouplingPercent, 
  decouplingStatus,
  className = '' 
}: DecouplingBadgeProps) {
  // Don't render if no decoupling data
  if (decouplingPercent === undefined || decouplingStatus === undefined) {
    return null;
  }

  // Determine badge color and label
  const badgeConfig = {
    green: {
      bgColor: 'bg-green-500',
      borderColor: 'border-green-400',
      textColor: 'text-green-400',
      label: 'Excellent'
    },
    yellow: {
      bgColor: 'bg-yellow-500',
      borderColor: 'border-yellow-400',
      textColor: 'text-yellow-400',
      label: 'Moderate'
    },
    red: {
      bgColor: 'bg-red-500',
      borderColor: 'border-red-400',
      textColor: 'text-red-400',
      label: 'High Drift'
    }
  };

  const config = badgeConfig[decouplingStatus];

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Traffic Light Badge */}
      <div className="flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={`w-4 h-4 rounded-full ${config.bgColor} border-2 ${config.borderColor} shadow-lg`} />
          </TooltipTrigger>
          <TooltipContent side="top">
            Aerobic decoupling: {decouplingPercent > 0 ? '+' : ''}{decouplingPercent.toFixed(1)}% ({config.label})
          </TooltipContent>
        </Tooltip>
        <span className={`text-sm font-medium ${config.textColor}`}>
          {config.label}
        </span>
      </div>
      
      {/* Exact Percentage */}
      <div className="flex items-center gap-1">
        <span className="text-sm text-slate-400">Decoupling:</span>
        <span className={`text-sm font-semibold ${config.textColor}`}>
          {decouplingPercent > 0 ? '+' : ''}
          {decouplingPercent.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}


