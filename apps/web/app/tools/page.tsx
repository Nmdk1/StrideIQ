import type { Metadata } from 'next'
import ToolsContent from './ToolsContent'

export const metadata: Metadata = {
  title: 'Free Running Calculators - Pace, Age-Grading, Heat Adjustment',
  description: 'Free training pace calculator, WMA age-grading calculator, and heat-adjusted pace calculator. Research-backed formulas, instant results. No signup required.',
  alternates: {
    canonical: 'https://strideiq.run/tools',
  },
  openGraph: {
    url: 'https://strideiq.run/tools',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - Free Running Calculators' }],
  },
}

export default function ToolsPage() {
  return <ToolsContent />
}
