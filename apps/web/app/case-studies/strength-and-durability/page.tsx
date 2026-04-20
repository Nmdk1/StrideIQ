import type { Metadata } from 'next'
import Link from 'next/link'
import Footer from '../../components/Footer'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'Strength Training and Long-Run Durability — A StrideIQ Case Study',
  description:
    'A masters runner added hip thrusts and RDLs to his weekly routine. Three months later his cardiac drift on long runs had dropped from 8.9% to 2.1%. StrideIQ traced the dated evidence and showed him the trend.',
  alternates: {
    canonical: 'https://strideiq.run/case-studies/strength-and-durability',
  },
  openGraph: {
    title: 'Strength Training and Long-Run Durability — A StrideIQ Case Study',
    description:
      'A masters runner added hip thrusts and RDLs. Three months later his cardiac drift on long runs had dropped from 8.9% to 2.1%.',
    url: 'https://strideiq.run/case-studies/strength-and-durability',
    siteName: 'StrideIQ',
    type: 'article',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Case Study' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Strength Training and Long-Run Durability — A StrideIQ Case Study',
    description:
      'A masters runner added hip thrusts and RDLs. Three months later his cardiac drift on long runs had dropped from 8.9% to 2.1%.',
  },
}

const articleJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'Article',
  headline: 'Strength Training and Long-Run Durability',
  description:
    'A masters runner added hip thrusts and RDLs to his weekly routine. Three months later his cardiac drift on long runs had dropped from 8.9% to 2.1%. StrideIQ traced the dated evidence and showed him the trend.',
  author: { '@type': 'Organization', name: 'StrideIQ' },
  publisher: { '@type': 'Organization', name: 'StrideIQ' },
  url: 'https://strideiq.run/case-studies/strength-and-durability',
}

type DriftRow = { date: string; distance: string; drift: string; verdict: 'red' | 'yellow' | 'green' }

const EARLY_BLOCK: DriftRow[] = [
  { date: 'Early Dec', distance: '8.1 mi', drift: '7.0%', verdict: 'yellow' },
  { date: 'Late Dec', distance: '8.2 mi', drift: '8.9%', verdict: 'red' },
  { date: 'Mid Jan', distance: '11.7 mi', drift: '3.8%', verdict: 'yellow' },
  { date: 'Late Jan', distance: '12.1 mi', drift: '10.4%', verdict: 'red' },
]

const LATE_BLOCK: DriftRow[] = [
  { date: 'Mid Feb', distance: '15.3 mi', drift: '1.4%', verdict: 'green' },
  { date: 'Late Feb', distance: '16.0 mi', drift: '2.1%', verdict: 'green' },
  { date: 'Late Feb', distance: '18.4 mi', drift: '3.2%', verdict: 'green' },
  { date: 'Early Mar', distance: '13.1 mi', drift: '2.2%', verdict: 'green' },
]

