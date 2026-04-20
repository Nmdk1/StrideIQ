import type { Metadata } from 'next'
import React from 'react';
import Footer from '../components/Footer';

export const metadata: Metadata = {
  title: 'Our Mission - Evidence-Based Running Coaching for Every Age',
  description: 'StrideIQ is a record of what your training is telling you. No age-based assumptions. No template plans. Auditable evidence, decided by the athlete.',
  alternates: {
    canonical: 'https://strideiq.run/mission',
  },
  openGraph: {
    url: 'https://strideiq.run/mission',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - AI Running Coach' }],
  },
}

export default function MissionStatement() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <section className="relative py-20 overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-orange-500/10 rounded-full blur-3xl" />

        <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Our Mission
          </h1>

          <blockquote className="text-xl md:text-2xl italic mb-8 text-slate-300 max-w-3xl mx-auto border-l-4 border-orange-500 pl-6 text-left">
            &ldquo;We are commonly bound by our uncommon ability to embrace and overcome discomfort.&rdquo;
            <footer className="mt-4 text-lg not-italic text-orange-400">&mdash; Michael Shaffer, Founder</footer>
          </blockquote>
        </div>
      </section>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="prose prose-invert prose-lg max-w-none space-y-12">

          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">The Core Philosophy</h2>

            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-3 text-slate-300">The Mission</h3>
                <p className="text-slate-300 leading-relaxed">
                  StrideIQ is not a training plan. It is a record of what your training is telling you — built from your data, available the moment you need it, with evidence attached to every claim. Athletes of every age, every background, every starting point are held to the same standard: what does your data actually show?
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3 text-slate-300">The Stance</h3>
                <p className="text-slate-300 leading-relaxed">
                  We do not assume athletes slow down. We do not assume they speed up. We measure. The same diagnostic engine runs against a 25-year-old&apos;s training as a 75-year-old&apos;s, and reports the same kind of finding from the same kind of evidence. Age-grading is the only place age enters the math.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3 text-slate-300">Guided Self-Coaching</h3>
                <p className="text-slate-300 leading-relaxed">
                  The athlete decides. The system records the patterns and shows the evidence. You own the plan, you read the findings, you choose what to do with them. No middleman, no theater, no template narrative — just real adaptation, observed and reported back to you.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">Our Approach</h2>

            <div className="space-y-6">
              <p className="text-slate-300 leading-relaxed">
                A Bayesian discovery engine runs across your data every night, looking for correlations between your inputs (sleep, nutrition, training load, weather) and your outputs (pace, heart rate response, recovery, race results). When the evidence is strong enough, the coach surfaces it. When it is not, the system stays quiet.
              </p>

              <p className="text-slate-300 leading-relaxed">
                Insights are built from your training history alone. Population averages are useful as context but never as prescription. Whatever the literature says about athletes like you is irrelevant compared to what your own data says about you.
              </p>

              <p className="text-slate-300 leading-relaxed p-4 bg-slate-800 rounded-lg">
                <strong>No Age-Based Assumptions:</strong> We make zero preconceptions about adaptation speed, recovery, or performance potential based on age. All insights are discovered from your own data. What averages say about any age group is irrelevant — only what your individual data shows matters.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">What This Means for You</h2>
            <p className="text-slate-300 leading-relaxed mb-4">
              You&apos;ll receive findings that are:
            </p>
            <ul className="list-disc list-inside space-y-2 text-slate-300 ml-4">
              <li>Rooted in your own data, not generic averages</li>
              <li>Cited — every claim points back to the runs, dates, and numbers behind it</li>
              <li>Suppressed when the evidence is not strong enough to defend</li>
              <li>Yours to decide what to do with</li>
            </ul>
            <p className="text-slate-300 leading-relaxed mt-6">
              Real, actionable truth — not motivation, averages, or wishful thinking.
            </p>
          </section>

          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">Fair Comparison</h2>
            <p className="text-slate-300 leading-relaxed">
              We use <strong className="text-orange-400">age-grading</strong> to ensure fair comparison across all age groups. This means your performance is measured against world-standard benchmarks for your age, not just raw times. Whether you&apos;re 25 or 75, you&apos;re held to the same high standards relative to your age group.
            </p>
          </section>

          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">The Coaching Process</h2>
            <p className="text-slate-300 leading-relaxed mb-4">
              The coaching process is a continuous feedback loop:
            </p>
            <ul className="list-disc list-inside space-y-2 text-slate-300 ml-4">
              <li><strong>Observe:</strong> Ingest every run, every check-in, every weather day</li>
              <li><strong>Detect:</strong> Run the discovery engine nightly to find patterns specific to you</li>
              <li><strong>Surface:</strong> Show findings only when the evidence is strong enough to defend</li>
              <li><strong>Decide:</strong> The athlete reads the finding and decides what to do</li>
            </ul>
            <p className="text-slate-300 leading-relaxed mt-6">
              You and the system evolve together. The system is never the decision maker.
            </p>
          </section>

        </div>
      </main>

      <Footer />
    </div>
  );
}
