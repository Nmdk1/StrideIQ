import type { Metadata } from 'next'
import Link from 'next/link'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'Race Equivalency Calculator — Predict Times Across Distances',
  description:
    'Understand race equivalency: how your 5K fitness predicts marathon potential, when to trust the formula, and when distance-specific training overrides aerobic equivalency.',
  alternates: {
    canonical: 'https://strideiq.run/tools/race-equivalency',
  },
  openGraph: {
    url: 'https://strideiq.run/tools/race-equivalency',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'Race Equivalency' }],
  },
}

const FEATURED_CONVERSIONS = [
  {
    slug: '5k-to-marathon',
    title: '5K → Marathon Equivalency',
    description:
      'Given your 5K time, what is your equivalent marathon potential? 12 time points from 16:00 to 35:00.',
    inputLabel: '5K',
    outputLabel: 'Marathon',
  },
  {
    slug: '10k-to-half-marathon',
    title: '10K → Half Marathon Equivalency',
    description:
      'Given your 10K time, what is your equivalent half marathon potential? The most physiologically accurate distance-pair for equivalency.',
    inputLabel: '10K',
    outputLabel: 'Half Marathon',
  },
]

const ALL_CONVERSIONS = [
  { slug: 'mile-to-5k', label: 'Mile → 5K' },
  { slug: 'mile-to-10k', label: 'Mile → 10K' },
  { slug: 'mile-to-half-marathon', label: 'Mile → Half Marathon' },
  { slug: 'mile-to-marathon', label: 'Mile → Marathon' },
  { slug: '5k-to-10k', label: '5K → 10K' },
  { slug: '5k-to-half-marathon', label: '5K → Half Marathon' },
  { slug: '5k-to-marathon', label: '5K → Marathon' },
  { slug: '10k-to-half-marathon', label: '10K → Half Marathon' },
  { slug: '10k-to-marathon', label: '10K → Marathon' },
  { slug: 'half-marathon-to-marathon', label: 'Half → Marathon' },
  { slug: 'marathon-to-5k', label: 'Marathon → 5K' },
  { slug: 'marathon-to-10k', label: 'Marathon → 10K' },
  { slug: 'marathon-to-half-marathon', label: 'Marathon → Half' },
  { slug: '800m-to-mile', label: '800m → Mile' },
  { slug: '800m-to-5k', label: '800m → 5K' },
]

const faqItems = [
  {
    q: 'What is race equivalency?',
    a: 'Race equivalency translates your performance at one distance into a predicted time at another, using the Daniels/Gilbert oxygen cost equation. The calculation finds the Running Performance Index (RPI) — a measure of aerobic capacity — from your race result, then determines what time at a different distance would require the same RPI. It is the most rigorous publicly available method for cross-distance performance prediction.',
  },
  {
    q: 'When should I trust race equivalency — and when should I not?',
    a: 'Equivalency is most accurate between physiologically similar distances. 10K → half marathon predictions are highly reliable because both events demand sustained effort near lactate threshold. 5K → marathon predictions are less reliable because the marathon requires specific training adaptations — long runs, glycogen management, pacing experience — that pure aerobic fitness does not capture. A 20:00 5K runner may have the aerobic capacity for a 3:11 marathon, but without marathon-specific training, the actual performance will fall short. Trust equivalency as a potential ceiling, not a race-day prediction.',
  },
  {
    q: 'Why does my marathon time underperform my 5K equivalency?',
    a: 'Almost always: insufficient marathon-specific preparation. The marathon punishes runners whose training is not distance-specific, even when aerobic capacity is high. The key elements equivalency does not measure: long-run adaptation (training the body to sustain 3+ hours of effort), glycogen economy (efficient fat metabolism during extended running), and pacing discipline (the ability to run the first half at effort that feels "too easy"). Runners who do the specific training — 18-22 mile long runs, marathon-pace segments, consistent high volume — tend to match their equivalency predictions closely.',
  },
  {
    q: 'How is race equivalency different from WMA age-grading?',
    a: 'They measure different things. Race equivalency converts performance between distances using aerobic capacity (RPI). WMA age-grading compares your performance to the world-record standard for your age and sex — it tells you how your time ranks on a 0–100% scale relative to the best possible performance for your demographic. Equivalency is about what you could run at a different distance; age-grading is about how good your time is relative to your age group.',
  },
]