function VerdictBadge({ verdict }: { verdict: DriftRow['verdict'] }) {
  const styles: Record<DriftRow['verdict'], string> = {
    green: 'bg-green-900/40 text-green-300 border-green-500/30',
    yellow: 'bg-yellow-900/40 text-yellow-300 border-yellow-500/30',
    red: 'bg-red-900/40 text-red-300 border-red-500/30',
  }
  const label: Record<DriftRow['verdict'], string> = {
    green: 'Rock solid',
    yellow: 'Yellow flag',
    red: 'Red flag',
  }
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-semibold border rounded ${styles[verdict]}`}>
      {label[verdict]}
    </span>
  )
}

function DriftTable({ rows, caption }: { rows: DriftRow[]; caption: string }) {
  return (
    <div className="mb-6">
      <p className="text-sm font-semibold text-slate-300 mb-2">{caption}</p>
      <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/50 text-slate-400">
              <th className="text-left p-3 font-medium">When</th>
              <th className="text-left p-3 font-medium">Distance</th>
              <th className="text-left p-3 font-medium">Cardiac drift</th>
              <th className="text-left p-3 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-slate-700/30 last:border-0">
                <td className="p-3 text-slate-300">{row.date}</td>
                <td className="p-3 text-slate-300">{row.distance}</td>
                <td className="p-3 text-slate-200 font-mono font-semibold">{row.drift}</td>
                <td className="p-3"><VerdictBadge verdict={row.verdict} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function StrengthDurabilityCaseStudy() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={articleJsonLd} />

      <article className="max-w-3xl mx-auto px-6 py-16">
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/" className="hover:text-orange-400 transition-colors">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/case-studies" className="hover:text-orange-400 transition-colors">Case Studies</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Strength and Durability</span>
        </nav>

        <header className="mb-10">
          <p className="text-sm uppercase tracking-widest text-orange-400 font-semibold mb-3">
            Case Study
          </p>
          <h1 className="text-4xl md:text-5xl font-bold mb-4 leading-tight">
            Strength Training and Long-Run Durability
          </h1>
          <p className="text-xl text-slate-300 leading-relaxed">
            A masters runner added hip thrusts and Romanian deadlifts to his weekly routine. Three months later his cardiac drift on long runs had dropped from 8.9% to 2.1%. The coach traced the dated evidence and showed him the trend.
          </p>
        </header>

        <section className="prose prose-invert prose-lg max-w-none space-y-6 mb-8">
          <h2 className="text-2xl font-bold text-orange-400">What is cardiac drift?</h2>
          <p>
            Cardiac drift (also called cardiovascular drift) measures how much your heart rate climbs at a steady pace as a long run progresses. Lower is better. It is one of the cleanest available proxies for muscular durability — when the muscles supporting your running form fatigue, your cardiovascular system has to work harder to compensate, and the drift number rises.
          </p>
          <p>
            Sub-5% drift on a long run is generally considered green. Above 7% suggests durability is the limiter. The number is computable from any run with a heart rate strap and consistent pace.
          </p>

          <h2 className="text-2xl font-bold text-orange-400">The early block</h2>
          <p>
            Before the strength program had taken hold, the athlete&apos;s long runs showed a clear durability ceiling. Drift was high, the verdicts were yellow and red, and the long runs were costing him more than they should have:
          </p>
        </section>

        <DriftTable rows={EARLY_BLOCK} caption="December – January (early in the strength block)" />

        <section className="prose prose-invert prose-lg max-w-none space-y-6 mb-8">
          <p>
            The late January run with the head cold (10.4% drift, average HR 179) shows what happens when an immune-system confounder gets stacked on top of an under-built durability profile. The body had no margin.
          </p>

          <h2 className="text-2xl font-bold text-orange-400">The late block</h2>
          <p>
            Three months of consistent hip thrusts and RDLs later, the drift profile had completely changed. The same athlete, the same routes, longer distances — and the drift had collapsed:
          </p>
        </section>

        <DriftTable rows={LATE_BLOCK} caption="February – March (after months of consistent hip thrusts and RDLs)" />

        <section className="prose prose-invert prose-lg max-w-none space-y-6 mb-8">
          <p>
            The 18.4-miler is the headline. Longest run of the block, 3.2% drift — still green. The 13.1 the following weekend with admitted poor sleep and four beers the night before still came in at 2.2%. The body had built enough margin to absorb confounders that previously would have shoved him into the red.
          </p>

          <h2 className="text-2xl font-bold text-orange-400">What the coach said</h2>
          <p>
            When the athlete asked the coach what was happening, the response did not just describe the numbers. It connected the cause to the effect with dated evidence, and named the confounders rather than ignoring them:
          </p>
          <blockquote className="border-l-4 border-orange-500 pl-6 italic text-slate-200 my-6">
            &ldquo;Look at your cardiac decoupling on long runs — this measures how much your heart rate drifts up relative to pace as the run goes on. Lower is better, and it is a direct measure of muscular durability. The strength block did this. The numbers are right there.&rdquo;
          </blockquote>

          <h2 className="text-2xl font-bold text-orange-400">Why this matters</h2>
          <p>
            Strength training advice for runners is one of the most-template-driven topics in the sport. Every plan has a generic two-day-a-week recommendation. None of them can show you whether the program is working for you, because they cannot see your drift numbers and they cannot run the comparison across a three-month block.
          </p>
          <p>
            StrideIQ can. The cardiac drift was already in the data — it just took a system that ingests every long run, computes drift on each one, and is willing to show the comparison without hedging.
          </p>
          <p>
            This is what a finding looks like when the data is strong enough to defend. When it is not, the system stays quiet. That is the contract.
          </p>
        </section>

        <aside className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-6 mb-12">
          <p className="text-sm text-slate-400 leading-relaxed">
            <strong className="text-slate-200">Note on identity:</strong> This case study is published with the athlete&apos;s pre-cleared permission for de-identified use. Names, race names, and exact dates have been omitted. The numbers and the coach output are real.
          </p>
        </aside>

        <div className="border-t border-slate-800 pt-8 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
          <Link href="/case-studies/dexa-and-the-7-pound-gap" className="text-orange-400 hover:text-orange-300 font-semibold">
            ← DEXA and the 7-Pound Gap
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-semibold px-6 py-3 rounded-xl transition-all"
          >
            Try StrideIQ free
          </Link>
        </div>
      </article>

      <Footer />
    </div>
  )
}
