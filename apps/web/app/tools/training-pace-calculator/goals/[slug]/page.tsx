import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import goalPaceData from '@/data/goal-pace-tables.json'

// ============================================================================
// TYPES — mirror the schema in goal-pace-tables.json
// ============================================================================

type PaceEntry = { mi: string; km: string; secPerMile: number }
type EquivEntry = {
  label: string
  distanceMeters: number
  timeSeconds: number
  timeFormatted: string
  paceMi: string
  paceKm: string
}
type GoalEntry = {
  slug: string
  label: string
  goalLabel: string
  distance: string
  distanceMeters: number
  goalTimeLabel: string
  goalTimeSeconds: number
  rpi: number
  paces: {
    easy: PaceEntry
    marathon: PaceEntry
    threshold: PaceEntry
    interval: PaceEntry
    repetition: PaceEntry
  }
  equivalents: Record<string, EquivEntry>
}

// ============================================================================
// STATIC PER-PAGE CONFIG
// All numbers come from goalPaceData JSON — none are hardcoded here.
// openingParagraph, trainingContext, and faq Q2/Q3 answers contain
// coaching philosophy only — no numeric claims.
// ============================================================================

const GOAL_PAGE_CONFIG: Record<
  string,
  {
    title: string
    description: string
    h1: string
    openingParagraph: string
    trainingContext: string
    buildFaq: (data: GoalEntry) => { q: string; a: string }[]
  }
