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
      return [
        {
          q: 'How accurate is the 10K to half marathon equivalency?',
          a: `Very accurate — this is the most reliable cross-distance pair in running equivalency. The 10K and half marathon both require sustained effort near lactate threshold, so the aerobic capacity measured by the 10K closely predicts half marathon performance. Most consistently trained runners fall within three to five minutes of their prediction.`,
        },
        {
          q: row45 ? `What half marathon time does a 45:00 10K predict?` : `How do I use this table?`,
          a: row45
            ? `A 45:00 10K gives an RPI of ${row45.rpi}. The equivalent half marathon is ${row45.outputTime} at ${row45.outputPaceMi}/mi. This assumes comparable half marathon preparation.`
            : `Find your 10K time in the left column and read across to the predicted half marathon time.`,
        },
        {
          q: row40 ? `If I can run ${row40.inputTime} for 10K, what half marathon is realistic?` : `What is the relationship between 10K and half marathon pace?`,
          a: row40
            ? `A ${row40.inputTime} 10K runner (RPI ${row40.rpi}) has the aerobic capacity for a ${row40.outputTime} half marathon at ${row40.outputPaceMi}/mi. Half marathon pace runs about 10–15 seconds per mile slower than 10K race pace.`
            : `Half marathon pace runs approximately 10–15 seconds per mile slower than 10K pace. The Daniels formula captures this relationship precisely.`,
        },
      ]
    },
  },

  // ============================================================================
  // BATCH 2D: 13 new equivalency configs
  // ============================================================================

  'mile-to-5k': {
    title: 'Mile to 5K Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your mile time, find your equivalent 5K potential. Computed via the Daniels/Gilbert oxygen cost equation.',
    h1: 'Mile to 5K Race Equivalency',
    openingParagraph: 'Your mile time is a precise measure of aerobic capacity and raw speed. This table shows what that capacity predicts for the 5K — the equivalent time a runner with the same fitness would run, assuming 5K-specific preparation. The formula is the Daniels/Gilbert oxygen cost equation.',
    accuracyNote: 'The mile → 5K prediction is highly accurate for runners who train for both distances. Mile specialists may underperform their 5K equivalent slightly (pure speed training without the threshold stamina the 5K demands); 5K specialists may slightly outperform their mile equivalent. Most consistently trained runners land within 30–60 seconds of the prediction.',
    buildFaq: (data) => {
      const row5 = data.rows.find(r => r.inputTime === '5:00')
      const row4 = data.rows.find(r => r.inputTime === '4:30')
      return [
        { q: 'How accurate is the mile to 5K equivalency?', a: `The mile and 5K are physiologically similar — both demand high aerobic output for 4–20 minutes. The equivalency is reliable for runners who train for both distances. The primary divergence: pure mile specialists who lack 5K-specific threshold training may underperform by 30–60 seconds.` },
        { q: row5 ? `What 5K does a 5:00 mile predict?` : `How do I use this table?`, a: row5 ? `A 5:00 mile (RPI ${row5.rpi}) projects to a ${row5.outputTime} 5K at ${row5.outputPaceMi}/mi. This assumes 5K-specific threshold and interval training — not just mile-race fitness.` : `Find your mile time and read across to the predicted 5K equivalent.` },
        { q: row4 ? `What 5K does a ${row4.inputTime} mile predict?` : `What is the relationship between mile and 5K pace?`, a: row4 ? `A ${row4.inputTime} mile (RPI ${row4.rpi}) projects to ${row4.outputTime} 5K fitness at ${row4.outputPaceMi}/mi.` : `5K race pace runs roughly 20–30 seconds per mile slower than mile race pace for most runners — the longer distance requires a lower sustainable intensity.` },
      ]
    },
  },

  'mile-to-10k': {
    title: 'Mile to 10K Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your mile time, find your equivalent 10K potential. Daniels/Gilbert oxygen cost equation.',
    h1: 'Mile to 10K Race Equivalency',
    openingParagraph: 'This table shows what your mile time predicts for the 10K — the equivalent time that the same aerobic capacity would support at 6.2 miles, assuming threshold-specific preparation. The 10K demands substantially more threshold stamina than the mile; raw speed transfers differently than aerobic capacity.',
    accuracyNote: 'Mile → 10K predictions have more divergence than shorter-to-longer predictions because the 10K demands prolonged threshold running that mile specialists often lack. Runners who specifically train threshold work (20–30 minute tempo runs) tend to match their mile-to-10K equivalency closely. Mile specialists who lack threshold training may underperform by 2–5 minutes.',
    buildFaq: (data) => {
      const row5 = data.rows.find(r => r.inputTime === '5:00')
      return [
        { q: 'How accurate is mile to 10K prediction?', a: `Less accurate than mile-to-5K because the 10K demands sustained threshold effort for 32–60+ minutes — a quality that mile training does not fully develop. Runners who add regular tempo runs to their mile training close most of this gap.` },
        { q: row5 ? `What 10K does a 5:00 mile predict?` : `How do I use this table?`, a: row5 ? `A 5:00 mile (RPI ${row5.rpi}) projects to a ${row5.outputTime} 10K at ${row5.outputPaceMi}/mi. This assumes threshold-specific training beyond mile preparation.` : `Find your mile time and read across to the predicted 10K equivalent.` },
        { q: 'Why does the 10K demand different training than the mile?', a: `The mile is run at near-maximum aerobic output for 4–8 minutes. The 10K is run near the lactate threshold for 32–65+ minutes — a fundamentally different energy system demand. Converting mile fitness to 10K performance requires adding sustained threshold work (tempo runs) that mile training alone does not develop.` },
      ]
    },
  },

  'mile-to-half-marathon': {
    title: 'Mile to Half Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your mile time, find your equivalent half marathon potential. Daniels/Gilbert oxygen cost equation.',
    h1: 'Mile to Half Marathon Race Equivalency',
    openingParagraph: 'Your mile time reflects your aerobic ceiling. This table shows what that ceiling predicts for the half marathon — 13.1 miles of sustained threshold-level effort. The physiological distance between a mile and a half marathon is significant; raw speed converts to half marathon fitness only with distance-specific training.',
    accuracyNote: 'Mile → half marathon predictions have substantial divergence for runners who lack half marathon-specific training. The equivalency reflects aerobic potential, not fitness developed for sustained 90-minute effort. Runners who add threshold training and long runs (12–15 miles) typically close to within 5 minutes of their prediction.',
    buildFaq: (data) => {
      const row5 = data.rows.find(r => r.inputTime === '5:00')
      return [
        { q: 'How accurate is mile to half marathon equivalency?', a: `This has the most divergence among the short-to-long predictions. The half marathon demands sustained threshold stamina for 70–120 minutes — a quality that mile training alone does not develop. Runners who add long runs and tempo work to their mile training typically land within 5–8 minutes of the equivalency.` },
        { q: row5 ? `What half marathon does a 5:00 mile predict?` : `How do I use this table?`, a: row5 ? `A 5:00 mile (RPI ${row5.rpi}) projects to ${row5.outputTime} half marathon potential at ${row5.outputPaceMi}/mi. Reaching this requires threshold-specific training and long runs to 12–15 miles.` : `Find your mile time and read across to the predicted half marathon equivalent.` },
        { q: 'What training is needed to convert mile fitness to half marathon fitness?', a: `Add weekly threshold tempo runs (20–35 minutes at threshold pace) and build long runs to 12–15 miles. These two additions develop the specific aerobic endurance and lactate stamina that convert raw mile speed into half marathon performance.` },
      ]
    },
  },

  'mile-to-marathon': {
    title: 'Mile to Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your mile time, find your equivalent marathon potential. Daniels/Gilbert oxygen cost equation.',
    h1: 'Mile to Marathon Race Equivalency',
    openingParagraph: 'This table shows what your mile time predicts for the marathon — a projection that reflects aerobic potential, not marathon readiness. The marathon demands glycogen economy, long-run adaptation, and pacing experience that a mile performance cannot measure. Use this as a ceiling, not a guarantee.',
    accuracyNote: 'Mile → marathon predictions have the largest divergence of any distance pair. Without 20-mile long runs, marathon-pace work, and sustained high-volume training, most mile specialists underperform their marathon equivalent by 30–60+ minutes. This table shows aerobic potential — realizing it requires complete marathon-specific preparation over 18–24+ weeks.',
    buildFaq: (data) => {
      const row5 = data.rows.find(r => r.inputTime === '5:00')
      return [
        { q: 'How reliable is mile to marathon equivalency?', a: `Use this as a potential ceiling, not a race prediction. The marathon demands distance-specific adaptations — glycogen economy, long-run fitness, pacing experience, heat management — that a mile performance cannot reflect. Runners with full marathon training typically perform 10–30 minutes over their mile equivalency without this preparation.` },
        { q: row5 ? `What marathon does a 5:00 mile predict?` : `How do I use this table?`, a: row5 ? `A 5:00 mile (RPI ${row5.rpi}) projects to ${row5.outputTime} marathon potential. This is an aerobic ceiling that requires 20-mile long runs and sustained marathon-pace work to realize.` : `Find your mile time and read across to see what your aerobic capacity could produce in the marathon with proper preparation.` },
        { q: 'What marathon training does a miler need?', a: `A complete marathon build: 18–20 week program, long runs building to 20–22 miles, weekly threshold work, marathon-pace segments in long runs (final 4–6 miles at goal pace), and weekly mileage of 50–80+ miles. The aerobic engine from mile training is excellent; the specific endurance requires dedicated marathon preparation.` },
      ]
    },
  },

  '5k-to-10k': {
    title: '5K to 10K Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 5K time, find your equivalent 10K potential. Daniels/Gilbert oxygen cost equation.',
    h1: '5K to 10K Race Equivalency',
    openingParagraph: 'Your 5K time measures aerobic capacity and VO2max-level performance. This table shows what that capacity predicts for the 10K — a distance that demands more sustained threshold stamina but shares the same aerobic engine. Use this for goal-setting when you have a recent 5K result and are targeting a 10K.',
    accuracyNote: 'The 5K → 10K prediction is reliable for runners who train for both distances with threshold work. The primary divergence: runners whose training emphasizes interval work (5K-specific) over tempo runs (10K-specific) may underperform their 10K equivalent by 1–3 minutes. Adding weekly threshold sessions closes this gap.',
    buildFaq: (data) => {
      const row20 = data.rows.find(r => r.inputTime === '20:00')
      const row25 = data.rows.find(r => r.inputTime === '25:00')
      return [
        { q: 'How accurate is 5K to 10K prediction?', a: `Accurate for runners who train both quality types (interval + threshold). The 5K and 10K share similar aerobic demands, but the 10K requires more sustained threshold stamina. Most consistently trained runners land within 2 minutes of the prediction.` },
        { q: row20 ? `What 10K does a 20:00 5K predict?` : `How do I use this table?`, a: row20 ? `A 20:00 5K (RPI ${row20.rpi}) projects to a ${row20.outputTime} 10K at ${row20.outputPaceMi}/mi. Adding threshold work to your training bridges any gap between your 5K and 10K fitness.` : `Find your 5K time and read across to the predicted 10K equivalent.` },
        { q: row25 ? `What 10K does a 25:00 5K predict?` : `What training develops 10K fitness from 5K fitness?`, a: row25 ? `A 25:00 5K (RPI ${row25.rpi}) projects to ${row25.outputTime} 10K at ${row25.outputPaceMi}/mi.` : `Add weekly threshold tempo runs (20–30 minutes at threshold pace) to 5K-focused interval training. This converts raw aerobic capacity into the sustained threshold stamina the 10K demands.` },
      ]
    },
  },

  '5k-to-half-marathon': {
    title: '5K to Half Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 5K time, find your equivalent half marathon potential. Daniels/Gilbert oxygen cost equation.',
    h1: '5K to Half Marathon Race Equivalency',
    openingParagraph: 'Your 5K time is a reliable measure of aerobic capacity. This table shows what that capacity predicts for the half marathon — assuming threshold-specific training and half marathon-appropriate long runs. The physiological distance is bridgeable with the right training additions.',
    accuracyNote: 'The 5K → half marathon prediction is accurate when half marathon-specific training is in place: long runs of 12–15 miles and threshold tempo runs (25–35 minutes). Without these, most 5K-trained runners underperform their half marathon equivalent by 5–10 minutes. With them, the typical gap closes to 2–4 minutes.',
    buildFaq: (data) => {
      const row20 = data.rows.find(r => r.inputTime === '20:00')
      return [
        { q: 'What training converts 5K fitness to half marathon fitness?', a: `Add two key elements to 5K training: weekly threshold tempo runs (25–35 minutes at threshold pace) and long runs building to 12–15 miles at easy pace. These develop the sustained effort and aerobic endurance that 5K training alone does not.` },
        { q: row20 ? `What half marathon does a 20:00 5K predict?` : `How do I use this table?`, a: row20 ? `A 20:00 5K (RPI ${row20.rpi}) projects to ${row20.outputTime} half marathon fitness at ${row20.outputPaceMi}/mi. This assumes half-marathon specific preparation is in place.` : `Find your 5K time in the left column and read across to the predicted half marathon equivalent.` },
        { q: 'Is the 5K to half marathon equivalency reliable?', a: `Reliable when half-specific training exists. The 5K measures aerobic capacity that the half marathon uses — but the half demands sustained effort for 70–120 minutes, which requires specific endurance development beyond what 5K training produces.` },
      ]
    },
  },

  '10k-to-marathon': {
    title: '10K to Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 10K time, find your equivalent marathon potential. Daniels/Gilbert oxygen cost equation.',
    h1: '10K to Marathon Race Equivalency',
    openingParagraph: 'Your 10K time reveals your aerobic capacity and threshold fitness. This table shows what that fitness predicts for the marathon — the equivalent time that the same aerobic engine could support, assuming full marathon-specific preparation. The caveat is always marathon preparation: long runs, glycogen economy, and pacing experience matter enormously.',
    accuracyNote: 'The 10K → marathon prediction is accurate for runners with complete marathon training (20-mile long runs, marathon-pace work, 50+ miles/week). Without this preparation, most 10K-trained runners underperform by 15–30 minutes. The 10K is a better aerobic benchmark for marathon than shorter distances — but specific marathon training is the non-negotiable variable.',
    buildFaq: (data) => {
      const row40 = data.rows.find(r => r.inputTime === '40:00')
      const row50 = data.rows.find(r => r.inputTime === '50:00')
      return [
        { q: 'How accurate is 10K to marathon prediction?', a: `Accurate for runners with proper marathon preparation. The 10K measures aerobic and threshold fitness that the marathon uses — but the marathon demands glycogen economy and sustained pacing that only long-run training develops. Runners with 20-mile long runs and marathon-pace work typically land within 5–10 minutes of their prediction.` },
        { q: row40 ? `What marathon does a 40:00 10K predict?` : `How do I use this table?`, a: row40 ? `A 40:00 10K (RPI ${row40.rpi}) projects to a ${row40.outputTime} marathon at ${row40.outputPaceMi}/mi. This is the aerobic potential — reaching it requires 20-mile long runs and a full marathon build.` : `Find your 10K time and read across to the predicted marathon equivalent.` },
        { q: row50 ? `What marathon does a 50:00 10K predict?` : `What marathon training is needed after building 10K fitness?`, a: row50 ? `A 50:00 10K (RPI ${row50.rpi}) projects to ${row50.outputTime} marathon potential at ${row50.outputPaceMi}/mi.` : `Long runs to 20+ miles, marathon-pace segments in long runs (final 4–6 miles at goal pace), and weekly mileage of 45–65+ miles are the key additions to 10K training for full marathon preparation.` },
      ]
    },
  },

  'half-marathon-to-marathon': {
    title: 'Half Marathon to Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your half marathon time, find your marathon equivalent. The most reliable long-distance cross-prediction. Daniels/Gilbert oxygen cost equation.',
    h1: 'Half Marathon to Marathon Race Equivalency',
    openingParagraph: 'Your half marathon time is the best single predictor of marathon fitness available short of racing a marathon. Both distances demand aerobic and threshold endurance — the half marathon measures these qualities directly. This table shows what your half time predicts for the full 26.2, assuming full marathon preparation.',
    accuracyNote: 'Half marathon → marathon is the most reliable long-distance prediction. Both distances tax similar energy systems, and runners who have built comparable training for each distance typically run within 5–10 minutes of their equivalency. The main divergence: runners who have trained specifically for the half but lack 20-mile long runs underperform their marathon equivalent by 10–20 minutes. Long-run endurance is the variable the half cannot measure.',
    buildFaq: (data) => {
      const row130 = data.rows.find(r => r.inputTime === '1:30:00')
      const row145 = data.rows.find(r => r.inputTime === '1:45:00')
      return [
        { q: 'Is half marathon to marathon the most reliable equivalency?', a: `Yes — the half marathon is the best single non-marathon predictor of marathon fitness. Both distances require sustained aerobic and threshold endurance for 70–210+ minutes. The primary gap: the marathon demands specific long-run adaptation (20-mile long runs) that the half marathon does not test.` },
        { q: row130 ? `What marathon does a 1:30:00 half predict?` : `How do I use this table?`, a: row130 ? `A 1:30:00 half marathon (RPI ${row130.rpi}) projects to a ${row130.outputTime} marathon at ${row130.outputPaceMi}/mi. This assumes full marathon preparation including 20-mile long runs.` : `Find your half marathon time and read across to the predicted marathon equivalent.` },
        { q: row145 ? `What marathon does a 1:45:00 half predict?` : `What training is needed to convert half fitness to marathon fitness?`, a: row145 ? `A 1:45:00 half marathon (RPI ${row145.rpi}) projects to ${row145.outputTime} marathon at ${row145.outputPaceMi}/mi.` : `Long runs to 20 miles, marathon-pace work in long runs (final 4–6 miles at goal pace), and sustained weekly mileage of 40–60+ miles are the key additions to half marathon training for full marathon preparation.` },
      ]
    },
  },

  'marathon-to-5k': {
    title: 'Marathon to 5K Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your marathon time, find your equivalent 5K potential. Daniels/Gilbert oxygen cost equation.',
    h1: 'Marathon to 5K Race Equivalency',
    openingParagraph: 'Your marathon time reflects deep aerobic fitness built from high mileage and sustained endurance training. This table shows what that aerobic capacity predicts for the 5K — a very different kind of race. The 5K demands raw speed and VO2max output that marathon training may not fully develop.',
    accuracyNote: 'Marathon → 5K predictions often show that marathon-trained runners underperform their 5K equivalent. Marathon training builds endurance and fat metabolism; the 5K demands high-intensity VO2max output that requires specific interval training. Most marathon runners find their actual 5K runs 30–90 seconds per mile slower than race pace implies — their aerobic engine is there but the high-speed neuromuscular and metabolic systems need 5K-specific training.',
    buildFaq: (data) => {
      const row3 = data.rows.find(r => r.inputTime === '3:00:00')
      const row4 = data.rows.find(r => r.inputTime === '4:00:00')
      return [
        { q: 'Why do marathon runners often underperform their 5K equivalent?', a: `Marathon training develops aerobic endurance and fat-based fuel economy. The 5K requires running at near-maximum aerobic output for 15–35 minutes — a VO2max-demanding effort that marathon training does not specifically develop. Adding interval training (800m–1200m repeats at interval pace) bridges this gap for marathon runners wanting to run fast 5Ks.` },
        { q: row3 ? `What 5K does a 3:00:00 marathon predict?` : `How do I use this table?`, a: row3 ? `A 3:00:00 marathon (RPI ${row3.rpi}) projects to ${row3.outputTime} 5K fitness at ${row3.outputPaceMi}/mi. Marathon runners may need 6–12 weeks of 5K-specific interval training to realize this potential.` : `Find your marathon time and read across to the predicted 5K equivalent.` },
        { q: row4 ? `What 5K does a 4:00:00 marathon predict?` : `What 5K training does a marathon runner need?`, a: row4 ? `A 4:00:00 marathon (RPI ${row4.rpi}) projects to ${row4.outputTime} 5K fitness.` : `Add weekly interval sessions (800m–1200m repeats at interval pace) to your marathon easy-running base. Six to twelve weeks of interval work typically converts marathon aerobic capacity into competitive 5K performance.` },
      ]
    },
  },

  'marathon-to-10k': {
    title: 'Marathon to 10K Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your marathon time, find your equivalent 10K potential. Daniels/Gilbert oxygen cost equation.',
    h1: 'Marathon to 10K Race Equivalency',
    openingParagraph: 'Your marathon time is a measure of your aerobic and threshold capacity. The 10K uses similar energy systems — this table shows what your marathon fitness predicts for the 10K. Marathon runners often perform closer to their 10K equivalency than their 5K equivalency because both require sustained threshold effort.',
    accuracyNote: 'Marathon runners typically run closer to their 10K equivalent than to their 5K equivalent. The 10K requires threshold stamina that marathon training develops. The primary gap: the 10K also demands higher-intensity interval-pace fitness. Runners who add occasional interval sessions to marathon training often match their 10K prediction within 1–2 minutes.',
    buildFaq: (data) => {
      const row3 = data.rows.find(r => r.inputTime === '3:00:00')
      return [
        { q: 'How accurate is marathon to 10K equivalency?', a: `More accurate than marathon-to-5K because the 10K relies more heavily on threshold fitness that marathon training develops. Most marathon runners fall within 2–4 minutes of their 10K equivalent — closer when they include some threshold work in training.` },
        { q: row3 ? `What 10K does a 3:00:00 marathon predict?` : `How do I use this table?`, a: row3 ? `A 3:00:00 marathon (RPI ${row3.rpi}) projects to ${row3.outputTime} 10K fitness at ${row3.outputPaceMi}/mi.` : `Find your marathon time and read across to the predicted 10K equivalent.` },
        { q: 'What training converts marathon fitness to 10K performance?', a: `Add threshold tempo runs (20–30 minutes at threshold pace) and occasional interval sessions to your marathon base. Two to three months of this targeted work typically converts marathon aerobic capacity into competitive 10K performance.` },
      ]
    },
  },

  'marathon-to-half-marathon': {
    title: 'Marathon to Half Marathon Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your marathon time, find your equivalent half marathon potential. Daniels/Gilbert oxygen cost equation.',
    h1: 'Marathon to Half Marathon Race Equivalency',
    openingParagraph: 'The half marathon and marathon share similar physiological demands — both require sustained aerobic and threshold endurance. This table shows what your marathon fitness predicts for the half marathon. For runners transitioning from marathon to half-marathon focus, the equivalency is often achievable or exceeded within a few weeks.',
    accuracyNote: 'Marathon → half marathon is among the more reliable reverse-direction predictions. Both distances tax similar energy systems. Marathon-trained runners often slightly outperform their half marathon equivalent because the high-threshold intensity of the half marathon is easier to sustain than marathon pace over 13.1 miles with full marathon training. Typical accuracy: within 2–4 minutes.',
    buildFaq: (data) => {
      const row3 = data.rows.find(r => r.inputTime === '3:00:00')
      const row4 = data.rows.find(r => r.inputTime === '4:00:00')
      return [
        { q: 'Will marathon training help my half marathon time?', a: `Yes — marathon training builds the aerobic base and threshold stamina that the half marathon demands. Marathon runners transitioning to the half often find their performance exceeds the prediction because the shorter distance demands less endurance but similar aerobic and threshold capacity.` },
        { q: row3 ? `What half marathon does a 3:00:00 marathon predict?` : `How do I use this table?`, a: row3 ? `A 3:00:00 marathon (RPI ${row3.rpi}) projects to ${row3.outputTime} half marathon fitness at ${row3.outputPaceMi}/mi.` : `Find your marathon time and read across to the predicted half marathon equivalent.` },
        { q: row4 ? `What half marathon does a 4:00:00 marathon predict?` : `What changes when switching from marathon to half marathon focus?`, a: row4 ? `A 4:00:00 marathon (RPI ${row4.rpi}) projects to ${row4.outputTime} half marathon potential.` : `Add threshold work (20–30 minute tempo runs) to your marathon base. Reduce long runs to 12–15 miles and add more intensity. Within 6–10 weeks of half-specific training, most marathon runners approach or exceed their half marathon equivalency.` },
      ]
    },
  },

  '800m-to-mile': {
    title: '800m to Mile Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 800m time, find your equivalent mile potential. Daniels/Gilbert oxygen cost equation.',
    h1: '800m to Mile Race Equivalency',
    openingParagraph: 'The 800m and mile share high-intensity aerobic demands with a significant anaerobic component. This table shows what your 800m time predicts for the mile — assuming mile-specific endurance development. Pure 800m speed transfers closely to the mile for runners with strong aerobic training.',
    accuracyNote: 'The 800m → mile prediction is accurate for runners who train both distances. The primary divergence: runners with very high anaerobic capacity relative to aerobic capacity (pure 800m specialists) may underperform their mile equivalent slightly. Aerobic training — easy running volume and threshold work — bridges this gap. Most track athletes find the prediction accurate within 5–10 seconds.',
    buildFaq: (data) => {
      const row2 = data.rows.find(r => r.inputTime === '2:00')
      return [
        { q: 'How accurate is 800m to mile equivalency?', a: `Accurate for runners with strong aerobic development. The 800m and mile both require high-intensity output — the formula predicts the mile time that the same aerobic capacity supports. Purely anaerobic runners may underperform; aerobically trained middle-distance runners typically match the prediction within 5–10 seconds.` },
        { q: row2 ? `What mile does a 2:00 800m predict?` : `How do I use this table?`, a: row2 ? `A 2:00 800m (RPI ${row2.rpi}) projects to ${row2.outputTime} mile fitness at ${row2.outputPaceMi}/mi.` : `Find your 800m time and read across to the predicted mile equivalent.` },
        { q: 'What training converts 800m speed to mile fitness?', a: `Add easy aerobic volume (easy running at easy pace for 30–50+ miles/week) and threshold training (1600m–3200m tempo runs) to 800m-specific interval work. The aerobic base that mile racing demands is the primary addition for 800m runners transitioning to the mile.` },
      ]
    },
  },

  '800m-to-5k': {
    title: '800m to 5K Equivalency Table — Daniels/Gilbert Formula',
    description: 'Given your 800m time, find your equivalent 5K potential. Daniels/Gilbert oxygen cost equation.',
    h1: '800m to 5K Race Equivalency',
    openingParagraph: 'Your 800m time measures raw speed and aerobic capacity at high intensity. This table shows what that capacity predicts for the 5K — a distance that demands sustained aerobic output for 15–35 minutes. The conversion requires specific aerobic development beyond what 800m training produces.',
    accuracyNote: 'The 800m → 5K prediction has substantial divergence for 800m specialists who lack 5K-specific endurance training. The aerobic ceiling measured by the 800m is real, but converting it to 5K performance requires threshold training and adequate easy-run volume that pure 800m training may not develop. Runners with 5–10 weeks of 5K-specific preparation typically close to within 30–60 seconds of the prediction.',
    buildFaq: (data) => {
      const row2 = data.rows.find(r => r.inputTime === '2:00')
      return [
        { q: 'Why do 800m runners often struggle in the 5K?', a: `The 800m is run at near-VO2max intensity for 1:45–3:00 — demanding anaerobic capacity and raw speed. The 5K requires sustaining effort near (but below) VO2max for 15–35 minutes — a fundamentally different stamina demand. Without threshold training and easy aerobic volume, 800m speed does not convert directly to 5K performance.` },
        { q: row2 ? `What 5K does a 2:00 800m predict?` : `How do I use this table?`, a: row2 ? `A 2:00 800m (RPI ${row2.rpi}) projects to ${row2.outputTime} 5K fitness at ${row2.outputPaceMi}/mi. This assumes 5K-specific training: threshold work and easy volume.` : `Find your 800m time and read across to the predicted 5K equivalent.` },
        { q: 'What training does an 800m runner need to develop 5K fitness?', a: `Add threshold tempo runs (15–25 minutes at threshold pace) and increase easy running volume to 35–50+ miles per week. Six to twelve weeks of this aerobic base development converts 800m speed into competitive 5K performance. The aerobic ceiling from 800m training is high — it just needs the endurance layer to support 5K duration.` },
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
