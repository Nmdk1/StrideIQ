"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks/useAuth';

// ─── Tier data ──────────────────────────────────────────────────────────────

const FREE_FEATURES = [
  'Training Pace Calculator (RPI)',
  'WMA Age-Grading',
  'Heat-Adjusted Pace',
  'Race Equivalency Tool',
  'Plan structure preview (phases, weeks, distances)',
];

const PLAN_UNLOCK_FEATURES = [
  'Everything in Free',
  'One race-plan unlock with full training paces',
  'Calculated training paces (Easy / Threshold / Interval / MP)',
  'Single plan entitlement, no recurring subscription',
];

const STRIDEIQ_FEATURES = [
  'Personal AI running coach',
  'Morning briefing with your data',
  'Daily intelligence and readiness',
  'Adaptive training plans and modification',
  'Performance analytics and workout narratives',
  'Living Fingerprint that compounds over time',
];

// ─── Component ───────────────────────────────────────────────────────────────

export default function Pricing() {
  const [period, setPeriod] = useState<'monthly' | 'annual'>('annual');
  const { isAuthenticated } = useAuth();

  const strideiqLabel = period === 'annual' ? '$199/yr' : '$24.99/mo';
  const strideiqSub = period === 'annual' ? 'Billed annually - save $100' : 'Billed monthly';

  // Authenticated users go straight to Settings upgrade panel.
  // New users go to /register; they upgrade in Settings after onboarding.
  const strideiqHref = isAuthenticated
    ? `/settings?upgrade=premium&period=${period}`
    : `/register?tier=premium&period=${period}`;

  return (
    <section id="pricing" className="py-20 bg-slate-800 scroll-mt-16">
      <div className="max-w-7xl mx-auto px-6">

        {/* Header */}
        <div className="text-center mb-10">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            One coach. One clear upgrade.
          </h2>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            Every athlete starts with a 30-day full trial. Keep Free tools forever, or subscribe to keep your personal coach unlocked.
          </p>
        </div>

        {/* Monthly / Annual toggle */}
        <div className="flex justify-center mb-10">
          <div className="inline-flex items-center bg-slate-900 border border-slate-700 rounded-xl p-1 gap-1">
            <button
              onClick={() => setPeriod('monthly')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                period === 'monthly'
                  ? 'bg-slate-700 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setPeriod('annual')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                period === 'annual'
                  ? 'bg-orange-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Annual
              {period !== 'annual' && (
                <span className="text-xs bg-emerald-600/30 text-emerald-400 px-1.5 py-0.5 rounded">
                  Save $100
                </span>
              )}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

          {/* ── Free ── */}
          <div className="bg-slate-900 rounded-2xl p-6 border border-slate-700/50 flex flex-col">
            <div className="mb-5">
              <h3 className="text-lg font-bold mb-1">Free</h3>
              <div className="text-3xl font-bold">$0</div>
              <p className="text-xs text-slate-500 mt-1">30-day full trial included</p>
            </div>
            <ul className="space-y-2 text-sm text-slate-400 flex-1 mb-6">
              {FREE_FEATURES.map(f => (
                <li key={f} className="flex items-start gap-2">
                  <span className="text-slate-600 mt-0.5 shrink-0">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/register"
              className="block w-full text-center bg-slate-700 hover:bg-slate-600 text-white py-2.5 rounded-lg transition-colors text-sm font-medium"
            >
              Start 30-Day Free Trial
            </Link>
          </div>

          {/* ── One-Time Plan Unlock ($5) ── */}
          <div className="bg-sky-950/50 rounded-2xl p-6 border border-sky-700/40 flex flex-col">
            <div className="mb-5">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-lg font-bold">Plan Unlock</h3>
                <span className="text-xs bg-sky-600/30 text-sky-400 px-2 py-0.5 rounded-full font-medium">One-time</span>
              </div>
              <div className="text-3xl font-bold">$5</div>
              <p className="text-xs text-sky-400/70 mt-1">Per race plan, no subscription</p>
            </div>
            <ul className="space-y-2 text-sm text-slate-300 flex-1 mb-6">
              {PLAN_UNLOCK_FEATURES.map(f => (
                <li key={f} className="flex items-start gap-2">
                  <span className="text-sky-500 mt-0.5 shrink-0">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/register"
              className="block w-full text-center bg-sky-700 hover:bg-sky-600 text-white py-2.5 rounded-lg transition-colors text-sm font-medium"
            >
              Unlock a plan for $5
            </Link>
          </div>

          {/* ── StrideIQ ── */}
          <div className="relative bg-gradient-to-br from-orange-900/50 to-slate-900 rounded-2xl p-6 border-2 border-orange-500 flex flex-col shadow-xl shadow-orange-500/10">
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-xs font-bold px-4 py-1 rounded-full uppercase tracking-wide whitespace-nowrap">
              Full Access
            </div>
            <div className="mb-5 mt-2">
              <h3 className="text-lg font-bold mb-1">StrideIQ</h3>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{strideiqLabel}</span>
              </div>
              <p className="text-xs text-orange-300/80 mt-1">{strideiqSub}</p>
            </div>
            <ul className="space-y-2 text-sm text-slate-300 flex-1 mb-6">
              {STRIDEIQ_FEATURES.map(f => (
                <li key={f} className="flex items-start gap-2">
                  <span className="text-orange-400 mt-0.5 shrink-0">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href={strideiqHref}
              className="block w-full text-center bg-orange-600 hover:bg-orange-500 text-white py-2.5 rounded-lg transition-colors text-sm font-semibold shadow-md shadow-orange-600/30"
            >
              Start 30-Day Free Trial
            </Link>
          </div>
        </div>

        {/* Footer note */}
        <p className="text-center text-xs text-slate-500 mt-8">
          No commitments on monthly plans. Annual plans billed upfront. Cancel anytime via the customer portal.
        </p>

      </div>
    </section>
  );
}
