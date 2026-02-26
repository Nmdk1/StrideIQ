import type { Metadata } from 'next'
import React from 'react';
import Hero from './components/Hero';
import QuickValue from './components/QuickValue';
import FreeTools from './components/FreeTools';
import HowItWorks from './components/HowItWorks';
import WhyGuidedCoaching from './components/WhyGuidedCoaching';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import FAQ from './components/FAQ';
import { JsonLd } from '@/components/seo/JsonLd';

const LANDING_META_DESCRIPTION =
  'Your body has a voice. StrideIQ is AI running intelligence that turns your data into decisions — training paces, trend signals, and coaching that adapts to you.'

const organizationJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'StrideIQ',
  url: 'https://strideiq.run',
  logo: 'https://strideiq.run/og-image.png',
  description:
    'Evidence-based AI running coach. Free training pace calculator, age-grading calculator, and heat-adjusted pace tools.',
}

const webAppJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'WebApplication',
  name: 'StrideIQ',
  url: 'https://strideiq.run',
  applicationCategory: 'HealthApplication',
  operatingSystem: 'Web',
  description:
    'AI-powered running coaching platform with free training calculators for pace, age-grading, and heat adjustment. Connects with Garmin Connect and Strava.',
  offers: [
    {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
      description: 'Free training pace calculator, age-grading, and heat-adjusted pace tools',
    },
  ],
}

export const metadata: Metadata = {
  title: 'StrideIQ - AI Running Coach & Training Intelligence',
  description: LANDING_META_DESCRIPTION,
  alternates: {
    canonical: 'https://strideiq.run',
  },
  openGraph: {
    description: LANDING_META_DESCRIPTION,
    url: 'https://strideiq.run',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - AI Running Coach' }],
  },
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={organizationJsonLd} />
      <JsonLd data={webAppJsonLd} />
      <Hero />
      <QuickValue />
      <FreeTools />
      <HowItWorks />
      <WhyGuidedCoaching />
      <Pricing />
      <FAQ />
      <Footer />
    </div>
  );
}
