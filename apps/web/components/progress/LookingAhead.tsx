'use client';

import React from 'react';
import { CapabilityBars } from './CapabilityBars';
import type {
  LookingAhead as LookingAheadData,
  RaceScenario,
} from '@/lib/hooks/queries/progress';

const C = {
  card: '#141c2e',
  border: 'rgba(255,255,255,0.07)',
  orange: '#c2650a',
  oFaint: 'rgba(194,101,10,0.11)',
  oBorder: 'rgba(194,101,10,0.27)',
  green: '#2ab87a',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  t80: 'rgba(255,255,255,0.8)',
  w: '#fff',
};

function ReadinessGauge({ score, label }: { score: number; label: string }) {
  const clamp = Math.min(100, Math.max(0, score));
  const color = clamp >= 70 ? C.green : clamp >= 40 ? C.orange : '#e05252';
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, color: C.t60 }}>Race readiness</span>
        <span style={{ fontSize: 13, color, fontWeight: 600 }}>
          {label} ({Math.round(clamp)}%)
        </span>
      </div>
      <div
        style={{
          height: 6,
          background: 'rgba(255,255,255,0.08)',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${clamp}%`,
            height: '100%',
            background: color,
            borderRadius: 3,
            transition: 'width 1s ease',
          }}
        />
      </div>
    </div>
  );
}

function ScenarioCard({ scenario }: { scenario: RaceScenario }) {
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: '14px 16px',
      }}
    >
      <p style={{ fontSize: 12, fontWeight: 600, color: C.t80, marginBottom: 4 }}>
        {scenario.label}
      </p>
      <p style={{ fontSize: 13, color: C.t60, lineHeight: 1.6 }}>{scenario.narrative}</p>
      {scenario.estimated_finish && (
        <p style={{ fontSize: 12, color: C.orange, marginTop: 6 }}>
          Est. finish: {scenario.estimated_finish}
        </p>
      )}
      {scenario.key_action && (
        <p style={{ fontSize: 12, color: C.green, marginTop: 4 }}>{scenario.key_action}</p>
      )}
    </div>
  );
}

interface LookingAheadProps {
  data: LookingAheadData;
}

export function LookingAheadSection({ data }: LookingAheadProps) {
  const { variant, race, trajectory } = data;

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
          marginBottom: 16,
        }}
      >
        Looking Ahead
      </p>

      {variant === 'race' && race && (
        <>
          <div style={{ marginBottom: 16 }}>
            <p style={{ fontSize: 16, fontWeight: 600, color: C.w }}>{race.race_name}</p>
            <p style={{ fontSize: 13, color: C.t40, marginTop: 2 }}>
              {race.days_remaining} days · {race.training_phase}
            </p>
          </div>

          <ReadinessGauge score={race.readiness_score} label={race.readiness_label} />

          {race.scenarios.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {race.scenarios.map((s, i) => (
                <ScenarioCard key={i} scenario={s} />
              ))}
            </div>
          )}
        </>
      )}

      {variant === 'trajectory' && trajectory && (
        <>
          <CapabilityBars capabilities={trajectory.capabilities} />

          <p style={{ fontSize: 14, color: C.t60, lineHeight: 1.7, marginTop: 16 }}>
            {trajectory.narrative}
          </p>

          {trajectory.milestone_hint && (
            <p style={{ fontSize: 13, color: C.orange, marginTop: 10, fontWeight: 500 }}>
              {trajectory.milestone_hint}
            </p>
          )}
        </>
      )}
    </div>
  );
}
