'use client';

import React, { useState, useEffect } from 'react';

const C = {
  bg: '#0d1321',
  border: 'rgba(255,255,255,0.07)',
  orange: '#c2650a',
  oL: '#e07b20',
  oFaint: 'rgba(194,101,10,0.11)',
  blue: '#4a90d9',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  w: '#fff',
};

function useCountUp(target: number, ms = 900, delay = 0) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => {
      const t0 = Date.now();
      const tick = () => {
        const p = Math.min((Date.now() - t0) / ms, 1);
        const e = 1 - Math.pow(1 - p, 3);
        setV(+(e * target).toFixed(1));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, delay);
    return () => clearTimeout(t);
  }, [target, ms, delay]);
  return v;
}

interface HeroStat {
  label: string;
  value: string;
  color: string;
}

interface ProgressHeroProps {
  dateLabel: string;
  headline: string;
  headlineAccent: string;
  subtext: string;
  stats: HeroStat[];
}

const COLOR_MAP: Record<string, string> = {
  muted: C.t40,
  blue: C.blue,
  orange: C.oL,
};

export function ProgressHero({ dateLabel, headline, headlineAccent, subtext, stats }: ProgressHeroProps) {
  return (
    <div
      style={{
        background: `linear-gradient(160deg, ${C.oFaint} 0%, transparent 55%)`,
        borderBottom: `1px solid ${C.border}`,
        padding: '44px 32px 36px',
        animation: 'fadeUp 0.7s ease both',
      }}
    >
      <div
        style={{
          maxWidth: 900,
          margin: '0 auto',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 24,
        }}
      >
        <div style={{ flex: 1, minWidth: 280 }}>
          <p
            style={{
              color: C.t40,
              fontSize: 10,
              textTransform: 'uppercase',
              letterSpacing: '0.16em',
              fontWeight: 600,
              margin: '0 0 8px',
            }}
          >
            {dateLabel}
          </p>
          <h1
            style={{
              fontSize: 36,
              fontWeight: 800,
              letterSpacing: '-1px',
              lineHeight: 1.15,
              marginBottom: 14,
              color: C.w,
            }}
          >
            {headline}
            <br />
            <span style={{ color: C.oL }}>{headlineAccent}</span>
          </h1>
          <p style={{ color: C.t60, fontSize: 15, lineHeight: 1.75, maxWidth: 500 }}>
            {subtext}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 32, alignItems: 'center', paddingTop: 4 }}>
          {stats.map((s) => {
            const numVal = parseFloat(s.value);
            const isNum = !isNaN(numVal);
            const decimals = s.value.includes('.') ? 1 : 0;
            const animated = useCountUp(isNum ? numVal : 0, 1100, 300);
            const color = COLOR_MAP[s.color] || C.t40;

            return (
              <div key={s.label} style={{ textAlign: 'center' }}>
                <p
                  style={{
                    fontSize: 10,
                    color: C.t40,
                    textTransform: 'uppercase',
                    letterSpacing: '0.13em',
                    marginBottom: 4,
                  }}
                >
                  {s.label}
                </p>
                <span
                  style={{
                    fontSize: 34,
                    fontWeight: 800,
                    color,
                    letterSpacing: '-1.5px',
                    lineHeight: 1,
                  }}
                >
                  {isNum ? animated.toFixed(decimals) : s.value}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
