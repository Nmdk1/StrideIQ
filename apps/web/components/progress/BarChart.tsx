'use client';

import React, { useState } from 'react';

interface BarChartProps {
  labels: string[];
  values: number[];
  highlightIndex?: number;
  unit?: string;
}

export function BarChart({ labels, values, highlightIndex, unit = 'mi' }: BarChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const maxVal = Math.max(...values, 1);

  return (
    <div className="space-y-1.5">
      {values.map((val, i) => {
        const pct = (val / maxVal) * 100;
        const isHighlight = i === highlightIndex;
        const isHover = i === hoverIdx;
        return (
          <div
            key={i}
            className="flex items-center gap-2 group"
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
          >
            <span className={`text-xs w-12 text-right flex-shrink-0 ${isHighlight ? 'text-orange-400 font-medium' : 'text-slate-500'}`}>
              {labels[i] || ''}
            </span>
            <div className="flex-1 bg-slate-700/30 rounded-full h-6 overflow-hidden relative">
              <div
                className={`h-full rounded-full flex items-center justify-end pr-2 transition-all duration-300 ${
                  isHighlight
                    ? 'bg-orange-500/50 border border-orange-500/30'
                    : isHover
                      ? 'bg-slate-500/40'
                      : 'bg-slate-600/40'
                }`}
                style={{ width: `${Math.max(pct, 8)}%` }}
              >
                <span className={`text-xs font-medium ${isHighlight ? 'text-white' : 'text-slate-300'}`}>
                  {val}{unit ? ` ${unit}` : ''}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
