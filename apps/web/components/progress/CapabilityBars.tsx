'use client';

import React from 'react';

interface Capability {
  distance: string;
  current: string | null;
  previous?: string | null;
  confidence: 'high' | 'moderate' | 'low';
}

interface CapabilityBarsProps {
  capabilities: Capability[];
}

const CONFIDENCE_COLORS = {
  high: 'bg-emerald-500/60 border-emerald-500/30',
  moderate: 'bg-blue-500/50 border-blue-500/30',
  low: 'bg-slate-500/40 border-slate-500/30',
};

const CONFIDENCE_TEXT = {
  high: 'text-emerald-400',
  moderate: 'text-blue-400',
  low: 'text-slate-400',
};

export function CapabilityBars({ capabilities }: CapabilityBarsProps) {
  if (!capabilities.length) return null;

  return (
    <div className="space-y-2">
      {capabilities.map((cap) => (
        <div key={cap.distance} className="flex items-center gap-3">
          <span className="text-xs text-slate-400 w-16 text-right flex-shrink-0">{cap.distance}</span>
          <div className="flex-1 relative">
            {cap.previous && (
              <div className="absolute inset-0 bg-slate-700/30 rounded h-7 flex items-center justify-end pr-2">
                <span className="text-xs text-slate-600">{cap.previous}</span>
              </div>
            )}
            <div
              className={`relative h-7 rounded border flex items-center justify-end pr-2 ${CONFIDENCE_COLORS[cap.confidence]}`}
              style={{ width: cap.previous ? '85%' : '100%' }}
            >
              <span className={`text-sm font-bold ${CONFIDENCE_TEXT[cap.confidence]}`}>
                {cap.current || '—'}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
