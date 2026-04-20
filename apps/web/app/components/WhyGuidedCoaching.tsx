"use client";

import React from 'react';
import Link from 'next/link';

export default function WhyGuidedCoaching() {
  return (
    <section className="py-20 bg-slate-800">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Why StrideIQ exists
          </h2>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto">
            A record of what your training is telling you — built from your data, auditable to the last decimal, available the moment you need it. It does not replace a coach. It gives you and your coach the same view.
          </p>
        </div>

        {/* Four cooperative cards — Memory / Pattern detection / Availability / Evidence */}
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          <div className="bg-slate-900 rounded-lg p-8 border border-slate-700/50">
            <h3 className="text-xl font-bold mb-3 text-orange-400">Memory</h3>
            <p className="text-slate-300 leading-relaxed">
              Remembers every run, every wellness check-in, every weather day. A pattern that takes 200 runs to emerge is a pattern most plans and most coaches will never see.
            </p>
          </div>

          <div className="bg-slate-900 rounded-lg p-8 border border-slate-700/50">
            <h3 className="text-xl font-bold mb-3 text-orange-400">Pattern detection</h3>
            <p className="text-slate-300 leading-relaxed">
              Finds correlations across your sleep, nutrition, training load, and outcomes. A Bayesian engine runs every night and compiles what it learns. The coach reads what the engine compiled.
            </p>
          </div>

          <div className="bg-slate-900 rounded-lg p-8 border border-slate-700/50">
            <h3 className="text-xl font-bold mb-3 text-orange-400">Availability</h3>
            <p className="text-slate-300 leading-relaxed">
              There at 5am when you are deciding whether to run. Not as a substitute for human judgment — as a record of what your data has actually shown.
            </p>
          </div>

          <div className="bg-slate-900 rounded-lg p-8 border border-slate-700/50">
            <h3 className="text-xl font-bold mb-3 text-orange-400">Evidence</h3>
            <p className="text-slate-300 leading-relaxed">
              Every recommendation cites the runs, the dates, the numbers. If the data is not strong enough, the system stays quiet. Suppression over hallucination.
            </p>
          </div>
        </div>

        {/* DEXA case-study callout — single-paragraph proof, links to depth */}
        <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 rounded-lg p-8 border border-orange-500/30">
          <p className="text-lg text-slate-200 leading-relaxed mb-4">
            One athlete uploaded his DEXA scan. The coach reconciled it with his Garmin scale, his lift history, and his upcoming 20-miler — and explained why his bones are 7 lbs heavier than Garmin thinks.
          </p>
          <Link
            href="/case-studies/dexa-and-the-7-pound-gap"
            className="inline-flex items-center gap-2 text-orange-400 hover:text-orange-300 font-semibold transition-colors"
          >
            Read the full finding
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </div>
      </div>
    </section>
  );
}
