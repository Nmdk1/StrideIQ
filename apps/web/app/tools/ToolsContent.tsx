'use client';

/**
 * Tools Page
 *
 * Enhanced with shadcn/ui + Lucide while preserving existing good style.
 * Provides access to all running calculators.
 * Each calculator also has a dedicated SEO subpage linked below.
 */

import React from 'react';
import Link from 'next/link';
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator';
import WMACalculator from '@/app/components/tools/WMACalculator';
import HeatAdjustedPace from '@/app/components/tools/HeatAdjustedPace';
// CriticalSpeedPredictor hidden - redundant with Training Pace Calculator, low perceived value
// import { CriticalSpeedPredictor } from '@/components/tools/CriticalSpeedPredictor';
import { useAuth } from '@/lib/context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Zap, BarChart3, Sun, Lightbulb } from 'lucide-react';

export default function ToolsPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Running Calculators
          </h1>
          <p className="text-lg text-slate-300 max-w-2xl mx-auto">
            Free, research-backed tools to optimize your training. 
            Calculate training paces, age-grade your performances, and adjust for heat.
          </p>
          {!isAuthenticated && (
            <Badge className="mt-4 bg-orange-500/10 text-orange-400 border border-orange-500/30 px-4 py-1.5">
              100% FREE • NO SIGNUP REQUIRED
            </Badge>
          )}
        </div>

        {/* Tools Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {/* Training Pace Calculator */}
          <Card className="bg-slate-800 border-slate-700 shadow-xl hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                    <Zap className="w-6 h-6 text-orange-500" />
                  </div>
                  <CardTitle className="text-xl text-white">Training Pace Calculator</CardTitle>
                </div>
                <Link href="/tools/training-pace-calculator" className="text-xs text-orange-400 hover:text-orange-300 transition-colors shrink-0">
                  Full page →
                </Link>
              </div>
              <CardDescription className="text-slate-400">
                Enter a race time to get personalized training paces for Easy, Marathon,
                Threshold, Interval, and Repetition workouts.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TrainingPaceCalculator />
            </CardContent>
          </Card>

          {/* WMA Age-Grading Calculator */}
          <Card className="bg-slate-800 border-slate-700 shadow-xl hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                    <BarChart3 className="w-6 h-6 text-orange-500" />
                  </div>
                  <CardTitle className="text-xl text-white">Age-Grading Calculator</CardTitle>
                </div>
                <Link href="/tools/age-grading-calculator" className="text-xs text-orange-400 hover:text-orange-300 transition-colors shrink-0">
                  Full page →
                </Link>
              </div>
              <CardDescription className="text-slate-400">
                Compare performances across ages using World Masters Athletics standards.
                See your age-graded percentage and equivalent open-age time.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <WMACalculator />
            </CardContent>
          </Card>

          {/* Heat-Adjusted Pace Calculator */}
          <Card className="bg-slate-800 border-slate-700 shadow-xl hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                    <Sun className="w-6 h-6 text-orange-500" />
                  </div>
                  <CardTitle className="text-xl text-white">Heat-Adjusted Pace</CardTitle>
                </div>
                <Link href="/tools/heat-adjusted-pace" className="text-xs text-orange-400 hover:text-orange-300 transition-colors shrink-0">
                  Full page →
                </Link>
              </div>
              <CardDescription className="text-slate-400">
                Adjust your training paces for temperature and humidity.
                Maintain true physiological effort in hot conditions.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <HeatAdjustedPace />
            </CardContent>
          </Card>

          {/* Race Equivalency */}
          <Card className="bg-slate-800 border-slate-700 shadow-xl hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                    <BarChart3 className="w-6 h-6 text-orange-500" />
                  </div>
                  <CardTitle className="text-xl text-white">Race Equivalency</CardTitle>
                </div>
                <Link href="/tools/race-equivalency" className="text-xs text-orange-400 hover:text-orange-300 transition-colors shrink-0">
                  View tables →
                </Link>
              </div>
              <CardDescription className="text-slate-400">
                Predict your race potential at any distance from an existing result.
                Based on the Daniels/Gilbert oxygen cost equation.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Link href="/tools/race-equivalency/5k-to-marathon" className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors">5K → Marathon</Link>
                <Link href="/tools/race-equivalency/10k-to-half-marathon" className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors">10K → Half</Link>
                <Link href="/tools/race-equivalency/half-marathon-to-marathon" className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors">Half → Marathon</Link>
              </div>
            </CardContent>
          </Card>

          {/* Boston Qualifying */}
          <Card className="bg-slate-800 border-slate-700 shadow-xl hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                    <Zap className="w-6 h-6 text-orange-500" />
                  </div>
                  <CardTitle className="text-xl text-white">Boston Qualifying</CardTitle>
                </div>
                <Link href="/tools/boston-qualifying" className="text-xs text-orange-400 hover:text-orange-300 transition-colors shrink-0">
                  All age groups →
                </Link>
              </div>
              <CardDescription className="text-slate-400">
                2026 BAA qualifying standards with training paces for every age group.
                See what fitness level your BQ standard requires.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Link href="/tools/boston-qualifying/boston-qualifying-time-men-18-34" className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors">Men 18–34</Link>
                <Link href="/tools/boston-qualifying/boston-qualifying-time-women-18-34" className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors">Women 18–34</Link>
                <Link href="/tools/boston-qualifying/boston-qualifying-time-men-50-54" className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors">Men 50–54</Link>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Pro Tip for authenticated users */}
        {isAuthenticated && (
          <Card className="mt-12 bg-gradient-to-r from-orange-500/10 to-pink-500/10 border-orange-500/30">
            <CardContent className="pt-6">
              <div className="flex items-start gap-4">
                <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                  <Lightbulb className="w-6 h-6 text-orange-500" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-2">Pro Tip</h3>
                  <p className="text-slate-300">
                    Your training plan already includes personalized paces based on your race history. 
                    Use these calculators to check paces for aspirational goals or experiment with 
                    different race scenarios.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
