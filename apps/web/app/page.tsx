"use client";

import React from 'react';
import Hero from './components/Hero';
import QuickValue from './components/QuickValue';
import FreeTools from './components/FreeTools';
import HowItWorks from './components/HowItWorks';
import WhyGuidedCoaching from './components/WhyGuidedCoaching';
import Pricing from './components/Pricing';
import Footer from './components/Footer';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
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
