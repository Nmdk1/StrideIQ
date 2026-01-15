"use client";

import React from 'react';

export default function HowItWorks() {
  return (
    <section className="py-20 bg-[#0a0a0f]">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            How It Works
          </h2>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto">
            No templates. No scores. Adaptation based on your efficiency trends.
          </p>
          <p className="text-lg text-slate-400 max-w-3xl mx-auto mt-4">
            You coach yourself — with intelligent guidance from decades of proven principles and your own data.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-12">
          {/* Step 1 */}
          <div className="text-center">
            <div className="w-20 h-20 bg-orange-600 rounded-full flex items-center justify-center text-3xl font-bold mb-6 mx-auto">
              1
            </div>
            <h3 className="text-2xl font-bold mb-4">Connect Strava</h3>
            <p className="text-slate-400 text-lg">
              Securely sync your activity data from Strava. We pull your runs, splits, heart rate, and power metrics automatically.
            </p>
          </div>

          {/* Step 2 */}
          <div className="text-center">
            <div className="w-20 h-20 bg-orange-600 rounded-full flex items-center justify-center text-3xl font-bold mb-6 mx-auto">
              2
            </div>
            <h3 className="text-2xl font-bold mb-4">Complete the interview</h3>
            <p className="text-slate-400 text-lg">
              Tell us about your goals, training history, and what you&apos;re trying to achieve. We listen, we learn.
            </p>
          </div>

          {/* Step 3 */}
          <div className="text-center">
            <div className="w-20 h-20 bg-orange-600 rounded-full flex items-center justify-center text-3xl font-bold mb-6 mx-auto">
              3
            </div>
            <h3 className="text-2xl font-bold mb-4">Receive training that evolves</h3>
            <p className="text-slate-400 text-lg">
              Your plan adapts as you improve. We track efficiency trends, not arbitrary scores. Real adaptation based on real data.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

