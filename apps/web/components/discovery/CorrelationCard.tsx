/**
 * Correlation Card Component
 * 
 * Displays a single correlation with interpretation.
 * Tone: Sparse, direct, data-driven.
 */

'use client';

import type { Correlation } from '@/lib/api/services/correlations';
import { InfoIcon } from './InfoIcon';
import { InsightFeedback } from '@/components/insights/InsightFeedback';

interface CorrelationCardProps {
  correlation: Correlation;
  className?: string;
}

function formatInputName(name: string, lagDays: number = 0): string {
  // Convert snake_case to readable format
  const formatted = name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
  
  // Add lag info if present
  if (lagDays > 0) {
    return `${formatted} (${lagDays} day${lagDays > 1 ? 's' : ''} before)`;
  }
  
  return formatted;
}

function getCorrelationInterpretation(correlation: Correlation): string {
  const absR = Math.abs(correlation.correlation_coefficient);
  const inputName = formatInputName(correlation.input_name, correlation.time_lag_days);
  
  // For efficiency factor: negative correlation = better (lower EF = more efficient)
  // So "negative" direction means input improves efficiency
  if (correlation.direction === 'negative') {
    // This input improves efficiency
    const percent = Math.round(absR * 100);
    return `${inputName} explains ${percent}% of your efficiency gains.`;
  } else {
    // This input reduces efficiency
    const percent = Math.round(absR * 100);
    return `${inputName} correlates with ${percent}% worse efficiency.`;
  }
}

function getStrengthColor(strength: string): string {
  switch (strength) {
    case 'strong':
      return 'text-green-400';
    case 'moderate':
      return 'text-yellow-400';
    case 'weak':
      return 'text-slate-400';
    default:
      return 'text-slate-400';
  }
}

export function CorrelationCard({ correlation, className = '' }: CorrelationCardProps) {
  const interpretation = getCorrelationInterpretation(correlation);
  const isPositive = correlation.direction === 'negative'; // Negative correlation = better efficiency
  
  return (
    <div
      className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="text-lg font-semibold mb-1">
            {formatInputName(correlation.input_name, correlation.time_lag_days)}
          </h3>
          <p className="text-sm text-slate-400">
            {interpretation}
          </p>
        </div>
        <div className={`text-right ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          <div className="text-2xl font-bold">
            {correlation.correlation_coefficient > 0 ? '+' : ''}
            {correlation.correlation_coefficient.toFixed(2)}
          </div>
          <div className={`text-xs ${getStrengthColor(correlation.strength)}`}>
            {correlation.strength}
          </div>
        </div>
      </div>
      
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-700/50">
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span>
            p = {correlation.p_value.toFixed(3)}
          </span>
          <span>
            n = {correlation.sample_size}
          </span>
          {correlation.time_lag_days > 0 && (
            <span>
              Lag: {correlation.time_lag_days}d
            </span>
          )}
        </div>
        <InsightFeedback
          insightType="correlation"
          insightId={correlation.input_name}
          insightText={interpretation}
          className="text-xs"
        />
      </div>
    </div>
  );
}