> = {
  'sub-20-minute-5k': {
    title: 'Sub-20 Minute 5K Training Paces — What It Actually Takes',
    description:
      'Training paces, RPI, and race equivalents for breaking 20 minutes in the 5K. Easy, threshold, and interval zones based on the Daniels/Gilbert formula. No generic advice.',
    h1: 'Sub-20 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph:
      'Breaking 20 minutes in the 5K is a genuine milestone — one that separates deliberate training from casual running. It requires developed VO2max, real threshold stamina, and the discipline to run easy days easy. The training paces below show exactly what fitness this demands.',
    trainingContext:
      'For sub-20 5K, interval training is the primary driver. VO2max development — the engine that sustains hard effort at near-maximum aerobic capacity — is what separates 21-minute runners from 19-minute runners. Threshold runs build the stamina that keeps you from blowing up in mile 2. Easy running is the foundation that lets you train hard consistently without breaking down. The typical sub-20 week: four easy runs, one threshold session, one interval session.',
    buildFaq: (data) => [
      {
        q: `What training paces do I need to break 20 minutes in the 5K?`,
        a: `To train for a sub-20:00 5K (${data.goalTimeLabel}), your five training zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, and Repetition ${data.paces.repetition.mi}/mi. These come from an RPI of ${data.rpi}. Your easy runs — the bulk of your weekly volume — should genuinely feel easy at ${data.paces.easy.mi} or slower. Your interval sessions should feel hard but controlled: you could do one more repeat if you had to.`,
      },
      {
        q: 'What is the most important workout for sub-20 5K training?',
        a: 'Interval-pace repeats targeting VO2max — typically 800m to 1200m at interval pace with equal-time recovery jogs. These are the sessions that directly raise your aerobic ceiling. Without VO2max development, threshold and marathon paces cannot improve past a point. One interval session per week is standard; two per week is possible during peak training but increases injury risk.',
      },
      {
        q: 'How do I know if I am ready to race sub-20?',
        a: 'Race readiness is better assessed from a recent workout than from a pace chart. If you can hold your threshold pace for 25–30 minutes without excessive effort, and your interval repeats feel controlled rather than desperate, you are likely in sub-20 fitness. Race-day conditions, pacing strategy, and course all affect the outcome. A tune-up race at shorter distance — a mile or two-mile — often gives the clearest picture of current race fitness.',
      },
    ],
  },

  'sub-25-minute-5k': {
    title: 'Sub-25 Minute 5K Training Paces — What This Level of Fitness Requires',
    description:
      'Training paces, RPI, and race equivalents for breaking 25 minutes in the 5K. Exact easy, threshold, and interval zones from the Daniels/Gilbert formula.',
    h1: 'Sub-25 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph:
      'Sub-25 is the first meaningful 5K milestone for recreational runners building toward competitive fitness. It signals consistent aerobic base, some structured quality work, and genuine race-day focus. The paces below show what training at this level actually looks like.',
    trainingContext:
      'For sub-25 5K, easy running volume and threshold training are the two highest-leverage levers. Most runners chasing this mark are running too fast on easy days and too slow on quality sessions. Genuine easy running — the kind where you can hold a full conversation without effort — builds the aerobic base that makes threshold and interval work productive. One threshold session per week and one interval session per week, with the rest of volume at easy pace, is the standard structure.',
    buildFaq: (data) => [
      {
        q: `What training paces should I use to break 25 minutes in the 5K?`,
        a: `To train for a sub-25:00 5K (${data.goalTimeLabel}), your training zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, and Repetition ${data.paces.repetition.mi}/mi. These are derived from an RPI of ${data.rpi} — the fitness level required to run ${data.goalTimeLabel}. If your easy runs feel harder than this pace, you are either running too fast or not yet at this fitness level.`,
      },
      {
        q: 'Is sub-25 a realistic 5K goal for a recreational runner?',
        a: 'Yes — for most healthy adults who run consistently and train with some structure, sub-25 is reachable. The key word is consistently. Sporadic training produces sporadic fitness. Runners who run regularly three to four times per week for six to twelve months, with some threshold and interval work, typically reach this level. The main barrier is usually not physical ceiling — it is inconsistency and running easy days too fast to absorb training properly.',
      },
      {
        q: 'How often should I run to break 25 minutes in the 5K?',
        a: 'Three to four runs per week is the practical minimum for building 5K-specific fitness. Two of those runs should be easy, one should be a quality session (threshold or intervals), and a fourth optional run adds volume. More days of running mean more aerobic base — but only if the additional runs are genuinely easy. Adding hard days without adequate easy running is a common cause of stagnation and injury.',
      },
    ],
  },

  'sub-40-minute-10k': {
    title: 'Sub-40 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description:
      'Training paces, RPI, and race equivalents for breaking 40 minutes in the 10K. Exact easy, threshold, and interval zones from the Daniels/Gilbert formula.',
    h1: 'Sub-40 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph:
      'A sub-40 10K places you well into the competitive tier at most local races. It demands both VO2max capacity and threshold stamina — you cannot sprint or grind your way to this mark. The training paces here show what that fitness profile looks like in workouts.',
    trainingContext:
      'For sub-40 10K, threshold training is the most important quality session. The 10K demands sustained effort near your lactate threshold for 30–40 minutes. Tempo runs at threshold pace build the metabolic stamina that lets you hold a controlled, hard effort for that duration. Interval work raises the aerobic ceiling above threshold so that race pace feels more manageable. Weekly volume matters too — sub-40 fitness generally requires consistent high-volume training blocks over several months.',
    buildFaq: (data) => [
      {
        q: `What training paces do I need to break 40 minutes in the 10K?`,
        a: `To train for a sub-40:00 10K (${data.goalTimeLabel}), your training zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. Your RPI is ${data.rpi}. Note the equivalent marathon fitness: ${data.equivalents.marathon?.timeFormatted || 'see above'} — if you can run that marathon, you have the aerobic base for sub-40 10K.`,
      },
      {
        q: 'Is threshold or interval training more important for sub-40 10K?',
        a: 'Threshold is more important — but both are necessary. The 10K demands sustained effort near your lactate threshold for the entire race. Threshold runs build the specific metabolic quality that 10K racing requires. Intervals raise the aerobic ceiling, which makes threshold pace feel more sustainable. A typical week at this training level: three to four easy runs, one threshold session (20–40 minutes at threshold pace), and one interval session (800m–1200m repeats). Threshold sessions do the direct work; intervals amplify the ceiling.',
      },
      {
        q: 'What marathon time is equivalent to sub-40 10K fitness?',
        a: `Using the Daniels/Gilbert equivalency formula, a sub-40 10K runner (RPI ${data.rpi}) has equivalent marathon fitness of approximately ${data.equivalents.marathon?.timeFormatted || 'calculable above'}. This assumes comparable training for each distance — specific marathon fitness (long runs, marathon-pace work) is required to actually run that time. The equivalency predicts aerobic potential, not race outcome without distance-specific preparation.`,
      },
    ],
  },

  'sub-50-minute-10k': {
    title: 'Sub-50 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description:
      'Training paces, RPI, and race equivalents for breaking 50 minutes in the 10K. Easy, threshold, and interval zones from the Daniels/Gilbert formula.',
    h1: 'Sub-50 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph:
      'Breaking 50 minutes in the 10K signals solid aerobic fitness, meaningful weekly volume, and real experience pacing a sustained hard effort. The paces here show what a genuine sub-50 runner trains at — and what it implies across other distances.',
    trainingContext:
      'For sub-50 10K, the primary bottleneck is usually aerobic base, not speed. Most runners at this level run too fast on easy days and accumulate fatigue before their quality sessions can be truly productive. Running easy days genuinely easy — a pace that feels almost too slow — allows threshold and interval sessions to generate real adaptation. One threshold session and one interval or fartlek session per week, supported by several easy days, is the standard building-block structure.',
    buildFaq: (data) => [
      {
        q: `What training paces should I use to break 50 minutes in the 10K?`,
        a: `To train for a sub-50:00 10K (${data.goalTimeLabel}), your training zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. These derive from an RPI of ${data.rpi}. Your half marathon equivalent at this fitness level is approximately ${data.equivalents.halfMarathon?.timeFormatted || 'see calculator'} — a useful cross-check.`,
      },
      {
        q: 'What is the biggest training mistake for runners chasing sub-50 in the 10K?',
        a: `Running easy days too fast is the single most common error. At this training level, easy pace is ${data.paces.easy.mi}/mi or slower — often two minutes per mile slower than race pace. When easy runs feel "moderate," threshold sessions cannot be genuinely threshold: the athlete is too fatigued. The result is weeks of medium-effort running that builds neither aerobic base nor high-end quality. Slowing easy days dramatically is often the highest-leverage change a sub-50 runner can make.`,
      },
      {
        q: 'How does sub-50 10K fitness compare to half marathon and marathon fitness?',
        a: `Sub-50 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} for the half marathon and ${data.equivalents.marathon?.timeFormatted || 'calculable'} for the marathon — assuming adequate distance-specific training. The 10K equivalency is most accurate for the half marathon (physiologically similar) and less accurate for the marathon (which has glycogen depletion and pacing demands that pure aerobic fitness does not capture).`,
      },
    ],
  },

  'sub-2-hour-half-marathon': {
    title: 'Sub-2 Hour Half Marathon Training Paces — What This Goal Requires',
    description:
      'Training paces, RPI, and race equivalents for breaking 2 hours in the half marathon. Easy, threshold, and interval zones from the Daniels/Gilbert formula.',
    h1: 'Sub-2 Hour Half Marathon — Training Paces and Fitness Profile',
    openingParagraph:
      'Two hours in the half marathon has become the recreational runner\'s most widely aspired-to milestone — meaningful, achievable with structured training, and more demanding than most first-timers expect. The training paces here represent what a genuine sub-2 runner trains at across all five zones.',
    trainingContext:
      'For sub-2 hour half marathon, threshold running is the most race-specific training. The half marathon is essentially a long, sustained threshold effort — 75 to 110 minutes near your lactate threshold. Tempo runs at threshold pace build the metabolic capacity to sustain that effort. Long runs at easy pace build the endurance infrastructure that makes late-race pacing possible. Marathon-pace segments in long runs bridge the gap between easy endurance and race-day pace.',
    buildFaq: (data) => [
      {
        q: `What training paces do I need for a sub-2 hour half marathon?`,
        a: `To train for a sub-2:00:00 half marathon (${data.goalTimeLabel}), your training zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. Your race pace (approximately ${Math.floor(data.goalTimeSeconds / 13.1 / 60)}:${String(Math.round((data.goalTimeSeconds / 13.1) % 60)).padStart(2,'0')}/mi) falls between your marathon and threshold pace — which is exactly where half marathon effort sits physiologically.`,
      },
      {
        q: 'How important is the long run for a sub-2 hour half marathon?',
        a: 'Essential — but pace matters as much as distance. Long runs for half marathon training should be at easy pace (genuinely conversational). The aerobic adaptation comes from time on feet, not from pushing pace. Runners who hammer every long run accumulate fatigue and underperform at quality sessions during the week. A typical sub-2 half training block includes weekly long runs building to 14–18 miles over several months, all at easy pace, with marathon-pace miles added at the finish as fitness develops.',
      },
      {
        q: 'What marathon time does sub-2 hour half marathon fitness predict?',
        a: `Sub-2 hour half marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable above'} for the full marathon — assuming full marathon-specific preparation (20-mile long runs, marathon-pace work, adequate weekly volume). Without marathon-specific training, most runners hit the wall well before this equivalent time. Aerobic fitness is necessary but not sufficient for marathon performance.`,
      },
    ],
  },

  'sub-4-hour-marathon': {
    title: 'Sub-4 Hour Marathon Training Paces — What This Goal Actually Requires',
    description:
      'Training paces, RPI, and race equivalents for breaking 4 hours in the marathon. Easy, threshold, marathon-pace, and interval zones from the Daniels/Gilbert formula.',
    h1: 'Sub-4 Hour Marathon — Training Paces and Fitness Profile',
    openingParagraph:
      'Sub-4:00 is the most commonly cited marathon goal in recreational running. It requires real endurance, consistent volume over months, smart pacing on race day, and honest easy-day discipline. The training paces here represent what a genuine sub-4 marathoner actually runs during their training cycle.',
    trainingContext:
      'For sub-4 marathon, marathon-pace runs and long runs at easy pace are the two most critical training elements. Marathon-pace work — running the final miles of a long run at goal pace — teaches your body to maintain effort when glycogen is depleted, which is exactly what the final 10K of the marathon demands. Easy running makes up 80% or more of weekly volume and builds the aerobic base and fat-oxidation capacity that sustains marathon effort for hours. Threshold running matters, but marathon pace and easy base are the top priorities.',
    buildFaq: (data) => [
      {
        q: `What training paces does a sub-4 hour marathon runner use?`,
        a: `To train for a sub-4:00:00 marathon (${data.goalTimeLabel}), your training zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. Your marathon-pace training runs target ${data.paces.marathon.mi}/mi — your long run easy days should be at ${data.paces.easy.mi} or slower. The gap between these paces is deliberate: different adaptations, different sessions.`,
      },
      {
        q: 'What is the most common mistake runners make when chasing a sub-4 marathon?',
        a: `Going out too fast on race day, and running easy training days at marathon pace. Both errors stem from the same cause: underestimating how much the marathon punishes pace that feels "comfortable" early. Easy training pace for a sub-4 runner (${data.paces.easy.mi}/mi or slower) often feels almost embarrassingly slow. But running easy days at marathon pace leaves no adaptation reserve for the quality sessions that build fitness. And starting a marathon at a pace that feels good virtually guarantees a painful final 10K.`,
      },
      {
        q: 'What half marathon time does sub-4 marathon fitness predict?',
        a: `Sub-4:00 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable above'} for the half marathon — assuming comparable training for the half distance. Because the half marathon is run at a higher percentage of VO2max than the marathon, runners who are specifically marathon-trained (high volume, long runs, marathon-pace work) may underperform their half marathon equivalent until they do more half-specific work. The equivalency reflects aerobic capacity, not single-distance peaking.`,
      },
    ],
  },
}

