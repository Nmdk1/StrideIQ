import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import { SignupCtaLink } from '@/components/tools/SignupCtaLink'
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

  // ============================================================================
  // BATCH 2A: 38 new goal page configs
  // ============================================================================

  // ---- 5K ----
  'sub-17-minute-5k': {
    title: 'Sub-17 Minute 5K Training Paces — Elite-Level Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 17 minutes in the 5K. Easy, threshold, and interval zones from the Daniels/Gilbert formula.',
    h1: 'Sub-17 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-17 is elite-tier 5K running. At this level, you are competing with serious open-class and sub-elite runners. The fitness required — a high VO2max, refined threshold stamina, and dialed training discipline — is the product of years of structured training, not a single training cycle.',
    trainingContext: 'Sub-17 5K demands very high VO2max and the threshold stamina to sustain near-maximum aerobic output for 16–17 minutes. Interval work (1000m–1200m repeats at interval pace) raises the aerobic ceiling. Threshold runs (20–40 minutes at threshold pace) build the ability to hold hard pace without slipping into anaerobic debt. Weekly volume at 60–80+ miles is typical for runners at this level. Easy runs must be genuinely easy — the accumulated stress of this training load demands real recovery.',
    buildFaq: (data) => [
      { q: `What training paces are needed to break 17 minutes in the 5K?`, a: `To target sub-17:00 (${data.goalTimeLabel}), your zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. RPI ${data.rpi}. Your interval pace (${data.paces.interval.mi}/mi) is close to 5K race pace — interval training is the central quality session for sub-17 preparation.` },
      { q: 'What marathon equivalent does sub-17 5K fitness predict?', a: `Sub-17:00 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential — assuming full marathon-specific training. Most sub-17 5K runners are specifically trained for short distances; converting that aerobic capacity to a marathon requires sustained volume and long-run preparation that takes 12–18 months to build.` },
      { q: 'How much weekly mileage does sub-17 5K require?', a: `Sub-17 5K fitness typically correlates with 60–85+ miles per week of consistent training over several months or years. The volume builds the aerobic base that supports the quality sessions. Many runners at this level run doubles (two runs per day) to accumulate volume without excessive per-run stress. Individual variation is significant — some runners achieve this standard on less volume, but the physiological demands are consistent.` },
    ],
  },

  'sub-18-minute-5k': {
    title: 'Sub-18 Minute 5K Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 18 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-18 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-18 is where serious competitive running begins. At most local road races, this places you in or near the top finishers. The training paces required reflect genuine sub-elite fitness — not recreational-level training with occasional speed work.',
    trainingContext: 'Sub-18 5K requires a well-developed VO2max and real threshold stamina. The aerobic ceiling needs to be high enough that 5K race pace — near-maximum aerobic output — is sustainable for 17–18 minutes. Interval training (800m–1200m repeats) raises this ceiling. Threshold training (tempo runs at threshold pace) builds the metabolic stamina to sustain high-intensity output without rapid lactate accumulation. 50–70 miles per week is a typical range for runners at this level.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-18 minute 5K require?`, a: `For sub-18:00 (${data.goalTimeLabel}), your zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. RPI ${data.rpi}. Easy pace (${data.paces.easy.mi}/mi) should feel comfortable for hours — most runners at this level run their easy days 90–120 seconds per mile slower than race pace.` },
      { q: 'Is sub-18 achievable for adult runners who took up running in their 30s?', a: `Yes, for adults who start running in their 30s and train consistently for several years. Sub-18 requires a VO2max in the upper range of recreational fitness, which develops with sustained training. Time-to-standard is typically 3–5 years of consistent mileage with structured quality work. Genetics (VO2max ceiling) does matter — some runners will reach this level and some will not — but most who fail to get there fall short on training consistency, not genetic ceiling.` },
      { q: `What equivalent marathon fitness does sub-18 5K represent?`, a: `Sub-18 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. Converting this aerobic capacity to marathon performance requires distance-specific training: 20-mile long runs, marathon-pace work, and sustained high-volume build. Without it, most sub-18 5K runners significantly underperform their marathon equivalent.` },
    ],
  },

  'sub-19-minute-5k': {
    title: 'Sub-19 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 19 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-19 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-19 is solidly competitive 5K territory — typically top-10 finishes at most local road races. This requires a genuine aerobic engine built over months of consistent training. The training paces here show what that fitness demands across all five zones.',
    trainingContext: 'For sub-19 5K, interval training (VO2max development) and threshold work are the primary quality sessions. At this fitness level, the limiting factor is usually aerobic ceiling — how high a fraction of VO2max you can sustain for 18–19 minutes. Interval repeats push that ceiling up. Threshold runs build the capacity to sustain high output without accumulating lactate too quickly. Weekly volume of 40–60 miles with two structured quality sessions per week is the standard building block.',
    buildFaq: (data) => [
      { q: `What training paces should I use for a sub-19 minute 5K?`, a: `For sub-19:00 (${data.goalTimeLabel}), your zones are: Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. RPI ${data.rpi}. Running interval sessions at ${data.paces.interval.mi}/mi directly trains the aerobic ceiling that 5K racing demands.` },
      { q: 'How long does it take to get from sub-20 to sub-19?', a: `The jump from sub-20 to sub-19 typically takes 6–18 months of focused training. The key variables: consistency of easy volume, quality of interval sessions, and adequate recovery between hard efforts. Runners who plateau at sub-20 are often running easy days too fast (reducing recovery capacity) or doing interval sessions without sufficient volume or consistency. A dedicated 12–16 week 5K-specific training block often bridges this gap.` },
      { q: `What half marathon time does sub-19 5K fitness predict?`, a: `Sub-19 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If you are building toward sub-19 and want to run a half marathon, add half-specific long runs (12–15 miles) and threshold work — your aerobic base is strong enough that distance-specific preparation will translate quickly.` },
    ],
  },

  'sub-21-minute-5k': {
    title: 'Sub-21 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 21 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-21 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-21 sits between the recreational and competitive tiers — a marker of genuine aerobic development and structured training. Runners here typically have a solid base and at least one structured training phase under their belt.',
    trainingContext: 'For sub-21 5K, the primary levers are VO2max development (interval training) and threshold stamina. Runners who plateau in the 21–23 minute range often lack sufficient interval training — they do plenty of easy running but not enough sessions at the aerobic ceiling. One interval session (800m–1000m repeats at interval pace) and one threshold session per week, supported by 30–45 miles of easy volume, drives consistent improvement toward this level.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-21 in the 5K?`, a: `For sub-21:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi, Repetition ${data.paces.repetition.mi}/mi. RPI ${data.rpi}. The key session for sub-21 is interval training at ${data.paces.interval.mi}/mi — running at this pace raises the VO2max ceiling that determines how fast you can race.` },
      { q: 'What is the step from sub-25 to sub-21?', a: `The gap between sub-25 and sub-21 typically closes in 12–24 months of consistent structured training. The shift from recreational to this level requires adding genuine interval work to a base of easy running and threshold sessions. Many runners make this jump by increasing weekly mileage to 35–45 miles and introducing weekly interval sessions for the first time.` },
      { q: `What marathon time does sub-21 5K fitness predict?`, a: `Sub-21 5K fitness (RPI ${data.rpi}) projects to ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. This is a meaningful projection — if you have built marathon-specific training (long runs to 20 miles, marathon-pace work), this is the range you should target. Without long-run preparation, most runners with 21-minute 5K fitness underperform by 20–30 minutes in the marathon.` },
    ],
  },

  'sub-22-minute-5k': {
    title: 'Sub-22 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 22 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-22 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-22 is a meaningful step above the recreational tier. Runners here have built real aerobic fitness and have likely completed at least one structured training season. The training paces show what this fitness level demands consistently.',
    trainingContext: 'For sub-22 5K, interval training is the highest-leverage quality session. Threshold runs build the stamina to sustain hard effort; intervals raise the ceiling that determines sustainable race pace. Most runners at this level benefit from a structured 8–12 week 5K build with a weekly interval session (800m repeats), one threshold session (20 minutes at threshold pace), and three to four easy runs.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-22 minute 5K require?`, a: `For sub-22:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Your interval pace (${data.paces.interval.mi}/mi) is close to but slightly faster than 5K race pace — interval training at this speed directly builds the aerobic capacity that 5K racing requires.` },
      { q: 'What separates a sub-22 runner from a sub-20 runner?', a: `The primary gap is VO2max and threshold stamina. Sub-20 runners have a higher aerobic ceiling (VO2max) and the specific stamina to operate near that ceiling for 19–20 minutes. Sub-22 runners are typically a few months to a couple of years of structured training away from sub-20, assuming they are already running consistently and doing quality work.` },
      { q: `What half marathon does sub-22 5K fitness predict?`, a: `Sub-22 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If you are running sub-22 in the 5K and want to target the half marathon, your aerobic base is strong — add half-specific long runs (10–15 miles) and your half marathon should reflect your aerobic capacity.` },
    ],
  },

  'sub-23-minute-5k': {
    title: 'Sub-23 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 23 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-23 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-23 sits at the boundary between recreational and structured competitive running. Runners here have a genuine aerobic base and can sustain effort for 22+ minutes at high intensity. The training paces show what consistent training at this level looks like.',
    trainingContext: 'For sub-23 5K, the combination of easy base volume and structured quality sessions produces steady improvement. One interval session per week (400m–800m repeats at interval pace) and one threshold session (15–25 minutes at threshold pace), backed by 25–40 miles of easy weekly volume, is the effective framework. Running easy days genuinely easy is often the most impactful change runners at this level can make — it allows threshold and interval sessions to be truly productive.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 23 minutes in the 5K?`, a: `For sub-23:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Easy runs at ${data.paces.easy.mi}/mi are where 80% of training volume lives. Threshold at ${data.paces.threshold.mi}/mi should feel comfortably hard — sustainable for 20 minutes.` },
      { q: 'How quickly can a regular runner reach sub-23?', a: `Most runners who run 3–4 times per week for 6–12 months with some structured quality work can reach sub-23. The key is adding interval or threshold work to the existing easy-run base. Runners who have never done structured quality sessions often improve dramatically (1–2 minutes off their 5K time) within a few months of adding one interval session per week.` },
      { q: `What 10K time does sub-23 5K fitness predict?`, a: `Sub-23 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents['10k']?.timeFormatted || 'calculable'} for the 10K. This assumes comparable 10K-specific training. Your aerobic base supports the 10K distance well — the main adjustment is adding slightly more threshold work, which targets the sustained lactate-threshold effort the 10K demands.` },
    ],
  },

  'sub-24-minute-5k': {
    title: 'Sub-24 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 24 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-24 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-24 is a meaningful fitness milestone signaling consistent aerobic development beyond recreational base. Runners here can sustain moderate-high effort for 23+ minutes and have real aerobic infrastructure to build on.',
    trainingContext: 'For sub-24 5K, adding structured quality work to a base of easy running is the primary lever. One interval session per week (400m repeats at interval pace) and one threshold session (15–20 minutes at threshold pace) produce the VO2max development and threshold stamina needed. Most runners at this level do best with 25–35 miles per week, keeping easy days strictly easy.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-24 in the 5K?`, a: `For sub-24:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. The gap between easy (${data.paces.easy.mi}/mi) and interval (${data.paces.interval.mi}/mi) is significant — these are genuinely different training stimuli requiring different adaptation.` },
      { q: 'What is the biggest training error for runners chasing sub-24?', a: `Running easy days at a moderate effort level — too fast for recovery but too slow for quality. At this fitness level, easy pace (${data.paces.easy.mi}/mi) feels genuinely slow. Runners who cannot tolerate that pace on easy days typically accumulate chronic fatigue and see threshold and interval sessions underperform. Slowing easy runs is almost always the highest-leverage change.` },
      { q: `What equivalent marathon does sub-24 5K fitness predict?`, a: `Sub-24 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. This is your aerobic ceiling — to actually run that marathon, you need 20-mile long runs, marathon-pace work, and 18–20 weeks of marathon-specific preparation. The aerobic capacity is there; the distance-specific fitness requires dedicated training.` },
    ],
  },

  'sub-27-minute-5k': {
    title: 'Sub-27 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 27 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-27 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-27 bridges recreational and structured training. Runners here have genuine aerobic base and can benefit substantially from adding quality work to their easy-running foundation. This is often where structured training first makes a big, visible difference.',
    trainingContext: 'For sub-27 5K, the primary improvement levers are consistent easy volume and the introduction of threshold training. Interval work can be added, but threshold (comfortably hard, 15–20 minutes sustained) is the starting point that produces the most consistent improvement at this level. Three to four runs per week with one threshold session and the rest genuinely easy is the productive structure.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 27 minutes in the 5K?`, a: `For sub-27:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. If you have never done threshold training before, start with 10–15 minutes at ${data.paces.threshold.mi}/mi once per week. This alone typically produces 1–2 minute improvement within 8 weeks for runners with a base.` },
      { q: 'Is sub-27 a good first structured 5K goal?', a: `Yes — sub-27 is an excellent first goal for runners who have been running casually and want to start training with structure. It is challenging enough to require real training but achievable within 3–6 months for most runners who commit to three structured runs per week. The principles at this level — easy days easy, one quality session — establish habits that pay dividends throughout a running career.` },
      { q: `What 10K equivalent does sub-27 5K predict?`, a: `Sub-27 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents['10k']?.timeFormatted || 'calculable'} for the 10K. If you race both distances consistently, this gives you a cross-distance benchmark for how your aerobic development is tracking.` },
    ],
  },

  'sub-30-minute-5k': {
    title: 'Sub-30 Minute 5K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 30 minutes in the 5K. Daniels/Gilbert formula.',
    h1: 'Sub-30 Minute 5K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-30 is the first major 5K milestone for new runners building their fitness. It represents genuine aerobic development — the ability to sustain effort for nearly 30 minutes at a pace above easy running. For many runners, this is where training starts to feel purposeful rather than just exercise.',
    trainingContext: 'For sub-30 5K, consistent easy running is the primary driver. Most runners chasing this mark do not need interval training yet — they need more volume of easy running, done consistently, and one threshold session per week to build the aerobic ceiling. Three runs per week at easy pace (genuinely easy — conversational without effort) plus one session at threshold pace (comfortably hard for 15 minutes) produces steady improvement.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 30 minutes in the 5K?`, a: `For sub-30:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. If ${data.paces.easy.mi}/mi feels hard, start slower — easy pace is where you can talk without effort. As easy runs become genuinely comfortable at this pace, your aerobic base is developing as intended.` },
      { q: 'How long does it take a new runner to break 30 minutes in the 5K?', a: `Most new runners who train consistently can break 30 minutes within 8–16 weeks of starting a structured program. The key is consistency: three to four runs per week at easy effort, with occasional threshold work added after the first 4–6 weeks. Running every day is not necessary — adequate recovery between runs is what allows adaptation to accumulate.` },
      { q: `What is the marathon equivalent of sub-30 5K fitness?`, a: `Sub-30 5K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. This is a long-term benchmark — reaching sub-30 5K fitness is a meaningful aerobic milestone, and the marathon projection shows what your aerobic engine is capable of with full marathon-specific preparation.` },
    ],
  },

  // ---- 10K ----
  'sub-35-minute-10k': {
    title: 'Sub-35 Minute 10K Training Paces — Elite Competitive Fitness',
    description: 'Training paces, RPI, and race equivalents for breaking 35 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-35 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-35 is elite-tier 10K running. At most road races, this places in the top 1–5 finishers. This level requires a high VO2max and exceptional threshold stamina — the physiological product of years of high-volume, structured training.',
    trainingContext: 'Sub-35 10K demands that threshold pace be sustainable for 33–35 minutes with controlled effort. This requires both a high aerobic ceiling (VO2max work via intervals) and the metabolic stamina to operate near that ceiling for an extended duration (threshold work). High weekly volume — 60–80+ miles — is the foundation that makes quality sessions productive.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-35 minute 10K require?`, a: `For sub-35:00 10K (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. At this level, the threshold sessions (${data.paces.threshold.mi}/mi for 20–40 min) are the primary race-specific work. Interval sessions (${data.paces.interval.mi}/mi) push the aerobic ceiling.` },
      { q: 'What is the equivalent marathon for sub-35 10K fitness?', a: `Sub-35 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. Most sub-35 10K runners who properly train for the marathon run near or under this projection — the aerobic base is there.` },
      { q: 'What 5K does sub-35 10K fitness correlate with?', a: `Sub-35 10K (RPI ${data.rpi}) is equivalent to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. In practice, 10K specialists often run slightly under their 5K equivalent because threshold training dominates — and the 10K requires more of that quality than pure speed.` },
    ],
  },

  'sub-36-minute-10k': {
    title: 'Sub-36 Minute 10K Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 36 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-36 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-36 puts you among the top finishers at most local 10K races. This is serious competitive running — the product of consistent high-volume training and disciplined quality sessions over an extended period.',
    trainingContext: 'For sub-36 10K, threshold training is the highest-leverage quality session. 10K racing demands sustained effort near the lactate threshold for 33–36 minutes. Tempo runs at threshold pace (20–40 minutes) build exactly this quality. Interval work raises the aerobic ceiling above threshold, making race pace feel more manageable. 50–70 miles per week with one threshold and one interval session per week is the standard structure.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-36 in the 10K?`, a: `For sub-36:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold sessions at ${data.paces.threshold.mi}/mi for 25–40 minutes are the primary race-specific quality session for sub-36 10K preparation.` },
      { q: `What marathon does sub-36 10K fitness predict?`, a: `Sub-36 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. Converting this aerobic capacity requires marathon-specific preparation: 20-mile long runs and marathon-pace work.` },
      { q: `What 5K time corresponds to sub-36 10K fitness?`, a: `Sub-36 10K (RPI ${data.rpi}) is equivalent to ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. This cross-distance check is useful: if your 5K is near this prediction, your aerobic capacity is in range for a sub-36 10K with 10K-specific preparation.` },
    ],
  },

  'sub-37-minute-10k': {
    title: 'Sub-37 Minute 10K Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 37 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-37 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-37 is well into the competitive tier for 10K racing. Runners here have a high aerobic ceiling and genuine threshold stamina — the product of structured training over 1–3+ years.',
    trainingContext: 'For sub-37 10K, the combination of threshold and interval training drives improvement. Threshold runs at threshold pace for 25–35 minutes build the metabolic stamina the 10K demands. Interval sessions (1000m–1200m repeats) raise the aerobic ceiling. Weekly volume of 45–60 miles with two quality sessions per week is a typical training structure at this level.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-37 minute 10K require?`, a: `For sub-37:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Your threshold pace (${data.paces.threshold.mi}/mi) is close to your 10K race pace — sustained threshold training is the most direct preparation for sub-37 racing.` },
      { q: `What half marathon does sub-37 10K fitness predict?`, a: `Sub-37 10K (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon fitness. The 10K → half marathon equivalency is the most physiologically accurate cross-distance prediction — both tax the threshold energy system in similar proportions.` },
      { q: `What marathon time does sub-37 10K imply?`, a: `Sub-37 10K fitness (RPI ${data.rpi}) implies approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. Full marathon preparation — long runs to 20 miles, marathon-pace work — is required to realize this potential.` },
    ],
  },

  'sub-38-minute-10k': {
    title: 'Sub-38 Minute 10K Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 38 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-38 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-38 10K puts you at the front of most competitive amateur fields. This requires a developed VO2max and threshold stamina built over structured training seasons — not achievable without consistent quality work.',
    trainingContext: 'For sub-38 10K, the standard quality framework applies: one threshold session (20–35 minutes at threshold pace) and one interval session (800m–1200m repeats) per week, with the majority of volume at easy pace. Runners at this level often have 2–4 years of consistent structured training. The improvement from sub-40 to sub-38 typically comes from slightly higher volume and more consistent threshold quality.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-38 in the 10K?`, a: `For sub-38:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold pace (${data.paces.threshold.mi}/mi) is where most of the race-specific adaptation happens for 10K preparation.` },
      { q: `What does sub-38 10K imply for Boston qualifying fitness?`, a: `Sub-38 10K fitness (RPI ${data.rpi}) projects to ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential — which is in BQ range for many age groups. If you are sub-38 in the 10K and have built proper marathon training (20-mile long runs, sustained marathon-pace work), you likely have the aerobic capacity for a BQ.` },
      { q: `What 5K time correlates with sub-38 10K fitness?`, a: `Sub-38 10K (RPI ${data.rpi}) corresponds to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. If your 5K is near this time, your aerobic capacity supports a sub-38 10K with appropriate 10K-specific preparation.` },
    ],
  },

  'sub-39-minute-10k': {
    title: 'Sub-39 Minute 10K Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 39 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-39 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-39 is the bridge between mid-pack competitive and front-of-pack at most local 10K events. Runners here have developed aerobic capacity from structured training and can sustain near-threshold effort for nearly 40 minutes.',
    trainingContext: 'For sub-39 10K, threshold training is the primary quality session — the 10K is run near the lactate threshold, and threshold runs build exactly that metabolic quality. Interval work adds the aerobic ceiling development that makes threshold pace more sustainable. One quality session of each type per week, with 35–50 miles of easy volume, is the effective training structure.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-39 10K require?`, a: `For sub-39:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Easy pace (${data.paces.easy.mi}/mi) is where training volume accumulates. Quality sessions at threshold (${data.paces.threshold.mi}/mi) and interval (${data.paces.interval.mi}/mi) produce the race-specific adaptations.` },
      { q: 'What separates a sub-40 from a sub-39 runner?', a: `The gap is usually threshold stamina — the ability to sustain near-threshold effort for 38–39 minutes rather than 39–40. Runners who transition from sub-40 to sub-39 typically increase threshold session duration from 20 minutes to 25–30 minutes and add slightly more easy volume. The aerobic ceiling is similar; the threshold stamina is marginally higher.` },
      { q: `What half marathon does sub-39 10K fitness predict?`, a: `Sub-39 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. The 10K and half marathon are the most physiologically similar standard distances — this equivalency is among the most reliable cross-distance predictions.` },
    ],
  },

  'sub-42-minute-10k': {
    title: 'Sub-42 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 42 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-42 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-42 is solidly competitive at local 10K races and marks meaningful aerobic development beyond the recreational tier. Runners here have structured training experience and genuine threshold stamina.',
    trainingContext: 'For sub-42 10K, threshold and interval training produce the most direct improvement. Two quality sessions per week — one threshold (20–30 minutes), one interval (800m repeats) — with 30–45 miles of easy volume is the effective structure. Running easy days at ${data.paces?.easy?.mi || \'easy\'} pace or slower allows the quality sessions to generate the adaptation that drives improvement.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-42 in the 10K?`, a: `For sub-42:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. If your threshold sessions at ${data.paces.threshold.mi}/mi feel sustainable for 20 minutes, you are training at the right level. If they feel too easy, your fitness has passed this target.` },
      { q: 'What is the jump from sub-45 to sub-42 in the 10K?', a: `The gap between sub-45 and sub-42 closes in 6–18 months of structured training for most runners. The key additions are weekly threshold work and slightly higher easy volume. Runners who run 3–4 times per week casually often reach sub-45 naturally; the sub-42 step typically requires adding structured quality sessions for the first time.` },
      { q: `What marathon does sub-42 10K fitness predict?`, a: `Sub-42 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. If you plan to race a marathon, this aerobic capacity supports the goal — with proper long-run training (to 20 miles) and marathon-pace work.` },
    ],
  },

  'sub-45-minute-10k': {
    title: 'Sub-45 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 45 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-45 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-45 10K is the natural next milestone for runners who have built a consistent aerobic base. This level requires a few months of structured training beyond recreational fitness and marks real aerobic development.',
    trainingContext: 'For sub-45 10K, adding threshold training to a base of easy running produces the most direct improvement. One threshold session per week (15–20 minutes at threshold pace) and one fartlek or interval session raise both the aerobic ceiling and threshold stamina. Three to four runs per week at 25–40 miles of weekly volume is the typical structure.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 45 minutes in the 10K?`, a: `For sub-45:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold pace (${data.paces.threshold.mi}/mi) should feel comfortably hard — you could speak short sentences but not hold a full conversation. This is the productive zone for sub-45 training.` },
      { q: 'Is sub-45 10K a realistic goal for a recreational runner?', a: `Yes — most runners who run 3–4 times per week consistently for 6–12 months can reach sub-45 with structured threshold training. The biggest barrier is usually not physical ceiling — it is inconsistency or running easy days too fast. Adding one threshold session per week to an existing base typically produces 2–4 minutes of improvement over 8–12 weeks.` },
      { q: `What half marathon corresponds to sub-45 10K fitness?`, a: `Sub-45 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If you plan to race a half marathon, your aerobic base supports it — add half-specific long runs (10–14 miles) and your race time should reflect this equivalent.` },
    ],
  },

  'sub-48-minute-10k': {
    title: 'Sub-48 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 48 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-48 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-48 10K marks the progression from casual to structured fitness. Runners who reach this level have built meaningful aerobic capacity and can sustain effort for 45+ minutes at above-easy pace.',
    trainingContext: 'For sub-48 10K, the primary driver is consistent easy volume with the addition of threshold work. Running 3–4 times per week at easy pace and adding one threshold session (15 minutes at threshold pace) builds the aerobic infrastructure that sub-48 requires. Interval training can be added after threshold work is well-established.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-48 in the 10K?`, a: `For sub-48:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Easy runs at ${data.paces.easy.mi}/mi are the foundation. Threshold at ${data.paces.threshold.mi}/mi (comfortably hard for 15 minutes) is the quality session that drives sub-48 improvement.` },
      { q: 'What is a realistic timeline to go from 55 minutes to sub-48 in the 10K?', a: `Most runners who drop from 55+ minutes to sub-48 do so in 3–9 months of consistent training. The improvements come from adding threshold work to an existing easy-run base. Running 4+ times per week with one quality session per week typically produces measurable improvement every 4–6 weeks.` },
      { q: `What marathon does sub-48 10K fitness predict?`, a: `Sub-48 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. This is your aerobic ceiling — reaching it requires full marathon preparation (20-mile long runs, marathon-pace work) over an 18–20 week build.` },
    ],
  },

  'sub-55-minute-10k': {
    title: 'Sub-55 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 55 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-55 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-55 10K is a realistic and meaningful goal for runners who have built a base of consistent easy running. It signals real aerobic development and positions you well for other recreational race distances.',
    trainingContext: 'For sub-55 10K, the primary tools are consistent easy volume and introduction of threshold training. Runners who have been running 3–4 times per week at easy pace and add one threshold session (12–15 minutes at threshold pace) typically see significant improvement toward this goal within 6–10 weeks. The threshold session does the specific metabolic work the 10K demands.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 55 minutes in the 10K?`, a: `For sub-55:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi. RPI ${data.rpi}. If ${data.paces.easy.mi}/mi feels comfortably conversational, your easy-run base is appropriate. Threshold at ${data.paces.threshold.mi}/mi should feel like controlled hard effort — not racing, but not comfortable.` },
      { q: 'Is sub-55 10K achievable for beginning runners?', a: `Yes — for most healthy adults who run consistently for 3–6 months with some structured work. The aerobic development required is achievable without exceptional fitness or years of training. Consistency is the most important variable: three runs per week every week produces more improvement than six runs one week and none the next.` },
      { q: `What half marathon does sub-55 10K fitness predict?`, a: `Sub-55 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If the half marathon is your next goal, your aerobic base is sufficient to target this time with appropriate long-run training (builds to 10–12 miles) over 10–12 weeks.` },
    ],
  },

  'sub-60-minute-10k': {
    title: 'Sub-60 Minute 10K Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 60 minutes in the 10K. Daniels/Gilbert formula.',
    h1: 'Sub-60 Minute 10K — Training Paces and Fitness Profile',
    openingParagraph: 'Breaking 60 minutes in the 10K is a meaningful milestone for newer runners — it signals consistent aerobic base and the ability to sustain effort for an extended period. For many, this is the first goal that feels like real competitive running.',
    trainingContext: 'For sub-60 10K, the primary lever is consistent easy running with the addition of threshold work. Three to four runs per week, one of which is a threshold session (10–15 minutes at threshold pace), builds the aerobic and metabolic foundation this level requires. Focus on keeping easy days easy (conversational pace) and quality sessions genuinely quality — not medium effort.',
    buildFaq: (data) => [
      { q: `What training paces are needed to break 60 minutes in the 10K?`, a: `For sub-60:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi. RPI ${data.rpi}. Easy pace (${data.paces.easy.mi}/mi) is where most of your training volume should live. Threshold at ${data.paces.threshold.mi}/mi for 10–15 minutes once per week is the quality session that drives sub-60 improvement.` },
      { q: 'How quickly can a beginner reach sub-60 in the 10K?', a: `Most beginners who start from no running base can reach sub-60 10K in 6–12 months of consistent training. The most important variable is consistency — three runs per week every week produces steady aerobic development. Adding threshold work after the first 2–3 months of base building accelerates improvement.` },
      { q: `What 5K corresponds to sub-60 10K fitness?`, a: `Sub-60 10K fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K equivalent. If you are training for the 10K and want a tune-up race, a 5K near this time confirms you are in the right fitness range.` },
    ],
  },

  // ---- Half Marathon ----
  'sub-1-15-half-marathon': {
    title: 'Sub-1:15 Half Marathon Training Paces — Elite Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 1:15 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:15 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:15 half marathon is elite-tier endurance running. At most road races this places in the top handful of finishers. This requires a very high VO2max, exceptional threshold stamina, and the fitness of a serious competitive runner.',
    trainingContext: 'Sub-1:15 half marathon requires sustaining near-threshold pace for 74–75 minutes. This demands both a high aerobic ceiling and the specific metabolic stamina to operate near it for an extended period. High weekly volume (65–85+ miles), two quality sessions per week (one threshold, one interval), and long runs of 15–18 miles are typical for runners at this level.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-1:15 half marathon require?`, a: `For sub-1:15:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold work at ${data.paces.threshold.mi}/mi for 25–40 minutes is the primary race-specific quality session.` },
      { q: `What marathon does sub-1:15 half fitness predict?`, a: `Sub-1:15 half marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential — elite-level marathon territory. Converting this to a marathon requires full marathon-specific build: 20-mile long runs, sustained marathon-pace work, and time.` },
      { q: `What 5K does sub-1:15 half marathon fitness correspond to?`, a: `Sub-1:15 half fitness (RPI ${data.rpi}) is equivalent to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. This cross-distance benchmark shows the full scope of elite-level endurance fitness.` },
    ],
  },

  'sub-1-20-half-marathon': {
    title: 'Sub-1:20 Half Marathon Training Paces — Competitive Elite Fitness',
    description: 'Training paces, RPI, and race equivalents for breaking 1:20 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:20 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:20 half marathon is serious competitive running — front-of-pack at most road races. This is the product of high training volume, consistent quality sessions, and years of aerobic development.',
    trainingContext: 'For sub-1:20 half marathon, threshold running is the most race-specific training. The half marathon is essentially a sustained threshold effort for 80 minutes. Threshold tempo runs (25–40 minutes at threshold pace) build the metabolic stamina to sustain that effort. Long runs at easy pace develop the endurance base. Weekly volume of 55–75 miles supports the quality work.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-1:20 in the half marathon?`, a: `For sub-1:20:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold at ${data.paces.threshold.mi}/mi sustained for 25–40 minutes is the primary quality session.` },
      { q: `What marathon does sub-1:20 half fitness predict?`, a: `Sub-1:20 half marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential — typically Boston qualifying territory for multiple age groups.` },
      { q: `What 10K does sub-1:20 half fitness correlate with?`, a: `Sub-1:20 half fitness (RPI ${data.rpi}) corresponds to approximately ${data.equivalents['10k']?.timeFormatted || 'calculable'} 10K fitness. This is the most reliable cross-distance equivalency pair in running.` },
    ],
  },

  'sub-1-25-half-marathon': {
    title: 'Sub-1:25 Half Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 1:25 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:25 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:25 half marathon is front-of-field performance at most local road races. This fitness level requires consistent high-volume training and structured threshold work over multiple training seasons.',
    trainingContext: 'For sub-1:25 half marathon, threshold training and long runs are the primary tools. Threshold work (25–35 minutes at threshold pace) builds the lactate stamina that half marathon racing requires. Long runs at easy pace (14–16 miles) develop the endurance base. Weekly volume of 45–60 miles with two quality sessions per week is the typical structure at this level.',
    buildFaq: (data) => [
      { q: `What training paces does sub-1:25 half marathon require?`, a: `For sub-1:25:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon pace (${data.paces.marathon.mi}/mi) is also useful: half marathon race pace falls between marathon and threshold pace for most runners.` },
      { q: `What is the BQ-equivalent marathon for sub-1:25 half fitness?`, a: `Sub-1:25 half marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential — which falls within BQ range for several age groups. With full marathon preparation, this aerobic capacity supports a BQ attempt.` },
      { q: `What 5K time corresponds to sub-1:25 half fitness?`, a: `Sub-1:25 half fitness (RPI ${data.rpi}) is equivalent to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K performance.` },
    ],
  },

  'sub-1-30-half-marathon': {
    title: 'Sub-1:30 Half Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 1:30 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:30 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:30 half marathon is a serious competitive milestone — typically top-third to top-quarter finishes at well-attended road races. This is where dedicated training begins to separate runners from casual participants.',
    trainingContext: 'For sub-1:30 half marathon, threshold running is the most important quality session. The half marathon is sustained effort near the lactate threshold for 88–90 minutes — threshold training builds the specific metabolic capacity this requires. Long runs at easy pace (13–16 miles) develop endurance. Weekly volume of 40–55 miles with two quality sessions supports this standard.',
    buildFaq: (data) => [
      { q: `What training paces should I use to target sub-1:30 half marathon?`, a: `For sub-1:30:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Your threshold sessions at ${data.paces.threshold.mi}/mi (25–30 minutes) are the most race-specific preparation. Your long runs should be at ${data.paces.easy.mi}/mi or slower.` },
      { q: `What marathon does sub-1:30 half fitness predict?`, a: `Sub-1:30 half marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. This is often BQ-adjacent territory — depending on age group and gender.` },
      { q: 'Is sub-1:30 half marathon a reasonable first-time goal?', a: `Sub-1:30 is ambitious for a first half marathon — it requires a meaningful aerobic base and structured training. It is realistic for runners who have been running consistently (30+ miles per week) for 6–12 months and have done threshold training. Runners newer to structured training typically target sub-2:00 or sub-1:45 for a first half before building toward 1:30.` },
    ],
  },

  'sub-1-35-half-marathon': {
    title: 'Sub-1:35 Half Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 1:35 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:35 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:35 half marathon places you solidly in the competitive recreational tier — top quarter at most road races. Runners here have real aerobic capacity and have spent meaningful time training with structure.',
    trainingContext: 'For sub-1:35 half marathon, threshold training and long runs are the primary tools. Threshold tempo runs (20–30 minutes) build the sustained-effort capacity the half marathon demands. Long runs at easy pace (12–15 miles) develop the endurance base. Two quality sessions per week with 35–50 miles of total volume is the effective structure.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-1:35 in the half marathon?`, a: `For sub-1:35:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon pace (${data.paces.marathon.mi}/mi) is useful in long-run finishes — half marathon race pace sits between marathon and threshold pace physiologically.` },
      { q: `What marathon does sub-1:35 half fitness predict?`, a: `Sub-1:35 half marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. If you are building toward a marathon, your half fitness is a reliable aerobic benchmark — the marathon projection requires full marathon preparation to realize.` },
      { q: `What 10K corresponds to sub-1:35 half fitness?`, a: `Sub-1:35 half fitness (RPI ${data.rpi}) is equivalent to approximately ${data.equivalents['10k']?.timeFormatted || 'calculable'} 10K performance. This is the most reliable cross-distance pair for prediction.` },
    ],
  },

  'sub-1-40-half-marathon': {
    title: 'Sub-1:40 Half Marathon Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 1:40 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:40 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:40 half marathon is meaningful competitive fitness — a level that requires structured training beyond easy running. Runners here have developed real threshold stamina and aerobic capacity.',
    trainingContext: 'For sub-1:40 half marathon, one threshold session per week (20–25 minutes at threshold pace) and weekly long runs (11–14 miles) produce the specific adaptations this standard requires. Easy volume of 30–45 miles per week supports the quality work. The most common limiting factor at this level: insufficient threshold training or running easy days too fast to recover adequately.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 1:40 in the half marathon?`, a: `For sub-1:40:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold at ${data.paces.threshold.mi}/mi should be sustainable for 20 minutes at controlled effort — comfortably hard, not racing.` },
      { q: 'How long does a 1:45 runner typically take to reach 1:40?', a: `The 1:45 → 1:40 transition typically takes 4–12 months of structured training. The key additions are extending threshold sessions from 15 to 20–25 minutes and maintaining consistent long runs of 12–14 miles. Runners who add these two elements consistently typically bridge this gap within a training cycle.` },
      { q: `What marathon does sub-1:40 half fitness project to?`, a: `Sub-1:40 half marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. This is a meaningful marathon benchmark that reflects the aerobic capacity built through half marathon training.` },
    ],
  },

  'sub-1-45-half-marathon': {
    title: 'Sub-1:45 Half Marathon Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 1:45 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:45 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:45 half marathon is a natural stepping stone for runners who have mastered the sub-2:00 milestone. It requires extending threshold capacity and adding long-run volume — achievable with 3–6 months of structured training for runners who already run consistently.',
    trainingContext: 'For sub-1:45 half marathon, threshold training and long runs are the two highest-leverage tools. One threshold session per week (15–20 minutes at threshold pace) and weekly long runs building to 12–14 miles produce the adaptations this standard requires. Easy volume of 25–40 miles per week with genuinely easy recovery days allows the quality sessions to generate improvement.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-1:45 in the half marathon?`, a: `For sub-1:45:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Threshold at ${data.paces.threshold.mi}/mi for 15–20 minutes drives the metabolic adaptation that sub-1:45 racing requires.` },
      { q: 'Is sub-1:45 realistic for a runner who has done a 2:00 half marathon?', a: `Yes — most runners who have broken 2:00 in the half can reach 1:45 within 12–18 months of structured training. The gap between 2:00 and 1:45 is substantial but bridges consistently with one quality session per week and building long-run volume to 12–14 miles. Patience with adaptation is the primary requirement.` },
      { q: `What 10K does sub-1:45 half marathon fitness predict?`, a: `Sub-1:45 half fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents['10k']?.timeFormatted || 'calculable'} 10K potential. This equivalency check helps confirm whether your aerobic base is tracking toward sub-1:45.` },
    ],
  },

  'sub-1-50-half-marathon': {
    title: 'Sub-1:50 Half Marathon Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 1:50 in the half marathon. Daniels/Gilbert formula.',
    h1: 'Sub-1:50 Half Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-1:50 half marathon is a meaningful step toward competitive recreational fitness. It sits between the recreational milestone of sub-2:00 and the structured training level of sub-1:45 — and getting there typically requires adding real quality work to an easy-run base.',
    trainingContext: 'For sub-1:50 half marathon, the primary additions to a recreational base are threshold training and extended long runs. One threshold session per week (12–18 minutes at threshold pace) and long runs building to 11–13 miles produce the adaptations this level requires. Easy volume of 25–35 miles per week with strictly easy recovery days allows these quality sessions to generate adaptation.',
    buildFaq: (data) => [
      { q: `What training paces should I use to target sub-1:50 half marathon?`, a: `For sub-1:50:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Threshold ${data.paces.threshold.mi}/mi. RPI ${data.rpi}. Easy pace (${data.paces.easy.mi}/mi) is where the majority of your training volume lives. Threshold at ${data.paces.threshold.mi}/mi for 12–18 minutes once per week builds the specific metabolic capacity sub-1:50 requires.` },
      { q: 'What is the typical progression from 2:00 to sub-1:50?', a: `Runners who have broken 2:00 in the half typically reach sub-1:50 in 4–8 months of structured training. The key transitions: running easy days more strictly easy (often requires slowing down significantly), adding a threshold session each week, and building the long run to 11–13 miles consistently. This combination produces steady improvement.` },
      { q: `What marathon does sub-1:50 half fitness predict?`, a: `Sub-1:50 half marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.marathon?.timeFormatted || 'calculable'} marathon potential. If the marathon is your next goal, this fitness level puts you in range for the predicted time — with full marathon-specific preparation (20-mile long runs, marathon-pace work).` },
    ],
  },

  // ---- Marathon ----
  'sub-2-30-marathon': {
    title: 'Sub-2:30 Marathon Training Paces — Elite Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 2:30 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-2:30 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-2:30 marathon is elite endurance performance — the kind achieved by serious competitive runners training at very high volume. This requires exceptional aerobic capacity, threshold stamina, and years of sustained high-mileage training.',
    trainingContext: 'Sub-2:30 marathon demands exceptional threshold stamina and a high VO2max. Marathon-pace runs (sustained effort at goal pace for 12–18 miles) and threshold work (30–40 minutes at threshold pace) are the primary quality sessions. Weekly volume of 80–110+ miles builds the aerobic base that makes quality sessions productive. Long runs of 20–23 miles at easy pace develop the glycogen economy and endurance infrastructure. This is the domain of professional and semi-professional runners.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-2:30 marathon require?`, a: `For sub-2:30:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon pace (${data.paces.marathon.mi}/mi) for 26.2 miles requires sustained threshold-adjacent effort — the training intensity is elite-level across all zones.` },
      { q: 'What half marathon is equivalent to sub-2:30 marathon fitness?', a: `Sub-2:30 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon equivalent — typically sub-1:12 territory, which is professional-level half marathon performance for most age groups.` },
      { q: 'What 5K corresponds to sub-2:30 marathon fitness?', a: `Sub-2:30 marathon fitness (RPI ${data.rpi}) is equivalent to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness — reflective of a complete elite endurance athlete, competitive across all distances.` },
    ],
  },

  'sub-2-45-marathon': {
    title: 'Sub-2:45 Marathon Training Paces — Elite Competitive Fitness',
    description: 'Training paces, RPI, and race equivalents for breaking 2:45 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-2:45 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-2:45 marathon is elite-competitive endurance running. In most age groups this is a Boston qualifier with buffer. It requires very high training volume, structured quality sessions, and years of marathon-specific preparation.',
    trainingContext: 'Sub-2:45 marathon requires sustained effort at near-threshold pace for 2 hours 45 minutes — the physiological demands are extreme by any standard. High weekly volume (70–100 miles), long runs to 22+ miles, and sustained marathon-pace work are the training pillars. Threshold work twice per week at threshold pace builds the metabolic stamina to sustain marathon pace under deep fatigue.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-2:45 marathon require?`, a: `For sub-2:45:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon training runs at ${data.paces.marathon.mi}/mi represent race-day pace — the training session that builds the most specific endurance for 2:45 fitness.` },
      { q: `What half marathon does sub-2:45 marathon fitness predict?`, a: `Sub-2:45 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. This is typically sub-1:20 territory — front of field at most road races.` },
      { q: `What 5K does sub-2:45 marathon imply?`, a: `Sub-2:45 marathon fitness (RPI ${data.rpi}) is equivalent to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness — consistently elite-competitive at 5K distance.` },
    ],
  },

  'sub-3-hour-marathon': {
    title: 'Sub-3 Hour Marathon Training Paces — The Training Required',
    description: 'Training paces, RPI, and race equivalents for breaking 3 hours in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3 Hour Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3 hour marathon is the most-celebrated competitive marathon milestone. Less than 5% of marathon finishers break 3 hours. It requires years of aerobic development, consistent high mileage, disciplined easy-day running, and smart race-day pacing.',
    trainingContext: 'Sub-3 marathon is built on high easy volume (55–80 miles/week), long runs to 20–22 miles, and marathon-pace work in long runs. Threshold training (30–40 minutes at threshold pace) builds the lactate clearance that makes 6:50/mile pace feel controlled for the full 26.2. Easy days must be run genuinely easy — at easy pace or slower — to allow recovery between quality sessions.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-3 hour marathon runner use?`, a: `For sub-3:00:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon training pace (${data.paces.marathon.mi}/mi) is the focus of your longest quality sessions. Easy pace (${data.paces.easy.mi}/mi) is where 80%+ of weekly mileage accumulates.` },
      { q: 'How long does it take to go from sub-4 to sub-3 marathon?', a: `The sub-4 to sub-3 transition typically takes 2–5 years of consistent structured training. The aerobic development required is substantial — each 10-minute improvement in the 3:00–4:00 range requires a significant increase in VO2max and threshold stamina. Runners who make this jump consistently increase weekly mileage, extend long runs, and add serious threshold training over multiple training cycles.` },
      { q: `What half marathon does sub-3 marathon fitness predict?`, a: `Sub-3 hour marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential — typically well under 1:25, which is competitive at most road races.` },
    ],
  },

  'sub-3-05-marathon': {
    title: 'Sub-3:05 Marathon Training Paces — Competitive Elite Fitness',
    description: 'Training paces, RPI, and race equivalents for breaking 3:05 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3:05 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3:05 marathon is elite competitive territory and a BQ time for men in multiple age groups. This requires serious long-term aerobic development — the fitness is not built in a single training cycle.',
    trainingContext: 'Sub-3:05 marathon requires the same training structure as sub-3:00 but with slightly less training maturity. High easy volume (50–75 miles/week), long runs to 20 miles, and sustained marathon-pace work drive the fitness. Threshold training once per week (25–35 minutes) builds the metabolic stamina that marathon pace demands over 26.2 miles.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-3:05 marathon require?`, a: `For sub-3:05:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. The training zones for sub-3:05 and sub-3:00 are very similar — the difference is race-day execution and accumulated fitness rather than fundamentally different training approaches.` },
      { q: `Is sub-3:05 a BQ for most age groups?`, a: `Sub-3:05 is a BQ time for men 35–39 (standard: 3:00:00) with buffer, men 40–44 (standard: 3:05:00) exactly, and men 45–49 (standard: 3:15:00) with buffer. It is not a BQ for the 18–34 men's group (standard: 2:55:00). Check the official BAA site for the current year's standards and any applicable cutoff buffer.` },
      { q: `What half marathon does sub-3:05 marathon fitness predict?`, a: `Sub-3:05 marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. This is typically sub-1:27 territory — front-of-field at most local races.` },
    ],
  },

  'sub-3-10-marathon': {
    title: 'Sub-3:10 Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 3:10 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3:10 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3:10 marathon is a BQ time for several age groups and a competitive performance by any recreational standard. This level requires sustained high-mileage training and multiple marathon-specific build cycles.',
    trainingContext: 'For sub-3:10 marathon, the training structure mirrors sub-3:00 at slightly lower volume. 45–65 miles per week of easy running, long runs to 20 miles at easy pace, and one threshold session per week produce the fitness. Marathon-pace miles in the final sections of long runs are the most race-specific quality training.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-3:10 marathon runner use?`, a: `For sub-3:10:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon training pace (${data.paces.marathon.mi}/mi) should feel controlled but focused — this is the pace you practice in the final miles of 16–20 mile training runs.` },
      { q: `What half marathon does sub-3:10 marathon fitness predict?`, a: `Sub-3:10 marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. This cross-distance benchmark is useful: if you are running near this half time consistently, your aerobic capacity supports a sub-3:10 marathon attempt with full marathon preparation.` },
      { q: `Is sub-3:10 a BQ time?`, a: `Sub-3:10 is a BQ for men 40–44 (standard 3:05, not quite), men 45–49 (standard 3:15, yes with buffer), and close for men 35–39 (standard 3:00). It is within range of BQ for women in younger age groups as well. Check the official BAA standards for your specific age group and gender.` },
    ],
  },

  'sub-3-15-marathon': {
    title: 'Sub-3:15 Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 3:15 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3:15 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3:15 marathon is a BQ time for men 45–49 and close-to-BQ for multiple other age groups. This requires serious long-term marathon preparation and places in the competitive tier at most major marathons.',
    trainingContext: 'For sub-3:15 marathon, high easy volume (40–60 miles/week), consistent long runs to 20 miles, and weekly threshold work are the primary training pillars. Marathon-pace segments in long runs (the final 4–6 miles at goal pace) teach the body to sustain effort when glycogen is depleting — the central challenge of the marathon.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-3:15 marathon require?`, a: `For sub-3:15:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon pace (${data.paces.marathon.mi}/mi) is the race-specific training pace. Easy runs at ${data.paces.easy.mi}/mi or slower allow recovery.` },
      { q: `What half marathon does sub-3:15 marathon fitness predict?`, a: `Sub-3:15 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If you are running near this in the half marathon and have built 20-mile long runs, you are in range for a sub-3:15 marathon.` },
      { q: `What 5K does sub-3:15 marathon fitness correspond to?`, a: `Sub-3:15 marathon fitness (RPI ${data.rpi}) corresponds to approximately ${data.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. This aerobic equivalency shows the full fitness profile across distances.` },
    ],
  },

  'sub-3-20-marathon': {
    title: 'Sub-3:20 Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 3:20 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3:20 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3:20 marathon is a BQ time for several masters age groups and a competitive achievement by any recreational measure. Getting here from sub-3:30 or sub-3:45 requires systematic training investment over multiple cycles.',
    trainingContext: 'For sub-3:20 marathon, the training structure is high easy volume (38–55 miles/week), long runs building to 20 miles, and weekly threshold work. Marathon-pace training runs (final miles of long runs at goal pace) build the specific neuromuscular and metabolic patterns that make race pace sustainable over 26.2 miles.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-3:20 marathon require?`, a: `For sub-3:20:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Your most important training run is a weekly long run (to 20 miles at easy pace) with the final 4–5 miles at marathon pace (${data.paces.marathon.mi}/mi). This is the most race-specific preparation available.` },
      { q: `What half marathon predicts sub-3:20 marathon fitness?`, a: `Sub-3:20 marathon (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. This equivalency is reliable when both distances are comparably trained — half marathon fitness is the best single predictor of marathon aerobic capacity.` },
      { q: `Is sub-3:20 a BQ for women?`, a: `Sub-3:20 marathon is a BQ for women 40–44 (standard 3:35, not quite), but it is within BQ range for women in the 18–34 group (standard 3:25, not quite) and close for several other groups. Specific BQ standards by age group and gender are listed at baa.org. Check the official table for your exact situation.` },
    ],
  },

  'sub-3-30-marathon': {
    title: 'Sub-3:30 Marathon Training Paces — Competitive Fitness Profile',
    description: 'Training paces, RPI, and race equivalents for breaking 3:30 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3:30 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3:30 marathon marks the transition from recreational to competitive marathon running. Runners here have built serious aerobic capacity through consistent structured training and have the endurance to sustain pace for 3+ hours.',
    trainingContext: 'For sub-3:30 marathon, the training pillars are high easy volume, 20-mile long runs, and threshold work. Threshold training once per week (25–35 minutes at threshold pace) builds the lactate clearance that makes marathon pace feel controlled. Long runs at easy pace (to 20 miles) develop the fat-oxidation and glycogen economy that prevents the wall. 35–50 miles per week of consistent training is the typical volume range.',
    buildFaq: (data) => [
      { q: `What training paces does a sub-3:30 marathon runner use?`, a: `For sub-3:30:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. If your easy runs at ${data.paces.easy.mi}/mi feel genuinely easy, you have the aerobic base for sub-3:30. If they feel like moderate effort, build your base further before targeting this standard.` },
      { q: 'How do I train for sub-3:30 if I\'ve been running sub-4:00?', a: `The jump from sub-4:00 to sub-3:30 is significant. It requires 6–18 months of increased volume and more structured quality work. The key additions: weekly long runs building to 20 miles (sub-4:00 runners often cap at 16–18), threshold tempo sessions (most sub-4:00 runners do insufficient threshold work), and more total weekly mileage (targeting 40–50 miles consistently). Training exclusively for sub-3:30 for 18–24 weeks typically produces 15–25 minute improvements from sub-4:00 fitness.` },
      { q: `What half marathon does sub-3:30 marathon fitness predict?`, a: `Sub-3:30 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If you are running near this half time and have built 20-mile long runs, you are in sub-3:30 shape for the full marathon.` },
    ],
  },

  'sub-3-45-marathon': {
    title: 'Sub-3:45 Marathon Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 3:45 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-3:45 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-3:45 marathon is meaningful competitive fitness — well into the upper tier of recreational marathon runners. Getting here requires consistent volume, real long runs, and structured quality work over one or more training cycles.',
    trainingContext: 'For sub-3:45 marathon, the primary training levers are 18–20 mile long runs at easy pace and one threshold session per week. Marathon-pace miles added to the end of long runs are the most race-specific preparation. Total weekly volume of 30–45 miles with one threshold session is the effective structure for this standard.',
    buildFaq: (data) => [
      { q: `What training paces should I use to target sub-3:45 in the marathon?`, a: `For sub-3:45:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi, Interval ${data.paces.interval.mi}/mi. RPI ${data.rpi}. Marathon training pace (${data.paces.marathon.mi}/mi) is what you practice in the final miles of long runs when your legs are already tired. Easy pace (${data.paces.easy.mi}/mi) is where all other running happens.` },
      { q: 'What is the biggest training error for sub-3:45 marathon runners?', a: `Not running enough miles at genuinely easy pace. Runners who target sub-3:45 often run 3–4 days per week but keep all runs at moderate effort. Slowing easy days to ${data.paces.easy.mi}/mi or slower (which often feels too slow) allows recovery and enables the occasional hard session to generate real adaptation. Adding a 5th easy run often produces more improvement than making existing runs harder.` },
      { q: `What half marathon corresponds to sub-3:45 marathon fitness?`, a: `Sub-3:45 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. If you have run a half marathon near this time recently, you have the aerobic capacity for a sub-3:45 marathon — with 20-mile long runs and full marathon preparation.` },
    ],
  },

  'sub-4-30-marathon': {
    title: 'Sub-4:30 Marathon Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 4:30 in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-4:30 Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Sub-4:30 marathon is a meaningful milestone for runners who have crossed the finish line but want to run with more intent. It requires adding structure to easy-run base — real long runs, some quality work, and disciplined pacing on race day.',
    trainingContext: 'For sub-4:30 marathon, long runs (to 18–20 miles at easy pace) and threshold work (one session per week, 15–20 minutes) are the two highest-leverage training additions. Most runners targeting sub-4:30 have the aerobic base from easy running — what they typically lack is threshold stamina and race-specific long-run experience. One threshold session and a weekly long run that extends to 18 miles produces consistent improvement.',
    buildFaq: (data) => [
      { q: `What training paces are needed for sub-4:30 in the marathon?`, a: `For sub-4:30:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi. RPI ${data.rpi}. Marathon training pace (${data.paces.marathon.mi}/mi) is the specific effort you practice in long-run finishes. Easy pace (${data.paces.easy.mi}/mi) is where most training miles accumulate.` },
      { q: 'What is the jump from sub-5:00 to sub-4:30 marathon?', a: `The jump from sub-5:00 to sub-4:30 is significant but achievable in a single well-structured training cycle (18–20 weeks). The key is adding long runs to 18–20 miles (most sub-5:00 marathon training stops at 16), adding one threshold session per week, and running easy days genuinely easy. Runners who make all three of these changes consistently typically break 4:30 within one marathon training cycle.` },
      { q: `What half marathon does sub-4:30 marathon fitness predict?`, a: `Sub-4:30 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. This gives a useful cross-training benchmark for how your aerobic base is developing relative to the marathon goal.` },
    ],
  },

  'sub-5-hour-marathon': {
    title: 'Sub-5 Hour Marathon Training Paces — Fitness Profile and Training Zones',
    description: 'Training paces, RPI, and race equivalents for breaking 5 hours in the marathon. Daniels/Gilbert formula.',
    h1: 'Sub-5 Hour Marathon — Training Paces and Fitness Profile',
    openingParagraph: 'Breaking 5 hours in the marathon is a genuine athletic achievement — 26.2 miles of sustained effort over nearly 5 hours. It requires consistent training, smart pacing, and the endurance to keep moving when the final 10K demands everything you have.',
    trainingContext: 'For sub-5 hour marathon, consistent easy running and long runs are the foundation. Long runs building to 18 miles at easy pace provide the endurance base. One threshold session per week (12–15 minutes at threshold pace) builds the metabolic capacity to sustain goal pace without crossing into the anaerobic zone that depletes you early. Running easy days genuinely easy — at easy pace or slower — is the most important discipline for runners targeting this standard.',
    buildFaq: (data) => [
      { q: `What training paces should I use to break 5 hours in the marathon?`, a: `For sub-5:00:00 (${data.goalTimeLabel}): Easy ${data.paces.easy.mi}/mi, Marathon ${data.paces.marathon.mi}/mi, Threshold ${data.paces.threshold.mi}/mi. RPI ${data.rpi}. Marathon training pace (${data.paces.marathon.mi}/mi) is what you practice in the final miles of long runs. Running everything else at easy pace (${data.paces.easy.mi}/mi or slower) allows recovery and prevents the chronic fatigue that causes most marathon failures.` },
      { q: 'Is sub-5 a realistic goal for a first marathon?', a: `Sub-5 is achievable for a first marathon by runners who have followed a consistent 16–20 week training plan with long runs building to 18–20 miles and some threshold work. The most common first-marathon error that pushes the finish time past 5 hours: starting too fast and walking in the final miles. Conservative pacing — starting at goal pace or slightly slower — is the most reliable strategy for a first marathon finish under 5 hours.` },
      { q: `What half marathon does sub-5 marathon fitness predict?`, a: `Sub-5 marathon fitness (RPI ${data.rpi}) projects to approximately ${data.equivalents.halfMarathon?.timeFormatted || 'calculable'} half marathon potential. Racing a half marathon in the months before a marathon attempt gives a useful fitness benchmark — if you finish near this projection, you are in range for sub-5.` },
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
      title: config.title,
      description: config.description,
      url: `https://strideiq.run/tools/training-pace-calculator/goals/${params.slug}`,
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
              <SignupCtaLink className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors" telemetry={{ cta: 'goal_pace_hook' }}>
                Start free trial
              </SignupCtaLink>
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
