"use client";

import React from 'react';
import Link from "next/link";
import { sendToolTelemetry } from "@/lib/hooks/useToolTelemetry";

export default function Hero() {
  const handleHashClick = (e: React.MouseEvent<HTMLAnchorElement>, hash: string) => {
    e.preventDefault();
    setTimeout(() => {
      const element = document.getElementById(hash);
      if (element) {
        const offset = 80;
        const elementPosition = element.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - offset;
        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });
      }
    }, 10);
  };

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div
          className="absolute inset-0 opacity-5"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
          }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-orange-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-20 text-center">
        <div className="mb-8">
          <h1 className="sr-only">StrideIQ — your body has a voice</h1>
          <p aria-hidden="true" className="text-6xl md:text-8xl font-black tracking-tight">
            <span className="bg-gradient-to-r from-orange-400 via-orange-500 to-orange-600 bg-clip-text text-transparent">
              Stride
            </span>
            <span className="text-white">IQ</span>
          </p>
        </div>

        {/* Manifesto headline — the line the meta description has always carried */}
        <p className="text-3xl md:text-5xl font-bold mb-4 text-white leading-tight max-w-4xl mx-auto">
          Your body has a voice.{" "}
          <span className="text-orange-400">StrideIQ gives it one.</span>
        </p>

        {/* Supporting tagline */}
        <p className="text-xl md:text-2xl font-medium mb-8 text-slate-300">
          Deep Intelligence. Zero Fluff.
        </p>

        {/* Value-prop stack — outcome-named */}
        <p className="text-lg md:text-xl mb-4 max-w-2xl mx-auto leading-relaxed text-slate-200">
          What&apos;s making you faster. What&apos;s holding you back. What no template can see — because it&apos;s specific to you.
        </p>

        {/* Subhead — replaces the orange uppercase "AI Running Coach" pill */}
        <p className="text-base md:text-lg text-slate-400 mb-10 max-w-2xl mx-auto">
          Personal patterns. Real evidence. Coaching that can&apos;t be faked.
        </p>

        {/* Real-user testimonial — Adam S., distillation #1, founder pre-cleared */}
        <figure className="max-w-2xl mx-auto mb-10 bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 text-left">
          <blockquote className="text-slate-200 italic leading-relaxed">
            &ldquo;Ask Coach is getting more detailed and more dialed in every week. You&apos;ve got something pretty awesome here.&rdquo;
          </blockquote>
          <figcaption className="mt-3 text-sm text-orange-400 font-medium">
            — Adam S., StrideIQ user
          </figcaption>
        </figure>

        <div className="flex flex-wrap justify-center gap-6 mb-10 text-sm text-slate-400">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>Free 30-day trial</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>Cancel anytime via Stripe</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>Garmin Connect &amp; Strava</span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-8">
          <a
            href="/register"
            onClick={() => void sendToolTelemetry("signup_cta_click", { cta: "hero_primary" })}
            className="group inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-semibold px-8 py-4 rounded-xl text-lg transition-all duration-300 shadow-lg shadow-orange-500/25 hover:shadow-xl hover:shadow-orange-500/30 hover:-translate-y-0.5"
          >
            Get Started Free
            <svg className="w-5 h-5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </a>
          <a
            href="#tools"
            onClick={(e) => handleHashClick(e, 'tools')}
            className="inline-flex items-center gap-2 bg-white/5 hover:bg-white/10 text-white font-semibold px-8 py-4 rounded-xl text-lg transition-all duration-300 border border-white/20 hover:border-white/40 backdrop-blur-sm"
          >
            Try Our Calculators
          </a>
        </div>

        <p className="text-sm text-slate-500 mb-16 max-w-2xl mx-auto">
          Popular tools:{" "}
          <Link href="/tools/training-pace-calculator" className="text-orange-400/90 hover:text-orange-300 underline-offset-2 hover:underline">
            training paces
          </Link>
          {" · "}
          <Link href="/tools/boston-qualifying" className="text-orange-400/90 hover:text-orange-300 underline-offset-2 hover:underline">
            Boston qualifying times
          </Link>
          {" · "}
          <Link href="/tools/heat-adjusted-pace" className="text-orange-400/90 hover:text-orange-300 underline-offset-2 hover:underline">
            heat-adjusted pace
          </Link>
          {" · "}
          <Link href="/tools/race-equivalency/10k-to-half-marathon" className="text-orange-400/90 hover:text-orange-300 underline-offset-2 hover:underline">
            race equivalency
          </Link>
          {" · "}
          <Link href="/tools/age-grading-calculator" className="text-orange-400/90 hover:text-orange-300 underline-offset-2 hover:underline">
            age grading
          </Link>
        </p>

        <blockquote className="max-w-xl mx-auto">
          <p className="text-slate-400 italic text-lg">
            &ldquo;We are commonly bound by our uncommon ability to embrace and overcome discomfort.&rdquo;
          </p>
          <footer className="mt-3 text-orange-400 font-medium">
            — Michael Shaffer, Founder
          </footer>
        </blockquote>

        <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
          <a
            href="#tools"
            onClick={(e) => handleHashClick(e, 'tools')}
            className="flex flex-col items-center text-slate-500 hover:text-orange-400 transition-colors"
          >
            <span className="text-xs uppercase tracking-widest mb-2">Tools</span>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </a>
        </div>
      </div>
    </section>
  );
}
