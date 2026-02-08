"use client";

import { TrendingUp } from "lucide-react";

/**
 * Progress page — placeholder for Phase 3.
 * Will merge Analytics, Training Load, Compare, PBs, and Insights
 * into a single conclusion-first page.
 */
export default function ProgressPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 pb-24 md:pb-12">
      <div className="flex items-center gap-3 mb-8">
        <TrendingUp className="w-7 h-7 text-orange-500" />
        <h1 className="text-2xl font-bold text-white">Progress</h1>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center">
        <p className="text-slate-400 text-lg mb-2">Coming soon</p>
        <p className="text-slate-500 text-sm max-w-md mx-auto">
          Your unified progress view — what&apos;s working, what&apos;s not,
          fitness trends, efficiency, personal bests in context, and period
          comparisons — all in one place.
        </p>
      </div>
    </div>
  );
}
