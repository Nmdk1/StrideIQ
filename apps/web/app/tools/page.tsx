'use client';

/**
 * Tools Page
 * 
 * Provides access to all running calculators for both authenticated and
 * unauthenticated users. Authenticated users see this within the app context.
 */

import React from 'react';
import VDOTCalculator from '@/app/components/tools/VDOTCalculator';
import WMACalculator from '@/app/components/tools/WMACalculator';
import HeatAdjustedPace from '@/app/components/tools/HeatAdjustedPace';
import { useAuth } from '@/lib/context/AuthContext';

export default function ToolsPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Running Calculators
          </h1>
          <p className="text-lg text-gray-300 max-w-2xl mx-auto">
            Free, research-backed tools to optimize your training. 
            Calculate training paces, age-grade your performances, and adjust for heat.
          </p>
          {!isAuthenticated && (
            <div className="mt-4 inline-block bg-orange-500/10 border border-orange-500/30 rounded-full px-4 py-1">
              <span className="text-orange-400 text-sm font-semibold">
                100% FREE • NO SIGNUP REQUIRED
              </span>
            </div>
          )}
        </div>

        {/* Tools Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {/* Training Pace Calculator */}
          <div className="bg-gray-800 rounded-xl p-6 shadow-xl border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-orange-500/20 rounded-lg">
                <svg className="w-6 h-6 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-white">Training Pace Calculator</h2>
            </div>
            <p className="text-gray-400 text-sm mb-6">
              Enter a race time to get personalized training paces for Easy, Marathon, 
              Threshold, Interval, and Repetition workouts.
            </p>
            <VDOTCalculator />
          </div>

          {/* WMA Age-Grading Calculator */}
          <div className="bg-gray-800 rounded-xl p-6 shadow-xl border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-orange-500/20 rounded-lg">
                <svg className="w-6 h-6 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-white">Age-Grading Calculator</h2>
            </div>
            <p className="text-gray-400 text-sm mb-6">
              Compare performances across ages using World Masters Athletics standards.
              See your age-graded percentage and equivalent open-age time.
            </p>
            <WMACalculator />
          </div>

          {/* Heat-Adjusted Pace Calculator */}
          <div className="bg-gray-800 rounded-xl p-6 shadow-xl border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-orange-500/20 rounded-lg">
                <svg className="w-6 h-6 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-white">Heat-Adjusted Pace</h2>
            </div>
            <p className="text-gray-400 text-sm mb-6">
              Adjust your training paces for temperature and humidity.
              Maintain true physiological effort in hot conditions.
            </p>
            <HeatAdjustedPace />
          </div>
        </div>

        {/* Pro Tip for authenticated users */}
        {isAuthenticated && (
          <div className="mt-12 p-6 bg-gradient-to-r from-orange-500/10 to-pink-500/10 border border-orange-500/30 rounded-xl">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-orange-500/20 rounded-lg">
                <svg className="w-6 h-6 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1z" />
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z" clipRule="evenodd" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Pro Tip</h3>
                <p className="text-gray-300">
                  Your training plan already includes personalized paces based on your race history. 
                  Use these calculators to check paces for aspirational goals or experiment with 
                  different race scenarios.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
