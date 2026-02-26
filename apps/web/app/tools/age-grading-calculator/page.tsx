import type { Metadata } from 'next'
import Link from 'next/link'
import WMACalculator from '@/app/components/tools/WMACalculator'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'Age-Grading Calculator - WMA Age Graded Running Performance',
  description:
    'Free WMA age-grading calculator for runners. Compare your race time to world-standard benchmarks for your age. See your age-graded percentage and equivalent open-age performance.',
  alternates: {
    canonical: 'https://strideiq.run/tools/age-grading-calculator',
  },
  openGraph: {
    url: 'https://strideiq.run/tools/age-grading-calculator',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Age-Grading Calculator' }],
  },
}

const toolJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'StrideIQ WMA Age-Grading Calculator',
  url: 'https://strideiq.run/tools/age-grading-calculator',
  applicationCategory: 'HealthApplication',
  operatingSystem: 'Web',
  description:
    'Calculate your WMA age-graded running performance percentage and equivalent open-age time. Enables fair comparison across all ages.',
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
}

const FAQ_ITEMS = [
  {
    q: 'What is a good age-graded percentage for runners?',
    a: '90%+ is world-class (national/world record territory for your age). 80–89% is elite masters performance. 70–79% is highly competitive. 60–69% is solid recreational running. Below 60% represents developing fitness. Most recreational runners score 40–65%.',
  },
  {
    q: 'What are the WMA age-grading tables based on?',
    a: 'WMA (World Masters Athletics) tables are built from world-record performances by age group across all standard distances. They are periodically updated as masters athletes set new age-group world records. The tables provide age-specific world-best benchmarks for men and women separately.',
  },
  {
    q: 'Can I use age-grading to compare my 5K to my marathon performance?',
    a: 'Yes — that\'s one of age-grading\'s most useful applications. If your 5K age-grades at 72% but your marathon grades at 65%, you have more aerobic endurance to develop relative to your speed. The gap tells you where to focus training.',
  },
]

export default function AgeGradingCalculatorPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={toolJsonLd} />

      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Breadcrumb */}
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/tools" className="hover:text-orange-400 transition-colors">Tools</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Age-Grading Calculator</span>
        </nav>

        {/* H1 */}
        <h1 className="text-3xl md:text-4xl font-bold mb-4">
          Age-Grading Calculator
        </h1>

        {/* Answer capsule */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-6">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong> Age-grading expresses your race time as a percentage of the world-record standard for your age and sex, using official WMA (World Masters Athletics) tables. A 75% age-grade means you ran 75% as fast as the world record holder in your age group — across any distance.
          </p>
        </div>

        {/* Calculator island */}
        <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 mb-10 shadow-xl">
          <WMACalculator />
        </div>

        {/* How it works */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-4">How WMA age grading works</h2>
          <div className="prose prose-invert prose-slate max-w-none space-y-4 text-slate-300">
            <p>
              The <strong>World Masters Athletics (WMA) age-grading system</strong> provides a standardized method for comparing running performances across different ages. For each standard distance, WMA maintains world-best benchmark times for every age from 35 to 100+, derived from official world records set in competition.
            </p>
            <p>
              Your age-graded percentage is calculated as: <strong>(world-best time for your age ÷ your time) × 100</strong>. A score of 100% would mean you ran as fast as the world record for your age group. This makes it possible to compare a 70-year-old&apos;s marathon time to a 35-year-old&apos;s — something raw times can&apos;t do fairly.
            </p>
            <p>
              For <strong>masters runners</strong> (35+), age-grading is particularly valuable for tracking improvement over time. As you age, your raw times naturally slow — but your age-graded percentage can remain stable or even improve if your relative performance within your age group stays strong. This is a truer measure of fitness development.
            </p>
            <p>
              The calculator also shows your <strong>equivalent open-age time</strong> — what your performance would be equivalent to as a peak-age athlete. This is useful for setting training goals and understanding your absolute performance level independent of age.
            </p>
          </div>
        </section>

        {/* Related FAQs */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6">Common questions</h2>
          <div className="space-y-5">
            {FAQ_ITEMS.map((item, i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="font-semibold text-white mb-2">{item.q}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Related tools */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Related calculators</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator →
            </Link>
            <Link href="/tools/heat-adjusted-pace" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Heat-Adjusted Pace →
            </Link>
            <Link href="/tools" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              All Tools →
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
