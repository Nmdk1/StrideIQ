import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import WMACalculator from '@/app/components/tools/WMACalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import ageDemoData from '@/data/age-gender-tables.json'

// ============================================================================
// TYPES — mirror the schema in age-gender-tables.json
// ============================================================================

type TrainingPaces = {
  easy:      { mi: string; km: string }
  threshold: { mi: string; km: string }
  interval:  { mi: string; km: string }
}

type LevelEntry = {
  label:         string
  timeSeconds:   number
  timeFormatted: string
  paceMi:        string
  rpi:           number | null
  trainingPaces: TrainingPaces | null
}

type DemoRow = {
  age:                number
  ageFactor:          number
  ageStandardSeconds: number
  levels: Record<string, LevelEntry>
}

type DemoEntry = {
  slug:           string
  gender:         string
  genderLabel:    string
  distance:       string
  distanceMeters: number
  ageDecade:      string
  ageRange:       string
  ages:           number[]
  rows:           DemoRow[]
}

// ============================================================================
// STATIC PER-PAGE CONFIG
// All numeric claims in BLUF/FAQ are computed from ageDemoData JSON.
// Only coaching philosophy and non-numeric context are hardcoded here.
// ============================================================================

const DEMO_PAGE_CONFIG: Record<
  string,
  {
    title: string
    description: string
    h1: string
    openingParagraph: string
    trainingContext: string
    buildFaq: (data: DemoEntry) => { q: string; a: string }[]
  }
