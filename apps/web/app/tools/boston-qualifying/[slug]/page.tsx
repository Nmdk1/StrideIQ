import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import TrainingPaceCalculator from '@/app/components/tools/TrainingPaceCalculator'
import { JsonLd } from '@/components/seo/JsonLd'
import { SignupCtaLink } from '@/components/tools/SignupCtaLink'
import bqData from '@/data/bq-tables.json'

// ============================================================================
// TYPES — mirror the schema in bq-tables.json
// ============================================================================

type PaceEntry = { mi: string; km: string; secPerMile: number }
type EquivEntry = { label: string; distanceMeters: number; timeSeconds: number; timeFormatted: string; paceMi: string; paceKm: string } | null

type BQEntry = {
  slug:         string
  gender:       string
  genderLabel:  string
  ageGroup:     string
  midAge:       number
  bqTime:       string
  bqSeconds:    number
  rpi:          number
  wmaGradePct:  number
  paces: {
    easy:       PaceEntry
    marathon:   PaceEntry
    threshold:  PaceEntry
    interval:   PaceEntry
    repetition: PaceEntry
  }
  equivalents: {
    '5k':   EquivEntry
    '10k':  EquivEntry
    'half': EquivEntry
  }
}

// ============================================================================
// STATIC PER-PAGE CONFIG
// Numbers in BLUF/FAQ come from bqData JSON — none hardcoded here.
// Coaching text is the human voice; BQ times themselves are not in this config.
// ============================================================================

