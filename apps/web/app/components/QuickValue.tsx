"use client";

import React from 'react';

export default function QuickValue() {
  return (
    <section className="py-12 bg-gradient-to-r from-slate-800 to-slate-900 border-y border-slate-700/50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid md:grid-cols-3 gap-8 text-center">
          <div className="flex flex-col items-center">
            <div className="text-4xl font-bold text-orange-500 mb-2">3</div>
            <div className="text-lg font-semibold mb-1">Training Calculators</div>
            <div className="text-sm text-slate-400">Paces, age-grading, heat adjustments</div>
          </div>
          <div className="flex flex-col items-center">
            <div className="text-4xl font-bold text-orange-500 mb-2">360°</div>
            <div className="text-lg font-semibold mb-1">Complete View</div>
            <div className="text-sm text-slate-400">Nutrition, sleep, work, activities—all connected</div>
          </div>
          <div className="flex flex-col items-center">
            <div className="text-4xl font-bold text-orange-500 mb-2">24/7</div>
            <div className="text-lg font-semibold mb-1">Correlation Analysis</div>
            <div className="text-sm text-slate-400">Identifies trends and correlates inputs to outputs</div>
          </div>
        </div>
      </div>
    </section>
  );
}