> = {
  '5k-times-women-age-40s': {
    title: "Good 5K Times for Women in Their 40s — WMA Benchmarks and Training Paces",
    description:
      "WMA age-graded 5K benchmarks for women 40–49, with the training paces that each performance level requires. Data from Alan Jones 2025 WMA standards.",
    h1: "5K Benchmarks for Women in Their 40s",
    openingParagraph:
      "Many women run their fastest times in their 40s — not despite age, but because of the consistency, discipline, and training intelligence that comes with experience. The WMA benchmarks here show what strong 5K performance looks like at 40 and 45, and the training paces that produce it.",
    trainingContext:
      "5K performance in the 40s responds strongly to structured training. The aerobic system adapts well at this age, and the primary limiters are usually insufficient volume and running easy days too fast. One quality threshold session and one interval session per week, with the rest of running genuinely easy, drives consistent improvement. Recovery takes longer than in the 20s — spacing quality sessions with adequate easy days is more important, not less.",
    buildFaq: (data) => {
      const r0 = data.rows[0]
      const l70 = r0?.levels[70]
      const l60 = r0?.levels[60]
      return [
        {
          q: `What is a good 5K time for a woman in her ${data.ageDecade}?`,
          a: `Using WMA age-grading standards, a ${r0?.age}-year-old woman running ${l60?.timeFormatted} scores 60% ("Local Class") — competitive at local races. A 70% "Regional Class" performance at that age is ${l70?.timeFormatted}. These benchmarks are derived from world-record data for each age group, not population averages.`,
        },
        {
          q: `What training paces should a woman in her ${data.ageDecade} use for 5K training?`,
          a: `The right training paces depend on your current fitness. If you are running at 70% age-grade (${l70?.timeFormatted} for a ${r0?.age}-year-old), your training zones are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. If you are at 60% age-grade, the equivalent paces are: Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Use the calculator below to find your exact paces.`,
        },
        {
          q: `Does 5K performance decline significantly in the 40s?`,
          a: `WMA data shows a modest performance decline through the 40s — roughly two to four percent per five years. The age factors account for this and allow fair comparison across ages. Many women find that consistent, structured training in their 40s produces times faster than their unstructured 30s running. The decline becomes more noticeable after age 60, not 40.`,
        },
      ]
    },
  },

  '5k-times-women-age-50s': {
    title: "Good 5K Times for Women in Their 50s — WMA Benchmarks and Training Paces",
    description:
      "WMA age-graded 5K benchmarks for women 50–59, with the training paces that each performance level requires. Data from Alan Jones 2025 WMA standards.",
    h1: "5K Benchmarks for Women in Their 50s",
    openingParagraph:
      "5K performance for women in their 50s is more trainable than most women realize. The WMA standards reflect serious competitive depth at this age group — and the training paces required are well within reach for women who train consistently. The benchmarks below show what each performance level looks like at ages 50 and 55.",
    trainingContext:
      "Running in the 50s requires more intentional recovery than in earlier decades, but the aerobic adaptation response is similar. Women who train consistently in their 50s often outperform their younger selves on an age-adjusted basis. The key shifts: prioritize sleep and recovery between hard sessions, extend easy run duration rather than intensity, and be patient with adaptation timelines that are slightly longer than in the 40s.",
    buildFaq: (data) => {
      const r0 = data.rows[0]
      const l70 = r0?.levels[70]
      const l60 = r0?.levels[60]
      return [
        {
          q: `What is a good 5K time for a woman in her ${data.ageDecade}?`,
          a: `Using WMA age-grading standards, a ${r0?.age}-year-old woman running ${l60?.timeFormatted} scores 60% ("Local Class"). A 70% "Regional Class" performance at that age is ${l70?.timeFormatted}. These are computed from world-record standards and age factors — not from average runner data, which skews toward recreational fitness.`,
        },
        {
          q: `What training paces should a ${r0?.age}-year-old woman use for 5K training?`,
          a: `At 70% age-grade (${l70?.timeFormatted} for a ${r0?.age}-year-old), your training zones are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. At 60% age-grade (${l60?.timeFormatted}): Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Enter your exact race time into the calculator below to get your precise zones.`,
        },
        {
          q: `Is masters 5K racing competitive for women in their 50s?`,
          a: `Yes — the masters 5K field for women 50–59 is one of the most competitive age groups at many road races. Women who train seriously in this decade often run times that would have placed well in their 30s on an absolute basis. WMA age-grading reveals the competitive depth: the 90% age-grade mark represents world-record-caliber masters racing, and runners at 70–80% are legitimately strong competitors at regional level.`,
        },
      ]
    },
  },

  'marathon-times-men-age-50s': {
    title: "Good Marathon Times for Men in Their 50s — WMA Benchmarks and Training Paces",
    description:
      "WMA age-graded marathon benchmarks for men 50–59, with the training paces each performance level requires. Data from Alan Jones 2025 WMA standards.",
    h1: "Marathon Benchmarks for Men in Their 50s",
    openingParagraph:
      "Masters marathon running in the 50s is where many men discover their strongest race performances relative to age-adjusted standards. The endurance component of marathon running ages more gradually than speed, and consistent training in the 50s can produce times that compare favorably — age-adjusted — to a man's 30s racing.",
    trainingContext:
      "Marathon training in the 50s demands the same structural elements as at any age — high easy volume, marathon-pace long run segments, threshold work — with greater emphasis on recovery. Easy runs should be genuinely easy. Back-to-back hard sessions are riskier than in the 40s. Long runs remain the most important session, but the recovery time after 20-mile long runs extends. Many masters marathoners find that three or four runs per week with one quality session produces more adaptation than higher-frequency training that compromises recovery.",
    buildFaq: (data) => {
      const r0 = data.rows[0]
      const l70 = r0?.levels[70]
      const l60 = r0?.levels[60]
      return [
        {
          q: `What is a good marathon time for a man in his ${data.ageDecade}?`,
          a: `Using WMA age-grading standards, a ${r0?.age}-year-old man running ${l60?.timeFormatted} scores 60% ("Local Class"). A 70% "Regional Class" performance at that age is ${l70?.timeFormatted}. These are derived from world-record data — at age ${r0?.age}, a 70% grade represents genuinely competitive masters marathon running.`,
        },
        {
          q: `What training paces should a ${r0?.age}-year-old male marathoner use?`,
          a: `At 70% age-grade (${l70?.timeFormatted} for a ${r0?.age}-year-old male), marathon training paces are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. At 60% (${l60?.timeFormatted}): Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Marathon-pace runs should target the pace implied by your goal time.`,
        },
        {
          q: `Does marathon performance decline sharply in the 50s?`,
          a: `WMA data shows a gradual decline through the 50s — roughly four to six percent per five years. The marathon ages more gracefully than shorter distances because the endurance component degrades more slowly than raw speed or VO2max. Many men in their 50s are fitter and faster — age-adjusted — than they were as recreational runners in their 30s. The decline accelerates after 65, not 55.`,
        },
      ]
    },
  },

  'marathon-times-women-age-50s': {
    title: "Good Marathon Times for Women in Their 50s — WMA Benchmarks and Training Paces",
    description:
      "WMA age-graded marathon benchmarks for women 50–59, with the training paces each performance level requires. Data from Alan Jones 2025 WMA standards.",
    h1: "Marathon Benchmarks for Women in Their 50s",
    openingParagraph:
      "Women 50–59 are one of the fastest-growing marathon demographics, and the WMA standards reflect serious competitive depth at this age group. Marathon fitness in the 50s is real, achievable, and — for women who train consistently — often reflects the best age-adjusted performances of their running careers.",
    trainingContext:
      "Women marathon runners in their 50s often benefit from the patience and race-day discipline that comes with experience. Easy running should genuinely feel easy — a common error is running daily mileage at marathon pace or faster, which prevents real recovery and limits quality session output. Long runs at easy pace, with marathon-pace miles added late in the build, are the primary training tool. Threshold work once per week supports the lactate clearance that keeps marathon pace feeling controlled.",
    buildFaq: (data) => {
      const r0 = data.rows[0]
      const l70 = r0?.levels[70]
      const l60 = r0?.levels[60]
      return [
        {
          q: `What is a good marathon time for a woman in her ${data.ageDecade}?`,
          a: `Using WMA age-grading standards, a ${r0?.age}-year-old woman running ${l60?.timeFormatted} scores 60% ("Local Class"). A 70% "Regional Class" performance at that age requires ${l70?.timeFormatted}. These are based on world-record data — they represent what consistently trained masters women can achieve, not the median finish time at a mass-participation event.`,
        },
        {
          q: `What marathon training paces should a woman in her ${data.ageDecade} use?`,
          a: `At 70% age-grade (${l70?.timeFormatted} at age ${r0?.age}), training paces are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. At 60% (${l60?.timeFormatted}): Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Marathon-specific preparation — long runs with late-race effort — is required beyond these base zones.`,
        },
        {
          q: `How should women in their 50s adjust marathon training compared to their 40s?`,
          a: `Recovery time is the primary adjustment. The aerobic system responds to training stimulus similarly, but tissue recovery between hard sessions takes longer. Prioritizing sleep, spacing quality sessions further apart (every five to seven days rather than five), and extending easy-run duration rather than adding hard days are the most common successful adaptations. Many women in their 50s run their most consistent, best-recovered marathon training — they have the life experience to protect their sleep and not over-race.`,
        },
      ]
    },
  },

  '10k-times-men-age-60s': {
    title: "Good 10K Times for Men in Their 60s — WMA Benchmarks and Training Paces",
    description:
      "WMA age-graded 10K benchmarks for men 60–69, with the training paces each performance level requires. Data from Alan Jones 2025 WMA standards.",
    h1: "10K Benchmarks for Men in Their 60s",
    openingParagraph:
      "10K racing in your 60s is where age-grading proves its full value. The same absolute fitness that placed a man in the middle of the field at 35 may represent Regional Class performance at 65. The benchmarks here show what each performance level looks like at 60 and 65, and what training produces it.",
    trainingContext:
      "For men in their 60s, 10K performance responds primarily to consistent easy volume and one quality session per week. Threshold runs — comfortably hard tempo efforts — are the most race-specific session for the 10K and remain effective in this decade. Interval training requires more recovery than in the 40s; one interval session every 10–14 days is often more productive than weekly. The single most impactful change for most 60s-era runners: genuinely slowing easy runs to allow full recovery.",
    buildFaq: (data) => {
      const r0 = data.rows[0]
      const l70 = r0?.levels[70]
      const l60 = r0?.levels[60]
      return [
        {
          q: `What is a good 10K time for a man in his ${data.ageDecade}?`,
          a: `Using WMA age-grading standards, a ${r0?.age}-year-old man running ${l60?.timeFormatted} scores 60% ("Local Class"). A 70% "Regional Class" performance at that age requires ${l70?.timeFormatted}. At age ${r0?.age}, these represent genuinely competitive masters 10K running — the top quarter of masters fields at most regional races.`,
        },
        {
          q: `What training paces should a man in his ${data.ageDecade} use for 10K training?`,
          a: `At 70% age-grade (${l70?.timeFormatted} at age ${r0?.age}), your 10K training paces are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. At 60% (${l60?.timeFormatted}): Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Use the calculator below to get your exact zones from your current race time.`,
        },
        {
          q: `Is it realistic to improve 10K times in your 60s?`,
          a: `Yes — men who add consistent training in their 60s often show significant improvement in absolute times and consistent improvement age-adjusted. The aerobic base responds to training stimulus throughout the lifespan. The adaptation timeline is longer than in earlier decades, and the training stimulus needs to be adequate but not excessive. Men who were inactive in their 50s often have substantial room to improve simply through consistent easy running before any structured quality work.`,
        },
      ]
    },
  },

  'marathon-times-men-age-60s': {
    title: "Good Marathon Times for Men in Their 60s — WMA Benchmarks and Training Paces",
    description:
      "WMA age-graded marathon benchmarks for men 60–69, with the training paces each performance level requires. Data from Alan Jones 2025 WMA standards.",
    h1: "Marathon Benchmarks for Men in Their 60s",
    openingParagraph:
      "Men who race marathons in their 60s are a determined, high-performing cohort — and the WMA standards reflect that competitive depth. Marathon endurance ages more gradually than speed, and men in their 60s who train consistently can maintain impressive absolute times while achieving strong age-adjusted scores.",
    trainingContext:
      "Marathon training in the 60s works best when structured around recovery. Long runs remain the most important session — they drive the endurance adaptation that marathon performance depends on. Easy pace must be genuinely easy, often two minutes per mile slower than race pace. Threshold work once per week supports the lactate clearance needed for the sustained marathon effort. Most 60s-era marathoners do best with three to four runs per week — fewer, but of higher quality and with full recovery — rather than high-frequency lower-quality mileage.",
    buildFaq: (data) => {
      const r0 = data.rows[0]
      const l70 = r0?.levels[70]
      const l60 = r0?.levels[60]
      return [
        {
          q: `What is a good marathon time for a man in his ${data.ageDecade}?`,
          a: `Using WMA age-grading standards, a ${r0?.age}-year-old man running ${l60?.timeFormatted} scores 60% ("Local Class"). A 70% "Regional Class" performance at that age is ${l70?.timeFormatted}. At age ${r0?.age}, a 70% WMA grade represents running in the competitive tier of masters marathon fields — typically top third in the age group at major marathons.`,
        },
        {
          q: `What marathon training paces should a ${r0?.age}-year-old man use?`,
          a: `At 70% age-grade (${l70?.timeFormatted} at age ${r0?.age}), marathon training paces are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. At 60% (${l60?.timeFormatted}): Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Marathon-pace runs should target the pace implied by your goal finish time.`,
        },
        {
          q: `What are the key training adjustments for marathon racing in the 60s?`,
          a: `Three adjustments have the highest impact. First: protect recovery — hard sessions need five to seven days of genuine easy running between them. Second: trust long runs at easy pace — the aerobic adaptation is there at this age, but adding race-pace effort to every long run blunts recovery. Third: reduce racing frequency — racing more than once every six to eight weeks limits the ability to train through a full preparation cycle. Men in their 60s who protect recovery between hard efforts often train more consistently than they did a decade earlier.`,
        },
      ]
    },
  },
}

