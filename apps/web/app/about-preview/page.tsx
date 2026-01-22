"use client";

import Link from "next/link";
import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ShieldCheck, BrainCircuit, Target, Activity } from "lucide-react";

export default function AboutPreviewPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
              About v1 preview
            </Badge>
            <Badge className="bg-slate-800/50 text-slate-300 border-slate-700/50">N=1</Badge>
            <Badge className="bg-slate-800/50 text-slate-300 border-slate-700/50">Evidence</Badge>
          </div>

          <h1 className="text-4xl md:text-5xl font-black tracking-tight">About StrideIQ</h1>
          <p className="text-lg text-slate-300 leading-relaxed">
            StrideIQ is running intelligence built around one idea: the only training data that truly predicts your outcome is yours.
            Not averages. Not templates. Not motivation.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Link
              href="/landing-preview"
              className="inline-flex items-center justify-center rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-100 font-semibold px-5 py-3 border border-slate-700/60 transition-colors"
            >
              Back to landing preview
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center justify-center rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold px-5 py-3 shadow-lg shadow-orange-500/20 transition-colors"
            >
              Start free trial
            </Link>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <Card className="bg-slate-800/40 border-slate-700/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                  <BrainCircuit className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <div className="text-lg font-semibold">N=1 intelligence</div>
                  <p className="mt-2 text-slate-300">
                    We learn from your data. Your response curves, your injury history, your consistency, your tolerance for volume and intensity.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-800/40 border-slate-700/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                  <ShieldCheck className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <div className="text-lg font-semibold">Evidence contract</div>
                  <p className="mt-2 text-slate-300">
                    When StrideIQ uses athlete-specific numbers, it cites the underlying evidence (dates + run labels + key values). You can audit every claim.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-800/40 border-slate-700/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                  <Target className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <div className="text-lg font-semibold">Plans you can understand</div>
                  <p className="mt-2 text-slate-300">
                    Training paces are computed from real equations and flow into your workouts automatically. No manual calculator juggling.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-800/40 border-slate-700/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                  <Activity className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <div className="text-lg font-semibold">Beginner → elite</div>
                  <p className="mt-2 text-slate-300">
                    We meet you where you are. The system adapts to your baseline and makes conservative claims when evidence is thin.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-3">
          <h2 className="text-2xl font-bold">What happens after you sign up?</h2>
          <ol className="list-decimal list-inside space-y-2 text-slate-300">
            <li>Create your account and start your trial.</li>
            <li>Connect Strava (ingestion begins immediately; you’ll see progress).</li>
            <li>Get your first baseline: training paces, load context, and “what to do next” suggestions — with evidence.</li>
          </ol>
          <p className="text-sm text-slate-400">
            Preview note: the onboarding sequence and trial enforcement will be validated before the public landing replaces the current page.
          </p>
        </div>
      </div>
    </div>
  );
}

