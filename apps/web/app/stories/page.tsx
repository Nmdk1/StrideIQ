import type { Metadata } from 'next'
import Link from 'next/link'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'Real Results - StrideIQ Athletes',
  description:
    'Evidence-based outcomes from real athletes using StrideIQ. Race results, training outcomes, and case studies — with the data behind them.',
  alternates: {
    canonical: 'https://strideiq.run/stories',
  },
  openGraph: {
    url: 'https://strideiq.run/stories',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - Real Results' }],
  },
}

const breadcrumbJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://strideiq.run' },
    { '@type': 'ListItem', position: 2, name: 'Stories', item: 'https://strideiq.run/stories' },
  ],
}

export default function StoriesPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={breadcrumbJsonLd} />

      <div className="max-w-4xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="mb-16">
          <p className="text-orange-400 text-sm font-semibold uppercase tracking-widest mb-4">
            Real Results
          </p>
          <h1 className="text-4xl md:text-5xl font-black mb-6">
            StrideIQ Athletes
          </h1>
          <p className="text-xl text-slate-300 max-w-2xl leading-relaxed">
            Evidence-based outcomes from athletes using StrideIQ. Race results, training
            outcomes, and what the data actually showed — not what anyone predicted.
          </p>
        </div>

        {/* Incoming story teaser */}
        <div className="bg-slate-800/60 border border-orange-500/30 rounded-2xl p-8 mb-12">
          <div className="flex items-start gap-4">
            <div className="w-2 h-full min-h-[4rem] bg-orange-500 rounded-full shrink-0 mt-1" />
            <div>
              <p className="text-orange-400 text-xs font-semibold uppercase tracking-widest mb-3">
                Coming soon
              </p>
              <h2 className="text-2xl font-bold mb-3">
                Father and Son. Same race. State age group records. Both on StrideIQ.
              </h2>
              <p className="text-slate-300 leading-relaxed mb-4">
                A 57-year-old and a 79-year-old. One race. Two age group records set on the same
                day. The training data, the pacing strategy, and what StrideIQ saw before the race
                that no one else was tracking. Published within 48 hours of the gun.
              </p>
              <p className="text-slate-400 text-sm">
                This is what evidence-based running looks like. Real data. Real outcomes. Nothing
                fabricated.
              </p>
            </div>
          </div>
        </div>

        {/* Why stories exist */}
        <div className="prose prose-invert prose-slate max-w-none mb-16">
          <h2 className="text-2xl font-bold mb-4">Why we publish outcomes, not claims</h2>
          <p className="text-slate-300 leading-relaxed mb-4">
            Any running app can tell you it works. We&apos;d rather show you the data — the actual
            training files, the readiness signals, the pacing decisions, and the results. When
            StrideIQ says something about an athlete&apos;s performance, it cites the evidence. The
            stories here follow the same contract.
          </p>
          <p className="text-slate-300 leading-relaxed">
            We won&apos;t publish a story that doesn&apos;t have real outcomes tied to real data. No
            testimonials. No before-and-after photos. Evidence, or nothing.
          </p>
        </div>

        {/* CTA */}
        <div className="border-t border-slate-800 pt-10 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <Link
            href="/tools"
            className="inline-flex items-center gap-2 px-6 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-xl text-slate-200 font-semibold transition-colors"
          >
            Try the free training calculators
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 px-6 py-3 bg-orange-600 hover:bg-orange-500 text-white rounded-xl font-semibold shadow-lg shadow-orange-500/20 transition-colors"
          >
            Start free trial
          </Link>
        </div>
      </div>
    </div>
  )
}