// ============================================================================
// PAGE
// ============================================================================

interface Props {
  params: { slug: string }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const config = DEMO_PAGE_CONFIG[params.slug]
  if (!config) return {}
  return {
    title: config.title,
    description: config.description,
    alternates: {
      canonical: `https://strideiq.run/tools/age-grading-calculator/demographics/${params.slug}`,
    },
    openGraph: {
      url: `https://strideiq.run/tools/age-grading-calculator/demographics/${params.slug}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: config.title }],
    },
  }
}

export function generateStaticParams() {
  return Object.keys(ageDemoData)
    .filter((k) => k !== '_meta')
    .map((slug) => ({ slug }))
}

const LEVEL_COLORS: Record<number, string> = {
  50: 'text-slate-400',
  60: 'text-teal-400',
  70: 'text-green-400',
  80: 'text-blue-400',
}

function DemoTable({ rows }: { rows: DemoRow[] }) {
  const levels = [50, 60, 70, 80]
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400">
            <th className="text-left py-3 px-2">Age</th>
            <th className="text-center py-3 px-2">
              Recreational<br /><span className="text-xs font-normal">50%</span>
            </th>
            <th className="text-center py-3 px-2">
              Local Class<br /><span className="text-xs font-normal">60%</span>
            </th>
            <th className="text-center py-3 px-2">
              Regional<br /><span className="text-xs font-normal">70%</span>
            </th>
            <th className="text-center py-3 px-2">
              National<br /><span className="text-xs font-normal">80%</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.age} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="py-2.5 px-2 font-semibold text-slate-200">{row.age}</td>
              {levels.map((pct) => {
                const lvl = row.levels[pct]
                return (
                  <td key={pct} className={`text-center py-2.5 px-2 ${LEVEL_COLORS[pct]}`}>
                    {lvl?.timeFormatted || '—'}
                    <br />
                    <span className="text-xs text-slate-500">{lvl?.paceMi}/mi</span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TrainingPaceTable({ rows }: { rows: DemoRow[] }) {
  const levels = [60, 70, 80]
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400">
            <th className="text-left py-3 px-2">Age</th>
            <th className="text-left py-3 px-2">Level</th>
            <th className="text-center py-3 px-2">Time</th>
            <th className="text-center py-3 px-2">Easy</th>
            <th className="text-center py-3 px-2">Threshold</th>
            <th className="text-center py-3 px-2">Interval</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) =>
            levels.map((pct, pctIdx) => {
              const lvl = row.levels[pct]
              const tp = lvl?.trainingPaces
              return (
                <tr
                  key={`${row.age}-${pct}`}
                  className={`border-b border-slate-800 hover:bg-slate-800/50 ${pctIdx === 0 ? 'border-t border-slate-700' : ''}`}
                >
                  <td className="py-2.5 px-2 font-semibold text-slate-200">
                    {pctIdx === 0 ? row.age : ''}
                  </td>
                  <td className={`py-2.5 px-2 text-xs ${LEVEL_COLORS[pct]}`}>{lvl?.label}</td>
                  <td className="text-center py-2.5 px-2 text-slate-300">{lvl?.timeFormatted}</td>
                  <td className="text-center py-2.5 px-2 text-slate-400">{tp?.easy.mi || '—'}</td>
                  <td className="text-center py-2.5 px-2 text-green-400">{tp?.threshold.mi || '—'}</td>
                  <td className="text-center py-2.5 px-2 text-blue-400">{tp?.interval.mi || '—'}</td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
      <p className="text-xs text-slate-500 mt-2">
        All paces per mile. Training paces derived from the WMA benchmark time for each age and performance level.
      </p>
    </div>
  )
}

export default function DemographicsPage({ params }: Props) {
  const config = DEMO_PAGE_CONFIG[params.slug]
  if (!config) notFound()

  const data = (ageDemoData as unknown as Record<string, DemoEntry>)[params.slug]
  if (!data) notFound()

  const faq = config.buildFaq(data)

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Age-Grading Calculator', item: 'https://strideiq.run/tools/age-grading-calculator' },
      { '@type': 'ListItem', position: 3, name: config.h1, item: `https://strideiq.run/tools/age-grading-calculator/demographics/${params.slug}` },
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
          <Link href="/tools/age-grading-calculator" className="hover:text-orange-400 transition-colors">Age-Grading Calculator</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">{config.h1}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">{config.h1}</h1>

        <p className="text-slate-300 leading-relaxed mb-8">{config.openingParagraph}</p>

        {/* BLUF — numbers from data */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            For {data.genderLabel.toLowerCase()} age {data.ageRange} running the {data.distance},
            a 60% age-grade (&ldquo;Local Class&rdquo;) at age {data.rows[0]?.age} is{' '}
            {data.rows[0]?.levels[60]?.timeFormatted}.
            A 70% Regional Class performance is{' '}
            {data.rows[0]?.levels[70]?.timeFormatted}, requiring
            easy pace {data.rows[0]?.levels[70]?.trainingPaces?.easy.mi}/mi,
            threshold {data.rows[0]?.levels[70]?.trainingPaces?.threshold.mi}/mi.
            These benchmarks are from WMA (World Masters Athletics) 2025 standards.
          </p>
        </div>

        {/* Benchmark table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">
            {data.genderLabel} {data.distance} Times — Ages {data.ageRange}
          </h2>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl">
            <DemoTable rows={data.rows} />
          </div>
        </section>

        {/* What the levels mean */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">What each level means</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-3">
            <ul className="space-y-2">
              <li><strong className="text-blue-400">National Class (80–89%)</strong> — Competitive at national masters championships. Requires serious, structured training over years.</li>
              <li><strong className="text-green-400">Regional Class (70–79%)</strong> — Strong age-group placements at regional races. Consistent training with quality sessions.</li>
              <li><strong className="text-teal-400">Local Class (60–69%)</strong> — Competitive in local races. Solid fitness from regular running and some structured training.</li>
              <li><strong className="text-slate-400">Recreational (below 60%)</strong> — Running for fitness and enjoyment. Most runners start here.</li>
            </ul>
          </div>
        </section>

        {/* Training pace table */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Training paces by performance level</h2>
          <p className="text-slate-400 text-sm mb-4">
            The training paces below are derived from each WMA benchmark time. If you are running at 70% age-grade, these are the training zones that produce and maintain that performance level.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-4 shadow-xl">
            <TrainingPaceTable rows={data.rows} />
          </div>
        </section>

        {/* Training context */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Training at this age and distance</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300">
            <p>{config.trainingContext}</p>
          </div>
        </section>

        {/* Calculator embed */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Calculate your exact age-graded score</h2>
          <p className="text-slate-400 mb-4">
            Enter your race time below to see your precise WMA age-graded percentage and where you fall relative to these benchmarks.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 shadow-xl">
            <WMACalculator />
          </div>
        </section>

        {/* N=1 hook */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">Population benchmarks are starting points</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              WMA age-grading tells you how your time compares to world-record standards for your age group. StrideIQ goes further — it tracks your individual efficiency trends, recovery patterns, and adaptation curves from your actual training data. At any age, knowing your population percentile is the beginning. Understanding your personal response to training is what drives real improvement.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools/age-grading-calculator" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                Full age-grading calculator →
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

        {/* Related pages */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Other demographic benchmarks</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(DEMO_PAGE_CONFIG)
              .filter(([key]) => key !== params.slug)
              .map(([key, cfg]) => (
                <Link
                  key={key}
                  href={`/tools/age-grading-calculator/demographics/${key}`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors"
                >
                  {cfg.h1} →
                </Link>
              ))}
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Full Age-Grading Calculator →
            </Link>
          </div>
        </section>

        <div className="mt-8 text-xs text-slate-500">
          <p>
            Data source: Alan Jones 2025 WMA Road Age-Grading Tables, approved by USATF Masters Long Distance Running Council (January 2025).
            Training paces derived from the Daniels/Gilbert oxygen cost equations using each WMA benchmark time as input.
          </p>
        </div>
      </div>
    </div>
  )
}
