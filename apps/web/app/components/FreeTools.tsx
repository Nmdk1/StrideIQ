"use client";

import React from 'react';
import VDOTCalculator from './tools/VDOTCalculator';
import WMACalculator from './tools/WMACalculator';
import HeatAdjustedPace from './tools/HeatAdjustedPace';

export default function FreeTools() {
  return (
    <section id="tools" className="py-20 bg-slate-800 scroll-mt-16">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-12">
          <div className="inline-block bg-orange-500/10 border border-orange-500/30 rounded-full px-4 py-1 mb-4">
            <span className="text-orange-400 text-sm font-semibold">TRAINING CALCULATORS</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Training calculators you’ll actually use
          </h2>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto mb-6">
            Training paces, age-grading, and heat adjustments—built with research-backed equations (not lookup tables).
          </p>
          <div className="flex flex-wrap justify-center gap-6 text-sm text-slate-400">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Research-backed formulas</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Instant results</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Mobile-friendly</span>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {/* Training Pace Calculator - Primary */}
          <div className="bg-slate-900 rounded-lg p-8 shadow-xl border border-slate-700/50">
            <h3 className="text-2xl font-bold mb-4 text-orange-500">Training Pace Calculator</h3>
            <p className="text-slate-400 mb-6">
              Input your recent race time and distance. Get your complete training pace table (E/M/T/I/R) in min/mile and min/km.
            </p>
            <VDOTCalculator />
          </div>

          {/* WMA Age-Grading Calculator - Mission-critical */}
          <div className="bg-slate-900 rounded-lg p-8 shadow-xl border border-slate-700/50">
            <h3 className="text-2xl font-bold mb-4 text-orange-500">WMA Age-Grading Calculator</h3>
            <p className="text-slate-400 mb-6">
              The same standard for every athlete — no excuses, no decline. See how you measure against world-class performance at any age.
            </p>
            <WMACalculator />
          </div>

          {/* Heat-Adjusted Training Pace Calculator */}
          <div className="bg-slate-900 rounded-lg p-8 shadow-xl border border-slate-700/50">
            <h3 className="text-2xl font-bold mb-4 text-orange-500">Heat-Adjusted Pace Calculator</h3>
            <p className="text-slate-400 mb-6">
              Adjust your training paces for heat and humidity. Maintain true physiological effort in hot conditions. Essential for summer training and warm-weather racing.
            </p>
            <HeatAdjustedPace />
          </div>
        </div>
      </div>
    </section>
  );
}

