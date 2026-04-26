import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import WMACalculator from '@/app/components/tools/WMACalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import { SignupCtaLink } from '@/components/tools/SignupCtaLink'
import ageGradingData from '@/data/age-grading-tables.json'

const DISTANCE_CONFIG: Record<string, {
  slug: string
  label: string
  title: string
  description: string
  h1: string
  bluf: string
  trainingNotes: string
  faq: { q: string; a: string }[]
}> = {
  'good-5k-times-by-age': {
    slug: 'good-5k-times-by-age',
    label: '5K',
    title: 'Good 5K Times by Age — WMA Age-Graded Benchmarks',
    description:
      'What is a good 5K time for your age? See WMA age-graded benchmarks for men and women from age 30 to 80. Performance levels from recreational to world class with actual times and paces.',
    h1: 'Good 5K Times by Age',
    bluf:
      'A good 5K time depends on your age and sex. Using WMA (World Masters Athletics) age-grading standards, a 50-year-old male running 24:21 scores 60% — "Local Class." A 70% Regional Class performance at that age requires 20:52. These are real benchmarks derived from world-record data, not generic estimates.',
    trainingNotes:
      'The 5K is the most aerobically demanding short race. At competitive levels, it requires strong VO2max — your ability to process oxygen at high intensity for 15–25 minutes. Training should emphasize threshold and interval work once a base of easy running is established. Most runners improve their 5K dramatically by running more easy miles, not more speed work.',
    faq: [
      {
        q: 'What is a good 5K time for a beginner?',
        a: 'For a true beginner, finishing a 5K at any pace is the goal. A sub-35:00 first 5K is solid. Within 6–12 months of consistent training, most runners reach 25:00–30:00. WMA age-grading shows that a 50% score (recreational) is around 25:38 for a 30-year-old male — that is a reasonable early target.',
      },
      {
        q: 'How does age affect 5K performance?',
        a: 'WMA data shows 5K performance declines roughly 3–5% per decade from age 30–60, then accelerates after 65. A 30-year-old male at 70% age-grade runs 18:19; a 60-year-old at the same 70% grade runs 22:40. The decline is real but slower than most people assume before age 65.',
      },
      {
        q: 'Is a sub-20 5K good for my age?',
        a: 'A sub-20:00 5K for a 30-year-old male is about 64% age-graded — solidly Local Class. For a 55-year-old male, the same 20:00 scores 76% — well into Regional Class. For a 60-year-old it reaches 79%, approaching National Class. Age-grading contextualizes the same time differently depending on your age.',
      },
    ],
  },
  'good-10k-times-by-age': {
    slug: 'good-10k-times-by-age',
    label: '10K',
    title: 'Good 10K Times by Age — WMA Age-Graded Benchmarks',
    description:
      'What is a good 10K time for your age? See WMA age-graded benchmarks for men and women from age 30 to 80. Performance levels from recreational to world class with actual times and paces.',
    h1: 'Good 10K Times by Age',
    bluf:
      'A good 10K time depends on your age and sex. Using WMA age-grading standards, a 50-year-old male running 49:31 scores 60% — "Local Class." A 70% Regional Class performance at that age requires 42:27. These are real benchmarks derived from world-record data, not population surveys.',
    trainingNotes:
      'The 10K sits at the intersection of aerobic endurance and lactate threshold. Competitive 10K running requires a high percentage of VO2max sustained for 30–60 minutes. Threshold training — comfortably hard effort held for 20–40 minutes — is the single most impactful session for 10K improvement. Volume matters too: most runners who break 45:00 run 25+ miles per week consistently.',
    faq: [
      {
        q: 'What is a good 10K time for a 50 year old?',
        a: 'For a 50-year-old male, WMA benchmarks show: 49:31 = Local Class (60%), 42:27 = Regional Class (70%), 37:08 = National Class (80%). For a 50-year-old female, the equivalent times are 54:21, 46:35, and 40:46. These are computed from actual world-record data for each age group.',
      },
      {
        q: 'How fast should I run a 10K for my age?',
        a: 'There is no universal "should." WMA age-grading gives you a factual benchmark: your time as a percentage of the world record for your age and sex. 50% is recreational, 60% is competitive for a local race, 70% places you well at regional events, and 80%+ is national-level masters running.',
      },
      {
        q: 'Is a 50-minute 10K good?',
        a: 'For a 30-year-old male, a 50:00 10K is about 53% age-graded — recreational. For a 60-year-old male, the same 50:00 is about 65% — solidly Local Class. For a 70-year-old male, it is about 71% — Regional Class. Context matters more than the raw time.',
      },
    ],
  },
  'good-half-marathon-times-by-age': {
    slug: 'good-half-marathon-times-by-age',
    label: 'Half Marathon',
    title: 'Good Half Marathon Times by Age — WMA Age-Graded Benchmarks',
    description:
      'What is a good half marathon time for your age? See WMA age-graded benchmarks for men and women from age 30 to 80. Performance levels from recreational to world class with actual times and paces.',
    h1: 'Good Half Marathon Times by Age',
    bluf:
      'A good half marathon time depends on your age and sex. Using WMA age-grading standards, a 50-year-old male running 1:48:12 scores 60% — "Local Class." A 70% Regional Class performance at that age requires 1:32:44. These benchmarks are derived from world-record data for each age group.',
    trainingNotes:
      'The half marathon demands sustained aerobic power — running at or near your lactate threshold for 75–120 minutes. Training should emphasize threshold runs (tempo efforts at comfortably hard pace) and progression long runs where the final miles approach half marathon effort. Volume is important: most runners who race well at this distance run 30+ miles per week during their training block.',
    faq: [
      {
        q: 'What is a good half marathon time for beginners?',
        a: 'Finishing your first half marathon is the achievement. A 2:15–2:30 finish is common for first-timers with basic training. WMA age-grading shows a 50% score (recreational) for a 30-year-old male is about 1:55:02 — a reasonable first-timer goal with a structured training plan.',
      },
      {
        q: 'How does age affect half marathon performance?',
        a: 'Half marathon performance declines about 3–5% per decade through your 50s, then accelerates after 60. A 40-year-old male at 70% age-grade runs 1:25:15; a 60-year-old at the same grade runs 1:41:40. The endurance component of the half marathon ages well — many masters runners maintain strong half marathon fitness into their 60s.',
      },
      {
        q: 'Is a sub-2-hour half marathon good for my age?',
        a: 'For a 30-year-old male, sub-2:00 is about 48% age-graded — entry-level recreational. For a 60-year-old male, sub-2:00 scores about 59%. For a 70-year-old male, sub-2:00 is about 66% — solidly Local Class. The older you are, the more impressive the same time becomes.',
      },
    ],
  },
  'good-marathon-times-by-age': {
    slug: 'good-marathon-times-by-age',
    label: 'Marathon',
    title: 'Good Marathon Times by Age — WMA Age-Graded Benchmarks',
    description:
      'What is a good marathon time for your age? See WMA age-graded benchmarks for men and women from age 30 to 80. Performance levels from recreational to world class with actual times and paces.',
    h1: 'Good Marathon Times by Age',
    bluf:
      'A good marathon time depends on your age and sex. Using WMA age-grading standards, a 50-year-old male running 3:44:13 scores 60% — "Local Class." A 70% Regional Class performance at that age requires 3:12:12. These benchmarks are derived from world-record data, not average finish times from mass-participation events.',
    trainingNotes:
      'The marathon is an aerobic endurance event that punishes undertrained runners. Competitive marathon performance requires months of consistent volume — typically 40–60+ miles per week at peak. Marathon-pace long runs are the most race-specific session: running the final 6–10 miles of a long run at goal marathon pace teaches your body to hold pace when glycogen-depleted. Most runners fail at the marathon because they train too fast on easy days and race without enough total volume.',
    faq: [
      {
        q: 'What is a good marathon time for a 40 year old?',
        a: 'For a 40-year-old male, WMA benchmarks show: 3:25:26 = Local Class (60%), 2:56:05 = Regional Class (70%), 2:34:05 = National Class (80%). For a 40-year-old female, the equivalent times are 3:43:43, 3:11:46, and 2:47:48. These are computed from world-record data, not average finishers.',
      },
      {
        q: 'Is a 4-hour marathon good for my age?',
        a: 'For a 30-year-old male, a 4:00:00 marathon is about 50% age-graded — recreational. For a 55-year-old male, the same time scores about 59%. For a 65-year-old male, it is about 65% — solidly Local Class. Marathon average finish times at mass events are typically 4:30–5:00, so sub-4:00 at any age is faster than most participants.',
      },
      {
        q: 'How much slower should I expect to be in my 50s vs 30s at the marathon?',
        a: 'WMA data shows about 15–17% slowdown from age 30 to 55 at the same performance level. A 30-year-old male at 70% age-grade runs 2:52:16; a 55-year-old at the same grade runs 3:21:25 — about 29 minutes slower. The marathon degrades slightly more with age than shorter distances because it taxes recovery and glycogen systems more heavily.',
      },
    ],
  },
}

