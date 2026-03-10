'use client';

/**
 * HOME PAGE PREVIEW — Static layout for founder visual review.
 *
 * Uses real MiniPaceChart component with hardcoded data.
 * Visit /home-preview to review. Delete after approval.
 */

import React from 'react';
import Link from 'next/link';
import { ArrowRight, Sparkles } from 'lucide-react';
import { MiniPaceChart } from '@/components/home/MiniPaceChart';

/* ── Hardcoded data from a real 10-mile easy run ──────────────────────── */

// Pace in s/km: warm-up (slow) → steady → slight pickup → cool-down
const PACE_STREAM: number[] = (() => {
  const pts: number[] = [];
  // 50 points simulating a real easy run shape
  const profile = [
    380, 370, 360, 350, 345, 340, 338, 336, 335, 334,
    333, 332, 332, 331, 330, 330, 331, 332, 331, 330,
    328, 326, 324, 322, 320, 318, 316, 315, 314, 312,
    310, 308, 306, 305, 304, 303, 302, 300, 298, 295,
    292, 290, 288, 286, 284, 282, 280, 290, 310, 340,
  ];
  return profile;
})();

// Effort: warm-up low → steady moderate → pickup harder → cool-down
const EFFORT_STREAM = [
  0.49, 0.52, 0.55, 0.58, 0.61, 0.63, 0.65, 0.66, 0.67, 0.68,
  0.69, 0.70, 0.70, 0.70, 0.71, 0.71, 0.70, 0.70, 0.71, 0.72,
  0.73, 0.74, 0.75, 0.76, 0.77, 0.78, 0.79, 0.80, 0.81, 0.82,
  0.83, 0.84, 0.84, 0.85, 0.85, 0.85, 0.86, 0.86, 0.85, 0.84,
  0.82, 0.80, 0.78, 0.75, 0.72, 0.68, 0.65, 0.62, 0.58, 0.55,
];

// Elevation in meters: gentle rolling terrain
const ELEVATION_STREAM = [
  45, 46, 48, 50, 53, 56, 58, 60, 61, 60,
  58, 55, 52, 50, 48, 47, 48, 50, 53, 56,
  60, 63, 66, 68, 70, 71, 70, 68, 65, 62,
  58, 55, 52, 50, 48, 47, 46, 45, 46, 48,
  50, 52, 54, 55, 56, 55, 53, 50, 48, 45,
];

/* ── Static Page ─────────────────────────────────────────────────────── */

export default function HomePreview() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">

      {/* ═══ ABOVE THE FOLD ═══ */}

      {/* 1. PACE CHART HERO — full bleed, edge to edge */}
      <div className="-mx-0">
        <MiniPaceChart
          paceStream={PACE_STREAM}
          effortIntensity={EFFORT_STREAM}
          elevationStream={ELEVATION_STREAM}
          height={120}
        />
      </div>

      {/* Metrics line */}
      <div className="px-5 py-2.5 flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Morning Run
          <span className="mx-1.5 text-slate-600">&middot;</span>
          10.0 mi
          <span className="mx-1.5 text-slate-600">&middot;</span>
          1:27:32
          <span className="mx-1.5 text-slate-600">&middot;</span>
          8:44/mi
          <span className="mx-1.5 text-slate-600">&middot;</span>
          113 bpm
        </p>
        <ArrowRight className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
      </div>

      {/* 2. THE VOICE — one paragraph, one voice */}
      <div className="px-5 pt-4 pb-4">
        <p className="text-base text-slate-300 leading-relaxed">
          48 miles across 5 runs this week. Yesterday&apos;s 10-miler averaged
          113 bpm — your aerobic engine is responding to the volume.
        </p>
      </div>

      {/* 3. TODAY&apos;S WORKOUT — plain text, no card chrome */}
      <div className="px-5 pb-5">
        <p className="text-xs uppercase tracking-wider text-slate-500 font-medium mb-2">
          Today
        </p>
        <p className="text-lg font-bold text-blue-400">
          18mi Long Run
          <span className="text-sm font-normal text-slate-500 ml-2">8:14/mi</span>
        </p>
        <p className="text-sm text-slate-400 leading-relaxed mt-1.5">
          This long run caps your peak week and teaches your legs to move when
          tired, which is exactly what miles 20-26 will demand.
        </p>
        <p className="text-xs text-slate-500 mt-2">Week 4 of 8 · Build Phase</p>
      </div>

      {/* ═══ BELOW THE FOLD ═══ */}

      <div className="mx-5 border-t border-slate-800" />

      {/* Coach insight — integrated, not a separate card */}
      <div className="px-5 py-4">
        <div className="flex gap-3">
          <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-slate-300 leading-relaxed">
            Your 66% volume jump over four weeks is aggressive but your body
            is absorbing it — the key now is not adding more stress, but
            letting this fitness consolidate.
          </p>
        </div>
      </div>

      <div className="mx-5 border-t border-slate-800" />

      {/* Placeholder for week strip / check-in / race countdown */}
      <div className="px-5 py-4 text-xs text-slate-600">
        [Week strip · Check-in · Race countdown would follow here]
      </div>

      <div className="h-20" />
    </div>
  );
}
