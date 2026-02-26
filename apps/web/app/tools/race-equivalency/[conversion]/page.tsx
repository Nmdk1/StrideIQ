import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { JsonLd } from '@/components/seo/JsonLd'
import equivalencyData from '@/data/equivalency-tables.json'

// ============================================================================
// TYPES — mirror the schema in equivalency-tables.json
// ============================================================================

type EquivRow = {
  inputTime:    string
  inputSeconds: number
  rpi:          number
  outputTime:   string
  outputSeconds: number
  outputPaceMi: string
  outputPaceKm: string
}

type EquivTable = {
  slug:                string
  label:               string
  inputDistance:       string
  inputDistanceMeters: number
  outputDistance:      string
  outputDistanceMeters: number
  rows:                EquivRow[]
}

// ============================================================================
// STATIC PER-PAGE CONFIG
// Numbers in BLUF and FAQ answers come from the JSON data.
// ============================================================================

const CONVERSION_PAGE_CONFIG: Record<
  string,
  {
    title:              string
    description:        string
    h1:                 string
    openingParagraph:   string
    accuracyNote:       string
    buildFaq: (data: EquivTable) => { q: string; a: string }[]
  }
> = {
  '5k-to-marathon': {
    title:       '5K to Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 5K time, find your equivalent marathon potential using the Daniels/Gilbert oxygen cost equation. 12 input times from 16:00 to 35:00.',
    h1:          '5K to Marathon Race Equivalency',
    openingParagraph:
      'Your 5K time reveals your current aerobic capacity. This table shows what that aerobic capacity predicts for the marathon — the equivalent time a runner with the same fitness would run, assuming full marathon-specific preparation. The formula is the Daniels/Gilbert oxygen cost equation; the caveat is that marathon performance requires distance-specific training that raw aerobic fitness alone does not provide.',
    accuracyNote:
      'The 5K → marathon prediction assumes comparable marathon training: 18–20 mile long runs, marathon-pace work, consistent high-volume build. Without this, most runners underperform their aerobic equivalency by 10–20 minutes. Use this as a potential ceiling and a training goal, not a race-day prediction without distance-specific preparation.',
    buildFaq: (data) => {
      const row20 = data.rows.find(r => r.inputTime === '20:00')
      const row25 = data.rows.find(r => r.inputTime === '25:00')
      const row17 = data.rows.find(r => r.inputTime === '17:00')
      return [
        {
          q: 'How accurate is the 5K to marathon equivalency?',
          a: `The Daniels/Gilbert formula is highly accurate for predicting aerobic potential — it gives the marathon time that the same aerobic capacity would support. The accuracy gap in practice comes from marathon-specific training: long runs, glycogen economy, and pacing experience. Runners with full marathon preparation tend to run within 5–10 minutes of their equivalency. Runners who are primarily 5K-trained typically underperform by 15–25 minutes due to insufficient long-run adaptation.`,
        },
        {
          q: row20 ? `What is the marathon equivalent of a 20:00 5K?` : `How do I use this table?`,
          a: row20
            ? `A 20:00 5K gives an RPI of ${row20.rpi}. The equivalent marathon time is ${row20.outputTime} at ${row20.outputPaceMi}/mi. This assumes full marathon training. Without distance-specific long runs and marathon-pace work, expect to run 15–20 minutes slower.`
            : `Find your 5K time in the left column, then read across to the predicted marathon time. All predictions use the Daniels/Gilbert oxygen cost equation applied to both distances.`,
        },
        {
          q: row25 ? `What marathon does a 25:00 5K runner have fitness for?` : `Why does my marathon time differ from the prediction?`,
          a: row25
            ? `A 25:00 5K runner (RPI ${row25.rpi}) has the aerobic capacity for a ${row25.outputTime} marathon at ${row25.outputPaceMi}/mi. The most common reason for underperforming this: insufficient long run mileage. The marathon wall at mile 20–22 is a glycogen problem, not an aerobic fitness problem. Long runs of 18–20 miles train the body to run on fat-based fuel at marathon pace — without them, aerobic capacity alone cannot prevent the wall.`
            : `The most common cause is insufficient marathon-specific training. The 5K equivalency predicts aerobic potential, not distance-specific readiness. The marathon demands adaptations — long-run glycogen economy, marathon-pace stamina — that 5K training does not develop.`,
        },
      ]
    },
  },

  '10k-to-half-marathon': {
    title:       '10K to Half Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 10K time, find your equivalent half marathon potential. The most physiologically accurate distance-pair for cross-distance prediction.',
    h1:          '10K to Half Marathon Race Equivalency',
    openingParagraph:
      'The 10K and half marathon are the most physiologically similar standard race distances — both demand sustained effort near the lactate threshold for 30–90 minutes. This makes the 10K → half marathon equivalency the most reliable cross-distance prediction available. The table below shows predicted half marathon times for a range of 10K inputs, all computed from the Daniels/Gilbert oxygen cost equation.',
    accuracyNote:
      'The 10K → half marathon prediction is the most accurate in the equivalency system. Both distances tax the same aerobic and threshold energy systems. Runners with consistent weekly training at both distances typically match their equivalency within two to four minutes. The main divergence factor: half marathon-specific long runs (12–15 miles) develop pacing stamina that shorter training blocks do not.',
    buildFaq: (data) => {
      const row45 = data.rows.find(r => r.inputTime === '45:00')
      const row40 = data.rows.find(r => r.inputTime === '40:00')
      const row60 = data.rows.find(r => r.inputTime === '60:00')
      return [
        {
          q: 'How accurate is the 10K to half marathon equivalency?',
          a: `Very accurate — this is the most reliable cross-distance pair in running equivalency. The 10K and half marathon both require sustained effort near lactate threshold, so the aerobic capacity measured by the 10K closely predicts half marathon performance. Most consistently trained runners fall within three to five minutes of their prediction. The gap widens for runners who have done much more 10K-specific training than half marathon preparation.`,
        },
        {
          q: row45 ? `What half marathon time does a 45:00 10K predict?` : `How do I use this table?`,
          a: row45
            ? `A 45:00 10K gives an RPI of ${row45.rpi}. The equivalent half marathon is ${row45.outputTime} at ${row45.outputPaceMi}/mi. This assumes comparable half marathon preparation. If you have only raced 10Ks and not half marathons, add 3–5 minutes for unfamiliarity with the longer distance until you have race-specific experience.`
            : `Find your 10K time in the left column and read across to the predicted half marathon time. Use this as a goal-setting tool when you have a recent 10K result but are targeting your first or next half marathon.`,
        },
        {
          q: row40
            ? `If I can run ${row40.inputTime} for 10K, what half marathon time is realistic?`
            : `What is the relationship between 10K and half marathon pace?`,
          a: row40
            ? `A ${row40.inputTime} 10K runner (RPI ${row40.rpi}) has the aerobic capacity for a ${row40.outputTime} half marathon. Half marathon race pace (${row40.outputPaceMi}/mi) runs about 10–15 seconds per mile slower than 10K race pace — which is exactly what the lactate threshold demands of running 13.1 miles versus 6.2 miles. Train at threshold pace and your half marathon time will naturally drop toward its equivalent.`
            : `Half marathon pace runs approximately 10–15 seconds per mile slower than 10K pace for most runners. This is the lactate threshold at work: the longer the sustained effort, the slightly lower the sustainable intensity. The Daniels formula captures this relationship precisely.`,
        },
      ]
    },
  },
}