const DISTANCE_KEY_MAP: Record<string, string> = {
  'good-5k-times-by-age': '5k',
  'good-10k-times-by-age': '10k',
  'good-half-marathon-times-by-age': 'half',
  'good-marathon-times-by-age': 'marathon',
}

interface Props {
  params: { distance: string }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const config = DISTANCE_CONFIG[params.distance]
  if (!config) return {}
  return {
    title: config.title,
    description: config.description,
    alternates: {
      canonical: `https://strideiq.run/tools/age-grading-calculator/${config.slug}`,
    },
    openGraph: {
      title: config.title,
      description: config.description,
      url: `https://strideiq.run/tools/age-grading-calculator/${config.slug}`,
      siteName: 'StrideIQ',
      type: 'website',
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: config.title }],
    },
    twitter: {
      card: 'summary_large_image',
      title: config.title,
      description: config.description,
    },
  }
}

export function generateStaticParams() {
  return Object.keys(DISTANCE_CONFIG).map((distance) => ({ distance }))
}

function TimeTable({ rows, gender }: { rows: any[]; gender: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400">
            <th className="text-left py-3 px-2">Age</th>
            <th className="text-center py-3 px-2">Recreational<br /><span className="text-xs font-normal">50%</span></th>
            <th className="text-center py-3 px-2">Local Class<br /><span className="text-xs font-normal">60%</span></th>
            <th className="text-center py-3 px-2">Regional<br /><span className="text-xs font-normal">70%</span></th>
            <th className="text-center py-3 px-2">National<br /><span className="text-xs font-normal">80%</span></th>
            <th className="text-center py-3 px-2">World Class<br /><span className="text-xs font-normal">90%</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any) => (
            <tr key={row.age} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="py-2.5 px-2 font-semibold text-slate-200">{row.age}</td>
              <td className="text-center py-2.5 px-2 text-slate-400">{row.levels['50'].timeFormatted}<br /><span className="text-xs text-slate-500">{row.levels['50'].pace}/mi</span></td>
              <td className="text-center py-2.5 px-2 text-teal-400">{row.levels['60'].timeFormatted}<br /><span className="text-xs text-slate-500">{row.levels['60'].pace}/mi</span></td>
              <td className="text-center py-2.5 px-2 text-green-400">{row.levels['70'].timeFormatted}<br /><span className="text-xs text-slate-500">{row.levels['70'].pace}/mi</span></td>
              <td className="text-center py-2.5 px-2 text-blue-400">{row.levels['80'].timeFormatted}<br /><span className="text-xs text-slate-500">{row.levels['80'].pace}/mi</span></td>
              <td className="text-center py-2.5 px-2 text-purple-400">{row.levels['90'].timeFormatted}<br /><span className="text-xs text-slate-500">{row.levels['90'].pace}/mi</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function AgeGradingDistancePage({ params }: Props) {
  const config = DISTANCE_CONFIG[params.distance]
  if (!config) notFound()

  const dataKey = DISTANCE_KEY_MAP[params.distance]
  const data = (ageGradingData as any)[dataKey]
  if (!data) notFound()

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Age-Grading Calculator', item: 'https://strideiq.run/tools/age-grading-calculator' },
      { '@type': 'ListItem', position: 3, name: config.h1, item: `https://strideiq.run/tools/age-grading-calculator/${config.slug}` },
    ],
  }

  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: config.faq.map((item) => ({
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
          <Link href="/tools/age-grading-calculator" className="hover:text-orange-400 transition-colors">Age-Grading Calculator</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">{config.h1}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">{config.h1}</h1>

        {/* BLUF — answer capsule for AI extraction */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            {config.bluf}
          </p>
        </div>

        {/* Male table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Men&apos;s {config.label} Times by Age</h2>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl">
            <TimeTable rows={data.male} gender="male" />
          </div>
        </section>

        {/* Female table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Women&apos;s {config.label} Times by Age</h2>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl">
            <TimeTable rows={data.female} gender="female" />
          </div>
        </section>

        {/* What the levels mean */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">What the performance levels mean</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-3">
            <ul className="space-y-2">
              <li><strong className="text-purple-400">World Class (90%+)</strong> — National or world age-group record territory. Very few runners at any age reach this level.</li>
              <li><strong className="text-blue-400">National Class (80–89%)</strong> — Competitive at national masters championships. Requires serious, structured training over years.</li>
              <li><strong className="text-green-400">Regional Class (70–79%)</strong> — Strong age-group placements at regional and larger local races. Consistent training with quality sessions.</li>
              <li><strong className="text-teal-400">Local Class (60–69%)</strong> — Competitive in local races. Solid fitness from regular running and some structured training.</li>
              <li><strong className="text-slate-400">Recreational (below 60%)</strong> — Running for fitness and enjoyment. Most runners start here and can improve significantly with consistent training.</li>
            </ul>
          </div>
        </section>

        {/* Training notes */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Training for a faster {config.label}</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300">
            <p>{config.trainingNotes}</p>
          </div>
        </section>

        {/* Calculator embed */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Calculate your exact age-graded score</h2>
          <p className="text-slate-400 mb-4">
            The table above shows benchmarks at round performance levels. Enter your exact race time below to see your precise WMA age-graded percentage.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 shadow-xl">
            <WMACalculator />
          </div>
        </section>

        {/* N=1 hook */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">These are population benchmarks</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              WMA age-grading tells you how your time compares to world-record standards. StrideIQ goes further — it tracks your individual recovery patterns, efficiency trends, and supercompensation curves from your own training data. Population benchmarks are a starting point. Your body&apos;s individual response is where real coaching begins.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                Try the free calculators
              </Link>
              <SignupCtaLink className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors" telemetry={{ cta: 'age_grade_distance_hook' }}>
                Start free trial
              </SignupCtaLink>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-6">Common questions</h2>
          <div className="space-y-5">
            {config.faq.map((item, i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="font-semibold text-white mb-2">{item.q}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Related pages */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">See times for other distances</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(DISTANCE_CONFIG)
              .filter(([key]) => key !== params.distance)
              .map(([key, cfg]) => (
                <Link
                  key={key}
                  href={`/tools/age-grading-calculator/${key}`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors"
                >
                  {cfg.h1} &rarr;
                </Link>
              ))}
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Full Calculator &rarr;
            </Link>
          </div>
        </section>

        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Other running calculators</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator &rarr;
            </Link>
            <Link href="/tools/race-equivalency" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Race Equivalency &rarr;
            </Link>
            <Link href="/tools/boston-qualifying" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Boston Qualifying Times &rarr;
            </Link>
            <Link href="/tools/heat-adjusted-pace" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Heat-Adjusted Pace &rarr;
            </Link>
          </div>
        </section>

        {/* Data source */}
        <div className="mt-8 text-xs text-slate-500">
          <p>
            Data source: Alan Jones 2025 WMA Road Age-Grading Tables, approved by USATF Masters Long Distance Running Council (January 2025).
            Times computed from official age-factor tables and open-class world-record standards.
          </p>
        </div>
      </div>
    </div>
  )
}
