'use client';

import React from 'react';

interface PairedSparklineProps {
  inputSeries: number[];
  outputSeries: number[];
  inputLabel: string;
  outputLabel: string;
}

function MiniSparkline({ data, color, height = 28 }: { data: number[]; color: string; height?: number }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 160;
  const pad = 2;

  const points = data.map((v, i) => ({
    x: pad + (i / (data.length - 1)) * (w - pad * 2),
    y: pad + (1 - (v - min) / range) * (height - pad * 2),
  }));

  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="none">
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r="2" fill={color} />
    </svg>
  );
}

export function PairedSparkline({ inputSeries, outputSeries, inputLabel, outputLabel }: PairedSparklineProps) {
  return (
    <div className="space-y-2 bg-slate-800/40 rounded-lg p-3 border border-slate-700/40">
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">{inputLabel}</span>
        </div>
        <MiniSparkline data={inputSeries} color="#fbbf24" />
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">{outputLabel}</span>
        </div>
        <MiniSparkline data={outputSeries} color="#34d399" />
      </div>
      <div className="flex items-center justify-center gap-1 text-xs text-slate-500">
        <span className="w-2 h-0.5 bg-amber-400 rounded-full" />
        <span>{inputLabel}</span>
        <span className="mx-1">·</span>
        <span className="w-2 h-0.5 bg-emerald-400 rounded-full" />
        <span>{outputLabel}</span>
      </div>
    </div>
  );
}
