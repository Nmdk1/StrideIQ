/**
 * What Doesn't Work Section
 * 
 * Displays negative correlations (inputs that reduce efficiency).
 * Tone: Sparse, direct, honest.
 */

'use client';

import type { Correlation } from '@/lib/api/services/correlations';
import { CorrelationCard } from './CorrelationCard';

interface WhatDoesntWorkSectionProps {
  correlations: Correlation[];
  className?: string;
}

export function WhatDoesntWorkSection({ correlations, className = '' }: WhatDoesntWorkSectionProps) {
  if (correlations.length === 0) {
    return (
      <div className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className}`}>
        <h2 className="text-xl font-semibold mb-2">What Doesn&apos;t Work</h2>
        <p className="text-slate-400">
          No negative patterns detected. Keep going.
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-4">
        <h2 className="text-2xl font-bold mb-2">What Doesn&apos;t Work</h2>
        <p className="text-slate-400 text-sm">
          Inputs that correlate with worse efficiency. Statistically significant.
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {correlations.map((correlation, index) => (
          <CorrelationCard key={index} correlation={correlation} />
        ))}
      </div>
    </div>
  );
}

