"use client";

import React from 'react';
import Footer from '../components/Footer';

export default function MissionStatement() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100">
      {/* Hero Section with Background */}
      <section className="relative py-20 overflow-hidden">
        <div 
          className="absolute inset-0 bg-cover bg-center opacity-20"
          style={{
            backgroundImage: "url('https://images.unsplash.com/photo-1545558014-8692077e9b5c?q=80&w=2070')",
            backgroundPosition: "center",
            backgroundSize: "cover"
          }}
        >
          <div className="absolute inset-0 bg-[#0a0a0f]/80"></div>
        </div>
        
        <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Our Mission
          </h1>
          
          <blockquote className="text-xl md:text-2xl italic mb-8 text-slate-300 max-w-3xl mx-auto border-l-4 border-orange-500 pl-6">
            &ldquo;We are commonly bound by our uncommon ability to embrace and overcome discomfort.&rdquo;
            <footer className="mt-4 text-lg not-italic text-orange-400">&mdash; Michael Shaffer, Founder</footer>
          </blockquote>
        </div>
      </section>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="prose prose-invert prose-lg max-w-none space-y-12">
          
          {/* Core Philosophy */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">The Core Philosophy</h2>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-3 text-slate-300">The Mission</h3>
                <p className="text-slate-300 leading-relaxed">
                  We are not creating cookie-cutter training plans. We are building <strong className="text-orange-400">StrideIQ</strong> — AI-powered running intelligence designed to empower athletes of all ages. Our system applies elite-level analysis to athletes in every age group, rejecting the &quot;decline narrative&quot;. Instead, we embrace and enhance the exceptional abilities of athletes at every stage of their journey.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3 text-slate-300">The Stance</h3>
                <p className="text-slate-300 leading-relaxed">
                  We treat athletes as individuals, rejecting the idea of &quot;slowing down&quot; and instead celebrating extraordinary performances from athletes of all ages. Our system applies elite-level analysis, ensuring athletes of all ages are held to the same high standards. Every athlete receives the same level of insights and feedback.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3 text-slate-300">Guided Self-Coaching</h3>
                <p className="text-slate-300 leading-relaxed">
                  Guided self-coaching empowers you to take control — with the depth and adaptation that rivals elite human coaching. The athlete is the coach, the system is the silent, brilliant assistant. You own your plan, understand your progress, and evolve with the system — no middleman, no hype, just measurable efficiency.
                </p>
              </div>
            </div>
          </section>

          {/* Our Approach */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">Our Approach</h2>
            
            <div className="space-y-6">
              <p className="text-slate-300 leading-relaxed">
                We use advanced diagnostic analysis to understand what drives improvement for each individual athlete. Our system analyzes multiple data sources to identify patterns, trends, and opportunities that are unique to you.
              </p>
              
              <p className="text-slate-300 leading-relaxed">
                Rather than relying on generic templates or one-size-fits-all approaches, we build personalized insights from your own training history. Every recommendation is tailored to your individual response patterns, goals, and current fitness level.
              </p>
              
              <p className="text-slate-300 leading-relaxed p-4 bg-slate-800 rounded-lg">
                <strong>No Age-Based Assumptions:</strong> We make zero preconceptions about adaptation speed, recovery, or performance potential based on age. All insights are discovered from your own data. What averages say about any age group is irrelevant — only what your individual data shows matters.
              </p>
            </div>
          </section>

          {/* What This Means for You */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">What This Means for You</h2>
            <p className="text-slate-300 leading-relaxed mb-4">
              You&apos;ll receive insights that are:
            </p>
            <ul className="list-disc list-inside space-y-2 text-slate-300 ml-4">
              <li>Rooted in your own data, not generic averages</li>
              <li>Personalized to your unique response patterns</li>
              <li>Focused on sustainable, long-term improvement</li>
              <li>Designed to help you understand what actually works for you</li>
            </ul>
            <p className="text-slate-300 leading-relaxed mt-6">
              Real, actionable truth — not motivation, averages, or wishful thinking.
            </p>
          </section>

          {/* Intelligent Coaching */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">Intelligent Coaching</h2>
            <p className="text-slate-300 leading-relaxed">
              The system draws from an extensive knowledge base of proven coaching principles — from classic training philosophies to cutting-edge physiological research. This knowledge is synthesized with your personal data and diagnostic signals to generate truly individualized recommendations. The system learns what works best for you, continuously refining your training. No generic plans — only coaching that evolves with your progress.
            </p>
          </section>

          {/* Taxonomy */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">Taxonomy: The New Masters</h2>
            <p className="text-slate-300 leading-relaxed mb-4">
              Age-based classification for fair comparison and recognition:
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Open</div>
                <div className="text-slate-400 text-sm">&lt;35</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Masters</div>
                <div className="text-slate-400 text-sm">40–49</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Grandmasters</div>
                <div className="text-slate-400 text-sm">50–59</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Senior Grandmasters</div>
                <div className="text-slate-400 text-sm">60–69</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Legend Masters</div>
                <div className="text-slate-400 text-sm">70–79</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Icon Masters</div>
                <div className="text-slate-400 text-sm">80–89</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Centurion Masters</div>
                <div className="text-slate-400 text-sm">90+</div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <div className="font-semibold text-orange-400">Centurion Prime</div>
                <div className="text-slate-400 text-sm">100+</div>
              </div>
            </div>
            <p className="text-slate-300 leading-relaxed mt-6">
              Defined by age + age-graded performance metrics. Age-grading creates a universal standard — no age diminishes recognition.
            </p>
          </section>

          {/* Key Metrics */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">Fair Comparison</h2>
            <p className="text-slate-300 leading-relaxed">
              We use <strong className="text-orange-400">age-grading</strong> to ensure fair comparison across all age groups. This means your performance is measured against world-standard benchmarks for your age, not just raw times. Whether you&apos;re 25 or 75, you&apos;re held to the same high standards relative to your age group.
            </p>
          </section>

          {/* The Coaching Process */}
          <section>
            <h2 className="text-3xl font-bold mb-6 text-orange-400">The Coaching Process</h2>
            <p className="text-slate-300 leading-relaxed mb-4">
              Our coaching adapts in real-time based on your goals, current fitness, and evolving context. We follow a continuous feedback loop:
            </p>
            <ul className="list-disc list-inside space-y-2 text-slate-300 ml-4">
              <li><strong>Observe:</strong> Analyze your training data</li>
              <li><strong>Hypothesize:</strong> Identify what&apos;s working and what&apos;s not</li>
              <li><strong>Intervene:</strong> Recommend specific, actionable changes</li>
              <li><strong>Validate:</strong> Measure results and refine</li>
            </ul>
            <p className="text-slate-300 leading-relaxed mt-6">
              You and the system evolve together, continuously improving.
            </p>
          </section>

        </div>
      </main>

      <Footer />
    </div>
  );
}

