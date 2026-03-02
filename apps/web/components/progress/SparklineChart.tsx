'use client';

import React, { useState } from 'react';

interface SparklineChartProps {
  data: number[];
  direction: string;
  currentValue?: number;
  height?: number;
  width?: string;
}

const DIRECTION_COLORS: Record<string, { stroke: string; fill: string }> = {
  rising: { stroke: '#34d399', fill: '#34d39920' },
  improving: { stroke: '#34d399', fill: '#34d39920' },
  stable: { stroke: '#fbbf24', fill: '#fbbf2420' },
  declining: { stroke: '#f87171', fill: '#f8717120' },
  worsening: { stroke: '#f87171', fill: '#f8717120' },
};

const DEFAULT_COLORS = { stroke: '#fbbf24', fill: '#fbbf2420' };

export function SparklineChart({
  data,
  direction,
  currentValue,
  height = 48,
  width = '100%',
}: SparklineChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!data.length) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 4;
  const svgWidth = 200;

  const points = data.map((v, i) => ({
    x: padding + (i / (data.length - 1 || 1)) * (svgWidth - padding * 2),
    y: padding + (1 - (v - min) / range) * (height - padding * 2),
    value: v,
  }));

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`;

  const colors = DIRECTION_COLORS[direction] || DEFAULT_COLORS;

  return (
    <div className="relative" style={{ width }}>
      <svg
        viewBox={`0 0 ${svgWidth} ${height}`}
        className="w-full"
        preserveAspectRatio="none"
        onMouseLeave={() => setHoverIdx(null)}
      >
        <path d={areaPath} fill={colors.fill} />
        <path d={linePath} fill="none" stroke={colors.stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <rect
            key={i}
            x={p.x - (svgWidth / data.length) / 2}
            y={0}
            width={svgWidth / data.length}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHoverIdx(i)}
            style={{ cursor: 'crosshair' }}
          />
        ))}
        {/* Current dot */}
        <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r="3" fill={colors.stroke} />
        {/* Hover dot */}
        {hoverIdx !== null && (
          <>
            <circle cx={points[hoverIdx].x} cy={points[hoverIdx].y} r="4" fill={colors.stroke} stroke="white" strokeWidth="1.5" />
            <line x1={points[hoverIdx].x} y1={0} x2={points[hoverIdx].x} y2={height} stroke={colors.stroke} strokeWidth="0.5" strokeDasharray="2,2" opacity="0.5" />
          </>
        )}
      </svg>
      {hoverIdx !== null && (
        <div
          className="absolute -top-6 bg-slate-800 border border-slate-600 rounded px-1.5 py-0.5 text-xs text-white whitespace-nowrap pointer-events-none"
          style={{ left: `${(points[hoverIdx].x / svgWidth) * 100}%`, transform: 'translateX(-50%)' }}
        >
          {points[hoverIdx].value.toFixed(1)}
        </div>
      )}
      <div className="flex justify-between text-xs text-slate-500 mt-1">
        <span>{data[0]?.toFixed(1)}</span>
        {currentValue !== undefined && (
          <span className="font-medium text-slate-300">{currentValue.toFixed(1)}</span>
        )}
      </div>
    </div>
  );
}
