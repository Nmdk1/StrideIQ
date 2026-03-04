'use client';

import React from 'react';
import { SparklineChart } from './SparklineChart';

const C = {
  card: '#141c2e',
  border: 'rgba(255,255,255,0.07)',
  orange: '#c2650a',
  oFaint: 'rgba(194,101,10,0.11)',
  oBorder: 'rgba(194,101,10,0.27)',
  green: '#2ab87a',
  red: '#e05252',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  w: '#fff',
};

interface VerdictProps {
  sparklineData: number[];
  sparklineDirection: 'rising' | 'stable' | 'declining';
  currentValue: number;
  text: string;
  grounding: string[];
  confidence: 'high' | 'moderate' | 'low';
}

export function VerdictSection({
  sparklineData,
  sparklineDirection,
  currentValue,
  text,
  grounding,
}: VerdictProps) {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: '26px 28px',
      }}
    >
      <p
        style={{
          color: C.t40,
          fontSize: 10,
          textTransform: 'uppercase',
          letterSpacing: '0.16em',
          fontWeight: 600,
          marginBottom: 14,
        }}
      >
        Fitness Trend
      </p>

      <SparklineChart
        data={sparklineData}
        direction={sparklineDirection}
        currentValue={currentValue}
        height={56}
      />

      <p
        style={{
          fontSize: 14,
          color: C.t60,
          lineHeight: 1.7,
          marginTop: 16,
          marginBottom: grounding.length > 0 ? 14 : 0,
        }}
      >
        {text}
      </p>

      {grounding.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {grounding.map((g, i) => (
            <span
              key={i}
              style={{
                fontSize: 11,
                color: C.orange,
                background: C.oFaint,
                border: `1px solid ${C.oBorder}`,
                borderRadius: 6,
                padding: '3px 10px',
                whiteSpace: 'nowrap',
              }}
            >
              {g}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