export default function RaceEquivalencyHubPage() {
  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Race Equivalency', item: 'https://strideiq.run/tools/race-equivalency' },
    ],
  }

  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqItems.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={breadcrumbJsonLd} />
      <JsonLd data={faqJsonLd} />

      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Breadcrumb */}
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/tools" className="hover:text-orange-400 transition-colors">Tools</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Race Equivalency</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">Race Equivalency</h1>
        <p className="text-slate-300 leading-relaxed mb-8">
          Race equivalency is one of running&apos;s most useful — and most misunderstood — tools.
          It translates your performance at one distance into predicted potential at another, based
          on aerobic capacity. Used correctly, it reveals what you&apos;re capable of. Used naively,
          it sets expectations that distance-specific training must earn.
        </p>

        {/* BLUF */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            Equivalency predicts your aerobic potential at an unfamiliar distance. It is most
            accurate for similar distances (10K ↔ half marathon) and least accurate for the marathon,
            which requires glycogen-specific adaptations that raw aerobic capacity does not capture.
            Use it as a ceiling estimate — meeting it requires distance-specific training.
          </p>
        </div>

        {/* Featured conversion links */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6">Distance conversion tables</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {FEATURED_CONVERSIONS.map((c) => (
              <Link
                key={c.slug}
                href={`/tools/race-equivalency/${c.slug}`}
                className="group block bg-slate-800 border border-slate-700/50 hover:border-orange-500/50 rounded-2xl p-6 transition-colors shadow-xl"
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-orange-400 text-xl font-bold">{c.inputLabel}</span>
                  <span className="text-slate-500">→</span>
                  <span className="text-orange-400 text-xl font-bold">{c.outputLabel}</span>
                </div>
                <h3 className="text-lg font-semibold text-slate-100 group-hover:text-orange-300 mb-2 transition-colors">
                  {c.title}
                </h3>
                <p className="text-slate-400 text-sm leading-relaxed">{c.description}</p>
                <div className="mt-4 text-orange-400 text-sm font-medium">
                  View table →
                </div>
              </Link>
            ))}
          </div>
          <h3 className="text-lg font-semibold text-slate-200 mb-3">All distance conversions</h3>
          <div className="flex flex-wrap gap-2">
            {ALL_CONVERSIONS.map((c) => (
              <Link
                key={c.slug}
                href={`/tools/race-equivalency/${c.slug}`}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-300 hover:text-orange-300 transition-colors"
              >
                {c.label}
              </Link>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">How race equivalency is calculated</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-4">
            <p>
              The calculation uses the Daniels/Gilbert oxygen cost equation — a physics-based formula
              published in 1979 that describes the relationship between running velocity and oxygen
              consumption. From your race time and distance, it computes your{' '}
              <strong>Running Performance Index (RPI)</strong> — a single number representing your
              current aerobic capacity.
            </p>
            <p>
              Given that RPI, the formula uses a binary search to find the time at any target
              distance that would require the same aerobic capacity to sustain. This is the
              &ldquo;equivalent&rdquo; time — the performance that aerobic fitness alone would predict.
            </p>
            <p>
              The prediction is accurate when the two distances make similar demands. When they diverge
              — especially for the marathon — the prediction represents potential, not guarantee.
            </p>
          </div>
        </section>

        {/* FAQ */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-6">Common questions</h2>
          <div className="space-y-5">
            {faqItems.map((item, i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="font-semibold text-white mb-2">{item.q}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* N=1 hook */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">Equivalency predicts potential — StrideIQ tracks actuals</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              Race equivalency formulas treat all runners with the same RPI as identical. StrideIQ
              tracks how your body specifically responds to different training stimuli — which sessions
              produce your sharpest fitness gains, how your aerobic ceiling shifts across a training
              cycle, and what conditions produce your best race-day readiness. The formula gives you
              the population prediction. Your training data gives you the individual truth.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                All calculators →
              </Link>
              <Link href="/register" className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors">
                Start free trial
              </Link>
            </div>
          </div>
        </section>

        {/* Related */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Related tools</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator →
            </Link>
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Age-Grading Calculator →
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
