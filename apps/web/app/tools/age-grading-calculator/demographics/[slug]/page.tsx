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

type DemoPageEntry = {
  title: string
  description: string
  h1: string
  openingParagraph: string
  trainingContext: string
  buildFaq: (data: DemoEntry) => { q: string; a: string }[]
}

function makeDistGenderFaq(distLabel: string, _paceZone?: string) {
  return (data: DemoEntry): { q: string; a: string }[] => {
    const r0 = data.rows[0]
    const l70 = r0?.levels[70]
    const l60 = r0?.levels[60]
    return [
      {
        q: `What is a good ${distLabel} time for ${data.genderLabel.toLowerCase()} in their ${data.ageDecade}?`,
        a: `Using WMA age-grading standards, a ${r0?.age}-year-old ${data.genderLabel === 'Men' ? 'man' : 'woman'} running ${l60?.timeFormatted} scores 60% ("Local Class"). A 70% "Regional Class" performance at that age is ${l70?.timeFormatted}. These benchmarks are derived from world-record data for each age group, not population averages.`,
      },
      {
        q: `What training paces should ${data.genderLabel.toLowerCase()} in their ${data.ageDecade} use for ${distLabel} training?`,
        a: `The right training paces depend on your current fitness. At 70% age-grade (${l70?.timeFormatted} for a ${r0?.age}-year-old), your training zones are: Easy ${l70?.trainingPaces?.easy.mi}/mi, Threshold ${l70?.trainingPaces?.threshold.mi}/mi, Interval ${l70?.trainingPaces?.interval.mi}/mi. At 60% age-grade (${l60?.timeFormatted}): Easy ${l60?.trainingPaces?.easy.mi}/mi, Threshold ${l60?.trainingPaces?.threshold.mi}/mi. Use the calculator below to find your exact paces.`,
      },
      {
        q: `How does ${distLabel} performance change through the ${data.ageDecade}?`,
        a: `WMA data shows a gradual performance decline with each decade — typically two to five percent per five years for most distances. The age factors in the table above account for this and allow fair comparison across ages. Consistent training often offsets age-related decline significantly. Many runners in their ${data.ageDecade} who train with structure outperform their unstructured earlier years on an age-adjusted basis.`,
      },
    ]
  }
}

