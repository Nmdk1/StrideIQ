/**
 * What's Working Section
 * 
 * Displays positive correlations (inputs that improve efficiency).
 * Tone: Sparse, direct, irreverent when earned.
 */

'use client';

import type { Correlation } from '@/lib/api/services/correlations';
import { CorrelationCard } from './CorrelationCard';

interface WhatWorksSectionProps {
  correlations: Correlation[];
  className?: string;
}

export function WhatWorksSection({ correlations, className = '' }: WhatWorksSectionProps) {
  if (correlations.length === 0) {
    return (
      <div className={`bg-gray-800 rounded-lg border border-gray-700 p-6 ${className}`}>
        <h2 className="text-xl font-semibold mb-2">What&apos;s Working</h2>
        <p className="text-gray-400">
          Not enough data yet. Log 10 more runs to see patterns.
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-4">
        <h2 className="text-2xl font-bold mb-2">What&apos;s Working</h2>
        <p className="text-gray-400 text-sm">
          Inputs that correlate with better efficiency. Pattern holds over {correlations[0]?.sample_size || 0} runs.
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

