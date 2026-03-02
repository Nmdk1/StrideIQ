'use client';

import React from 'react';

interface FormGaugeProps {
  value: number;
  zoneLabel: string;
  zones?: string[];
}

export function FormGauge({ value, zoneLabel, zones = ['fatigued', 'training', 'fresh', 'peaked'] }: FormGaugeProps) {
  // Map TSB to gauge position (0-100). TSB range roughly -30 to +30.
  const normalized = Math.max(0, Math.min(100, ((value + 30) / 60) * 100));

  const zoneColors: Record<string, string> = {
    fatigued: '#f87171',
    training: '#fbbf24',
    fresh: '#34d399',
    peaked: '#60a5fa',
    building: '#fbbf24',
    ready: '#34d399',
    'over-tapered': '#94a3b8',
  };

  const needleAngle = -90 + (normalized / 100) * 180;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 70" className="w-32 h-20">
        {/* Background arc segments */}
        {zones.map((zone, i) => {
          const startAngle = -90 + (i / zones.length) * 180;
          const endAngle = -90 + ((i + 1) / zones.length) * 180;
          const startRad = (startAngle * Math.PI) / 180;
          const endRad = (endAngle * Math.PI) / 180;
          const r = 45;
          const cx = 60;
          const cy = 60;
          return (
            <path
              key={zone}
              d={`M ${cx + r * Math.cos(startRad)} ${cy + r * Math.sin(startRad)} A ${r} ${r} 0 0 1 ${cx + r * Math.cos(endRad)} ${cy + r * Math.sin(endRad)}`}
              fill="none"
              stroke={zoneColors[zone] || '#64748b'}
              strokeWidth="8"
              strokeLinecap="round"
              opacity="0.4"
            />
          );
        })}
        {/* Needle */}
        {(() => {
          const rad = (needleAngle * Math.PI) / 180;
          const r = 35;
          return (
            <line
              x1={60}
              y1={60}
              x2={60 + r * Math.cos(rad)}
              y2={60 + r * Math.sin(rad)}
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
            />
          );
        })()}
        <circle cx={60} cy={60} r="3" fill="white" />
      </svg>
      <div className="text-center -mt-1">
        <p className="text-lg font-bold text-white">{value >= 0 ? '+' : ''}{value.toFixed(1)}</p>
        <p className="text-xs text-slate-400">{zoneLabel}</p>
      </div>
    </div>
  );
}