// ============================================================================
// PAGE
// ============================================================================

interface Props {
  params: { conversion: string }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const config = CONVERSION_PAGE_CONFIG[params.conversion]
  if (!config) return {}
  return {
    title: config.title,
    description: config.description,
    alternates: {
      canonical: `https://strideiq.run/tools/race-equivalency/${params.conversion}`,
    },
    openGraph: {
      url: `https://strideiq.run/tools/race-equivalency/${params.conversion}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: config.title }],
    },
  }
}

export function generateStaticParams() {
  return Object.keys(equivalencyData)
    .filter((k) => k !== '_meta')
    .map((conversion) => ({ conversion }))
}

function EquivalencyTable({ data }: { data: EquivTable }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400">
            <th className="text-left py-3 px-3">{data.inputDistance} Time</th>
            <th className="text-center py-3 px-2 text-xs">RPI</th>
            <th className="text-center py-3 px-3">{data.outputDistance} Equivalent</th>
            <th className="text-center py-3 px-3">Equiv Pace</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.inputTime} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="py-2.5 px-3 font-semibold text-slate-200">{row.inputTime}</td>
              <td className="text-center py-2.5 px-2 text-slate-500 text-xs">{row.rpi}</td>
              <td className="text-center py-2.5 px-3 text-orange-400 font-semibold">{row.outputTime}</td>
              <td className="text-center py-2.5 px-3 text-slate-400">
                {row.outputPaceMi}/mi
                <span className="text-xs text-slate-600 ml-1">({row.outputPaceKm}/km)</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-500 mt-2">
        Computed via Daniels/Gilbert oxygen cost equation (1979). Predictions assume distance-specific training is in place.
      </p>
    </div>
  )
}

export default function ConversionPage({ params }: Props) {
  const config = CONVERSION_PAGE_CONFIG[params.conversion]
  if (!config) notFound()

  const data = (equivalencyData as unknown as Record<string, EquivTable>)[params.conversion]
  if (!data) notFound()

  const faq = config.buildFaq(data)

  // Pick a representative mid-table row for BLUF
  const midRow = data.rows[Math.floor(data.rows.length / 2)]
  const firstRow = data.rows[0]
  const lastRow = data.rows[data.rows.length - 1]

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Race Equivalency', item: 'https://strideiq.run/tools/race-equivalency' },
      { '@type': 'ListItem', position: 3, name: config.h1, item: `https://strideiq.run/tools/race-equivalency/${params.conversion}` },
    ],
  }

  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map((item) => ({
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
          <Link href="/tools/race-equivalency" className="hover:text-orange-400 transition-colors">Race Equivalency</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">{config.h1}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">{config.h1}</h1>

        <p className="text-slate-300 leading-relaxed mb-8">{config.openingParagraph}</p>

        {/* BLUF — numbers from JSON */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            A {midRow.inputTime} {data.inputDistance} runner (RPI {midRow.rpi}) has equivalent{' '}
            {data.outputDistance} fitness of {midRow.outputTime} ({midRow.outputPaceMi}/mi).
            Range in this table: {firstRow.inputTime} {data.inputDistance} → {firstRow.outputTime}{' '}
            {data.outputDistance} through {lastRow.inputTime} → {lastRow.outputTime}.
          </p>
        </div>

        {/* Equivalency table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">
            {data.inputDistance} → {data.outputDistance} Equivalency Table
          </h2>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl">
            <EquivalencyTable data={data} />
          </div>
        </section>

        {/* Accuracy note */}
        <section className="mb-10">
          <div className="bg-slate-800/60 border border-slate-700/30 rounded-xl p-5">
            <h3 className="font-semibold text-white mb-2">How accurate is this prediction?</h3>
            <p className="text-slate-300 text-sm leading-relaxed">{config.accuracyNote}</p>
          </div>
        </section>

        {/* N=1 CTA */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">Equivalency predicts potential — training determines actuals</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              This table shows what your aerobic capacity predicts at a different distance. StrideIQ
              tracks whether your training is actually developing the distance-specific fitness needed
              to meet that potential — long-run adaptation, pacing control, threshold stamina — from
              your own workout data.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools/training-pace-calculator" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                Find your training paces →
              </Link>
              <Link href="/register" className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors">
                Start free trial
              </Link>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-6">Common questions</h2>
          <div className="space-y-5">
            {faq.map((item, i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="font-semibold text-white mb-2">{item.q}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Related */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Related</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/race-equivalency" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Race Equivalency Hub →
            </Link>
            {Object.keys(CONVERSION_PAGE_CONFIG)
              .filter((k) => k !== params.conversion)
              .map((k) => (
                <Link
                  key={k}
                  href={`/tools/race-equivalency/${k}`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors"
                >
                  {CONVERSION_PAGE_CONFIG[k].h1} →
                </Link>
              ))}
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator →
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
