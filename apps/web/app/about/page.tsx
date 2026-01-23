"use client";

import Link from "next/link";
import Image from "next/image";
import React from "react";
import Footer from "../components/Footer";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { BrainCircuit, ShieldCheck, Target, Activity } from "lucide-react";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-5xl mx-auto px-6 py-16 space-y-12">
        {/* Hero */}
        <div className="text-center space-y-5">
          <div className="flex items-center justify-center gap-2">
            <Badge className="bg-slate-800/50 text-slate-300 border-slate-700/50">N=1</Badge>
            <Badge className="bg-slate-800/50 text-slate-300 border-slate-700/50">Evidence</Badge>
          </div>

          <h1 className="text-4xl md:text-6xl font-black tracking-tight">
            Built by a runner who got it wrong — so you don’t have to.
          </h1>
          <p className="text-lg md:text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed">
            I’m Michael Shaffer. I founded StrideIQ because generic plans don’t know you — and when training doesn’t learn the athlete,
            it breaks people.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link
              href="/tools"
              className="inline-flex items-center justify-center rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-100 font-semibold px-6 py-3 border border-slate-700/60 transition-colors"
            >
              Use our training calculators
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center justify-center rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold px-6 py-3 shadow-lg shadow-orange-500/20 transition-colors"
            >
              Start free trial
            </Link>
          </div>
        </div>

        {/* Pillars */}
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
                    We learn from your history — your response curves, your tolerance, your constraints — instead of forcing you to match a template.
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
                    Training paces come from real equations and flow into your workouts automatically — no calculator juggling, no mystery numbers.
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
                    We meet you where you are. The promise is simple: measurable progress, honest constraints, and decisions backed by your data.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Story */}
        <div className="prose prose-invert prose-lg max-w-none space-y-8">
          <h2 className="text-2xl font-bold">Why I built this</h2>

          <Card className="not-prose overflow-hidden bg-slate-800/40 border-slate-700/50">
            <CardContent className="p-0">
              <div className="grid md:grid-cols-[340px,1fr]">
                <div className="relative aspect-[16/10] md:aspect-auto md:min-h-[320px] md:border-r md:border-slate-700/50">
                  <Image
                    src="/about/michael-10k-pb.jpg"
                    alt="Runner finishing a race."
                    fill
                    sizes="(min-width: 768px) 340px, 100vw"
                    className="object-cover object-[center_20%]"
                    priority={false}
                  />
                  <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/80 to-transparent p-4">
                    <div className="text-xs text-slate-200/90">December 13 — 10K PB finish.</div>
                  </div>
                </div>

                <div className="p-6 md:p-8">
                  <p className="m-0 text-slate-200 leading-relaxed">
                    I was injured by a plan that didn’t know me: population averages, rigid progressions, and no regard for real response curves.
                    That experience wasn’t just frustrating — it was the clearest possible signal that “generic” is not the same as “safe.”
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <p className="text-slate-300">
            I’ve built systems from scratch before. I founded US Medical Scientific with no prior background in chemistry, coding, or hospital operations.
            I saw the iPad launch and built self-report testing software that automated workflows and delivered results directly to physicians.
          </p>

          <p className="text-slate-300">
            That work exposed deeper gaps in healthcare, so we kept going: automated lab workflows, built on-campus high-complexity labs,
            and developed custom LIMS software integrated into hospital billing/EHR flows. We scaled to 200+ employees by obsessing over execution,
            and by attracting exceptional people through mission clarity — not credentials theater.
          </p>

          <p className="text-slate-300">
            That experience taught me something fundamental: when you start from nothing, success comes from judgment about the problem, the mission, and the people —
            not from pretending you already know everything.
          </p>

          <h2 className="text-2xl font-bold">What StrideIQ is (and what it isn’t)</h2>
          <p className="text-slate-300">
            Coaches and software often force athletes to adapt to the method. That’s backwards. StrideIQ flips it: <strong>your data calls the shots</strong>.
            We learn the athlete first, then we earn the right to prescribe — and we show our work when we do.
          </p>

          <p className="text-slate-300">
            StrideIQ is in active development. The free tools are live now; the Coach and planning system are being hardened around one non-negotiable principle:
            if the system says something about <em>you</em>, you should be able to verify it.
          </p>
        </div>

        {/* CTA */}
        <div className="text-center space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/tools"
              className="inline-flex items-center justify-center rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-100 font-semibold px-6 py-3 border border-slate-700/60 transition-colors"
            >
              Explore tools
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center justify-center rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold px-6 py-3 shadow-lg shadow-orange-500/20 transition-colors"
            >
              Start free trial
            </Link>
          </div>
          <p className="text-sm text-slate-400">
            Questions? Use the site footer links or the in-app feedback options after you sign up.
          </p>
        </div>
      </div>

      <Footer />
    </div>
  );
}

