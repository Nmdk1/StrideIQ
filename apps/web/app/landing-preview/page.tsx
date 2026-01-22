/* eslint-disable react/no-unescaped-entities */
"use client";

import Link from "next/link";
import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Zap, ShieldCheck, Sparkles } from "lucide-react";
import VDOTCalculator from "@/app/components/tools/VDOTCalculator";
import WMACalculator from "@/app/components/tools/WMACalculator";
import HeatAdjustedPace from "@/app/components/tools/HeatAdjustedPace";

export default function LandingPreviewPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Header (match Home page shell) */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
              <Sparkles className="w-6 h-6 text-orange-500" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold">Landing preview</h1>
                <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-xs">
                  Preview
                </Badge>
              </div>
              <p className="text-sm text-slate-400">
                Manifesto voice + free tools + evidence-backed coaching.
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2">
            <Badge className="bg-slate-800/50 text-slate-300 border-slate-700/50">N=1</Badge>
            <Badge className="bg-slate-800/50 text-slate-300 border-slate-700/50">Evidence</Badge>
            <Link
              href="/about-preview"
              className="ml-2 text-sm text-slate-300 hover:text-orange-400 transition-colors"
            >
              Read the philosophy →
            </Link>
          </div>
        </div>

        {/* HERO (single consistent surface) */}
        <Card className="bg-slate-800/50 border-slate-700/50 overflow-hidden">
          <CardContent className="p-0">
            <div className="relative p-6 md:p-8">
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-orange-500/10 to-pink-500/10" />
              <div className="relative grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
                <div className="flex flex-col justify-between">
                  <div>
                    <h2 className="text-5xl md:text-6xl font-black tracking-tight leading-[1.05]">
                      Deep Intelligence.
                      <span className="block text-orange-400">Zero Fluff.</span>
                    </h2>

                    <p className="mt-5 text-lg md:text-xl text-slate-300 leading-relaxed">
                      Generic motivation won’t make you faster. StrideIQ learns from your data to explain what to do next — and why.
                    </p>
                    <p className="mt-3 text-slate-400">
                      No templates. No averages. Just your response curves.
                    </p>

                    <div className="mt-7 flex flex-col sm:flex-row gap-3">
                      <Link
                        href="/register"
                        className="inline-flex items-center justify-center gap-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold px-6 py-3 shadow-lg shadow-orange-500/20 transition-colors"
                      >
                        Start 14-day free trial
                      </Link>
                      <a
                        href="#tools"
                        className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-100 font-semibold px-6 py-3 border border-slate-700/60 transition-colors"
                      >
                        Use free calculators
                      </a>
                    </div>
                  </div>

                  <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm text-slate-300">
                    <div className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/30 px-3 py-2">
                      <ShieldCheck className="w-4 h-4 text-orange-400" />
                      <span>Evidence for athlete-specific numbers</span>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/30 px-3 py-2">
                      <Sparkles className="w-4 h-4 text-orange-400" />
                      <span>Meet you where you are</span>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/30 px-3 py-2">
                      <Zap className="w-4 h-4 text-orange-400" />
                      <span>Real equations (not lookup tables)</span>
                    </div>
                  </div>
                </div>

                {/* Micro demo (nested surface, no “double border”) */}
                <Card className="bg-slate-900/30 border-slate-700/60 h-full">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle className="text-sm text-slate-300">Evidence micro demo</CardTitle>
                      <span className="text-xs text-slate-500">Example (illustrative)</span>
                    </div>
                    <CardDescription className="text-slate-400">
                      Readable by default; auditable when expanded.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-[92%] rounded-xl bg-orange-600 text-white px-4 py-3">
                        Any suggestions for my run today?
                      </div>
                    </div>

                    <div className="flex justify-start">
                      <div className="max-w-[92%] rounded-xl bg-slate-900/40 border border-slate-700/60 px-4 py-3">
                        <div className="text-slate-200 font-semibold">Here’s what I’d do today.</div>
                        <div className="mt-2 text-slate-300">
                          Keep it easy, and choose the distance based on how stable you feel coming off the last 2 weeks.
                        </div>
                        <ul className="mt-3 text-slate-300 list-disc list-inside">
                          <li>
                            <strong>Conservative:</strong> 3–4 mi easy
                          </li>
                          <li>
                            <strong>If you feel stable:</strong> 5–6 mi easy
                          </li>
                          <li>
                            <strong>Optional:</strong> 4 × 20s relaxed strides (only if pain-free)
                          </li>
                        </ul>

                        <details className="mt-4 rounded-lg border border-slate-700/60 bg-slate-950/40 px-3 py-2">
                          <summary className="cursor-pointer text-xs font-semibold text-slate-300">
                            Evidence (expand)
                          </summary>
                          <div className="mt-2 text-sm text-slate-300 space-y-1">
                            <div>- 2026-01-20: Progression Run 6.0 mi @ 8:05/mi</div>
                            <div>- 2026-01-18: Long Run 12.0 mi @ 9:19/mi</div>
                            <div>- 2026-01-22: Training load — ATL 31, CTL 22, TSB -10</div>
                          </div>
                        </details>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* TOOLS (consistent card section; no full-width band) */}
        <Card id="tools" className="bg-slate-800/50 border-slate-700/50 scroll-mt-16">
          <CardHeader className="pb-3">
            <div className="inline-flex items-center gap-2 rounded-full bg-orange-500/10 border border-orange-500/30 px-4 py-1 w-fit">
              <span className="text-orange-400 text-sm font-semibold">100% FREE • NO SIGNUP REQUIRED</span>
            </div>
            <CardTitle className="text-2xl md:text-3xl font-bold">
              All your essential tools. One place. Free.
            </CardTitle>
            <CardDescription className="text-slate-300">
              Real equations. No lookup tables. And these paces flow directly into your plans.
            </CardDescription>
          </CardHeader>

          <CardContent className="pt-0">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card className="bg-slate-900/30 border-slate-700/60">
                <CardContent className="p-6">
                  <h3 className="text-xl font-bold text-orange-400 mb-2">Training Pace Calculator</h3>
                  <p className="text-slate-400 mb-5">
                    Enter a race result. Get E/M/T/I/R paces in min/mi and min/km.
                  </p>
                  <VDOTCalculator />
                </CardContent>
              </Card>

              <Card className="bg-slate-900/30 border-slate-700/60">
                <CardContent className="p-6">
                  <h3 className="text-xl font-bold text-orange-400 mb-2">WMA Age-Grading Calculator</h3>
                  <p className="text-slate-400 mb-5">
                    World-standard comparison across ages — no decline narrative.
                  </p>
                  <WMACalculator />
                </CardContent>
              </Card>

              <Card className="bg-slate-900/30 border-slate-700/60">
                <CardContent className="p-6">
                  <h3 className="text-xl font-bold text-orange-400 mb-2">Heat-Adjusted Pace Calculator</h3>
                  <p className="text-slate-400 mb-5">Keep effort honest in hot conditions.</p>
                  <HeatAdjustedPace />
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        {/* COACH (upsell) */}
        <Card className="bg-slate-800/50 border-slate-700/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl md:text-3xl font-bold">
              The only AI coach that shows its work.
            </CardTitle>
            <CardDescription className="text-slate-300">
              Calculators give you numbers. StrideIQ gives you decisions — backed by evidence from your training data.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7">
              <div className="grid sm:grid-cols-2 gap-4 text-slate-300">
                <div className="rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
                  <div className="font-semibold">Hidden patterns</div>
                  <div className="mt-1 text-sm text-slate-400">Lagged effects, interaction effects, regime shifts.</div>
                </div>
                <div className="rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
                  <div className="font-semibold">Prescriptive options</div>
                  <div className="mt-1 text-sm text-slate-400">Multiple training choices with tradeoffs.</div>
                </div>
                <div className="rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
                  <div className="font-semibold">Auditable</div>
                  <div className="mt-1 text-sm text-slate-400">Readable by default; evidence when expanded.</div>
                </div>
                <div className="rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
                  <div className="font-semibold">Meets you where you are</div>
                  <div className="mt-1 text-sm text-slate-400">Beginner to elite — N=1.</div>
                </div>
              </div>

              <div className="mt-6 flex flex-col sm:flex-row gap-3">
                <Link
                  href="/coach"
                  className="inline-flex items-center justify-center rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold px-6 py-3 shadow-lg shadow-orange-500/20 transition-colors"
                >
                  Try Coach
                </Link>
                <Link
                  href="/about-preview"
                  className="inline-flex items-center justify-center rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-100 font-semibold px-6 py-3 border border-slate-700/60 transition-colors"
                >
                  Learn more
                </Link>
              </div>
            </div>

            <div className="lg:col-span-5">
              <Card className="bg-slate-900/30 border-slate-700/60">
                <CardContent className="p-6">
                  <div className="text-sm text-slate-400">What you get in 14 days</div>
                  <div className="mt-2 text-xl font-bold text-slate-100">A baseline you can trust</div>
                  <ul className="mt-4 space-y-2 text-slate-300">
                    <li>✓ Data ingestion + progress visibility</li>
                    <li>✓ Training paces computed from real equations</li>
                    <li>✓ First evidence-backed suggestions</li>
                  </ul>
                  <div className="mt-6">
                    <Link
                      href="/register"
                      className="inline-flex w-full items-center justify-center rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold px-4 py-3 transition-colors"
                    >
                      Start free trial
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        {/* PRICING */}
        <Card id="pricing" className="bg-slate-800/50 border-slate-700/50 scroll-mt-16">
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl md:text-3xl font-bold">Pricing</CardTitle>
            <CardDescription className="text-slate-300">
              Start free. Upgrade when you want evidence-backed coaching and planning.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="bg-slate-900/30 border-slate-700/60">
                <CardContent className="p-6">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-xl font-bold">Free</h3>
                    <div className="text-2xl font-bold">$0</div>
                  </div>
                  <ul className="mt-4 space-y-2 text-slate-300">
                    <li>✓ Training Pace Calculator</li>
                    <li>✓ WMA Age-Grading</li>
                    <li>✓ Heat-Adjusted Pace</li>
                    <li>✓ Basic log</li>
                  </ul>
                  <div className="mt-6">
                    <Link
                      href="/register"
                      className="inline-flex w-full items-center justify-center rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold px-4 py-3 transition-colors"
                    >
                      Create account
                    </Link>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-orange-900/25 to-slate-900/30 border-orange-500/30">
                <CardContent className="p-6">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-xl font-bold">Elite</h3>
                    <div className="text-2xl font-bold text-slate-200">Pricing TBA</div>
                  </div>
                  <p className="mt-2 text-sm text-orange-200">14-day free trial for new athletes</p>
                  <ul className="mt-4 space-y-2 text-slate-200">
                    <li>✓ Everything in Free</li>
                    <li>✓ AI Coach with evidence</li>
                    <li>✓ Training plans (pace-populated)</li>
                    <li>✓ Efficiency analysis + diagnostics</li>
                  </ul>
                  <div className="mt-6">
                    <Link
                      href="/register"
                      className="inline-flex w-full items-center justify-center rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold px-4 py-3 shadow-lg shadow-orange-500/20 transition-colors"
                    >
                      Start free trial
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="mt-6 text-sm text-slate-400">
              Preview note: pricing copy is intentionally conservative until subscription/trial enforcement is finalized.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

