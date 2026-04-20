import type { Metadata } from 'next'
import Link from 'next/link'
import Footer from '../../components/Footer'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'DEXA and the 7-Pound Gap — A StrideIQ Case Study',
  description:
    'A 47-year-old runner uploaded his DEXA scan to StrideIQ. The coach reconciled it with his Garmin scale and lift history — and explained why his bones are 7 pounds heavier than Garmin thinks.',
  alternates: {
    canonical: 'https://strideiq.run/case-studies/dexa-and-the-7-pound-gap',
  },
  openGraph: {
    title: 'DEXA and the 7-Pound Gap — A StrideIQ Case Study',
    description:
      'A 47-year-old runner uploaded his DEXA scan to StrideIQ. The coach reconciled it with his Garmin scale and lift history.',
    url: 'https://strideiq.run/case-studies/dexa-and-the-7-pound-gap',
    siteName: 'StrideIQ',
    type: 'article',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Case Study' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'DEXA and the 7-Pound Gap — A StrideIQ Case Study',
    description:
      'A 47-year-old runner uploaded his DEXA scan to StrideIQ. The coach reconciled it with his Garmin scale and lift history.',
  },
}

const articleJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'Article',
  headline: 'DEXA and the 7-Pound Gap',
  description:
    'A 47-year-old runner uploaded his DEXA scan to StrideIQ. The coach reconciled it with his Garmin scale, his lift history, and his upcoming race — and explained why his bones are 7 pounds heavier than Garmin thinks.',
  author: { '@type': 'Organization', name: 'StrideIQ' },
  publisher: { '@type': 'Organization', name: 'StrideIQ' },
  url: 'https://strideiq.run/case-studies/dexa-and-the-7-pound-gap',
}

export default function DexaCaseStudy() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={articleJsonLd} />

      <article className="max-w-3xl mx-auto px-6 py-16">
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/" className="hover:text-orange-400 transition-colors">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/case-studies" className="hover:text-orange-400 transition-colors">Case Studies</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">DEXA and the 7-Pound Gap</span>
        </nav>

        <header className="mb-10">
          <p className="text-sm uppercase tracking-widest text-orange-400 font-semibold mb-3">
            Case Study
          </p>
          <h1 className="text-4xl md:text-5xl font-bold mb-4 leading-tight">
            DEXA and the 7-Pound Gap
          </h1>
          <p className="text-xl text-slate-300 leading-relaxed">
            A 47-year-old strength-trained runner uploaded his DEXA scan into Ask Coach. What came back was a synthesis no template plan could produce — and a reconciliation of three data sources he had been treating as contradictory.
          </p>
        </header>

        <section className="prose prose-invert prose-lg max-w-none space-y-6 mb-12">
          <h2 className="text-2xl font-bold text-orange-400">The setup</h2>
          <p>
            The athlete is a 47-year-old man training for a 20-mile race. He deadlifts in the 300s, squats in the 270s, benches 225 for 11s. He runs consistently, logs everything in StrideIQ, and syncs his Garmin scale daily. He had recently spent the money on a DEXA scan — the gold standard for body composition.
          </p>
          <p>
            He had a problem. His Garmin scale said 188 lbs. His DEXA said 195 lbs. Same body, same week. He uploaded the DEXA report into Ask Coach and asked what it meant.
          </p>

          <h2 className="text-2xl font-bold text-orange-400">What the coach said</h2>
          <p>
            The DEXA showed a T-score of <strong>+3.2</strong> — bone density in the top 1% of the population. The coach connected this directly to his lift history (years of heavy compound work) and explained the implication for his 188-vs-195 reading:
          </p>
          <blockquote className="border-l-4 border-orange-500 pl-6 italic text-slate-200 my-6">
            &ldquo;Garmin&apos;s algorithm assumes you have a standard skeleton. It literally cannot see the extra 7 lbs of mineral density you have packed into your bones. You are not fat at 195 lbs; you are just physically more solid.&rdquo;
          </blockquote>
          <p>
            The coach went further than the reconciliation. It carried the finding forward into how he should fuel for his upcoming race:
          </p>
          <blockquote className="border-l-4 border-orange-500 pl-6 italic text-slate-200 my-6">
            &ldquo;Trust the 195-lb fueling. Your engine and chassis require more energy than a standard 188-lb runner.&rdquo;
          </blockquote>
          <p>
            And it told him what to ignore on race day:
          </p>
          <blockquote className="border-l-4 border-orange-500 pl-6 italic text-slate-200 my-6">
            &ldquo;If you feel heavy on the hills, remind yourself: it is not dead weight; it is armor and horsepower.&rdquo;
          </blockquote>

          <h2 className="text-2xl font-bold text-orange-400">Why this matters</h2>
          <p>
            This exchange traces a chain that almost no other product in the running space can complete:
          </p>
          <ul>
            <li>
              <strong>External data ingest:</strong> The coach read a DEXA scan PDF — a data source most coaching apps cannot accept and most coaches do not have access to.
            </li>
            <li>
              <strong>Multi-source reconciliation:</strong> DEXA, Garmin scale, lift logs, and run history were treated as one body of evidence rather than four disconnected feeds.
            </li>
            <li>
              <strong>Causal explanation:</strong> The +3.2 T-score was not just reported. It was traced backward to its likely cause (years of heavy lifting) and forward to its operational implications (fueling, race-day mental reframe).
            </li>
            <li>
              <strong>Cited and specific:</strong> Every claim referenced the actual numbers — the deadlift weights, the bench reps, the 20-miler in his calendar. Nothing was generic.
            </li>
          </ul>

          <h2 className="text-2xl font-bold text-orange-400">The point</h2>
          <p>
            Most training products treat body composition, strength, and running as three separate worlds. They have to, because they only see one of those worlds at a time. StrideIQ does not have that constraint — it ingests whatever the athlete brings and synthesizes across sources.
          </p>
          <p>
            This is what &ldquo;evidence-based coaching that learns from your data&rdquo; looks like in practice. Not a template plan with personalization theater on top. A coach that read the actual file, did the actual math, and reframed three numbers into a single story the athlete could use.
          </p>
        </section>

        <aside className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-6 mb-12">
          <p className="text-sm text-slate-400 leading-relaxed">
            <strong className="text-slate-200">Note on identity:</strong> This case study is published with the athlete&apos;s pre-cleared permission for de-identified use. Names, race names, and exact dates have been omitted. The numbers and the coach output are real.
          </p>
        </aside>

        <div className="border-t border-slate-800 pt-8 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
          <Link href="/case-studies/strength-and-durability" className="text-orange-400 hover:text-orange-300 font-semibold">
            Next: Strength and Durability →
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