// ============================================================================
// PAGE
// ============================================================================

interface Props {
  params: { slug: string }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const config = GOAL_PAGE_CONFIG[params.slug]
  if (!config) return {}
  return {
    title: config.title,
    description: config.description,
    alternates: {
      canonical: `https://strideiq.run/tools/training-pace-calculator/goals/${params.slug}`,
    },
    openGraph: {
      url: `https://strideiq.run/tools/training-pace-calculator/goals/${params.slug}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: config.title }],
    },
  }
}

export function generateStaticParams() {
  return Object.keys(goalPaceData)
    .filter((k) => k !== '_meta')
    .map((slug) => ({ slug }))
}

function PaceZoneRow({ label, pace, color }: { label: string; pace: PaceEntry; color: string }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-800">
      <span className="text-slate-300 text-sm font-medium">{label}</span>
      <div className="text-right">
        <span className={`font-mono font-semibold ${color}`}>{pace.mi}<span className="text-slate-500 font-normal">/mi</span></span>
        <span className="text-slate-500 text-xs ml-3">{pace.km}/km</span>
      </div>
    </div>
  )
}

export default function GoalPacePage({ params }: Props) {
  const config = GOAL_PAGE_CONFIG[params.slug]
  if (!config) notFound()

  const data = (goalPaceData as unknown as Record<string, GoalEntry>)[params.slug]
  if (!data) notFound()

  const faq = config.buildFaq(data)
  const equivKeys = Object.keys(data.equivalents)

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Training Pace Calculator', item: 'https://strideiq.run/tools/training-pace-calculator' },
      { '@type': 'ListItem', position: 3, name: config.h1, item: `https://strideiq.run/tools/training-pace-calculator/goals/${params.slug}` },
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
          <Link href="/tools/training-pace-calculator" className="hover:text-orange-400 transition-colors">Training Pace Calculator</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">{config.h1}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">{config.h1}</h1>

        {/* Opening paragraph — unique per page */}
        <p className="text-slate-300 leading-relaxed mb-8">{config.openingParagraph}</p>

        {/* BLUF — all numbers from JSON */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            To break {data.goalLabel} in the {data.distance} (RPI {data.rpi}), your training
            paces are: easy {data.paces.easy.mi}/mi, threshold {data.paces.threshold.mi}/mi,
            interval {data.paces.interval.mi}/mi.
            {equivKeys.length > 0 && (
              <>
                {' '}Equivalent fitness: {data.equivalents[equivKeys[0]]?.label}{' '}
                {data.equivalents[equivKeys[0]]?.timeFormatted}
                {equivKeys[1] && (
                  <>, {data.equivalents[equivKeys[1]]?.label} {data.equivalents[equivKeys[1]]?.timeFormatted}</>
                )}.
              </>
            )}
          </p>
        </div>

        {/* Training pace zones */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-2">Training paces for {data.goalLabel} {data.distance}</h2>
          <p className="text-slate-400 text-sm mb-4">
            RPI {data.rpi} · Goal: {data.goalTimeLabel} · All paces in min/mile
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-5 shadow-xl">
            <PaceZoneRow label="Easy (80%+ of weekly running)" pace={data.paces.easy} color="text-slate-300" />
            <PaceZoneRow label="Marathon Pace" pace={data.paces.marathon} color="text-orange-400" />
            <PaceZoneRow label="Threshold (comfortably hard)" pace={data.paces.threshold} color="text-green-400" />
            <PaceZoneRow label="Interval (VO2max sessions)" pace={data.paces.interval} color="text-blue-400" />
            <PaceZoneRow label="Repetition (short fast reps)" pace={data.paces.repetition} color="text-purple-400" />
            <p className="text-xs text-slate-500 mt-3">
              Calculated from Daniels/Gilbert oxygen cost equations. Easy pace means &quot;this pace or slower.&quot;
            </p>
          </div>
        </section>

        {/* Equivalent fitness */}
        {equivKeys.length > 0 && (
          <section className="mb-10">
            <h2 className="text-2xl font-bold mb-4">Equivalent race fitness</h2>
            <p className="text-slate-400 text-sm mb-4">
              These are the predicted equivalent times at other distances for a runner with RPI {data.rpi} — assuming comparable training for each distance.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {equivKeys.map((key) => {
                const e = data.equivalents[key]
                return (
                  <div key={key} className="bg-slate-800 border border-slate-700/50 rounded-xl p-4">
                    <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">{e.label}</p>
                    <p className="text-xl font-bold text-slate-100">{e.timeFormatted}</p>
                    <p className="text-sm text-slate-400">{e.paceMi}/mi</p>
                  </div>
                )
              })}
            </div>
          </section>
        )}

        {/* Training context */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Training approach for {data.goalLabel} {data.distance}</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300">
            <p>{config.trainingContext}</p>
          </div>
        </section>

        {/* Calculator embed */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Calculate your current training paces</h2>
          <p className="text-slate-400 mb-4">
            The table above shows paces for {data.goalLabel} {data.distance} fitness. Enter your current race time to see where you are now and how far from the goal you sit.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 shadow-xl">
            <TrainingPaceCalculator />
          </div>
        </section>

        {/* N=1 hook */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">These paces are based on your race time — not your body</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              The Daniels/Gilbert formula predicts training zones from a single race result. StrideIQ goes further: it tracks how your body specifically responds to threshold and interval work — which sessions produce your biggest gains, how quickly you recover, and when your fitness is peaking. Population formulas start the conversation. Your individual response data finishes it.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools/training-pace-calculator" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                Training pace tables →
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
          <h2 className="text-xl font-bold mb-4">Other goal pace guides</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(GOAL_PAGE_CONFIG)
              .filter(([key]) => key !== params.slug)
              .map(([key, cfg]) => (
                <Link
                  key={key}
                  href={`/tools/training-pace-calculator/goals/${key}`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors"
                >
                  {cfg.h1.split('—')[0].trim()} →
                </Link>
              ))}
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator →
            </Link>
          </div>
        </section>

        <div className="mt-8 text-xs text-slate-500">
          <p>
            Paces calculated using the Daniels/Gilbert oxygen cost equations (1979). All values
            derived from the same formula used by the StrideIQ training pace calculator. Goal times
            use the target-minus-one-second convention (e.g., sub-20 = 19:59 input).
          </p>
        </div>
      </div>
    </div>
  )
}