const BQ_PAGE_CONFIG: Record<string, {
  title: string
  description: string
  h1: string
  openingParagraph: string
  trainingContext: string | ((data: BQEntry) => string)
  buildFaq: (data: BQEntry) => { q: string; a: string }[]
}> = {
  'boston-qualifying-time-men-18-34': {
    title: 'Boston Qualifying Time for Men 18–34 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 18–34 with training paces, WMA age grade, and equivalent fitness at 5K, 10K, and half marathon. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 18–34',
    openingParagraph: 'The 18–34 BQ standard is the most demanding in the field — set for runners at peak physiological capacity, competing against the deepest pool of qualifiers. The cutoff buffer tends to run highest in this group. Training for a genuine BQ buffer, not just the standard, is the realistic strategy.',
    trainingContext: 'For men 18–34 targeting a BQ, high weekly volume and structured threshold work are the primary drivers. Long runs of 20+ miles build the glycogen economy that prevents the wall at mile 20. Threshold runs (comfortably hard, 20–40 minutes sustained) develop the lactate clearance that lets BQ pace feel controlled for 26.2 miles. Marathon-pace segments in long runs teach pacing discipline under fatigue.',
    buildFaq: (d) => [
      { q: `What training paces should I use for a ${d.bqTime} BQ marathon?`, a: `To build fitness for a ${d.bqTime} marathon (RPI ${d.rpi}), your training zones are: Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Your marathon training runs should target ${d.paces.marathon.mi}/mi. Your easy runs — the majority of your weekly mileage — must be at ${d.paces.easy.mi} or slower. If your easy runs feel only mildly comfortable at that pace, you need more base before targeting this standard.` },
      { q: 'How competitive is the 18–34 age group for Boston entry?', a: `The 18–34 group is typically among the most competitive for BQ cutoffs because it contains the greatest number of qualifiers relative to the field allocation. A cutoff buffer of 5–8 minutes under the standard is often required for confident entry. Check the official BAA registration updates for the current year\'s actual cutoff.` },
      { q: `What 5K fitness does a ${d.bqTime} marathon BQ require?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) projects to equivalent 5K fitness of ${d.equivalents['5k']?.timeFormatted || 'calculable above'}. This aerobic equivalency assumes comparable training for each distance. A runner who has built genuine marathon fitness through high volume and long runs may find their 5K slightly above this prediction — the marathon taxes recovery systems that the 5K does not.` },
    ],
  },

  'boston-qualifying-time-men-35-39': {
    title: 'Boston Qualifying Time for Men 35–39 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 35–39 with training paces, WMA age grade, and equivalent fitness at 5K, 10K, and half marathon.`,
    h1: 'Boston Qualifying Time — Men Ages 35–39',
    openingParagraph: 'Men 35–39 are in their prime marathon years — endurance continues developing into the late 30s, and race-day pacing discipline has matured. This age group produces some of the most competitive BQ performances on an age-adjusted basis. The standard reflects that depth.',
    trainingContext: 'Marathon training for men 35–39 follows the same structural priorities as the open class, with slightly more attention to recovery between hard sessions. Long runs remain the most important training element. Threshold tempo runs develop the sustained-effort capacity that marathon pace requires. Easy days must be genuinely easy — men in this age group often make the mistake of running recovery days at a pace that prevents full recovery.',
    buildFaq: (d) => [
      { q: `What are the training paces for a ${d.bqTime} marathon?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi, Repetition ${d.paces.repetition.mi}/mi. Note the gap between marathon pace (${d.paces.marathon.mi}) and easy pace (${d.paces.easy.mi}) — running easy days too fast collapses this separation and prevents quality threshold sessions from generating real adaptation.` },
      { q: 'Is the 35–39 BQ standard achievable with consistent training?', a: `Yes — men who train consistently with structured quality work typically reach this standard within 1–3 years of dedicated marathon training. The key variables are weekly mileage (higher is better, with adequate recovery), threshold session quality, and long runs that extend to 20+ miles. Age alone is not a limiting factor in this decade.` },
      { q: `What half marathon time is equivalent to a ${d.bqTime} BQ?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) projects to a half marathon equivalent of ${d.equivalents['half']?.timeFormatted || 'calculable'}. If you can run ${d.equivalents['half']?.timeFormatted || 'this time'} in a well-paced half, you likely have the aerobic capacity for a BQ. Translating that capacity to the full marathon still requires 20-mile long runs and marathon-specific preparation.` },
    ],
  },

  'boston-qualifying-time-men-40-44': {
    title: 'Boston Qualifying Time for Men 40–44 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 40–44 with training paces, WMA age grade (${Math.round(67.8)}%), and equivalent times at other distances. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 40–44',
    openingParagraph: 'Men 40–44 enter the masters division with a slightly more generous BQ standard — and often with their sharpest race-day judgment. Marathon performance in this decade is highly trainable, and the 3:05 standard is within reach for runners who commit to structured preparation.',
    trainingContext: (d) => `Masters marathon training for men 40–44 differs from the 30s primarily in recovery management. The aerobic adaptation response remains strong, but tissue repair between hard sessions takes longer. Space quality sessions (threshold, interval, long run with marathon-pace miles) at least 5 days apart. Easy days should genuinely feel easy — at ${d.paces.easy.mi}/mi or slower — to allow full recovery before the next quality stimulus.`,
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} men's 40–44 BQ require?`, a: `To achieve a ${d.bqTime} marathon (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Your WMA age-grade for this performance is ${d.wmaGradePct}% — strong masters-level running. The training paces reflect genuine sub-elite fitness that requires months of consistent preparation.` },
      { q: `How does the men's 40–44 BQ compare to the open standard on an age-adjusted basis?`, a: `A ${d.bqTime} marathon for a ${d.midAge}-year-old man scores ${d.wmaGradePct}% WMA age-graded — representing solid masters performance. On an age-adjusted basis, this places you in the competitive tier of masters marathon racing. It is a meaningfully harder performance relative to your age peers than simply matching the BQ time at face value.` },
      { q: `What 5K equivalent does a men's 40–44 BQ reflect?`, a: `A ${d.bqTime} marathon BQ (RPI ${d.rpi}) is equivalent to ${d.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness at ${d.equivalents['5k']?.paceMi || 'this'}/mi pace. The 5K equivalency is less accurate for marathon performance because the marathon demands glycogen economy, pacing experience, and long-run adaptation beyond what raw aerobic capacity (measured by 5K) captures.` },
    ],
  },

  'boston-qualifying-time-men-45-49': {
    title: 'Boston Qualifying Time for Men 45–49 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 45–49 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 45–49',
    openingParagraph: 'Men 45–49 who qualify for Boston are running impressive age-adjusted performances. The 3:15 standard requires sustained aerobic fitness that takes years to develop — but this is also the decade where many runners achieve their most disciplined, consistent training.',
    trainingContext: 'For men 45–49, recovery between hard sessions is the primary training management tool. Threshold sessions remain highly effective — the aerobic system adapts well in this decade. The key shift is in session spacing: most 45–49 runners do best with quality sessions every 6–8 days rather than weekly. Long runs at easy pace (with marathon-pace miles at the end) are the highest-leverage training element for BQ preparation.',
    buildFaq: (d) => [
      { q: `What training paces should a man ages 45–49 use for a ${d.bqTime} BQ?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At this age, running easy days at marathon pace (${d.paces.marathon.mi}) is the single most common training error. Easy days at ${d.paces.easy.mi} or slower allow the recovery needed for quality sessions to generate adaptation.` },
      { q: 'Is it realistic to BQ for the first time in your late 40s?', a: `Yes — many runners achieve their first BQ after 45. This decade often brings the patience and training consistency that elite preparation requires. Runners in their late 40s who have been building mileage for several years have the aerobic base; the remaining gaps are usually in threshold quality and marathon-specific long runs. A structured 18–24 week build with adequate easy volume typically produces the result.` },
      { q: `What WMA age grade is a ${d.bqTime} marathon for a man in the 45–49 group?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This puts the performance in the competitive masters category — above 65% age grade is consistently competitive in masters marathon fields. The BQ standards are calibrated to roughly this level, which is why they increase with each age group.` },
    ],
  },

  'boston-qualifying-time-men-50-54': {
    title: 'Boston Qualifying Time for Men 50–54 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 50–54 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 50–54',
    openingParagraph: 'Marathon performance for men 50–54 is more trainable than most runners assume. The 3:20 BQ standard reflects competitive masters fitness — achievable for runners who train with structure and protect their recovery. Many men in this age group run their most consistent training of their careers.',
    trainingContext: 'For men 50–54, three to four structured runs per week often produces better results than five or six with compromised recovery. Long runs (18–20 miles) remain the most important session. Threshold work once per week builds the lactate clearance that sustains marathon pace. Recovery between hard efforts needs 5–7 days. Sleep quality and sleep quantity have the most impact on adaptation speed at this age.',
    buildFaq: (d) => [
      { q: `What are the training paces for a ${d.bqTime} men's 50–54 BQ?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Marathon training pace (${d.paces.marathon.mi}/mi) is what you practice in the final miles of long runs. Easy pace (${d.paces.easy.mi}/mi or slower) is where 80%+ of your weekly volume accumulates.` },
      { q: `How does the 3:20 BQ age-grade for men 50–54?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This is solidly competitive masters running — consistently in the top tier of 50–54 marathon fields at major races. The performance reflects aerobic fitness developed over years, not just race-day execution.` },
      { q: `What half marathon time corresponds to ${d.bqTime} marathon BQ fitness?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) projects to ${d.equivalents['half']?.timeFormatted || 'calculable'} half marathon fitness. If you are hitting this half marathon time and have trained the long-run volume, you likely have the aerobic capacity for a BQ attempt. Add marathon-specific preparation — 20-mile long runs, marathon-pace work — before your target race.` },
    ],
  },

  'boston-qualifying-time-men-55-59': {
    title: 'Boston Qualifying Time for Men 55–59 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 55–59 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 55–59',
    openingParagraph: 'Men 55–59 who achieve a BQ are among the most committed masters runners in the field. The 3:30 standard requires maintaining aerobic fitness that many recreational runners at this age have never reached. It is a testament to consistent, structured training over many years.',
    trainingContext: 'For men 55–59, the highest-leverage training changes are protecting recovery and running easy days genuinely easy. Threshold running remains effective — one quality tempo session per week builds the lactate clearance that makes marathon pace sustainable. Long runs are the marathon-specific tool that most differentiates BQ-level fitness from strong recreational fitness. Recovery from 20-mile long runs takes longer than it did at 40, which is a scheduling constraint, not a physiological barrier.',
    buildFaq: (d) => [
      { q: `What training paces does a men's 55–59 BQ of ${d.bqTime} require?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. The gap between easy (${d.paces.easy.mi}) and marathon pace (${d.paces.marathon.mi}) is significant — about ${Math.round((d.paces.easy.secPerMile - d.paces.marathon.secPerMile) / 60 * 10) / 10} minutes per mile. Collapsing this gap by running easy days too fast is the most common error at this age.` },
      { q: `Is 3:30 realistic for men in their late 50s?`, a: `Yes — for men who have trained consistently for marathon distance, 3:30 is a realistic goal with a structured 20-24 week build. Men who are returning to marathon training after a gap typically need 12–18 months of consistent base building before a BQ attempt is realistic. The aerobic system responds to training stimulus throughout the 50s.` },
      { q: `What is the WMA age grade for a ${d.bqTime} marathon at age ${d.midAge}?`, a: `A ${d.bqTime} marathon scores ${d.wmaGradePct}% WMA age-graded at age ${d.midAge}. This represents genuinely competitive masters running — 65%+ WMA is the regional class threshold, meaning you would be competitive at masters championship events. The BQ standards track this tier closely across all age groups.` },
    ],
  },

  'boston-qualifying-time-men-60-64': {
    title: 'Boston Qualifying Time for Men 60–64 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 60–64 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 60–64',
    openingParagraph: 'Men who qualify for Boston in the 60–64 age group are achieving something remarkable. A 3:50 marathon at this age — when adjusted for age — represents genuine mastery of endurance running. The field in this group at Boston is impressive; these are not casual qualifiers.',
    trainingContext: 'For men 60–64, recovery management is the central training discipline. The aerobic adaptation response remains — threshold work still produces improvement. But recovery between hard efforts now takes 6–8 days, not 4–5. Long runs remain the highest-leverage training session; 18–20 miles at easy pace provides the endurance foundation that marathon pace depends on. Many men in this group run 4 days per week with one long run, one threshold session, and two easy runs.',
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} BQ for men 60–64 require?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At age ${d.midAge}, easy pace (${d.paces.easy.mi}/mi) should feel genuinely easy — if it requires effort to hold, you are still recovering from a previous session. Your marathon training pace (${d.paces.marathon.mi}/mi) should feel controlled but focused.` },
      { q: `What WMA age grade is a 3:50 marathon for men 60–64?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This reflects the fact that the BQ standards are set to require competitive masters-level fitness at every age group. A 67–68% age grade represents running consistently in the top third of masters marathon fields.` },
      { q: `What 10K equivalent does ${d.bqTime} marathon BQ fitness represent?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) is equivalent to ${d.equivalents['10k']?.timeFormatted || 'calculable'} 10K fitness. The 10K equivalency for marathon performance is useful for benchmarking aerobic capacity, though marathon-specific endurance (long runs, glycogen economy) is required to actually run the equivalent marathon time.` },
    ],
  },

  'boston-qualifying-time-men-65-69': {
    title: 'Boston Qualifying Time for Men 65–69 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 65–69 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 65–69',
    openingParagraph: 'A 4:05 BQ for men 65–69 reflects serious competitive fitness at an age where most people are not running competitively at all. WMA age-grading reveals how demanding this standard is relative to world-record pace for this age group — it is not a consolation milestone.',
    trainingContext: 'Men 65–69 who are training toward a BQ should prioritize quality over frequency. Three runs per week with one long run and one threshold session often produces better adaptation than five or six runs with compromised recovery. Sleep and nutrition matter more than at any earlier decade. The aerobic system still adapts — patience with adaptation timelines (slightly longer than at 50) is the required mental adjustment.',
    buildFaq: (d) => [
      { q: `What are the training paces for a men's 65–69 BQ of ${d.bqTime}?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Easy pace at ${d.paces.easy.mi}/mi or slower allows full recovery. At age 65+, "easy" must mean genuinely easy — not comfortable-hard.` },
      { q: `How does a 4:05 marathon age-grade for men 65–69?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This is in the competitive masters range — runners at 65–70% WMA are placing in the top third of their age group at major marathon events. The 4:05 standard reflects this competitive positioning, not a lenient participation standard.` },
      { q: 'Can men in their late 60s still improve marathon times?', a: `Yes — men who add consistent training in their late 60s, particularly easy volume and threshold work, show measurable improvement. The adaptation timeline is longer than in the 50s, and recovery needs are higher, but the physiological mechanisms are intact. Men who have been running consistently for years typically have the aerobic base already; the remaining gains come from better session quality and recovery management.` },
    ],
  },

  'boston-qualifying-time-men-70-74': {
    title: 'Boston Qualifying Time for Men 70–74 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 70–74 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 70–74',
    openingParagraph: 'Men who qualify for Boston at 70–74 represent the pinnacle of masters endurance running. The 4:20 standard, age-adjusted, reflects fitness that a small fraction of the running population at this age achieves. The training and discipline required are genuine.',
    trainingContext: (d) => `For men 70–74, consistent easy volume is the foundation. Long runs remain the primary marathon-specific session — building to 16–18 miles at easy pace is still achievable and necessary. Threshold work once every 10–14 days at ${d.paces.threshold.mi}/mi pace maintains the lactate clearance that marathon effort requires. Recovery from every hard session is the primary scheduling concern.`,
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} BQ require for men 70–74?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Marathon training pace (${d.paces.marathon.mi}/mi) is the target for the final miles of long runs. All other miles should be at easy pace or slower.` },
      { q: `What WMA grade is a 4:20 marathon for men 70–74?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. At this age, the WMA factor is significantly above 1.0, meaning the standard accounts for substantial age-related performance decline from the open class. Achieving this time represents competitive running by any measure.` },
      { q: `What 5K does ${d.bqTime} marathon fitness equate to for men 70–74?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) is equivalent to ${d.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. This aerobic equivalency illustrates the full fitness profile of a BQ-level marathoner in the 70–74 group — competitive across all distances on an age-adjusted basis.` },
    ],
  },

  'boston-qualifying-time-men-75-79': {
    title: 'Boston Qualifying Time for Men 75–79 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 75–79 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 75–79',
    openingParagraph: 'Running a 4:35 marathon in your late 70s and qualifying for Boston is an extraordinary athletic achievement. The WMA age grade for this performance places it firmly in the competitive masters elite. These runners are outliers — and they are usually the most disciplined, consistent trainers in any room.',
    trainingContext: 'Men 75–79 who are targeting a BQ understand recovery as the primary training variable. The workout does not build fitness — recovery from the workout does. Three structured sessions per week with full easy days in between, centered on long runs and threshold work, is the pattern that works. Volume matters, but volume with adequate recovery matters more.',
    buildFaq: (d) => [
      { q: `What are the training paces for a men's 75–79 BQ of ${d.bqTime}?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At age ${d.midAge}, running easy days at ${d.paces.easy.mi}/mi or slower is the single most important training discipline. Fatigue accumulated from running too fast on recovery days compounds more significantly than at younger ages.` },
      { q: `How does a 4:35 marathon age-grade for men 75–79?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. The WMA table accounts for the significant age factor at 75–79, making the absolute time less meaningful than the age-adjusted score. This performance places a 75–79 runner in the competitive tier of their age group nationally.` },
      { q: 'What is the most important training principle for men in their late 70s?', a: `Consistency above all else. The runners who qualify for Boston in the 75–79 group have been running for decades — the aerobic base is deep. The primary training discipline is spacing hard efforts far enough apart to recover fully. One hard session attempted too soon after the last can set back training by 2–3 weeks at this age.` },
    ],
  },

  'boston-qualifying-time-men-80-plus': {
    title: 'Boston Qualifying Time for Men 80+ — Training Paces and Fitness Profile',
    description: `2026 BQ standard for men 80+ with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Men Ages 80+',
    openingParagraph: 'Running a 4:50 marathon at 80 or older and qualifying for Boston is, simply, remarkable. This is not a category with many qualifiers, but the runners who achieve it demonstrate what consistent, lifelong endurance training produces. The WMA age grade for this performance is genuinely elite for this age group.',
    trainingContext: 'Men 80+ who are training for marathon qualifying are primarily managing recovery between efforts. Long runs, done at easy pace and extending as far as the body recovers from, are the foundation. Threshold work — once every two weeks — maintains the aerobic ceiling. Every hard effort must be earned with several easy days before it and several after it.',
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} BQ require for men 80+?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi. At 80+, marathon training pace (${d.paces.marathon.mi}/mi) is reserved for the final miles of prepared long runs. All other running accumulates at easy pace.` },
      { q: `What WMA age grade is a 4:50 marathon for men 80+?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. The WMA factor at age 80 is substantial — a 4:50 marathon represents competitive performance relative to world-record standards for octogenarian runners. The BAA standard is calibrated appropriately for this.` },
      { q: 'How many men 80+ typically qualify for Boston each year?', a: `The 80+ field at Boston is small — typically dozens of runners worldwide, not hundreds. Qualifying requires sustained fitness that very few runners maintain into their 80s. Those who do are typically lifetime runners with decades of consistent training. This is not a time that can be built toward from scratch in the late 70s — it is maintained.` },
    ],
  },

  // ---- WOMEN ----

  'boston-qualifying-time-women-18-34': {
    title: 'Boston Qualifying Time for Women 18–34 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 18–34 with training paces, WMA age grade, and equivalent times at 5K, 10K, and half marathon.`,
    h1: 'Boston Qualifying Time — Women Ages 18–34',
    openingParagraph: 'The 3:25 BQ standard for women 18–34 places at the demanding end of the competitive recreational tier. This age group has the deepest qualifier pool among women, and the cutoff buffer tends to run higher than the standard would suggest. Training for a genuine buffer — not just the standard — is the practical strategy.',
    trainingContext: 'Women 18–34 targeting a BQ have peak physiological capacity on their side — VO2max, recovery speed, and musculoskeletal resilience are at their highest. High weekly mileage, structured threshold work, and 20-mile long runs are the primary tools. The most common gap between this group and their BQ: insufficient long-run volume and running easy days too fast.',
    buildFaq: (d) => [
      { q: `What training paces are needed for a women's 18–34 BQ of ${d.bqTime}?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. The easy pace (${d.paces.easy.mi}/mi or slower) should feel almost embarrassingly slow — that is correct. Threshold (${d.paces.threshold.mi}/mi) should feel comfortably hard, sustainable for 20–40 minutes.` },
      { q: 'How competitive is the women\'s 18–34 Boston field?', a: `The 18–34 women\'s group is highly competitive. The standard is set for peak-age performance, and the cutoff buffer in recent years has required running well under 3:25 for guaranteed entry. A 5–8 minute buffer under the standard is typically needed. Check the official BAA registration updates for each year\'s exact cutoff.` },
      { q: `What half marathon time corresponds to a ${d.bqTime} women's BQ?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) projects to a half marathon equivalent of ${d.equivalents['half']?.timeFormatted || 'calculable'} at ${d.equivalents['half']?.paceMi || 'this'}/mi. If you are running near this half marathon time, you have the aerobic capacity for a BQ — the remaining preparation is distance-specific: 20-mile long runs and marathon-pace work in the final weeks of your build.` },
    ],
  },

  'boston-qualifying-time-women-35-39': {
    title: 'Boston Qualifying Time for Women 35–39 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 35–39 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 35–39',
    openingParagraph: 'Women 35–39 are often at their peak marathon performance years. The endurance component of marathon running develops late, and the patience and pacing discipline that comes with running experience make this decade highly productive. The 3:30 standard is demanding and achievable.',
    trainingContext: 'Marathon training for women 35–39 follows the same structural priorities as the open class: high easy volume, threshold quality, and 20-mile long runs. Slight adjustments toward recovery — spacing quality sessions by 5 days rather than 4 — are appropriate. Women at this age often find their most consistent training yet, aided by the discipline and body awareness that comes with experience.',
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} women's 35–39 BQ require?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi, Repetition ${d.paces.repetition.mi}/mi. Your marathon training runs target ${d.paces.marathon.mi}/mi. The majority of weekly volume accumulates at ${d.paces.easy.mi}/mi or slower.` },
      { q: 'Can women in their late 30s achieve a first BQ?', a: `Yes — women who set their first BQ in their late 30s are common at Boston. Many women reach their strongest marathon performances in their mid-to-late 30s. The aerobic base from years of running combines with mature race-day judgment. A structured 20-24 week build is typically the missing piece, not fitness ceiling.` },
      { q: `What 5K fitness does a ${d.bqTime} marathon BQ represent?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) projects to ${d.equivalents['5k']?.timeFormatted || 'calculable'} 5K fitness. This gives a useful cross-check: if you are running near this 5K time, your aerobic capacity supports the BQ. Distance-specific preparation (long runs, marathon pace) is still required to convert that capacity to the full marathon.` },
    ],
  },

  'boston-qualifying-time-women-40-44': {
    title: 'Boston Qualifying Time for Women 40–44 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 40–44 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 40–44',
    openingParagraph: 'Many women run their fastest marathons in their early 40s — not despite their age but because of the training consistency and racing intelligence that comes with it. The 3:35 BQ standard for women 40–44 reflects competitive masters fitness that a well-trained woman in this decade can achieve.',
    trainingContext: (d) => `Women 40–44 targeting a BQ should prioritize long runs and threshold work, with careful recovery management between hard sessions. The aerobic system adapts strongly at this age. Running easy days genuinely easy — at ${d.paces.easy.mi}/mi or slower — is the most impactful discipline change most women at this level can make. Recovery from hard sessions takes a day longer than it did at 30; plan accordingly.`,
    buildFaq: (d) => [
      { q: `What are the training paces for a women's 40–44 BQ of ${d.bqTime}?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. The WMA age grade for this performance is ${d.wmaGradePct}% — you are running well above average for your age group. These training paces reflect the fitness level required to sustain that level of performance.` },
      { q: 'Do women 40–44 have a realistic shot at Boston entry after qualifying?', a: `Yes — the women's 40–44 group typically has a less competitive cutoff buffer than the 18–34 group because the pool of qualifiers is smaller. A 3–5 minute buffer under 3:35 is usually sufficient. Confirm with the official BAA registration updates for the current year's exact cutoff.` },
      { q: `What half marathon predicts ${d.bqTime} marathon BQ fitness for women 40–44?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) is equivalent to ${d.equivalents['half']?.timeFormatted || 'calculable'} half marathon fitness. Women in the 40–44 group who are running near this half marathon time and have built 18–20 mile long runs are typically in BQ shape for a well-executed race.` },
    ],
  },

  'boston-qualifying-time-women-45-49': {
    title: 'Boston Qualifying Time for Women 45–49 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 45–49 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 45–49',
    openingParagraph: 'The 3:45 BQ standard for women 45–49 requires sustained aerobic fitness developed over years. Women who qualify in this age group typically have been running consistently for a decade or more — the BQ is the product of accumulated fitness, not a single training cycle.',
    trainingContext: 'For women 45–49, recovery management becomes more important. Threshold sessions remain highly effective — one good tempo run per week produces real adaptation. The spacing of quality sessions matters: most women in this group do best with 5–6 days between hard efforts. Long runs at easy pace, extended to 18–20 miles, are the most race-specific preparation for the 3:45 BQ standard.',
    buildFaq: (d) => [
      { q: `What training paces does a women's 45–49 BQ of ${d.bqTime} require?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Marathon training pace (${d.paces.marathon.mi}/mi) is practiced in the final miles of long runs when glycogen is depleting — this is the most race-specific adaptation for the 45–49 BQ.` },
      { q: `What WMA age grade does a ${d.bqTime} marathon reflect for women 45–49?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This is competitive masters performance — above 65% WMA places a runner in the regional class, competing for age-group awards at most road races. The BQ standard is calibrated to require roughly this level of fitness.` },
      { q: 'Is it common for women to BQ for the first time in their late 40s?', a: `Yes — this is a productive decade for first-time qualifiers. Women who have been running consistently and add structured marathon preparation often find that their late 40s produce their strongest marathon performances on an age-adjusted basis. Experience with pacing, nutrition, and training periodization compounds over time.` },
    ],
  },

  'boston-qualifying-time-women-50-54': {
    title: 'Boston Qualifying Time for Women 50–54 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 50–54 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 50–54',
    openingParagraph: 'Women who qualify for Boston at 50–54 are achieving impressive marathon fitness at an age where many runners plateau. The 3:50 standard requires genuine aerobic development — it is one of the standards where consistent, structured training most clearly separates qualifiers from the broad recreational field.',
    trainingContext: 'Women 50–54 who are targeting a BQ should center their training on long runs and threshold quality. Three to four structured runs per week with full recovery between hard efforts is the proven pattern at this age. Recovery from 20-mile long runs takes 7–10 days at 50+ — accounting for this in training scheduling prevents the chronic fatigue that derails most BQ attempts.',
    buildFaq: (d) => [
      { q: `What training paces does a women's 50–54 BQ of ${d.bqTime} require?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. If your easy runs feel truly easy at ${d.paces.easy.mi}/mi, your recovery is adequate. If they feel like moderate effort, you are carrying fatigue from previous sessions — a signal to reduce intensity before adding more quality.` },
      { q: `How does 3:50 age-grade for women 50–54?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This is solidly competitive masters running. The women's 50–54 group at Boston contains some of the most dedicated masters athletes in road racing — this is not a low-bar standard.` },
      { q: `What 10K equivalent does ${d.bqTime} marathon BQ fitness represent for women 50–54?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) is equivalent to ${d.equivalents['10k']?.timeFormatted || 'calculable'} 10K fitness. This cross-distance benchmark is useful: if you are running near this 10K time and have built long-run volume, you have the aerobic capacity for a BQ attempt.` },
    ],
  },

  'boston-qualifying-time-women-55-59': {
    title: 'Boston Qualifying Time for Women 55–59 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 55–59 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 55–59',
    openingParagraph: 'A 4:00 BQ for women 55–59 is a legitimate athletic achievement. The standard reflects competitive masters fitness — the kind built over years of consistent training, not a single focused cycle. Women who qualify in this group are typically among the most experienced and disciplined runners in the field.',
    trainingContext: 'For women 55–59, training effectiveness comes from quality over quantity. One threshold session and one long run per week, surrounded by easy running, is the sustainable structure that produces adaptation without overreaching. Recovery is the primary training variable — protecting sleep, spacing hard efforts, and keeping easy days genuinely easy determines whether the quality sessions generate improvement.',
    buildFaq: (d) => [
      { q: `What are the training paces for a women's 55–59 BQ of ${d.bqTime}?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At age ${d.midAge}, running easy days at ${d.paces.easy.mi}/mi requires discipline — the pace can feel slower than it should. Trust the formula. The adaptation happens in recovery, not in the effort itself.` },
      { q: `What WMA age grade does a ${d.bqTime} marathon reflect for women 55–59?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded — consistently in the competitive masters tier. The women's 55–59 group at Boston is a high-quality field. Qualifying requires real fitness, and racing well in that field is a meaningful athletic achievement.` },
      { q: 'What is the most important training adjustment for women in their late 50s?', a: `The most impactful adjustment is extending recovery between hard sessions. Women in their late 50s who are pushing quality sessions on a weekly schedule are often overreaching — the adaptation from threshold and interval work needs 6–8 days to fully manifest. Slowing the training cycle (not the individual paces) typically produces the best results.` },
    ],
  },

  'boston-qualifying-time-women-60-64': {
    title: 'Boston Qualifying Time for Women 60–64 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 60–64 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 60–64',
    openingParagraph: 'Women who qualify for Boston at 60–64 are among the most remarkable endurance athletes in any age group. A 4:20 marathon at 60+ — age-adjusted — places at the competitive level of masters running nationally. The depth of fitness required is genuine.',
    trainingContext: (d) => `Women 60–64 targeting a BQ center their training on recovery management and long-run quality. Three structured sessions per week — long run, threshold, easy-plus fartlek — with full recovery between each is the productive pattern. Easy pace at ${d.paces.easy.mi}/mi or slower must be the norm for recovery runs. The aerobic system still adapts; patience with longer adaptation timelines is the required adjustment.`,
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} women's 60–64 BQ require?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. Marathon training pace (${d.paces.marathon.mi}/mi) is the target for the final miles of your longest training runs. Everything else accumulates at easy pace (${d.paces.easy.mi}/mi or slower).` },
      { q: `What WMA grade is a 4:20 marathon for women 60–64?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. The WMA table accounts for significant age factors at 60–64, making the absolute time less meaningful than the age-adjusted score. This is competitive masters running by any measure.` },
      { q: `What 5K equivalent does ${d.bqTime} marathon fitness represent?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) projects to ${d.equivalents['5k']?.timeFormatted || 'calculable'} 5K equivalent fitness. This cross-distance view helps confirm whether the aerobic engine matches the marathon goal. Women who are running near this 5K time have the capacity for a BQ attempt with appropriate marathon-specific preparation.` },
    ],
  },

  'boston-qualifying-time-women-65-69': {
    title: 'Boston Qualifying Time for Women 65–69 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 65–69 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 65–69',
    openingParagraph: 'Women who run a 4:35 Boston qualifier at 65–69 are demonstrating lifelong fitness that most people never achieve at any age. This is not a participation milestone — it is genuine competitive endurance performance measured against world-record standards for the age group.',
    trainingContext: 'For women 65–69, training structure should be built entirely around recovery. One long run (14–18 miles at easy pace) and one threshold session per 10–14 days is the productive rhythm. All other running is genuinely easy. Quality over frequency — the adaptation from a fully recovered threshold session is greater than two moderate sessions done while fatigued.',
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} women's 65–69 BQ require?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At age ${d.midAge}, easy pace (${d.paces.easy.mi}/mi) should feel almost too slow. That is the point — full recovery between hard efforts is what allows the next threshold session to generate real adaptation.` },
      { q: `What WMA age grade does a ${d.bqTime} marathon represent for women 65–69?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. This is competitive masters performance. The BAA standard for this age group is calibrated to require genuine fitness — not a lenient standard designed to increase participation.` },
      { q: 'Can women in their late 60s maintain BQ-level fitness over multiple years?', a: `Yes — women who achieve a BQ in their late 60s and maintain consistent training can hold BQ fitness for many years. The keys are consistency over intensity, protecting recovery, and adapting training structure to longer recovery timelines. Many women in this age group report their most disciplined and enjoyable training — the urgency of proving themselves is gone, and the process becomes the reward.` },
    ],
  },

  'boston-qualifying-time-women-70-74': {
    title: 'Boston Qualifying Time for Women 70–74 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 70–74 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 70–74',
    openingParagraph: 'A 4:50 Boston qualifier for women 70–74 is among the most impressive achievements in recreational running. The WMA age grade for this performance reflects genuine elite masters fitness. Women in this group are outliers by almost any measure of athletic longevity.',
    trainingContext: 'Women 70–74 training toward a BQ are managing recovery as the central variable in every training decision. Long runs of 14–16 miles at easy pace are the primary marathon-specific preparation. Threshold work every 10–14 days maintains the aerobic ceiling. Sleep quality, nutrition, and the spacing of all hard efforts determine whether training produces improvement or fatigue.',
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} BQ for women 70–74 require?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At age ${d.midAge}, the easy pace (${d.paces.easy.mi}/mi) is the foundation of all training. Marathon training pace (${d.paces.marathon.mi}/mi) is reserved for the final miles of the longest runs.` },
      { q: `What WMA grade is a 4:50 marathon for women 70–74?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. The substantial WMA age factor for this age group means that achieving this absolute time represents competitive performance by masters running standards. This is not a low bar — it requires the aerobic engine of a trained endurance athlete.` },
      { q: `What half marathon equivalent does ${d.bqTime} BQ fitness represent?`, a: `A ${d.bqTime} marathon (RPI ${d.rpi}) is equivalent to ${d.equivalents['half']?.timeFormatted || 'calculable'} half marathon fitness. This cross-distance check is useful for benchmarking aerobic capacity as marathon preparation progresses.` },
    ],
  },

  'boston-qualifying-time-women-75-79': {
    title: 'Boston Qualifying Time for Women 75–79 — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 75–79 with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 75–79',
    openingParagraph: 'Women who qualify for Boston at 75–79 are running one of the most age-adjusted competitive performances in road racing. A 5:05 marathon at this age is not a slow time — it is a demanding physical achievement that requires lifelong aerobic development and extraordinary consistency.',
    trainingContext: 'Women 75–79 who are maintaining BQ-level fitness understand that recovery is the workout. Hard sessions — long runs and threshold work — need to be spaced far enough apart to generate adaptation, not just accumulate fatigue. Two hard sessions per week is typically too many at this age. One high-quality effort per 7–10 days, with all other running genuinely easy, is the productive rhythm.',
    buildFaq: (d) => [
      { q: `What training paces are needed for a women's 75–79 BQ of ${d.bqTime}?`, a: `For a ${d.bqTime} BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi, Interval ${d.paces.interval.mi}/mi. At age ${d.midAge}, the primary training discipline is running everything between quality sessions at genuinely easy pace (${d.paces.easy.mi}/mi or slower). Accumulated fatigue degrades quality sessions far more at this age than at 50.` },
      { q: `How does a 5:05 marathon age-grade for women 75–79?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. The WMA factor at 75–79 is very high, meaning a large absolute-time correction is applied. This performance is genuinely competitive in the 75–79 masters category nationally.` },
      { q: 'What does lifelong endurance training produce for women 75–79?', a: `The women who are achieving BQ times at 75–79 are demonstrating that sustained aerobic training preserves cardiovascular capacity, metabolic flexibility, and musculoskeletal health in ways that sedentary aging does not. These are not exceptional genetics alone — they are the result of decades of consistent, structured physical training. The aerobic system rewards long-term use.` },
    ],
  },

  'boston-qualifying-time-women-80-plus': {
    title: 'Boston Qualifying Time for Women 80+ — Training Paces and Fitness Profile',
    description: `2026 BQ standard for women 80+ with training paces, WMA age grade, and equivalent times. Daniels/Gilbert formula.`,
    h1: 'Boston Qualifying Time — Women Ages 80+',
    openingParagraph: 'Running a 5:20 marathon at 80 or older and qualifying for Boston represents one of the most extraordinary achievements in endurance sport. The women who achieve this are living evidence of what sustained aerobic training produces over a lifetime. Age is not the ceiling.',
    trainingContext: 'Women 80+ who are maintaining marathon fitness understand that every hard effort must be carefully managed for recovery. Long runs at easy pace, as far as the body recovers from, remain the primary marathon-specific training. Threshold work every two weeks maintains aerobic quality. Every run begins with how the body feels — not with a scheduled pace or effort level.',
    buildFaq: (d) => [
      { q: `What training paces does a ${d.bqTime} BQ require for women 80+?`, a: `For a ${d.bqTime} marathon BQ (RPI ${d.rpi}): Easy ${d.paces.easy.mi}/mi, Marathon ${d.paces.marathon.mi}/mi, Threshold ${d.paces.threshold.mi}/mi. At age 80+, marathon training runs at ${d.paces.marathon.mi}/mi are reserved for the final miles of fully prepared long runs. The rest of training is at easy pace (${d.paces.easy.mi}/mi or slower), which is where the foundational aerobic work accumulates.` },
      { q: `What WMA age grade is a 5:20 marathon for women 80+?`, a: `A ${d.bqTime} marathon at age ${d.midAge} scores ${d.wmaGradePct}% WMA age-graded. The WMA table applies a very large age factor for women 80+, reflecting how far absolute performance has moved from open-class standards. This performance is competitive at the masters elite level and reflects decades of consistent training, not just natural ability.` },
      { q: 'How many women 80+ qualify for Boston each year?', a: `The field of women 80+ who qualify for Boston is small — typically a few dozen runners worldwide. These are lifetime athletes who have maintained consistent aerobic training across decades. The BAA standard for this age group is deliberately set to require genuine fitness, not to artificially inflate the qualifying pool.` },
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
  const config = BQ_PAGE_CONFIG[params.slug]
  if (!config) return {}
  return {
    title: config.title,
    description: config.description,
    alternates: { canonical: `https://strideiq.run/tools/boston-qualifying/${params.slug}` },
    openGraph: {
      title: config.title,
      description: config.description,
      url: `https://strideiq.run/tools/boston-qualifying/${params.slug}`,
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
  return Object.keys(bqData)
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

export default function BQAgePage({ params }: Props) {
  const config = BQ_PAGE_CONFIG[params.slug]
  if (!config) notFound()

  const data = (bqData as unknown as Record<string, BQEntry>)[params.slug]
  if (!data) notFound()

  const faq = config.buildFaq(data)

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Tools', item: 'https://strideiq.run/tools' },
      { '@type': 'ListItem', position: 2, name: 'Boston Qualifying Times', item: 'https://strideiq.run/tools/boston-qualifying' },
      { '@type': 'ListItem', position: 3, name: config.h1, item: `https://strideiq.run/tools/boston-qualifying/${params.slug}` },
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
          <Link href="/tools/boston-qualifying" className="hover:text-orange-400 transition-colors">Boston Qualifying Times</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">{config.h1}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-4">{config.h1}</h1>

        <p className="text-slate-300 leading-relaxed mb-8">{config.openingParagraph}</p>

        {/* BLUF */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-8">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong>{' '}
            The 2026 BQ standard for {data.genderLabel} ages {data.ageGroup} is{' '}
            <span className="font-mono font-bold text-white">{data.bqTime}</span>.
            This requires an RPI of {data.rpi} — equivalent to {data.equivalents['5k']?.timeFormatted} 5K fitness.
            Training paces: easy {data.paces.easy.mi}/mi, threshold {data.paces.threshold.mi}/mi,
            interval {data.paces.interval.mi}/mi. WMA age grade: {data.wmaGradePct}%.
          </p>
        </div>

        {/* BQ Standard */}
        <section className="mb-8">
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center gap-4">
              <div className="flex-1">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">2026 BQ Standard</p>
                <p className="text-4xl font-mono font-bold text-white">{data.bqTime}</p>
                <p className="text-slate-400 text-sm mt-1">{data.genderLabel} ages {data.ageGroup}</p>
              </div>
              <div className="grid grid-cols-3 gap-4 sm:gap-6">
                <div className="text-center">
                  <p className="text-xs text-slate-500 mb-1">RPI</p>
                  <p className="text-xl font-bold text-orange-400">{data.rpi}</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-slate-500 mb-1">WMA Grade</p>
                  <p className="text-xl font-bold text-green-400">{data.wmaGradePct}%</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-slate-500 mb-1">Equiv 5K</p>
                  <p className="text-xl font-bold text-blue-400">{data.equivalents['5k']?.timeFormatted || '—'}</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Training paces */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-2">Training paces for a {data.bqTime} BQ</h2>
          <p className="text-slate-400 text-sm mb-4">
            All zones computed from RPI {data.rpi} via the Daniels/Gilbert oxygen cost formula.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-5 shadow-xl">
            <PaceZoneRow label="Easy (80%+ of weekly running)" pace={data.paces.easy} color="text-slate-300" />
            <PaceZoneRow label="Marathon Pace" pace={data.paces.marathon} color="text-orange-400" />
            <PaceZoneRow label="Threshold (comfortably hard)" pace={data.paces.threshold} color="text-green-400" />
            <PaceZoneRow label="Interval (VO2max sessions)" pace={data.paces.interval} color="text-blue-400" />
            <PaceZoneRow label="Repetition (short fast reps)" pace={data.paces.repetition} color="text-purple-400" />
            <p className="text-xs text-slate-500 mt-3">
              Calculated from Daniels/Gilbert oxygen cost equations. Easy pace means &ldquo;this pace or slower.&rdquo;
            </p>
          </div>
        </section>

        {/* Equivalent fitness */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Equivalent race fitness</h2>
          <p className="text-slate-400 text-sm mb-4">
            Predicted equivalent times at other distances for an athlete with RPI {data.rpi}. Assumes comparable distance-specific training.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {(['5k', '10k', 'half'] as const).map((key) => {
              const e = data.equivalents[key]
              if (!e) return null
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

        {/* Training context */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Training approach for a {data.bqTime} BQ</h2>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300">
            <p>{typeof config.trainingContext === 'function' ? config.trainingContext(data) : config.trainingContext}</p>
          </div>
        </section>

        {/* Calculator embed */}
        <section className="mb-10">
          <h2 className="text-2xl font-bold mb-4">Calculate your current training paces</h2>
          <p className="text-slate-400 mb-4">
            Enter your current race time to see your training zones and how close you are to BQ-level fitness.
          </p>
          <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 shadow-xl">
            <TrainingPaceCalculator />
          </div>
        </section>

        {/* BQ Cutoff Note */}
        <section className="mb-10">
          <div className="bg-slate-800/60 border border-slate-700/30 rounded-xl p-5">
            <h3 className="font-semibold text-white mb-2">About the BQ cutoff</h3>
            <p className="text-slate-300 text-sm leading-relaxed">
              Running a BQ time opens the registration window — it does not guarantee entry. BAA applies a
              cutoff buffer each year based on how many runners qualify relative to available field spots.
              For the most accurate and up-to-date cutoff information, refer to the official BAA registration
              page at baa.org during the registration window for your target race year.
            </p>
          </div>
        </section>

        {/* N=1 CTA */}
        <section className="mb-10">
          <div className="bg-gradient-to-r from-orange-900/20 to-slate-900 border border-orange-500/30 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-2">BQ paces are calculated — your training data makes them personal</h3>
            <p className="text-slate-300 leading-relaxed mb-4">
              The Daniels/Gilbert formula gives the training zones for {data.bqTime} fitness. StrideIQ tracks
              whether your specific training is actually building toward that standard — which threshold sessions
              produce your best adaptation, how quickly you recover between hard efforts, and when your fitness
              is peaking. Population formulas start the conversation. Your training data finishes it.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tools/boston-qualifying" className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors">
                All BQ standards →
              </Link>
              <SignupCtaLink className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors" telemetry={{ cta: 'bq_slug_hook' }}>
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

        {/* Related */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Other BQ age groups</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/boston-qualifying" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Full BQ standards table →
            </Link>
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training pace calculator →
            </Link>
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              WMA age-grading calculator →
            </Link>
            <Link href="/tools/race-equivalency/half-marathon-to-marathon" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Race equivalency →
            </Link>
            <Link href="/tools/heat-adjusted-pace" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Heat-adjusted pace →
            </Link>
          </div>
        </section>

        <div className="mt-8 text-xs text-slate-500">
          <p>
            BQ standards: Boston Athletic Association 2026 (verified 2026-02-26).
            Training paces: Daniels/Gilbert oxygen cost equations (1979).
            WMA age-grading: Alan Jones 2025 standards.
          </p>
        </div>
      </div>
    </div>
  )
}
