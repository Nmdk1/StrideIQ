import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import trainingPaceData from '@/data/training-pace-tables.json'

const DISTANCE_CONFIG: Record<string, {
  slug: string
  label: string
  distKey: string
  title: string
  description: string
  h1: string
  bluf: string
  zoneNotes: string
  commonMistakes: string
  faq: { q: string; a: string }[]
}> = {
  '5k-training-paces': {
    slug: '5k-training-paces',
    label: '5K',
    distKey: '5k',
    title: '5K Training Paces — Personalized Pace Zones from Race Time',
    description:
      'Free 5K training pace table. Find your Easy, Marathon, Threshold, Interval, and Repetition paces based on your current 5K time. Daniels/Gilbert oxygen cost equations.',
    h1: '5K Training Paces',
    bluf:
      'Your 5K training paces depend on your current race fitness, not generic advice. A 20:00 5K runner (RPI 49.8) trains at 8:29/mi easy, 6:49/mi threshold, and 5:58/mi intervals. A 25:00 runner (RPI 38.3) trains at 10:15/mi easy, 8:02/mi threshold, and 7:00/mi intervals. The table below shows exact paces for common 5K times.',
    zoneNotes:
      'For 5K training, the most impactful sessions are Interval pace (I) and Threshold pace (T). Interval pace targets VO2max — the engine that powers 5K racing. Threshold pace builds the aerobic foundation that lets you sustain hard effort. Easy pace makes up 80% of your weekly running and should feel genuinely easy — conversational, relaxed, no strain. Running easy days too fast is the most common training mistake and the easiest to fix.',
    commonMistakes:
      'The biggest 5K training mistake is running easy days at threshold effort. If your easy runs feel "moderate" or you cannot hold a conversation, you are running too fast. The second mistake is skipping interval work — 5K racing demands VO2max development, and only interval-pace running provides that stimulus. A typical week should be 3–4 easy runs, 1 threshold session, and 1 interval session.',
    faq: [
      {
        q: 'How do I find my 5K training paces?',
        a: 'Enter your most recent 5K race time into the calculator below. It uses the Daniels/Gilbert oxygen cost equations to derive your RPI (Running Performance Index) and calculate five training pace zones: Easy, Marathon, Threshold, Interval, and Repetition. Use a time from the last 3–6 months for accuracy.',
      },
      {
        q: 'What is easy pace for 5K training?',
        a: 'Easy pace is the speed at which 80% of your weekly running should happen. For a 20:00 5K runner, easy pace is 8:29/mi or slower. It should feel effortless — you could hold a conversation without gasping. Running easy days too fast reduces recovery and blunts the training response from quality sessions.',
      },
      {
        q: 'How fast should my 5K interval sessions be?',
        a: 'Interval pace for 5K training is close to your current 5K race pace — or slightly faster for short repeats (800m–1200m). A 20:00 5K runner does intervals at 5:58/mi. These sessions should feel hard but controlled — you should finish each repeat knowing you could do one more. Typical sessions: 5×1000m or 4×1200m with equal-time rest.',
      },
    ],
  },
  '10k-training-paces': {
    slug: '10k-training-paces',
    label: '10K',
    distKey: '10k',
    title: '10K Training Paces — Personalized Pace Zones from Race Time',
    description:
      'Free 10K training pace table. Find your Easy, Marathon, Threshold, Interval, and Repetition paces based on your current 10K time. Daniels/Gilbert oxygen cost equations.',
    h1: '10K Training Paces',
    bluf:
      'Your 10K training paces depend on your current race fitness. A 45:00 10K runner (RPI 45.3) trains at 9:02/mi easy, 7:13/mi threshold, and 6:19/mi intervals. A 50:00 runner (RPI 40.0) trains at 9:54/mi easy, 7:47/mi threshold, and 6:48/mi intervals. The table below shows exact paces for common 10K times.',
    zoneNotes:
      'For 10K training, Threshold pace (T) is the most important session. The 10K demands sustained effort at 85–90% of VO2max for 30–60 minutes — exactly what threshold training develops. Tempo runs of 20–40 minutes at threshold pace are the backbone of 10K preparation. Interval pace develops top-end speed that makes threshold pace feel more comfortable. Easy running builds the aerobic base that supports everything else.',
    commonMistakes:
      'The most common 10K training mistake is racing every run. If your easy days feel like moderate effort, your threshold sessions cannot be properly hard — you are fatigued before you start. The second mistake is insufficient volume: most runners who race 10K well run 25–40 miles per week. You cannot out-speed a weak aerobic base at this distance.',
    faq: [
      {
        q: 'What are good training paces for a 45-minute 10K?',
        a: 'A 45:00 10K gives an RPI of 45.3. Training paces: Easy 9:02/mi, Marathon 7:39/mi, Threshold 7:13/mi, Interval 6:19/mi, Repetition 5:52/mi. Easy running should be at 9:02 or slower — genuinely relaxed. Threshold runs at 7:13 for 20–40 minutes. Intervals at 6:19 for 800m–1200m repeats.',
      },
      {
        q: 'How often should I do threshold runs for 10K training?',
        a: 'Once per week is standard. A typical 10K threshold session is 20–40 minutes at threshold pace (comfortably hard — you can speak in short phrases but not hold a conversation). Start with 20 minutes and build to 30–40 minutes over several weeks. Cruise intervals — 3–4 x 8 minutes with 1 minute rest — are an effective variation.',
      },
      {
        q: 'Should I do interval training for a 10K?',
        a: 'Yes — but less than for a 5K. One interval session per week (in addition to your threshold session) develops the VO2max ceiling that makes your threshold pace sustainable. Typical 10K interval sessions: 5×1000m or 4×1200m at interval pace with equal-time recovery jogs.',
      },
    ],
  },
  'half-marathon-training-paces': {
    slug: 'half-marathon-training-paces',
    label: 'Half Marathon',
    distKey: 'half',
    title: 'Half Marathon Training Paces — Personalized Pace Zones from Race Time',
    description:
      'Free half marathon training pace table. Find your Easy, Marathon, Threshold, Interval, and Repetition paces based on your race time. Daniels/Gilbert oxygen cost equations.',
    h1: 'Half Marathon Training Paces',
    bluf:
      'Your half marathon training paces depend on your current race fitness. A 1:45:00 half runner (RPI 42.6) trains at 9:27/mi easy, 7:29/mi threshold, and 6:33/mi intervals. A 2:00:00 runner (RPI 36.5) trains at 10:39/mi easy, 8:19/mi threshold, and 7:14/mi intervals. The table below shows exact paces for common half marathon times.',
    zoneNotes:
      'For half marathon training, Threshold pace and Marathon pace are the two most important zones. Threshold runs build the lactate clearance that lets you sustain half marathon effort for 75–120 minutes. Marathon-pace segments in long runs teach your body to hold a steady, controlled effort for extended duration. Easy running should make up at least 80% of your weekly volume — it builds the aerobic base that everything else relies on.',
    commonMistakes:
      'The biggest half marathon training mistake is running long runs too fast. Your long run should be at easy pace — the aerobic adaptation comes from time on feet, not from hammering every long run. The second mistake is neglecting threshold work: tempo runs at comfortably hard effort are the single most race-specific session for the half marathon. A weekly structure of 3–4 easy runs, 1 long run at easy pace, and 1 threshold session covers the essentials.',
    faq: [
      {
        q: 'What training paces should I use for a 1:45 half marathon goal?',
        a: 'A 1:45:00 half marathon gives an RPI of about 42.6. Training paces: Easy 9:27/mi, Marathon 7:56/mi, Threshold 7:29/mi, Interval 6:33/mi. Your goal race pace is about 8:00/mi — between marathon and threshold pace. Train at these specific paces, not at race pace, to build the fitness that supports your goal.',
      },
      {
        q: 'How important is easy pace for half marathon training?',
        a: 'Critical. Easy running should be 80% of your weekly volume. For a 2:00:00 half runner, easy pace is 10:39/mi or slower. Running easy days at 8:30 instead of 10:39 does not make you faster — it makes you too tired to run quality sessions properly. Slow down your easy days and you will race faster.',
      },
      {
        q: 'Should I do interval training for a half marathon?',
        a: 'Yes, but less than for shorter races. One interval session every 1–2 weeks develops VO2max, which raises the ceiling for your threshold and marathon pace. Threshold sessions (tempo runs at comfortably hard effort) are more important for half marathon fitness and should happen weekly.',
      },
    ],
  },
  'marathon-training-paces': {
    slug: 'marathon-training-paces',
    label: 'Marathon',
    distKey: 'marathon',
    title: 'Marathon Training Paces — Personalized Pace Zones from Race Time',
    description:
      'Free marathon training pace table. Find your Easy, Marathon, Threshold, Interval, and Repetition paces based on your race time. Daniels/Gilbert oxygen cost equations.',
    h1: 'Marathon Training Paces',
    bluf:
      'Your marathon training paces depend on your current race fitness. A 3:30:00 marathon runner (RPI 44.6) trains at 9:08/mi easy, 7:17/mi threshold, and 6:23/mi intervals. Marathon-pace training runs at 7:43/mi. A 4:00:00 runner (RPI 37.9) trains at 10:20/mi easy, 8:05/mi threshold, and 7:03/mi intervals with marathon-pace runs at 8:35/mi. The table below shows exact paces for common marathon times.',
    zoneNotes:
      'For marathon training, Marathon pace (M) and Easy pace (E) are the most critical zones. Marathon-pace long runs — running the final 6–10 miles of a long run at goal marathon pace — are the most race-specific session. They teach your body to sustain effort when glycogen is depleted, which is exactly what the last 10K of a marathon demands. Easy pace makes up 80%+ of your weekly volume: this is where aerobic capillary density and fat oxidation develop. Threshold runs build the stamina buffer above marathon pace.',
    commonMistakes:
      'The marathon has the highest mistake rate of any distance. The #1 error: going out too fast on race day. Your first 10K should feel almost too easy — if it feels "good," you are going too fast. The #2 error in training: insufficient weekly volume. Most runners who race well at the marathon run 40–60+ miles per week at peak. You cannot fake marathon fitness with speed work alone. The #3 error: running easy days at marathon pace. Easy pace for a 4:00 marathoner is 10:22/mi — not 9:09.',
    faq: [
      {
        q: 'What training paces should I use for a 3:30 marathon goal?',
        a: 'A 3:30:00 marathon gives an RPI of about 44.6. Training paces: Easy 9:08/mi, Marathon 7:43/mi, Threshold 7:17/mi, Interval 6:23/mi. Your marathon-pace long runs should target 7:43/mi for the final 8–10 miles. All other long runs should be at easy pace (9:08 or slower). Tempo runs at 7:17/mi for 20–30 minutes once per week.',
      },
      {
        q: 'How fast should easy runs be for marathon training?',
        a: 'Easy runs should be at your calculated easy pace or slower. For a 4:00:00 marathoner, that is 10:20/mi — often 1–2 minutes per mile slower than race pace. Most marathoners run their easy days too fast, which accumulates fatigue and prevents quality sessions from being truly high quality. If you are breathing hard on an easy day, slow down.',
      },
      {
        q: 'How many miles per week do I need for a marathon?',
        a: 'Peak weekly volume depends on your goal and experience. General guidelines: sub-4:00 typically requires 35–45 miles/week at peak; sub-3:30 requires 40–55; sub-3:00 requires 55–70+. More important than the peak is consistency — 12–16 weeks of steady volume building matters more than one big week. Easy running should be 80% of that volume.',
      },
    ],
  },
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
      canonical: `https://strideiq.run/tools/training-pace-calculator/${config.slug}`,
    },
    openGraph: {
      url: `https://strideiq.run/tools/training-pace-calculator/${config.slug}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: config.title }],
    },
  }
}

export function generateStaticParams() {
  return Object.keys(DISTANCE_CONFIG).map((distance) => ({ distance }))
}

function PaceTable({ rows }: { rows: any[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400">
            <th className="text-left py-3 px-2">Race Time</th>
            <th className="text-center py-3 px-1 text-xs">RPI</th>
            <th className="text-center py-3 px-2">Easy</th>
            <th className="text-center py-3 px-2">Marathon</th>
            <th className="text-center py-3 px-2">Threshold</th>
            <th className="text-center py-3 px-2">Interval</th>
            <th className="text-center py-3 px-2">Repetition</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any) => (
            <tr key={row.raceTime} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="py-2.5 px-2 font-semibold text-slate-200">{row.raceTime}</td>
              <td className="text-center py-2.5 px-1 text-slate-500 text-xs">{row.rpi}</td>
              <td className="text-center py-2.5 px-2 text-slate-400">{row.paces.easy?.mi || '—'}</td>
              <td className="text-center py-2.5 px-2 text-orange-400">{row.paces.marathon?.mi || '—'}</td>
              <td className="text-center py-2.5 px-2 text-green-400">{row.paces.threshold?.mi || '—'}</td>
              <td className="text-center py-2.5 px-2 text-blue-400">{row.paces.interval?.mi || '—'}</td>
              <td className="text-center py-2.5 px-2 text-purple-400">{row.paces.repetition?.mi || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-500 mt-2">All paces in minutes per mile. Easy pace means &quot;this pace or slower.&quot;</p>
    </div>
  )
}

export default function TrainingPaceDistancePage({ params }: Props) {
  const config = DISTANCE_CONFIG[params.distance]
  if (!config) notFound()

  const data = (trainingPaceData as any)[config.distKey]
  if (!data) notFound()

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Training Pace Calculator', item: 'https://strideiq.run/tools/training-pace-calculator' },
      { '@type': 'ListItem', position: 3, name: config.h1, item: `https://strideiq.run/tools/training-pace-calculator/${config.slug}` },
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
          <Link href="/tools/training-pace-calculator" className="hover:text-orange-400 transition-colors">Training Pace Calculator</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">{config.h1}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">{config.h1}</h1>

        {/* BLUF */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            {config.bluf}
          </p>
        </div>

        {/* Pace table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">{config.label} Training Pace Table</h2>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl">
            <PaceTable rows={data.rows} />
          </div>
        </section>

        {/* Zone explanations */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">What each training zone does</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300">
            <p>{config.zoneNotes}</p>
          </div>
        </section>

        {/* Common mistakes */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Common {config.label} training mistakes</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300">
            <p>{config.commonMistakes}</p>
          </div>
        </section>

        {/* Calculator embed */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Calculate your exact training paces</h2>
          <p className="text-slate-400 mb-4">
            The table shows paces for common {config.label} times. Enter your exact race time below to get your personalized training paces.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 shadow-xl">
            <TrainingPaceCalculator />
          </div>
        </section>

        {/* N=1 hook */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">Your paces are a starting point</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              These paces are calculated from your race result — they reflect your current fitness as a single number. StrideIQ goes deeper: it learns how your body responds to training over time, identifies which sessions produce your biggest fitness gains, and adapts daily based on your actual data. Population-based paces get you started. Individual response data keeps you improving.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                Try the free calculators
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
          <h2 className="text-xl font-bold mb-4">Training paces for other distances</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(DISTANCE_CONFIG)
              .filter(([key]) => key !== params.distance)
              .map(([key, cfg]) => (
                <Link
                  key={key}
                  href={`/tools/training-pace-calculator/${key}`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors"
                >
                  {cfg.h1} &rarr;
                </Link>
              ))}
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Full Calculator &rarr;
            </Link>
          </div>
        </section>

        {/* Data source */}
        <div className="mt-8 text-xs text-slate-500">
          <p>
            Paces calculated using the Daniels/Gilbert oxygen cost equations — peer-reviewed exercise physiology published in 1979.
            These are the same formulas used by the StrideIQ training pace calculator. All paces fetched from the live calculator to ensure exact consistency.
          </p>
        </div>
      </div>
    </div>
  )
}
