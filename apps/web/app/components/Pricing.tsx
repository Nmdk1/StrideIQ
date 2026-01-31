"use client";

import React from 'react';
import Link from 'next/link';

export default function Pricing() {
  return (
    <section id="pricing" className="py-20 bg-slate-800 scroll-mt-16">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Transparent Pricing
          </h2>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto">
            Start free. Upgrade to Elite when you&apos;re ready for more.
          </p>
        </div>

        {/* Pricing Grid Container */}
        <div className="w-full">
          {/* Power couple: centered Free vs Elite */}
          <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
          {/* Free Tier */}
          <div className="bg-slate-900 rounded-lg p-6 border border-slate-700/50">
            <h3 className="text-xl font-bold mb-2">Free</h3>
            <div className="text-3xl font-bold mb-4">$0</div>
            <ul className="space-y-2 text-sm text-slate-400 mb-6">
              <li>✓ Training Pace Calculator</li>
              <li>✓ WMA Age-Grading</li>
              <li>✓ Heat-Adjusted Pace</li>
              <li>✓ Basic insights</li>
            </ul>
            <Link href="/register" className="block w-full bg-slate-700 hover:bg-slate-600 text-white py-2 rounded-lg transition-colors text-sm text-center">
              Get Started
            </Link>
          </div>

          {/* Elite Subscription (single paid tier) */}
          <div className="bg-gradient-to-br from-orange-900/40 to-slate-900 rounded-lg p-6 border-2 border-orange-500 relative md:shadow-xl md:shadow-orange-500/20">
            <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-orange-500 text-white px-3 py-1 text-xs font-semibold rounded-full whitespace-nowrap">
              ELITE
            </div>
            <h3 className="text-xl font-bold mb-2 mt-2">Elite</h3>
            <div className="text-3xl font-bold mb-1">
              $149<span className="text-base">/year</span>
            </div>
            <p className="text-sm text-slate-400 mb-3">or $14.99/month</p>
            <p className="text-xs text-orange-300 mb-4">Full product access • Adaptive insights</p>
            <ul className="space-y-2 text-sm text-slate-300 mb-6">
              <li>✓ Everything in Free</li>
              <li>✓ <strong>Adaptive updates</strong></li>
              <li>✓ <strong>Efficiency analysis</strong></li>
              <li>✓ <strong>Performance diagnostics</strong></li>
              <li>✓ Strava integration</li>
              <li>✓ <strong>AI-powered</strong></li>
            </ul>
            <Link href="/register" className="block w-full bg-orange-600 hover:bg-orange-700 text-white py-2 rounded-lg transition-colors font-semibold text-sm shadow-lg shadow-orange-600/30 text-center">
              Start Elite
            </Link>
          </div>
        </div>
        </div>
        </div>

        {/* Detailed Elite Section - Aligned with Pricing Grid */}
        <div className="mt-8 w-full">
          <div className="bg-gradient-to-r from-orange-900/30 to-slate-900 rounded-lg p-6 border border-orange-500/50">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-4">
              <div>
                <h3 className="text-2xl font-bold mb-1">Why Elite?</h3>
                <p className="text-sm text-slate-400">Elite-level guidance, accessible to everyone</p>
              </div>
              <a
                href="#tools"
                className="mt-4 md:mt-0 px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold rounded-lg transition-colors text-sm"
              >
                Try Training Calculators
              </a>
            </div>
            <div className="grid md:grid-cols-2 gap-4 text-sm text-slate-300">
              <div className="space-y-2">
                <p>✓ <strong>Encyclopedic knowledge:</strong> Decades of proven principles</p>
                <p>✓ <strong>Never sleeps:</strong> Continuous optimization</p>
                <p>✓ <strong>Learns from YOU:</strong> Personal response curves</p>
              </div>
              <div className="space-y-2">
                <p>✓ <strong>Always available:</strong> 24/7 analysis</p>
                <p>✓ <strong>Accessible everywhere:</strong> NYC to rural Montana</p>
                <p>✓ <strong>Affordable:</strong> $14.99/month vs. $50-$300 for coaches</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

