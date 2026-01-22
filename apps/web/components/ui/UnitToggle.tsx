"use client";

/**
 * Unit Toggle Component
 * 
 * Allows users to switch between metric (km) and imperial (miles) units.
 */

import React from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface UnitToggleProps {
  className?: string;
  compact?: boolean;
}

export function UnitToggle({ className = '', compact = false }: UnitToggleProps) {
  const { units, setUnits, isLoading } = useUnits();

  if (isLoading) {
    return null;
  }

  if (compact) {
    // Compact button toggle
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={() => setUnits(units === 'metric' ? 'imperial' : 'metric')}
            className={`px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded transition-colors ${className}`}
          >
            {units === 'metric' ? 'km' : 'mi'}
          </button>
        </TooltipTrigger>
        <TooltipContent side="top">
          Switch to {units === 'metric' ? 'miles' : 'kilometers'}
        </TooltipContent>
      </Tooltip>
    );
  }

  // Full toggle with both options
  return (
    <div className={`flex items-center gap-1 bg-slate-800 rounded-lg p-1 ${className}`}>
      <button
        onClick={() => setUnits('metric')}
        className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
          units === 'metric'
            ? 'bg-orange-600 text-white'
            : 'text-slate-400 hover:text-white'
        }`}
      >
        km
      </button>
      <button
        onClick={() => setUnits('imperial')}
        className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
          units === 'imperial'
            ? 'bg-orange-600 text-white'
            : 'text-slate-400 hover:text-white'
        }`}
      >
        mi
      </button>
    </div>
  );
}
