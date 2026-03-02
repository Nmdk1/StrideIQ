'use client';

import React from 'react';

interface CompletionRingProps {
  pct: number;
  size?: number;
}

export function CompletionRing({ pct, size = 80 }: CompletionRingProps) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(pct, 100) / 100);

  const color = pct >= 80 ? '#34d399' : pct >= 60 ? '#fbbf24' : '#f87171';

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#334155"
          strokeWidth="6"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000"
        />
      </svg>
      <span className="text-lg font-bold text-white -mt-12">{Math.round(pct)}%</span>
    </div>
  );
}
