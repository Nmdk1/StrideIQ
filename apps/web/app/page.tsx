import type { Metadata } from 'next'
import React from 'react';
import Hero from './components/Hero';
import QuickValue from './components/QuickValue';
import FreeTools from './components/FreeTools';
import HowItWorks from './components/HowItWorks';
import WhyGuidedCoaching from './components/WhyGuidedCoaching';
import Pricing from './components/Pricing';
import Footer from './components/Footer';

export const metadata: Metadata = {
  title: 'StrideIQ - AI Running Coach & Training Intelligence',
  description: 'Free training pace calculator, age-grading calculator, and heat-adjusted pace tools. Evidence-based AI running coach that correlates sleep, nutrition, and training with your performance.',
  alternates: {
    canonical: 'https://strideiq.run',
  },
  openGraph: {
    url: 'https://strideiq.run',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - AI Running Coach' }],
  },
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <Hero />
      <QuickValue />
      <FreeTools />
      <HowItWorks />
      <WhyGuidedCoaching />
      <Pricing />
      <Footer />
    </div>
  );
}
