import type { Metadata } from 'next'
import ToolsContent from './ToolsContent'

export const metadata: Metadata = {
  title: 'Free Running Calculators - Pace, Age-Grading, Heat Adjustment',
  description:
    'Free training pace calculator, WMA age-grading calculator, heat-adjusted pace, race equivalency tables, and Boston qualifying times. Research-backed formulas, instant results. No signup required.',
  alternates: {
    canonical: 'https://strideiq.run/tools',
  },
  openGraph: {
    title: 'Free Running Calculators - Pace, Age-Grading, Heat, BQ & Equivalency',
    description:
      'Training paces, age grading, heat-adjusted pace, race equivalency, and Boston qualifying standards — free, no signup.',
    url: 'https://strideiq.run/tools',
    siteName: 'StrideIQ',
    type: 'website',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - Free Running Calculators' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Free Running Calculators | StrideIQ',
    description: 'Pace zones, WMA age grading, heat adjustment, equivalency tables, and BQ times.',
  },
}

export default function ToolsPage() {
  return <ToolsContent />
}
