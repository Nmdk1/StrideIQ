'use client';

import React from 'react';
import { BarChart } from './BarChart';
import { SparklineChart } from './SparklineChart';
import { HealthStrip } from './HealthStrip';
import { FormGauge } from './FormGauge';
import { CompletionRing } from './CompletionRing';
import { StatHighlight } from './StatHighlight';

const C = {
  card: '#141c2e',
  border: 'rgba(255,255,255,0.07)',
  orange: '#c2650a',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  t80: 'rgba(255,255,255,0.8)',
  w: '#fff',
};

function ChapterVisual({ type, data }: { type: string; data: Record<string, unknown> }) {
  switch (type) {
    case 'bar_chart':
      return (
        <BarChart
          labels={(data.labels as string[]) ?? []}
          values={(data.values as number[]) ?? []}
          highlightIndex={data.highlight_index as number | undefined}
          unit={data.unit as string | undefined}
        />
      );
    case 'sparkline':
      return (
        <SparklineChart
          data={(data.values as number[]) ?? []}
          direction={(data.direction as string) ?? 'stable'}
          currentValue={data.current as number | undefined}
        />
      );
    case 'health_strip':
      return <HealthStrip indicators={(data.indicators as Array<{ label: string; value: string; status: 'green' | 'amber' | 'red'; trend?: 'up' | 'down' | 'stable' }>) ?? []} />;
    case 'gauge':
      return (
        <FormGauge
          value={(data.value as number) ?? 0}
          zoneLabel={(data.zone_label as string) ?? ''}
        />
      );
    case 'completion_ring':
      return <CompletionRing pct={(data.pct as number) ?? 0} />;
    case 'stat_highlight':
      return (
        <StatHighlight
          distance={(data.distance as string) ?? ''}
          time={(data.time as string) ?? ''}
          dateAchieved={data.date_achieved as string | undefined}
        />
      );
    default:
      return null;
  }
}

interface ChapterCardProps {
  title: string;
  visualType: string;
  visualData: Record<string, unknown>;
  observation: string;
  interpretation?: string;
  action?: string;
}

export function ChapterCard({
  title,
  visualType,
  visualData,
  observation,
  interpretation,
  action,
}: ChapterCardProps) {
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
        {title}
      </p>

      <ChapterVisual type={visualType} data={visualData} />

      {observation && (
        <p
          style={{
            fontSize: 14,
            color: C.t60,
            lineHeight: 1.7,
            marginTop: 16,
          }}
        >
          {observation}
        </p>
      )}

      {interpretation && (
        <p
          style={{
            fontSize: 13,
            color: C.t80,
            lineHeight: 1.7,
            marginTop: 10,
            fontStyle: 'italic',
          }}
        >
          {interpretation}
        </p>
      )}

      {action && (
        <p
          style={{
            fontSize: 13,
            color: C.orange,
            lineHeight: 1.6,
            marginTop: 10,
            fontWeight: 500,
          }}
        >
          {action}
        </p>
      )}
    </div>
  );
}
