import type { Metadata } from 'next'
import Link from 'next/link'
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'Training Pace Calculator - Running Pace Zones from Race Time',
  description:
    'Free training pace calculator. Enter any race result to get your personalized Easy, Marathon, Threshold, Interval, and Repetition pace zones. Based on Daniels/Gilbert exercise science equations.',
  alternates: {
    canonical: 'https://strideiq.run/tools/training-pace-calculator',
  },
  openGraph: {
    url: 'https://strideiq.run/tools/training-pace-calculator',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Training Pace Calculator' }],
  },
}

const FAQ_ITEMS = [
  {
    q: 'What race distance should I use for the training pace calculator?',
    a: 'Use your most recent race result from the past 3–6 months. A 5K or 10K gives the most accurate current fitness picture. Older or longer races may underestimate your current fitness if you\'ve been training consistently.',
  },
  {
    q: 'What are Easy, Threshold, and Interval training paces?',
    a: 'Easy pace (60–79% effort) builds aerobic base with minimal fatigue. Threshold pace (83–88% effort) is your comfortably hard tempo run pace — sustainable for 20–40 minutes. Interval pace (95–100% effort) builds VO2max in short, hard repeats with rest between.',
  },
  {
    q: 'How often should I recalculate my training paces?',
    a: 'After each significant race or time trial that reflects your current fitness — typically every 4–12 weeks of consistent training. Don\'t update based on a bad race day; wait for a performance that feels representative of your current shape.',
  },
]

const toolJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'StrideIQ Training Pace Calculator',
  url: 'https://strideiq.run/tools/training-pace-calculator',
  applicationCategory: 'HealthApplication',
  operatingSystem: 'Web',
  description:
    'Calculate personalized running training paces from any race result using the Daniels/Gilbert oxygen cost equations.',
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
}

const breadcrumbJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
    { '@type': 'ListItem', position: 2, name: 'Training Pace Calculator', item: 'https://strideiq.run/tools/training-pace-calculator' },
  ],
}

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ_ITEMS.map((item) => ({
    '@type': 'Question',
    name: item.q,
    acceptedAnswer: { '@type': 'Answer', text: item.a },
  })),
}

export default function TrainingPaceCalculatorPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={toolJsonLd} />
      <JsonLd data={breadcrumbJsonLd} />
      <JsonLd data={faqJsonLd} />

      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Breadcrumb */}
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/tools" className="hover:text-orange-400 transition-colors">Tools</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Training Pace Calculator</span>
        </nav>

        {/* H1 — exact query match */}
        <h1 className="text-3xl md:text-4xl font-bold mb-4">
          Training Pace Calculator
        </h1>

        {/* Answer capsule */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-6">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong> Enter a recent race time and distance below. The calculator applies the Daniels/Gilbert oxygen cost equations to derive your VDOT — your current running fitness score — and outputs your five training pace zones in both min/mile and min/km.
          </p>
        </div>

        {/* Calculator island */}
        <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 mb-10 shadow-xl">
          <TrainingPaceCalculator />
        </div>

        {/* How it works */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-4">How the training pace calculator works</h2>
          <div className="prose prose-invert prose-slate max-w-none space-y-4 text-slate-300">
            <p>
              The calculator uses the <strong>Daniels/Gilbert VDOT system</strong> — a measure of your current aerobic capacity derived from race performance rather than a lab test. The underlying oxygen cost equations were published in peer-reviewed exercise physiology research in 1979 and remain the gold standard for running pace prescription.
            </p>
            <p>
              Your race time and distance are converted to a VDOT score. Each VDOT score maps to five training intensity zones: Easy (E), Marathon (M), Threshold (T), Interval (I), and Repetition (R). These zones correspond to distinct physiological targets — aerobic base building, lactate threshold development, VO2max stimulus, and neuromuscular speed.
            </p>
            <p>
              The <strong>Easy pace</strong> range is wide intentionally — it&apos;s the zone for most of your weekly volume. Running too fast on easy days is the most common training mistake. The <strong>Threshold pace</strong> (tempo pace) should feel comfortably hard — you could hold it for 20 minutes in a race but not much longer. <strong>Interval pace</strong> is close to your 3K–5K race pace.
            </p>
            <p>
              For marathon and half marathon training specifically, your <strong>Marathon pace</strong> zone is the most important: it&apos;s the effort you need to sustain for 2–5 hours. Most runners train their marathon pace too fast in training and pay for it on race day.
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
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Age-Grading Calculator →
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
