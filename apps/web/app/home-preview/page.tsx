'use client';

/**
 * HOME PAGE PREVIEW — Static layout skeleton for founder review.
 *
 * No API calls. No hooks. No data. Just visual structure.
 * Hardcoded text from real Opus output so the proportions are honest.
 *
 * Visit /home-preview to review. Delete after approval.
 */

import React from 'react';
import Link from 'next/link';
import { ArrowRight, MessageSquare, Target, Sparkles } from 'lucide-react';

/* ── Fake effort gradient (canvas drawn on mount) ────────────────────── */
function FakeGradient() {
  const ref = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const w = c.parentElement?.clientWidth ?? 800;
    c.width = w;
    c.height = 200;
    const ctx = c.getContext('2d');
    if (!ctx) return;

    // Simulate a real effort curve: warm-up → steady → surge → cool-down
    const curve = [
      0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.63, 0.66, 0.68, 0.70,
      0.70, 0.69, 0.70, 0.71, 0.70, 0.70, 0.72, 0.73, 0.75, 0.76,
      0.78, 0.80, 0.82, 0.84, 0.85, 0.86, 0.85, 0.83, 0.80, 0.78,
      0.76, 0.74, 0.72, 0.70, 0.68, 0.67, 0.66, 0.65, 0.66, 0.67,
      0.68, 0.67, 0.66, 0.65, 0.64, 0.63, 0.62, 0.60, 0.58, 0.55,
    ];

    // HSL-based effort coloring (matches effortColor.ts palette)
    function effortHSL(t: number): string {
      if (t <= 0.3) return `hsl(205, 55%, ${32 + t * 10}%)`;
      if (t <= 0.5) return `hsl(${175 - (t - 0.3) * 685}, 50%, 35%)`;
      if (t <= 0.7) return `hsl(${38 - (t - 0.5) * 100}, 62%, 37%)`;
      if (t <= 0.85) return `hsl(${18 - (t - 0.7) * 87}, 65%, 35%)`;
      return `hsl(${5 - (t - 0.85) * 100}, 70%, 30%)`;
    }

    const px = w / curve.length;
    for (let i = 0; i < curve.length; i++) {
      ctx.fillStyle = effortHSL(curve[i]);
      ctx.fillRect(Math.floor(i * px), 0, Math.ceil(px) + 1, 200);
    }
  }, []);

  return (
    <canvas
      ref={ref}
      className="w-full"
      style={{ height: 200, display: 'block' }}
    />
  );
}

/* ── Static Page ─────────────────────────────────────────────────────── */

export default function HomePreview() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">

      {/* ═══════════════════════════════════════════════════════════════
          ABOVE THE FOLD — This is what the athlete sees at 6am
          before their long run. Three things. Nothing else.
          ═══════════════════════════════════════════════════════════════ */}

      {/* 1. EFFORT GRADIENT — full bleed, edge to edge, no chrome */}
      <div className="relative">
        <FakeGradient />

        {/* Run info overlaid on bottom of gradient */}
        <div className="absolute bottom-0 left-0 right-0 px-5 pb-3 bg-gradient-to-t from-slate-900/90 to-transparent pt-12">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-white font-semibold text-base">Morning Run</p>
              <p className="text-slate-300 text-xs">Yesterday · 10.0 mi · 1:27:32 · 8:44/mi · 113 bpm</p>
            </div>
            <span className="text-xs text-slate-400 font-medium">
              See run →
            </span>
          </div>
        </div>
      </div>

      {/* 2. THE VOICE — the app speaks. Big text. Room to breathe. */}
      <div className="px-5 pt-6 pb-4">
        <p className="text-lg text-slate-100 leading-relaxed font-light">
          48 miles across 5 runs this week. Yesterday&apos;s 10-miler averaged
          113 bpm — your aerobic engine is responding to the volume.
        </p>
      </div>

      {/* 3. COACH INSIGHT — the single most important thing to know */}
      <div className="px-5 pb-5">
        <div className="flex gap-3">
          <Sparkles className="w-4 h-4 text-orange-400 flex-shrink-0 mt-1" />
          <div>
            <p className="text-sm text-slate-200 leading-relaxed">
              Your 66% volume jump over four weeks is aggressive but your body
              is absorbing it — yesterday&apos;s 10-miler at 8:45 pace with HR at 113
              shows you&apos;re handling the load efficiently. The key now is not
              adding more stress, but letting this fitness consolidate.
            </p>
            <Link
              href="/coach"
              className="inline-flex items-center gap-1 mt-2 text-xs font-semibold text-orange-400 hover:text-orange-300"
            >
              Ask Coach <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-5 border-t border-slate-800" />

      {/* 4. TODAY'S WORKOUT — what to do and WHY */}
      <div className="px-5 pt-5 pb-4">
        <p className="text-xs uppercase tracking-wider text-slate-500 font-medium mb-3">
          Today
        </p>
        <div className="flex items-baseline gap-2 mb-1">
          <p className="text-xl font-bold text-blue-400">18mi Long Run</p>
          <span className="text-sm text-slate-500">8:14/mi</span>
        </div>
        <p className="text-sm text-slate-300 leading-relaxed mt-2">
          This long run caps your peak week and teaches your legs to move when
          tired, which is exactly what miles 20-26 will demand.
        </p>
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-slate-500">Week 4 · Build</span>
          <Link
            href="/coach"
            className="inline-flex items-center gap-1 text-xs font-semibold text-orange-400 hover:text-orange-300"
          >
            Ask Coach <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          BELOW THE FOLD — secondary info, scroll to see
          ═══════════════════════════════════════════════════════════════ */}

      <div className="mx-5 border-t border-slate-800" />

      {/* RACE COUNTDOWN */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-4 h-4 text-pink-400" />
          <span className="text-xs uppercase tracking-wider text-slate-500 font-medium">
            Race Countdown
          </span>
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-2xl font-bold text-white">28</span>
          <span className="text-sm text-slate-400">days to Tobacco Road</span>
        </div>
        <p className="text-sm text-slate-300 leading-relaxed mt-1">
          Four weeks out with fitness still building — you&apos;re tracking toward
          your goal, but the next two weeks of smart recovery will determine
          whether you arrive fresh or fatigued.
        </p>
      </div>

      <div className="mx-5 border-t border-slate-800" />

      {/* COACH LINK */}
      <div className="px-5 py-5">
        <Link
          href="/coach"
          className="flex items-center justify-center gap-2 w-full py-3 rounded-lg bg-slate-800 hover:bg-slate-750 text-sm font-medium text-slate-300 transition-colors"
        >
          <MessageSquare className="w-4 h-4" /> Talk to Coach
        </Link>
      </div>

      {/* Spacer for scroll */}
      <div className="h-20" />
    </div>
  );
}
