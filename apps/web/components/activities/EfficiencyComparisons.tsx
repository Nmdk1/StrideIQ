/**
 * Efficiency Comparisons Component
 * 
 * Shows how this activity compares to various baselines.
 */

'use client';

import type { ActivityAnalysis } from '@/lib/api/types';

interface EfficiencyComparisonsProps {
  analysis: ActivityAnalysis;
  className?: string;
}

export function EfficiencyComparisons({ analysis, className = '' }: EfficiencyComparisonsProps) {
  if (!analysis.comparisons || analysis.comparisons.length === 0) {
    return null;
  }

  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700 p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4">Efficiency Comparisons</h3>
      <div className="space-y-4">
        {analysis.comparisons.map((comparison, index) => {
          const isImprovement = comparison.improvement_pct < 0; // Negative = improvement (lower EF)
          const improvementAbs = Math.abs(comparison.improvement_pct);

          return (
            <div
              key={index}
              className="bg-slate-900 rounded border border-slate-700 p-4"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h4 className="font-medium capitalize">
                    {comparison.baseline_type.replace('_', ' ')}
                  </h4>
                  <p className="text-xs text-slate-400">
                    Baseline: {comparison.baseline_pace.toFixed(2)} min/mi @{' '}
                    {comparison.baseline_hr} bpm
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={`text-lg font-semibold ${
                      isImprovement && comparison.is_meaningful
                        ? 'text-green-400'
                        : !isImprovement && comparison.is_meaningful
                        ? 'text-red-400'
                        : 'text-slate-400'
                    }`}
                  >
                    {isImprovement ? '-' : '+'}
                    {improvementAbs.toFixed(1)}%
                  </p>
                  {comparison.is_confirmed_trend && (
                    <p className="text-xs text-green-400">Confirmed trend</p>
                  )}
                </div>
              </div>
              {comparison.trend_avg_improvement && (
                <p className="text-xs text-slate-400">
                  Avg improvement over {comparison.sample_size} runs:{' '}
                  {comparison.trend_avg_improvement.toFixed(1)}%
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