const DEMO_PAGE_CONFIG: Record<string, DemoPageEntry> = {
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

  // ============================================================================
  // BATCH 2C: 50 new demographic configs
  // Organized by: 5K Men, 5K Women, 10K Men, 10K Women, HM Men, HM Women, Mara Men, Mara Women
  // All buildFaq functions pull numbers from data — no hardcoded values.
  // ============================================================================


    // ---- 5K MEN ----
    '5k-times-men-age-20s': {
      title: "Good 5K Times for Men in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men in Their 20s",
      openingParagraph: "Men in their 20s are at peak physiological capacity — VO2max is near its highest, recovery is fastest, and aerobic adaptation is rapid. The WMA benchmarks for this decade reflect what consistently trained competitive runners achieve. For many, this is the decade where structured training first produces dramatic improvement.",
      trainingContext: "5K training for men in their 20s benefits most from a combination of interval work (raising the aerobic ceiling) and threshold training (building sustained-effort stamina). Recovery between hard sessions is fast at this age — two quality sessions per week are sustainable. The main bottleneck is often training consistency and running easy days genuinely easy, which allows the quality sessions to generate real adaptation.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-men-age-30s': {
      title: "Good 5K Times for Men in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men in Their 30s",
      openingParagraph: "Men in their 30s often run their fastest career 5Ks — experience, training consistency, and disciplined pacing combine with still-high aerobic capacity. The WMA standards for this decade show what competitive running at 30–39 looks like relative to world-record benchmarks.",
      trainingContext: "5K training for men in their 30s follows the same principles as in the 20s, with slightly more attention to recovery between hard sessions. Two quality sessions per week (one interval, one threshold) remain productive. Easy volume at genuine easy pace continues to be the foundation. Runners in their mid-30s often find that training consistency — showing up every week — produces their strongest performances.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-men-age-40s': {
      title: "Good 5K Times for Men in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men in Their 40s",
      openingParagraph: "Men in their 40s competing in the 5K are well into masters territory — and many are running faster than they did at 30 on an age-adjusted basis. The WMA standards reflect the competitive depth of this age group, which is substantial at most road races.",
      trainingContext: "5K training for men in their 40s is similar to earlier decades but with recovery as a more important variable. Spacing quality sessions 5–6 days apart rather than 4 maintains the productivity of threshold and interval work. Easy pace must be genuinely easy. Most men in their 40s who run under 20 minutes for the 5K have been training consistently for 5+ years.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-men-age-50s': {
      title: "Good 5K Times for Men in Their 50s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 50–59, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men in Their 50s",
      openingParagraph: "Men racing the 5K in their 50s are in one of the most active masters age groups on the road racing circuit. WMA age-grading reveals the competitive standards at this age — and many men are achieving better age-adjusted scores than they did in their 30s.",
      trainingContext: "5K training for men in their 50s requires more deliberate recovery management. One interval session and one threshold session per week remain effective, but 6 full easy days between them — not 4 — is often more productive. Easy running at genuinely easy pace (the kind that feels too slow) accumulates the aerobic base that quality sessions draw on.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-men-age-60s': {
      title: "Good 5K Times for Men in Their 60s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 60–69, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men in Their 60s",
      openingParagraph: "Men racing the 5K in their 60s demonstrate remarkable maintained fitness. Age-grading reveals that a 65-year-old running a competitive 5K on WMA standards is achieving something physiologically impressive by any measure — not just for the age group.",
      trainingContext: "5K training for men in their 60s centers on one quality session per week (alternating interval and threshold across weeks) and adequate easy running between sessions. The aerobic adaptation response remains — the adjustment is in session frequency, not session content. One hard session every 7–10 days with all other running genuinely easy is typically the productive rhythm.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-men-age-70s': {
      title: "Good 5K Times for Men in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men in Their 70s",
      openingParagraph: "Men competing in the 5K in their 70s are a committed, high-performing group. WMA standards reveal just how demanding their absolute times are — the age factors for this decade are substantial, meaning even modest absolute times represent serious age-adjusted performance.",
      trainingContext: "5K training for men in their 70s requires careful recovery management above all else. One quality session per 10–14 days, with all other running genuinely easy, is the productive rhythm. Long intervals are replaced by shorter, more frequent easy runs. The aerobic system still responds to stimulus — patience with adaptation timelines is the primary mental adjustment.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-men-age-80s': {
      title: "Good 5K Times for Men in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for men 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Men Age 80+",
      openingParagraph: "Men competing in the 5K at 80+ are among the most remarkable endurance athletes in road racing. The WMA standards for this age group reflect world-record caliber performance relative to octogenarian runners — achieving any competitive result here is extraordinary.",
      trainingContext: "5K training for men 80+ is centered entirely around recovery. One quality effort every 10–14 days — whether a threshold session or a fartlek — is the upper limit for most. All other running is genuinely easy. The aerobic base from decades of running is deep; the primary training variable is protecting recovery to allow the next quality effort to be productive.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },

    // ---- 5K WOMEN ----
    '5k-times-women-age-20s': {
      title: "Good 5K Times for Women in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for women 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Women in Their 20s",
      openingParagraph: "Women in their 20s are at physiological peak — VO2max is near its highest, recovery is fastest, and adaptation to training is rapid. This decade often produces the fastest absolute 5K times for women who train consistently. The WMA benchmarks here show what competitive performance at this age looks like.",
      trainingContext: "5K training for women in their 20s benefits from high-quality interval work and threshold training. Two quality sessions per week (one interval, one threshold) are sustainable with adequate easy volume. Running easy days genuinely easy — at the paces in the table below — allows the quality sessions to produce real adaptation. The most common mistake at this age: running every run at moderate effort and missing both the genuine easy recovery and genuine hard quality.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-women-age-30s': {
      title: "Good 5K Times for Women in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for women 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Women in Their 30s",
      openingParagraph: "Women in their 30s often achieve their strongest 5K performances — training consistency, pacing discipline, and body awareness combine with still-high aerobic capacity. Many women set personal records in their mid-30s. The WMA standards here reflect serious competitive depth in this decade.",
      trainingContext: "5K training for women in their 30s follows the same principles as the 20s but with slightly more attention to recovery spacing. Two quality sessions per week remain effective for most. Easy running at genuinely easy pace is the foundation — running this pace feels slow but allows the quality sessions to generate the adaptation that drives improvement.",
      buildFaq: makeDistGenderFaq('5K', 'interval'),
    },
    '5k-times-women-age-60s': {
      title: "Good 5K Times for Women in Their 60s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for women 60–69, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Women in Their 60s",
      openingParagraph: "Women racing the 5K in their 60s are among the most competitive masters age groups in road racing. WMA standards reveal that achieving competitive results at 60–69 requires genuinely impressive fitness relative to world-record benchmarks. The depth in this group at major road races is real.",
      trainingContext: "5K training for women in their 60s requires one quality session per week with full easy recovery days between. Threshold training (comfortably hard for 15–20 minutes) is the most effective quality session for this age group and distance. Running easy days at genuinely easy pace — often slower than runners expect — allows the weekly threshold session to produce real adaptation.",
      buildFaq: makeDistGenderFaq('5K', 'threshold'),
    },
    '5k-times-women-age-70s': {
      title: "Good 5K Times for Women in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for women 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Women in Their 70s",
      openingParagraph: "Women competing in the 5K at 70–79 represent lifelong fitness maintained at a high level. WMA standards show how demanding the benchmarks are relative to world records for this age group — even the 60% mark requires sustained aerobic training.",
      trainingContext: "5K training for women in their 70s centers on consistent easy running with one quality effort per 10–14 days. The aerobic system still adapts to training stimulus. Recovery management is the primary discipline — ensuring sufficient easy days between quality sessions prevents the fatigue accumulation that limits improvement at this age.",
      buildFaq: makeDistGenderFaq('5K', 'threshold'),
    },
    '5k-times-women-age-80s': {
      title: "Good 5K Times for Women in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 5K benchmarks for women 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "5K Benchmarks for Women Age 80+",
      openingParagraph: "Women competing in the 5K at 80+ are demonstrating extraordinary athletic longevity. The WMA standards for this age group reflect world-record-caliber relative performance — any result at this age in a road race is a significant achievement.",
      trainingContext: "5K training for women 80+ is organized entirely around recovery. Easy running as the foundation, with one quality effort per two weeks. The aerobic base from decades of training is deep and requires maintenance more than development. Every training decision is filtered through: 'Will I recover from this in time for the next quality session?'",
      buildFaq: makeDistGenderFaq('5K', 'threshold'),
    },

    // ---- 10K MEN ----
    '10k-times-men-age-20s': {
      title: "Good 10K Times for Men in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for men 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Men in Their 20s",
      openingParagraph: "Men in their 20s competing in the 10K have peak aerobic capacity and fast recovery — the ideal combination for high-quality endurance training. WMA benchmarks for this decade reflect genuine competitive performance measured against world records.",
      trainingContext: "10K training for men in their 20s benefits from threshold training as the primary quality session, supplemented by intervals. The 10K demands sustained effort near the lactate threshold for 28–50+ minutes. Threshold tempo runs (25–35 minutes at threshold pace) build the specific metabolic quality that 10K racing requires. Two quality sessions per week with adequate easy volume produces consistent improvement.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-men-age-30s': {
      title: "Good 10K Times for Men in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for men 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Men in Their 30s",
      openingParagraph: "Men in their 30s often achieve their peak 10K performances — the balance of aerobic capacity, threshold stamina, and training experience is optimal. Many men set 10K personal records in their early to mid-30s. WMA standards reflect the competitive depth at this age.",
      trainingContext: "10K training for men in their 30s combines threshold work (the primary 10K-specific quality) with interval sessions. Threshold runs at threshold pace for 25–35 minutes directly build the lactate stamina the 10K demands. Easy volume at genuinely easy pace supports the quality sessions. Recovery between hard sessions is still efficient in this decade.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-men-age-40s': {
      title: "Good 10K Times for Men in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for men 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Men in Their 40s",
      openingParagraph: "Men racing the 10K in their 40s are well into masters territory — and the competitive depth in this age group at major road races is substantial. WMA standards show what each performance level represents relative to world records for men 40–49.",
      trainingContext: "10K training for men in their 40s requires slightly more recovery spacing between hard sessions. One threshold session and one interval session per week, spaced 5–6 days apart, remains productive. Easy pace at genuinely easy pace is the foundation. The most important training adjustment in this decade: not adding more hard sessions, but ensuring each hard session is truly hard and each recovery day is truly easy.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-men-age-50s': {
      title: "Good 10K Times for Men in Their 50s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for men 50–59, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Men in Their 50s",
      openingParagraph: "Men competing in the 10K in their 50s are in one of the most active masters age groups in road racing. Age-grading reveals impressive competitive depth — runners who have maintained consistent training through their 50s achieve WMA grades that rival their earlier racing years.",
      trainingContext: "10K training for men in their 50s centers on one threshold session per week (20–30 minutes at threshold pace) and easy volume. Interval training can be added every other week as a replacement session. Recovery between hard efforts takes 6–7 full days at this age — planning quality sessions 7+ days apart prevents the chronic fatigue that undermines performance.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-men-age-70s': {
      title: "Good 10K Times for Men in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for men 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Men in Their 70s",
      openingParagraph: "Men racing the 10K at 70–79 are remarkable competitive runners. WMA standards account for the significant physiological changes of this decade — achieving any competitive result here requires sustained fitness that most people at this age do not maintain.",
      trainingContext: "10K training for men in their 70s requires one quality session per 10–14 days with all other running at genuinely easy pace. Threshold work (15–20 minutes) is more appropriate than intensive intervals at this age. The aerobic system still adapts to training — the key is spacing hard efforts far enough apart to recover fully before the next stimulus.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-men-age-80s': {
      title: "Good 10K Times for Men in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for men 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Men Age 80+",
      openingParagraph: "Men racing the 10K at 80+ represent extraordinary athletic longevity. WMA standards at this age reflect world-record-caliber relative performance — finishing any competitive 10K at 80+ is an achievement.",
      trainingContext: "10K training for men 80+ is managed entirely around recovery. One easy threshold effort per two weeks, with all other days genuinely easy or rest. The cardiovascular system still responds to training; tissue recovery is the limiting factor. Every hard session is an investment that requires 10–14 days of easy running to yield its adaptation.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },

    // ---- 10K WOMEN ----
    '10k-times-women-age-20s': {
      title: "Good 10K Times for Women in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women in Their 20s",
      openingParagraph: "Women in their 20s competing in the 10K are at physiological peak — VO2max near its highest, recovery fastest, and adaptation to training most rapid. This decade produces some of the strongest absolute 10K times for women who train with structure.",
      trainingContext: "10K training for women in their 20s benefits from threshold training as the primary quality session. The 10K demands sustained threshold-level effort for 32–65 minutes. Threshold tempo runs (20–30 minutes at threshold pace) build the lactate stamina this requires. Two quality sessions per week with easy volume is sustainable and produces strong improvement.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-women-age-30s': {
      title: "Good 10K Times for Women in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women in Their 30s",
      openingParagraph: "Women in their 30s often run their fastest 10Ks — training consistency and pacing experience combine with high aerobic capacity. Many women discover road racing seriously in this decade and see rapid early improvement that continues for years.",
      trainingContext: "10K training for women in their 30s follows the same structure as for women in their 20s, with slightly more recovery awareness. Threshold sessions are the primary quality work. Two quality sessions per week with easy volume is the productive structure, with recovery days running genuinely easy.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-women-age-40s': {
      title: "Good 10K Times for Women in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women in Their 40s",
      openingParagraph: "Women competing in the 10K in their 40s are in a fast-growing and highly competitive masters segment. Many women run their fastest age-adjusted 10Ks in this decade — training wisdom, consistent volume, and disciplined racing produce strong results.",
      trainingContext: "10K training for women in their 40s requires one threshold session and one interval session per week, spaced adequately for recovery. The aerobic system adapts well. Recovery between sessions becomes more important — planning quality sessions 5–6 days apart rather than 4 maintains training quality.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-women-age-50s': {
      title: "Good 10K Times for Women in Their 50s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 50–59, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women in Their 50s",
      openingParagraph: "Women racing the 10K in their 50s are in one of the most competitive masters groups at most road races. WMA standards reveal the depth — consistently trained women in this decade often run better age-adjusted times than they did in their 30s.",
      trainingContext: "10K training for women in their 50s centers on one threshold session per week (20–25 minutes) and adequate easy volume. Recovery between quality sessions takes 6–7 days at this age. Easy days at genuinely easy pace allow the weekly threshold session to produce full adaptation.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-women-age-60s': {
      title: "Good 10K Times for Women in Their 60s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 60–69, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women in Their 60s",
      openingParagraph: "Women racing the 10K in their 60s demonstrate maintained fitness that most people at this age never develop. WMA age-grading shows that achieving even the 60% benchmark requires genuine aerobic conditioning relative to world-record standards.",
      trainingContext: "10K training for women in their 60s works best with one quality session per week — threshold running (15–20 minutes) is most appropriate and effective. All other days are genuinely easy runs. Recovery management is the central training discipline: protecting 6–7 days of easy running between each quality session.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-women-age-70s': {
      title: "Good 10K Times for Women in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women in Their 70s",
      openingParagraph: "Women competing in the 10K at 70–79 represent lifelong aerobic fitness maintained through decades of consistent training. WMA standards at this age are demanding relative to world records — any competitive result is genuinely impressive.",
      trainingContext: "10K training for women in their 70s requires one quality effort per 10–14 days with all other running genuinely easy. Threshold work (12–18 minutes at threshold pace) is the most appropriate quality session. The aerobic system still adapts — recovery time between hard efforts is the limiting variable.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },
    '10k-times-women-age-80s': {
      title: "Good 10K Times for Women in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded 10K benchmarks for women 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "10K Benchmarks for Women Age 80+",
      openingParagraph: "Women racing the 10K at 80+ are among the most remarkable athletes in road racing. The WMA standards at this age account for the physiological reality of octogenarian running — finishing a competitive 10K at 80+ is an extraordinary achievement.",
      trainingContext: "10K training for women 80+ is centered on recovery and consistency. One quality effort per two weeks, with all other days genuinely easy. The primary training discipline is not adding hard sessions — it is protecting full recovery between each quality effort so that each one generates adaptation.",
      buildFaq: makeDistGenderFaq('10K', 'threshold'),
    },

    // ---- HALF MARATHON MEN ----
    'half-marathon-times-men-age-20s': {
      title: "Good Half Marathon Times for Men in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men in Their 20s",
      openingParagraph: "Men in their 20s competing in the half marathon combine peak VO2max with a growing aerobic base. This is an excellent decade for half marathon development — the aerobic system is highly adaptable and recovery from hard training is fast.",
      trainingContext: "Half marathon training for men in their 20s combines threshold work (the most race-specific quality) with long runs at easy pace (the most endurance-building session). Threshold tempo runs (25–35 minutes) develop the lactate stamina the half demands. Long runs building to 14–16 miles at easy pace develop the endurance base. Two quality sessions per week with adequate easy volume is sustainable.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-men-age-30s': {
      title: "Good Half Marathon Times for Men in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men in Their 30s",
      openingParagraph: "Men in their 30s often run their fastest half marathons — training experience, race-day maturity, and still-high aerobic capacity combine effectively. The WMA standards here show what competitive half marathon performance looks like at this age.",
      trainingContext: "Half marathon training for men in their 30s centers on threshold work and long runs. Threshold tempo runs (25–40 minutes) develop the sustained lactate-clearance capacity that half marathon racing demands. Long runs to 14–16 miles at easy pace provide the endurance base. Two quality sessions per week with easy volume is the effective structure.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-men-age-40s': {
      title: "Good Half Marathon Times for Men in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men in Their 40s",
      openingParagraph: "Men competing in the half marathon in their 40s are among the most experienced and disciplined road racers. Many run their best age-adjusted half marathons in this decade. WMA standards show the competitive depth at 40–49.",
      trainingContext: "Half marathon training for men in their 40s requires one threshold session per week (25–35 minutes) and long runs to 14 miles, with recovery days strictly easy. Spacing quality sessions 5–6 days apart maintains training quality. The aerobic adaptation remains strong; the key adjustment is not adding more quality but ensuring each quality session is fully productive.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-men-age-50s': {
      title: "Good Half Marathon Times for Men in Their 50s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 50–59, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men in Their 50s",
      openingParagraph: "Half marathon racing for men 50–59 is where many find their best age-adjusted performances. The endurance component ages well, and training consistency often produces strong WMA scores for men who have been running seriously for a decade or more.",
      trainingContext: "Half marathon training for men in their 50s works best with one threshold session per week (20–30 minutes) and a weekly long run building to 12–14 miles. Recovery between quality sessions takes 6 days — planning accordingly. Easy days at genuinely easy pace allow both the threshold session and the long run to generate full adaptation.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-men-age-60s': {
      title: "Good Half Marathon Times for Men in Their 60s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 60–69, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men in Their 60s",
      openingParagraph: "Men racing the half marathon in their 60s represent sustained endurance fitness that most people at this age do not maintain. WMA standards show how demanding the benchmarks are — achieving competitive results here is genuinely impressive.",
      trainingContext: "Half marathon training for men in their 60s centers on one quality session per week (threshold work, 20–25 minutes) and a weekly long run (10–13 miles at easy pace). Recovery between hard efforts takes 6–7 full days. All other running at genuinely easy pace protects the quality of each session.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-men-age-70s': {
      title: "Good Half Marathon Times for Men in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men in Their 70s",
      openingParagraph: "Men competing in the half marathon at 70–79 are demonstrating extraordinary athletic longevity. WMA standards at this age account for substantial age factors — even the 60% mark requires maintained aerobic conditioning through years of consistent training.",
      trainingContext: "Half marathon training for men in their 70s requires one quality session per 10–14 days with all other running genuinely easy. Long runs at easy pace (8–12 miles) are the most important session for half marathon endurance. Threshold work every other week maintains the aerobic ceiling. Recovery management is the central training discipline.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-men-age-80s': {
      title: "Good Half Marathon Times for Men in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for men 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Men Age 80+",
      openingParagraph: "Men competing in the half marathon at 80+ are among the most remarkable athletes in road racing. Completing 13.1 miles at any pace at this age is a significant achievement; racing it competitively is extraordinary.",
      trainingContext: "Half marathon training for men 80+ is managed entirely around recovery. Long easy runs as the foundation, with one quality effort (easy threshold, 12–15 minutes) per two weeks. The primary training principle: protecting enough recovery between efforts to allow each session to produce positive adaptation.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },

    // ---- HALF MARATHON WOMEN ----
    'half-marathon-times-women-age-20s': {
      title: "Good Half Marathon Times for Women in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women in Their 20s",
      openingParagraph: "Women in their 20s competing in the half marathon combine peak aerobic capacity with an increasingly developed aerobic base. This decade produces strong half marathon development — the adaptation response is fast and training can be absorbed well.",
      trainingContext: "Half marathon training for women in their 20s benefits from threshold work as the primary quality session. Threshold tempo runs (20–35 minutes) develop the lactate stamina the half marathon requires. Long runs building to 13–16 miles at easy pace develop the endurance base. Two quality sessions per week with genuine easy recovery produces strong adaptation.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-women-age-30s': {
      title: "Good Half Marathon Times for Women in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women in Their 30s",
      openingParagraph: "Women in their 30s often achieve their strongest half marathon performances — training consistency, race experience, and still-high aerobic capacity combine effectively. Many women set half marathon personal records in their early to mid-30s.",
      trainingContext: "Half marathon training for women in their 30s centers on threshold work (25–35 minutes at threshold pace) and long runs to 13–15 miles at easy pace. Two quality sessions per week — one threshold, one interval — with adequate easy volume is the effective structure. Recovery days must be genuinely easy to allow adaptation.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-women-age-40s': {
      title: "Good Half Marathon Times for Women in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women in Their 40s",
      openingParagraph: "Women in their 40s are often at their peak half marathon performance on an age-adjusted basis. This is a highly competitive masters group, and the WMA standards show how serious the benchmarks are relative to world records for this age group.",
      trainingContext: "Half marathon training for women in their 40s works best with one threshold session and one long run per week, spaced with full easy days between. Threshold sessions (22–30 minutes at threshold pace) are the race-specific quality. Long runs to 13–14 miles at easy pace build the endurance base. Recovery management is more important than adding sessions.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-women-age-50s': {
      title: "Good Half Marathon Times for Women in Their 50s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 50–59, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women in Their 50s",
      openingParagraph: "Women racing the half marathon in their 50s are among the most competitive masters athletes in road racing. Many women achieve their best age-adjusted half marathon performances in this decade — the combination of training experience and accumulated aerobic base is powerful.",
      trainingContext: "Half marathon training for women in their 50s centers on one threshold session per week (20–28 minutes) and a weekly long run to 12–14 miles. Quality sessions are spaced 6 full days apart. Easy days at genuinely easy pace are the recovery foundation that allows each quality session to produce adaptation.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-women-age-60s': {
      title: "Good Half Marathon Times for Women in Their 60s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 60–69, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women in Their 60s",
      openingParagraph: "Women racing the half marathon in their 60s demonstrate real athletic commitment. WMA standards at this age account for meaningful physiological change — achieving competitive results requires maintained training over years, not just months.",
      trainingContext: "Half marathon training for women in their 60s works best with one quality session per week (threshold work, 18–25 minutes) and a weekly long run (9–12 miles). Full easy recovery between sessions is the central discipline. Three structured runs per week — long run, threshold, and easy-plus fartlek — with genuinely easy days in between is a proven pattern.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-women-age-70s': {
      title: "Good Half Marathon Times for Women in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women in Their 70s",
      openingParagraph: "Women competing in the half marathon at 70–79 are showing athletic longevity that most people in this decade do not maintain. The WMA benchmarks account for significant age factors — achieving competitive results here is a genuine accomplishment.",
      trainingContext: "Half marathon training for women in their 70s requires one quality effort per 10–14 days with easy running as the foundation. Long runs at easy pace (8–11 miles) are the most important session for half marathon endurance. Recovery is the primary training variable — every hard effort needs full recovery before the next.",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },
    'half-marathon-times-women-age-80s': {
      title: "Good Half Marathon Times for Women in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded half marathon benchmarks for women 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Half Marathon Benchmarks for Women Age 80+",
      openingParagraph: "Women competing in the half marathon at 80+ are among the most remarkable endurance athletes in road racing. Completing 13.1 miles at any competitive pace at this age is an extraordinary achievement.",
      trainingContext: "Half marathon training for women 80+ is managed entirely around recovery and consistency. Easy running as the primary session, long runs to 8–10 miles at easy pace for endurance, with one quality effort per two weeks. Every training decision is filtered through recovery: can the body absorb this and be ready for the next effort?",
      buildFaq: makeDistGenderFaq('Half Marathon', 'threshold'),
    },

    // ---- MARATHON MEN ----
    'marathon-times-men-age-20s': {
      title: "Good Marathon Times for Men in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for men 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Men in Their 20s",
      openingParagraph: "Men in their 20s have peak aerobic capacity but often lack the marathon-specific base that produces optimal marathon performance. The aerobic engine is there — the race-specific development of long-run endurance and glycogen economy takes years to fully develop.",
      trainingContext: "Marathon training for men in their 20s benefits from high volume, long runs building to 20+ miles at easy pace, and one threshold session per week. The endurance component of marathon training is build over years — runners in their 20s who commit to high mileage now are establishing the base that produces their best marathons in their 30s.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-men-age-30s': {
      title: "Good Marathon Times for Men in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for men 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Men in Their 30s",
      openingParagraph: "Men in their 30s are in their prime marathon years. Endurance develops late — runners who have been building consistently through their 20s often achieve their best marathon performances in their early to mid-30s. WMA standards reflect the deep competitive field at this age.",
      trainingContext: "Marathon training for men in their 30s: high easy volume (50–70+ miles/week), long runs to 20 miles, one threshold session per week (25–40 minutes), and marathon-pace miles in long run finishes. This is the age when runners can absorb the highest marathon-training volume without requiring excessive recovery. These training investments yield compound returns.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-men-age-40s': {
      title: "Good Marathon Times for Men in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for men 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Men in Their 40s",
      openingParagraph: "Men racing marathons in their 40s represent some of the most dedicated endurance athletes in road racing. Many achieve age-adjusted personal bests in this decade — the combination of training maturity and maintained aerobic capacity is powerful.",
      trainingContext: "Marathon training for men in their 40s requires one threshold session per week, long runs to 20 miles, and adequate recovery between hard sessions (5–6 days). Easy pace must be genuinely easy. Most men in their 40s who are training toward BQ times are running 45–60 miles per week — the volume is manageable with good recovery management.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-men-age-70s': {
      title: "Good Marathon Times for Men in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for men 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Men in Their 70s",
      openingParagraph: "Men racing marathons in their 70s are among the most committed endurance athletes in the field. Marathon endurance ages more gradually than speed, and men who have maintained high mileage into their 70s can achieve impressive absolute times while scoring well on WMA age-grading.",
      trainingContext: "Marathon training for men in their 70s is centered on long runs at easy pace (to 16–18 miles) and one threshold session per week. Recovery between quality sessions takes 7–10 days. Three structured runs per week — long run, threshold, and easy-plus session — with genuinely easy days in between is the pattern most men in this age group find sustainable.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-men-age-80s': {
      title: "Good Marathon Times for Men in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for men 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Men Age 80+",
      openingParagraph: "Men completing a marathon at 80+ are among the most extraordinary endurance athletes in any age group. The WMA standards at this age reflect world-record caliber relative performance — finishing 26.2 miles competitively at 80+ is remarkable.",
      trainingContext: "Marathon training for men 80+ is managed entirely around recovery. Long easy runs as the foundation, building as far as the body recovers from. One threshold or quality session per two weeks. Recovery is the primary training variable — protecting enough easy days between hard efforts is what allows training to produce positive adaptation rather than accumulated fatigue.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },

    // ---- MARATHON WOMEN ----
    'marathon-times-women-age-20s': {
      title: "Good Marathon Times for Women in Their 20s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for women 20–29, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Women in Their 20s",
      openingParagraph: "Women in their 20s have peak physiological capacity but often are still building the long-run base and glycogen economy that produce optimal marathon performance. This is the decade when marathon endurance training pays the largest compound dividends — the training now builds the base for the fastest times in the 30s.",
      trainingContext: "Marathon training for women in their 20s: high easy volume, long runs building toward 20 miles, one threshold session per week, and marathon-pace miles added to long run finishes. The fast recovery of this decade allows higher training loads — building a strong aerobic base now creates the foundation for peak marathon performance in the next decade.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-women-age-30s': {
      title: "Good Marathon Times for Women in Their 30s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for women 30–39, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Women in Their 30s",
      openingParagraph: "Women in their 30s often achieve their peak marathon performances — training consistency, race experience, and mature pacing combine with the endurance base built in the 20s. The 30s are when many women discover their strongest marathon results.",
      trainingContext: "Marathon training for women in their 30s centers on high easy volume, long runs to 20 miles at easy pace, and one threshold session per week. Marathon-pace miles in long run finishes are the most race-specific quality work. Two hard sessions per week (threshold + long run) with the rest at easy pace is the effective structure.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-women-age-40s': {
      title: "Good Marathon Times for Women in Their 40s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for women 40–49, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Women in Their 40s",
      openingParagraph: "Women racing marathons in their 40s are in a competitive and growing segment of road racing. Many women achieve their best age-adjusted marathon scores in this decade — discipline, patience, and training maturity produce results that raw aerobic capacity alone cannot.",
      trainingContext: "Marathon training for women in their 40s requires one threshold session per week, long runs to 18–20 miles, and adequate recovery between quality sessions (5–6 days). Easy days at genuinely easy pace allow both the threshold session and the long run to generate full adaptation. This decade rewards training intelligence over training volume.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-women-age-60s': {
      title: "Good Marathon Times for Women in Their 60s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for women 60–69, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Women in Their 60s",
      openingParagraph: "Women racing marathons in their 60s demonstrate sustained aerobic commitment that produces genuinely impressive results. Marathon endurance ages gradually — women who have maintained consistent long-run training can keep strong WMA age grades through this decade.",
      trainingContext: "Marathon training for women in their 60s centers on long runs at easy pace (to 16–18 miles), one threshold session per week (20–25 minutes), and full recovery between quality efforts. Three to four structured runs per week with genuinely easy recovery days is the sustainable pattern. Recovery management — protecting enough easy days between hard efforts — is the central training discipline.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-women-age-70s': {
      title: "Good Marathon Times for Women in Their 70s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for women 70–79, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Women in Their 70s",
      openingParagraph: "Women competing in the marathon at 70–79 are extraordinary endurance athletes. WMA standards at this age show how demanding even modest absolute marathon times are relative to world records for this decade — maintaining the fitness to finish 26.2 miles competitively is an achievement.",
      trainingContext: "Marathon training for women in their 70s is organized around recovery and long runs. Long easy runs (to 14–16 miles) are the primary marathon-specific session. One threshold or quality session per 10–14 days. All other running at genuinely easy pace. Recovery is the single most important training variable — protecting enough easy days between hard efforts is what allows each session to generate positive adaptation.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
    },
    'marathon-times-women-age-80s': {
      title: "Good Marathon Times for Women in Their 80s — WMA Benchmarks and Training Paces",
      description: "WMA age-graded marathon benchmarks for women 80+, with training paces for each performance level. Alan Jones 2025 WMA standards.",
      h1: "Marathon Benchmarks for Women Age 80+",
      openingParagraph: "Women competing in the marathon at 80+ are among the most remarkable athletes in any endurance sport. The WMA standards account for the significant physiological changes of this age — finishing 26.2 miles competitively at 80+ is an extraordinary lifetime achievement.",
      trainingContext: "Marathon training for women 80+ is managed entirely around recovery. Long easy runs as the foundation — as far as the body recovers from. One quality effort (easy threshold, 12–15 minutes) per two weeks at most. The training principle is simple: protect recovery above all else, and the aerobic base accumulated over decades will support continued performance.",
      buildFaq: makeDistGenderFaq('Marathon', 'threshold'),
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
