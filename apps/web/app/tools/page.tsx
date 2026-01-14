'use client';

/**
 * Tools Page
 * 
 * Enhanced with shadcn/ui + Lucide while preserving existing good style.
 * Provides access to all running calculators.
 */

import React from 'react';
import VDOTCalculator from '@/app/components/tools/VDOTCalculator';
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
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                  <Zap className="w-6 h-6 text-orange-500" />
                </div>
                <CardTitle className="text-xl text-white">Training Pace Calculator</CardTitle>
              </div>
              <CardDescription className="text-slate-400">
                Enter a race time to get personalized training paces for Easy, Marathon, 
                Threshold, Interval, and Repetition workouts.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <VDOTCalculator />
            </CardContent>
          </Card>

          {/* WMA Age-Grading Calculator */}
          <Card className="bg-slate-800 border-slate-700 shadow-xl hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                  <BarChart3 className="w-6 h-6 text-orange-500" />
                </div>
                <CardTitle className="text-xl text-white">Age-Grading Calculator</CardTitle>
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
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2.5 bg-orange-500/20 rounded-xl ring-1 ring-orange-500/30">
                  <Sun className="w-6 h-6 text-orange-500" />
                </div>
                <CardTitle className="text-xl text-white">Heat-Adjusted Pace</CardTitle>
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

          {/* Critical Speed Predictor - HIDDEN
             Reason: Redundant with Training Pace Calculator, less accurate, confusing UX.
             Backend service (critical_speed.py) retained for potential future pivot to insight-only.
             See ADR-017 for details.
          */}
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
