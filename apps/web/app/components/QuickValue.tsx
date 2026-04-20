"use client";

import React from 'react';

export default function QuickValue() {
  return (
    <section className="py-12 bg-gradient-to-r from-slate-800 to-slate-900 border-y border-slate-700/50">
      <div className="max-w-4xl mx-auto px-6 text-center">
        <p className="text-lg md:text-xl text-slate-200 leading-relaxed">
          Sleep, nutrition, runs, splits, heart rate, cadence, weather — all correlated against your race times.{" "}
          <span className="text-orange-400 font-semibold">
            Every claim is yours to audit.
          </span>
        </p>
      </div>
    </section>
  );
}
