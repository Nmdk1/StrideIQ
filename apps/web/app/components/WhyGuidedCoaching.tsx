"use client";

import React from 'react';

export default function WhyGuidedCoaching() {
  return (
    <section className="py-20 bg-gray-800">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Why Guided Self-Coaching?
          </h2>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            Complete health and fitness management—comprehensive monitoring, correlation analysis, and outcomes-driven guidance. 
            Elite-level insights, accessible to everyone—whether you&apos;re in a major city or a small town.
          </p>
        </div>

        {/* Target Audiences */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          {/* Masters+ Runners */}
          <div className="bg-gray-900 rounded-lg p-8 border border-gray-700">
            <h3 className="text-2xl font-bold mb-4 text-orange-400">For Masters+ Runners</h3>
            <p className="text-gray-300 mb-4">
              Tired of being treated as &quot;fragile&quot; because of your age? We don&apos;t see decline—we see potential.
            </p>
            <ul className="space-y-2 text-gray-400">
              <li>✓ Held to the same high standards as athletes of all ages</li>
              <li>✓ Age-graded analysis shows your true performance</li>
              <li>✓ No assumptions about &quot;slowing down&quot;</li>
              <li>✓ Training that adapts to YOUR response curves, not averages</li>
            </ul>
          </div>

          {/* Rural/Small Town Runners */}
          <div className="bg-gray-900 rounded-lg p-8 border border-gray-700">
            <h3 className="text-2xl font-bold mb-4 text-orange-400">For Runners Everywhere</h3>
            <p className="text-gray-300 mb-4">
              Can&apos;t access coaches or running clubs? Elite coaching is now available wherever you are.
            </p>
            <ul className="space-y-2 text-gray-400">
              <li>✓ No geographic limitations</li>
              <li>✓ No need for local running groups</li>
              <li>✓ Same elite-level coaching whether you&apos;re in NYC or rural Montana</li>
              <li>✓ 24/7 availability—no scheduling conflicts</li>
            </ul>
          </div>
        </div>

        {/* Advantages Over Human Coaches */}
        <div className="bg-gradient-to-r from-orange-900/20 to-gray-900 rounded-lg p-8 border border-orange-500/30 mb-12">
          <h3 className="text-2xl font-bold mb-6 text-center">How Guided Self-Coaching Compares</h3>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-semibold text-gray-300 mb-3">Knowledge Base</h4>
              <p className="text-gray-400 text-sm mb-4">
                <strong className="text-orange-400">Guided Self-Coaching:</strong> Synthesizes decades of proven training principles from world-class coaches and exercise science—distilled into personalized guidance.
              </p>
              <p className="text-gray-500 text-sm">
                <strong>Human Coach:</strong> One person&apos;s experience, training, and biases.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-gray-300 mb-3">Availability</h4>
              <p className="text-gray-400 text-sm mb-4">
                <strong className="text-orange-400">Guided Self-Coaching:</strong> 24/7 analysis and optimization. Never sleeps, never forgets, never has an off day.
              </p>
              <p className="text-gray-500 text-sm">
                <strong>Human Coach:</strong> Scheduled calls, email delays, limited hours.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-gray-300 mb-3">Personalization</h4>
              <p className="text-gray-400 text-sm mb-4">
                <strong className="text-orange-400">Guided Self-Coaching:</strong> Learns specifically from YOUR data. Builds personal response curves—not general principles.
              </p>
              <p className="text-gray-500 text-sm">
                <strong>Human Coach:</strong> Applies general principles, limited personal data history.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-gray-300 mb-3">Cost & Accessibility</h4>
              <p className="text-gray-400 text-sm mb-4">
                <strong className="text-orange-400">Guided Self-Coaching:</strong> $24/month. Available everywhere, no geographic limitations.
              </p>
              <p className="text-gray-500 text-sm">
                <strong>Human Coach:</strong> $50-$300/month. Limited by location and availability.
              </p>
            </div>
          </div>
        </div>

        {/* Key Differentiators */}
        <div className="grid md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="w-16 h-16 bg-orange-600 rounded-full flex items-center justify-center text-2xl mb-4 mx-auto">
              📚
            </div>
            <h4 className="text-xl font-bold mb-2">Encyclopedic Knowledge</h4>
            <p className="text-gray-400">
              The knowledge of decades of elite coaching, distilled and personalized—not just one coach&apos;s experience.
            </p>
          </div>
          <div className="text-center">
            <div className="w-16 h-16 bg-orange-600 rounded-full flex items-center justify-center text-2xl mb-4 mx-auto">
              🔄
            </div>
            <h4 className="text-xl font-bold mb-2">Never Stops Learning</h4>
            <p className="text-gray-400">
              Analyzes every run, optimizes continuously. Your coach is always working, even when you&apos;re sleeping.
            </p>
          </div>
          <div className="text-center">
            <div className="w-16 h-16 bg-orange-600 rounded-full flex items-center justify-center text-2xl mb-4 mx-auto">
              🎯
            </div>
            <h4 className="text-xl font-bold mb-2">Optimized For You</h4>
            <p className="text-gray-400">
              Learns from YOUR data specifically. Builds personal response curves—what works for YOU, not averages.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

