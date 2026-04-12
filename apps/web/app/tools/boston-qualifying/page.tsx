import type { Metadata } from 'next'
import Link from 'next/link'
import { JsonLd } from '@/components/seo/JsonLd'
import { SignupCtaLink } from '@/components/tools/SignupCtaLink'

export const metadata: Metadata = {
  title: 'Boston Marathon Qualifying Times 2026 — All Age Groups',
  description:
    'Official 2026 BAA Boston qualifying standards for all age groups, with training paces and WMA age-grade equivalents. Men and women 18–80+.',
  alternates: { canonical: 'https://strideiq.run/tools/boston-qualifying' },
  openGraph: {
    title: 'Boston Marathon Qualifying Times 2026 — All Age Groups',
    description:
      'Official 2026 BAA Boston qualifying standards by age and gender, with Daniels/Gilbert training paces for each standard.',
    url: 'https://strideiq.run/tools/boston-qualifying',
    siteName: 'StrideIQ',
    type: 'website',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'Boston Qualifying Times 2026' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Boston Marathon Qualifying Times 2026',
    description: 'Full BQ standards table plus per age-group training paces and equivalencies.',
  },
}

const BQ_TABLE = [
  { group: '18–34', men: '2:55:00', women: '3:25:00', menSlug: 'boston-qualifying-time-men-18-34',    womenSlug: 'boston-qualifying-time-women-18-34'    },
  { group: '35–39', men: '3:00:00', women: '3:30:00', menSlug: 'boston-qualifying-time-men-35-39',    womenSlug: 'boston-qualifying-time-women-35-39'    },
  { group: '40–44', men: '3:05:00', women: '3:35:00', menSlug: 'boston-qualifying-time-men-40-44',    womenSlug: 'boston-qualifying-time-women-40-44'    },
  { group: '45–49', men: '3:15:00', women: '3:45:00', menSlug: 'boston-qualifying-time-men-45-49',    womenSlug: 'boston-qualifying-time-women-45-49'    },
  { group: '50–54', men: '3:20:00', women: '3:50:00', menSlug: 'boston-qualifying-time-men-50-54',    womenSlug: 'boston-qualifying-time-women-50-54'    },
  { group: '55–59', men: '3:30:00', women: '4:00:00', menSlug: 'boston-qualifying-time-men-55-59',    womenSlug: 'boston-qualifying-time-women-55-59'    },
  { group: '60–64', men: '3:50:00', women: '4:20:00', menSlug: 'boston-qualifying-time-men-60-64',    womenSlug: 'boston-qualifying-time-women-60-64'    },
  { group: '65–69', men: '4:05:00', women: '4:35:00', menSlug: 'boston-qualifying-time-men-65-69',    womenSlug: 'boston-qualifying-time-women-65-69'    },
  { group: '70–74', men: '4:20:00', women: '4:50:00', menSlug: 'boston-qualifying-time-men-70-74',    womenSlug: 'boston-qualifying-time-women-70-74'    },
  { group: '75–79', men: '4:35:00', women: '5:05:00', menSlug: 'boston-qualifying-time-men-75-79',    womenSlug: 'boston-qualifying-time-women-75-79'    },
  { group: '80+',   men: '4:50:00', women: '5:20:00', menSlug: 'boston-qualifying-time-men-80-plus',  womenSlug: 'boston-qualifying-time-women-80-plus'  },
]

const FAQ_ITEMS = [
  {
    q: 'What is a Boston Qualifying time?',
    a: 'A Boston Qualifying (BQ) time is the BAA-set marathon standard for your age group and gender. Running a BQ is necessary but not sufficient for entry — BAA applies a cutoff buffer each year based on how many runners qualify. The table above shows the official 2026 standards.',
  },
  {
    q: 'Does running a BQ time guarantee Boston entry?',
    a: 'No. The BAA requires a BQ time to register, but entry is competitive: when more runners qualify than the field allows, BAA applies a cutoff buffer, accepting only those who ran the most under their BQ standard. In recent years the cutoff has ranged from about 2 to 7 minutes under the BQ standard. Check the official BAA site for the current year\'s cutoff.',
  },
  {
    q: 'What is a good BQ buffer to train for?',
    a: 'Most coaches recommend targeting 5–10 minutes under your BQ standard to have a reasonable probability of entry. Training for exactly the BQ time is a ceiling race; training well below it — and racing conservatively — is the realistic strategy.',
  },
  {
    q: 'When is the 2026 Boston Marathon?',
    a: 'The 2026 Boston Marathon is held on Patriots\' Day in April. Check baa.org for the exact date and registration timeline for your qualifying window.',
  },
]

const breadcrumbJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
    { '@type': 'ListItem', position: 2, name: 'Boston Qualifying Times', item: 'https://strideiq.run/tools/boston-qualifying' },
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

export default function BQHubPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={breadcrumbJsonLd} />
      <JsonLd data={faqJsonLd} />

      <div className="max-w-5xl mx-auto px-6 py-12">
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/tools" className="hover:text-orange-400 transition-colors">Tools</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Boston Qualifying Times</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">
          2026 Boston Marathon Qualifying Times
        </h1>

        <p className="text-slate-300 leading-relaxed mb-8">
          The Boston Athletic Association sets qualifying standards by age group and gender. Running
          a BQ time opens the registration window — but entry is not guaranteed. Each year, BAA
          applies a cutoff buffer based on how many runners qualify relative to the available field.
          The table below shows the official 2026 standards. Click any age group to see the training
          paces and fitness profile that standard requires.
        </p>

        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">How to use this:</strong>{' '}
            Find your age group and gender in the table below. Click the time to see the exact
            training paces (easy, threshold, interval) required to build that fitness, plus
            WMA age-graded equivalents and equivalent times at 5K, 10K, and half marathon.
          </p>
        </div>

        {/* BQ Standards Table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">2026 BQ Standards — All Age Groups</h2>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400">
                  <th className="text-left py-3 px-3">Age Group</th>
                  <th className="text-center py-3 px-4">Men</th>
                  <th className="text-center py-3 px-4">Women &amp; Non-Binary</th>
                </tr>
              </thead>
              <tbody>
                {BQ_TABLE.map((row) => (
                  <tr key={row.group} className="border-b border-slate-800 hover:bg-slate-800/50">
                    <td className="py-3 px-3 font-semibold text-slate-200">{row.group}</td>
                    <td className="text-center py-3 px-4">
                      <Link
                        href={`/tools/boston-qualifying/${row.menSlug}`}
                        className="text-orange-400 hover:text-orange-300 font-mono font-semibold transition-colors"
                      >
                        {row.men}
                      </Link>
                    </td>
                    <td className="text-center py-3 px-4">
                      <Link
                        href={`/tools/boston-qualifying/${row.womenSlug}`}
                        className="text-blue-400 hover:text-blue-300 font-mono font-semibold transition-colors"
                      >
                        {row.women}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-slate-500 mt-3">
              Source: Boston Athletic Association 2026 qualifying standards. Verified 2026-02-26.
            </p>
          </div>
        </section>

        {/* How BQ Works */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">How Boston Qualifying Works</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-4">
            <p>
              Running a BQ time is the first gate. The BAA requires you to run the standard
              for your age group at a certified marathon within the qualifying window (roughly
              September through the following September for the next year&apos;s race).
            </p>
            <p>
              The second gate is the cutoff. When registrations open, runners submit their qualifying
              times. If more runners qualify than the field allows, BAA fills spots starting with
              those who ran most under their BQ standard. The cutoff varies annually — check the
              official BAA registration updates for the current year&apos;s exact figure.
            </p>
            <p>
              The practical implication: a BQ time is a floor, not a guarantee. Most runners who
              want confident entry target 5–10 minutes under their standard.
            </p>
          </div>
        </section>

        {/* Training note */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">BQ times require specific training paces</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              Each BQ standard has a corresponding set of training zones derived from the Daniels/Gilbert
              oxygen cost formula — the same formula used by elite coaches and the StrideIQ training pace
              calculator. Click your age group above to see the exact easy, threshold, and interval paces
              required to build BQ-level fitness.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools/training-pace-calculator" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                Training pace calculator →
              </Link>
              <SignupCtaLink className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors" telemetry={{ cta: 'bq_hub_hook' }}>
                Start free trial
              </SignupCtaLink>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="mb-10">
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

        <section className="border-t border-slate-800 pt-8 mb-10">
          <h2 className="text-xl font-bold mb-4">Related calculators</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator →
            </Link>
            <Link href="/tools/race-equivalency/marathon-to-5k" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Race Equivalency →
            </Link>
            <Link href="/tools/heat-adjusted-pace" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Heat-Adjusted Pace →
            </Link>
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Age-Grading Calculator →
            </Link>
          </div>
        </section>

        <div className="mt-8 text-xs text-slate-500">
          <p>
            BQ standards from the Boston Athletic Association official qualification page.
            Training paces computed via Daniels/Gilbert oxygen cost equations (1979).
            WMA age-grading from Alan Jones 2025 standards.
          </p>
        </div>
      </div>
    </div>
  )
}
