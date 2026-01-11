'use client';

/**
 * CreatePlanCTA Component
 * 
 * Call to action shown when athlete has no active training plan.
 * Guides them to create a new plan with clear options.
 */

import React from 'react';
import Link from 'next/link';

export function CreatePlanCTA() {
  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900 border border-gray-700 rounded-xl p-8 text-center">
      {/* Icon */}
      <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-pink-600/20 to-orange-600/20 rounded-full flex items-center justify-center">
        <span className="text-3xl">🎯</span>
      </div>
      
      {/* Heading */}
      <h2 className="text-2xl font-bold text-white mb-2">
        No Active Training Plan
      </h2>
      
      {/* Description */}
      <p className="text-gray-400 mb-6 max-w-md mx-auto">
        Create a training plan to see your workouts here. 
        Choose a goal race and we will build a periodized plan tailored to you.
      </p>
      
      {/* CTA Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <Link 
          href="/plans/create"
          className="px-6 py-3 bg-gradient-to-r from-pink-600 to-orange-600 hover:from-pink-700 hover:to-orange-700 rounded-lg font-semibold text-white transition-all duration-200 transform hover:scale-105"
        >
          Create Your Plan
        </Link>
        
        <Link
          href="/plans/preview"
          className="px-6 py-3 bg-gray-800 border border-gray-600 hover:border-gray-500 rounded-lg font-medium text-gray-300 hover:text-white transition-colors"
        >
          Preview Plans
        </Link>
      </div>
      
      {/* Tiers info */}
      <div className="mt-8 pt-6 border-t border-gray-700/50">
        <div className="flex flex-wrap justify-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span className="text-gray-400">Standard Plans</span>
            <span className="text-emerald-400 font-semibold">Free</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            <span className="text-gray-400">Semi-Custom</span>
            <span className="text-blue-400 font-semibold">$5</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500"></span>
            <span className="text-gray-400">Full Custom</span>
            <span className="text-purple-400 font-semibold">Pro</span>
          </div>
        </div>
      </div>
    </div>
  );
}
