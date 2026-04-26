'use client';

import React from 'react';

export interface FindingAnnotation {
  text: string;
  domain: string;
  confidence_tier: string;
  evidence_summary?: string | null;
}

interface FindingsCardsProps {
  findings: FindingAnnotation[] | undefined;
}

export function FindingsCards({ findings }: FindingsCardsProps) {
  if (!findings || findings.length === 0) return null;

  return (
    <div className="space-y-2">
      {findings.map((f, i) => (
        <div key={i} className="rounded-lg border border-slate-700/30 bg-slate-800/20 px-4 py-3">
          <div className="flex items-start gap-2">
            <span className="text-sm flex-shrink-0">🔬</span>
            <div>
              <p className="text-sm text-slate-300">{f.text}</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {f.confidence_tier === 'strong' ? 'Strong' : 'Confirmed'} · {f.domain.replace(/_/g, ' ')}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
