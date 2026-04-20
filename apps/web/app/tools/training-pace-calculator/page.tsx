import type { Metadata } from 'next'
import Link from 'next/link'
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import goalPaceData from '@/data/goal-pace-tables.json'

export const metadata: Metadata = {
  title: 'Training Pace Calculator - Running Pace Zones from Race Time',
  description:
    'Free training pace calculator. Enter any race result to get your personalized Easy, Marathon, Threshold, Interval, and Repetition pace zones. Based on Daniels/Gilbert exercise science equations.',
  alternates: {
    canonical: 'https://strideiq.run/tools/training-pace-calculator',
  },
  openGraph: {
    title: 'Training Pace Calculator - Running Pace Zones from Race Time',
    description:
      'Free training pace calculator. Enter any race result to get your personalized Easy, Marathon, Threshold, Interval, and Repetition pace zones. Based on Daniels/Gilbert exercise science equations.',
    url: 'https://strideiq.run/tools/training-pace-calculator',
    siteName: 'StrideIQ',
    type: 'website',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Training Pace Calculator' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Training Pace Calculator - Running Pace Zones from Race Time',
    description:
      'Free training pace calculator with Daniels/Gilbert pace zones — easy through repetition paces from any race result.',
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
            <strong className="text-orange-400">Quick answer:</strong> Enter a recent race time and distance below. The calculator applies the Daniels/Gilbert oxygen cost equations to derive your Running Performance Index (RPI) — your current aerobic fitness score — and outputs your five training pace zones in both min/mile and min/km.
          </p>
        </div>

        {/* RPI / VDOT reconciliation — for readers arriving via "VDOT" search queries */}
        <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 mb-10 text-sm">
          <p className="text-slate-300 leading-relaxed">
            <strong className="text-slate-200">RPI and VDOT are the same math.</strong>{" "}
            Daniels and Gilbert&apos;s 1979 oxygen cost equations produce a number that is publicly known as <strong>VDOT</strong>. StrideIQ surfaces it as <strong>RPI (Running Performance Index)</strong> — same math, same training zones, a name StrideIQ stands behind. The calculator above uses these equations directly. If you arrived here looking for a VDOT calculator, you are in the right place.
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
              The calculator uses the <strong>Daniels/Gilbert oxygen cost equations</strong> — a measure of your current aerobic capacity derived from race performance rather than a lab test. The equations were published in peer-reviewed exercise physiology research in 1979 and remain the gold standard for running pace prescription. StrideIQ expresses the result as an <strong>RPI (Running Performance Index)</strong> score.
            </p>
            <p>
              Your race time and distance are converted to an RPI score. Each RPI score maps to five training intensity zones: Easy (E), Marathon (M), Threshold (T), Interval (I), and Repetition (R). These zones correspond to distinct physiological targets — aerobic base building, lactate threshold development, VO2max stimulus, and neuromuscular speed.
            </p>
            <p>
              The <strong>Easy pace</strong> range is wide intentionally — it&apos;s the zone for most of your weekly volume. Running too fast on easy days is the most common training mistake. The <strong>Threshold pace</strong> (tempo pace) should feel comfortably hard — you could hold it for 20 minutes in a race but not much longer. <strong>Interval pace</strong> is close to your 3K–5K race pace.
            </p>
            <p>
              For marathon and half marathon training specifically, your <strong>Marathon pace</strong> zone is the most important: it&apos;s the effort you need to sustain for 2–5 hours. Most runners train their marathon pace too fast in training and pay for it on race day.
            </p>
          </div>
        </section>

        {/* Guide pages */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-4">Training pace tables by distance</h2>
          <p className="text-slate-400 mb-4">See complete pace tables for common race times at each distance — no calculator needed.</p>
          <div className="grid sm:grid-cols-2 gap-3">
            <Link href="/tools/training-pace-calculator/5k-training-paces" className="px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">5K Training Paces →</Link>
            <Link href="/tools/training-pace-calculator/10k-training-paces" className="px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">10K Training Paces →</Link>
            <Link href="/tools/training-pace-calculator/half-marathon-training-paces" className="px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">Half Marathon Training Paces →</Link>
            <Link href="/tools/training-pace-calculator/marathon-training-paces" className="px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">Marathon Training Paces →</Link>
          </div>
        </section>

        {/* Goal pace tables — internal links to pSEO pages */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-4">Training paces for specific goal times</h2>
          <p className="text-slate-400 mb-4">See the exact easy, threshold, interval, and marathon training paces for your goal time — no calculator needed.</p>
          {(['5k', '10k', 'half-marathon', 'marathon'] as const).map((dist) => {
            const goals = Object.entries(goalPaceData)
              .filter(([k, v]) => k !== '_meta' && (v as { slug: string }).slug.endsWith(dist))
              .map(([k, v]) => ({ slug: k, label: (v as { label: string }).label }))
            if (!goals.length) return null
            const heading = dist === '5k' ? '5K' : dist === '10k' ? '10K' : dist === 'half-marathon' ? 'Half Marathon' : 'Marathon'
            return (
              <div key={dist} className="mb-4">
                <h3 className="text-lg font-semibold text-slate-200 mb-2">{heading} Goals</h3>
                <div className="flex flex-wrap gap-2">
                  {goals.map((g) => (
                    <Link
                      key={g.slug}
                      href={`/tools/training-pace-calculator/goals/${g.slug}`}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-300 hover:text-orange-300 transition-colors"
                    >
                      {g.label}
                    </Link>
                  ))}
                </div>
              </div>
            )
          })}
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
            <Link href="/tools/race-equivalency/10k-to-half-marathon" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Race Equivalency →
            </Link>
            <Link href="/tools/boston-qualifying" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Boston Qualifying Times →
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
