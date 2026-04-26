import type { Metadata } from 'next'
import Link from 'next/link'
import Footer from '../components/Footer'

export const metadata: Metadata = {
  title: 'Case Studies — Real Findings from Real Athletes | StrideIQ',
  description:
    'De-identified case studies showing what StrideIQ&apos;s coach has produced for actual athletes — from DEXA reconciliation to strength-training durability findings.',
  alternates: {
    canonical: 'https://strideiq.run/case-studies',
  },
  openGraph: {
    url: 'https://strideiq.run/case-studies',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Case Studies' }],
  },
}

const STUDIES = [
  {
    slug: 'dexa-and-the-7-pound-gap',
    title: 'DEXA and the 7-Pound Gap',
    blurb:
      'A 47-year-old strength-trained runner uploaded his DEXA scan into Ask Coach. The coach reconciled it with his Garmin scale, his lift history, and his upcoming 20-miler — and explained why his bones are 7 lbs heavier than Garmin thinks.',
  },
  {
    slug: 'strength-and-durability',
    title: 'Strength Training and Long-Run Durability',
    blurb:
      'A masters runner added hip thrusts and Romanian deadlifts. Three months later his cardiac drift on long runs had dropped from 8.9% to 2.1% — even on a long run after four beers. The coach traced the dated evidence and showed him the trend.',
  },
]

export default function CaseStudiesIndex() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <main className="max-w-4xl mx-auto px-6 py-16">
        <header className="mb-12">
          <p className="text-sm uppercase tracking-widest text-orange-400 font-semibold mb-3">
            Case Studies
          </p>
          <h1 className="text-4xl md:text-5xl font-bold mb-4 leading-tight">
            Real findings from real athletes
          </h1>
          <p className="text-xl text-slate-300 leading-relaxed max-w-2xl">
            What the coach has actually produced — published de-identified, with the athletes&apos; permission. Numbers and coach output are real.
          </p>
        </header>

        <div className="space-y-6">
          {STUDIES.map((study) => (
            <Link
              key={study.slug}
              href={`/case-studies/${study.slug}`}
              className="block bg-slate-800/60 border border-slate-700/50 hover:border-orange-500/50 rounded-xl p-6 transition-all"
            >
              <h2 className="text-2xl font-bold text-orange-400 mb-3">{study.title}</h2>
              <p className="text-slate-300 leading-relaxed">{study.blurb}</p>
              <p className="mt-4 text-sm text-orange-400 font-semibold">Read the full finding →</p>
            </Link>
          ))}
        </div>
      </main>

      <Footer />
    </div>
  )
}
