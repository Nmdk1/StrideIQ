/**
 * Activity Insights Component
 * 
 * Displays efficiency insights with appropriate tone.
 * Can be swapped for different insight display styles.
 */

'use client';

import type { RunDelivery } from '@/lib/api/types';

interface ActivityInsightsProps {
  delivery: RunDelivery;
  className?: string;
}

export function ActivityInsights({ delivery, className = '' }: ActivityInsightsProps) {
  if (!delivery.show_insights || delivery.insights.length === 0) {
    return null;
  }

  const toneClasses = {
    irreverent: 'border-orange-500/50 bg-orange-900/20',
    sparse: 'border-slate-600/50 bg-slate-800/50',
  };

  return (
    <div className={`rounded-lg border p-4 ${toneClasses[delivery.insight_tone]} ${className}`}>
      <h3 className="text-lg font-semibold mb-3">
        {delivery.insight_tone === 'irreverent' ? 'Insights' : 'Run Summary'}
      </h3>
      <ul className="space-y-2">
        {delivery.insights.map((insight, index) => (
          <li key={index} className="text-sm">
            {insight}
          </li>
        ))}
      </ul>
      {delivery.metrics.efficiency_score && (
        <div className="mt-4 pt-4 border-t border-slate-700/50">
          <p className="text-xs text-slate-400">
            Efficiency Score: {delivery.metrics.efficiency_score.toFixed(4)}
          </p>
        </div>
      )}
    </div>
  );
}


