/**
 * Pre-compute age-grading and training pace data for programmatic SEO pages.
 *
 * Age-grading: computed from Alan Jones 2025 WMA constants (same values as
 * apps/api/services/wma_age_factors.py). Formula:
 *   time_seconds = (open_standard * age_factor) / (percentage / 100)
 *
 * Training paces: fetched from the production API at strideiq.run to guarantee
 * exact match with the live calculator. No independent reimplementation.
 *
 * Usage: node scripts/generate-pseo-data.mjs
 */

import { writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'apps', 'web', 'data');

// ============================================================================
// WMA OPEN CLASS STANDARDS (seconds) — Alan Jones 2025
// Copied verbatim from apps/api/services/wma_age_factors.py
// ============================================================================

const OPEN_STANDARDS = {
  male: {
    5000:    769,    // 12:49
    10000:   1584,   // 26:24
    21097.5: 3451,   // 57:31
    42195:   7235,   // 2:00:35
  },
  female: {
    5000:    834,    // 13:54
    10000:   1726,   // 28:46
    21097.5: 3772,   // 1:02:52
    42195:   7796,   // 2:09:56
  },
};

// ============================================================================
// WMA AGE FACTORS — Alan Jones 2025
// Copied verbatim from apps/api/services/wma_age_factors.py
// Only ages 30–80 included (the range we display on pSEO pages)
// ============================================================================

const AGE_FACTORS = {
  male: {
    5000: {
      30:1.0001,31:1.0012,32:1.0035,33:1.007,34:1.0118,
      35:1.0179,36:1.0251,37:1.0325,38:1.04,39:1.0477,
      40:1.0554,41:1.0633,42:1.0712,43:1.0793,44:1.0875,
      45:1.0959,46:1.1044,47:1.113,48:1.1217,49:1.1306,
      50:1.1396,51:1.1488,52:1.1581,53:1.1675,54:1.1772,
      55:1.1869,56:1.1969,57:1.207,58:1.2173,59:1.2277,
      60:1.2384,61:1.2492,62:1.2602,63:1.2715,64:1.2829,
      65:1.2945,66:1.3063,67:1.3184,68:1.3308,69:1.3448,
      70:1.36,71:1.3767,72:1.3949,73:1.4148,74:1.4368,
      75:1.4605,76:1.4863,77:1.5145,78:1.5451,79:1.5788,
      80:1.6152,
    },
    10000: {
      30:1.0,31:1.0004,32:1.0015,33:1.0033,34:1.0058,
      35:1.0092,36:1.0133,37:1.0181,38:1.0239,39:1.0304,
      40:1.0378,41:1.0459,42:1.0542,43:1.0626,44:1.0711,
      45:1.0798,46:1.0886,47:1.0976,48:1.1067,49:1.1159,
      50:1.1254,51:1.1349,52:1.1447,53:1.1546,54:1.1647,
      55:1.175,56:1.1854,57:1.196,58:1.2069,59:1.2179,
      60:1.2291,61:1.2405,62:1.2522,63:1.2641,64:1.2762,
      65:1.2885,66:1.3011,67:1.3139,68:1.327,69:1.3403,
      70:1.3539,71:1.3684,72:1.3845,73:1.4023,74:1.4219,
      75:1.4434,76:1.4671,77:1.4932,78:1.5216,79:1.5528,
      80:1.587,
    },
    21097.5: {
      30:1.0,31:1.0,32:1.0004,33:1.0018,34:1.004,
      35:1.0073,36:1.0113,37:1.0164,38:1.0224,39:1.0294,
      40:1.0376,41:1.046,42:1.0545,43:1.0633,44:1.0722,
      45:1.0812,46:1.0904,47:1.0996,48:1.1091,49:1.1188,
      50:1.1287,51:1.1387,52:1.1488,53:1.1592,54:1.1697,
      55:1.1805,56:1.1915,57:1.2025,58:1.2139,59:1.2255,
      60:1.2373,61:1.2494,62:1.2615,63:1.274,64:1.2868,
      65:1.2999,66:1.3132,67:1.3266,68:1.3405,69:1.3546,
      70:1.3691,71:1.3845,72:1.4015,73:1.4205,74:1.4413,
      75:1.4641,76:1.4892,77:1.5168,78:1.547,79:1.5803,
      80:1.6168,
    },
    42195: {
      30:1.0,31:1.0,32:1.0,33:1.0,34:1.0,
      35:1.0,36:1.0001,37:1.0021,38:1.0066,39:1.0137,
      40:1.0222,41:1.0308,42:1.0396,43:1.0485,44:1.0576,
      45:1.0669,46:1.0763,47:1.0859,48:1.0957,49:1.1056,
      50:1.1157,51:1.126,52:1.1365,53:1.1472,54:1.1581,
      55:1.1692,56:1.1805,57:1.192,58:1.2038,59:1.2158,
      60:1.228,61:1.2405,62:1.2533,63:1.2663,64:1.2796,
      65:1.2932,66:1.307,67:1.3212,68:1.3356,69:1.3504,
      70:1.3656,71:1.381,72:1.3976,73:1.4158,74:1.4362,
      75:1.4584,76:1.483,77:1.5099,78:1.5396,79:1.5721,
      80:1.608,
    },
  },
  female: {
    5000: {
      30:1.0041,31:1.0064,32:1.0093,33:1.0127,34:1.0167,
      35:1.0211,36:1.0263,37:1.0319,38:1.0382,39:1.0452,
      40:1.0527,41:1.061,42:1.07,43:1.0797,44:1.0903,
      45:1.1016,46:1.1136,47:1.1257,48:1.1382,49:1.1509,
      50:1.1639,51:1.1772,52:1.1908,53:1.2047,54:1.2189,
      55:1.2335,56:1.2486,57:1.2639,58:1.2796,59:1.2957,
      60:1.3122,61:1.3291,62:1.3464,63:1.3643,64:1.3826,
      65:1.4013,66:1.4209,67:1.4407,68:1.4611,69:1.4821,
      70:1.5038,71:1.526,72:1.5489,73:1.5726,74:1.5969,
      75:1.6221,76:1.6483,77:1.675,78:1.7042,79:1.7367,
      80:1.773,
    },
    10000: {
      30:1.002,31:1.0036,32:1.0056,33:1.0081,34:1.011,
      35:1.0145,36:1.0184,37:1.0228,38:1.0277,39:1.0332,
      40:1.0392,41:1.0457,42:1.0527,43:1.0606,44:1.0688,
      45:1.0778,46:1.0875,47:1.0978,48:1.109,49:1.121,
      50:1.1335,51:1.1464,52:1.1597,53:1.1732,54:1.1869,
      55:1.2012,56:1.2157,57:1.2306,58:1.2458,59:1.2614,
      60:1.2775,61:1.2938,62:1.3108,63:1.328,64:1.3457,
      65:1.3641,66:1.3827,67:1.4021,68:1.4219,69:1.4422,
      70:1.4633,71:1.4848,72:1.5072,73:1.53,74:1.5535,
      75:1.578,76:1.6041,77:1.6332,78:1.6653,79:1.701,
      80:1.7406,
    },
    21097.5: {
      30:1.0021,31:1.0038,32:1.0059,33:1.0086,34:1.0117,
      35:1.0153,36:1.0195,37:1.0242,38:1.0294,39:1.0352,
      40:1.0416,41:1.0485,42:1.0562,43:1.0644,44:1.0733,
      45:1.083,46:1.0933,47:1.1044,48:1.1163,49:1.1292,
      50:1.1425,51:1.1562,52:1.1701,53:1.1846,54:1.1992,
      55:1.2143,56:1.2297,57:1.2456,58:1.2618,59:1.2786,
      60:1.2957,61:1.3134,62:1.3314,63:1.3501,64:1.3691,
      65:1.3889,66:1.409,67:1.43,68:1.4514,69:1.4736,
      70:1.4963,71:1.52,72:1.5442,73:1.5694,74:1.5952,
      75:1.6221,76:1.6504,77:1.6821,78:1.7176,79:1.7569,
      80:1.8005,
    },
    42195: {
      30:1.0017,31:1.003,32:1.0047,33:1.0068,34:1.0094,
      35:1.0122,36:1.0155,37:1.0193,38:1.0234,39:1.0281,
      40:1.0331,41:1.0385,42:1.0445,43:1.051,44:1.0579,
      45:1.0654,46:1.0734,47:1.082,48:1.0911,49:1.101,
      50:1.1114,51:1.1225,52:1.1343,53:1.1468,54:1.1602,
      55:1.1744,56:1.1895,57:1.2053,58:1.2216,59:1.2382,
      60:1.2555,61:1.2732,62:1.2913,63:1.3101,64:1.3293,
      65:1.3492,66:1.3697,67:1.3906,68:1.4124,69:1.4347,
      70:1.4579,71:1.4819,72:1.5065,73:1.5321,74:1.5593,
      75:1.5898,76:1.6236,77:1.6609,78:1.7024,79:1.7483,
      80:1.7995,
    },
  },
};

// ============================================================================
// DISTANCE METADATA
// ============================================================================

const DISTANCES = {
  5000:    { key: '5k',   label: '5K',            miles: 5000 / 1609.34 },
  10000:   { key: '10k',  label: '10K',           miles: 10000 / 1609.34 },
  21097.5: { key: 'half', label: 'Half Marathon',  miles: 21097.5 / 1609.34 },
  42195:   { key: 'marathon', label: 'Marathon',   miles: 42195 / 1609.34 },
};

const AGES = [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80];

const PERFORMANCE_LEVELS = [
  { pct: 90, label: 'World Class' },
  { pct: 80, label: 'National Class' },
  { pct: 70, label: 'Regional Class' },
  { pct: 60, label: 'Local Class' },
  { pct: 50, label: 'Recreational' },
];

// ============================================================================
// TIME FORMATTING — matches apps/api/routers/public_tools.py _format_time
// ============================================================================

function formatTime(totalSeconds) {
  totalSeconds = Math.round(totalSeconds);
  const hours = Math.floor(totalSeconds / 3600);
  const mins  = Math.floor((totalSeconds % 3600) / 60);
  const secs  = totalSeconds % 60;
  if (hours > 0) return `${hours}:${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')}`;
  return `${mins}:${String(secs).padStart(2,'0')}`;
}

function formatPace(totalSeconds, distanceMeters) {
  const miles = distanceMeters / 1609.34;
  const secPerMile = Math.round(totalSeconds / miles);
  const mins = Math.floor(secPerMile / 60);
  const secs = secPerMile % 60;
  return `${mins}:${String(secs).padStart(2,'0')}`;
}

// ============================================================================
// AGE-GRADING TABLE GENERATION
// ============================================================================

function generateAgeGradingData() {
  const result = {};

  for (const [distM, distInfo] of Object.entries(DISTANCES)) {
    const dm = Number(distM);
    result[distInfo.key] = {
      distance: distInfo.label,
      distanceMeters: dm,
      male: [],
      female: [],
    };

    for (const gender of ['male', 'female']) {
      for (const age of AGES) {
        const factor = AGE_FACTORS[gender][dm]?.[age];
        if (!factor) continue;

        const openStandard = OPEN_STANDARDS[gender][dm];
        const ageStandard = openStandard * factor;

        const levels = {};
        for (const { pct, label } of PERFORMANCE_LEVELS) {
          const timeSec = ageStandard / (pct / 100);
          levels[pct] = {
            label,
            timeSeconds: Math.round(timeSec),
            timeFormatted: formatTime(timeSec),
            pace: formatPace(timeSec, dm),
          };
        }

        result[distInfo.key][gender].push({
          age,
          ageFactor: factor,
          ageStandardSeconds: Math.round(ageStandard * 10) / 10,
          levels,
        });
      }
    }
  }

  return result;
}

// ============================================================================
// TRAINING PACE TABLE GENERATION — via production API
// ============================================================================

const API_BASE = 'https://strideiq.run/v1/public';

const RACE_TIMES = {
  '5k': [
    { label: '15:00', seconds: 900 },
    { label: '17:00', seconds: 1020 },
    { label: '18:00', seconds: 1080 },
    { label: '19:00', seconds: 1140 },
    { label: '20:00', seconds: 1200 },
    { label: '21:00', seconds: 1260 },
    { label: '22:00', seconds: 1320 },
    { label: '23:00', seconds: 1380 },
    { label: '24:00', seconds: 1440 },
    { label: '25:00', seconds: 1500 },
    { label: '26:00', seconds: 1560 },
    { label: '27:00', seconds: 1620 },
    { label: '28:00', seconds: 1680 },
    { label: '30:00', seconds: 1800 },
    { label: '32:00', seconds: 1920 },
    { label: '35:00', seconds: 2100 },
  ],
  '10k': [
    { label: '32:00', seconds: 1920 },
    { label: '35:00', seconds: 2100 },
    { label: '38:00', seconds: 2280 },
    { label: '40:00', seconds: 2400 },
    { label: '42:00', seconds: 2520 },
    { label: '44:00', seconds: 2640 },
    { label: '45:00', seconds: 2700 },
    { label: '48:00', seconds: 2880 },
    { label: '50:00', seconds: 3000 },
    { label: '52:00', seconds: 3120 },
    { label: '55:00', seconds: 3300 },
    { label: '58:00', seconds: 3480 },
    { label: '1:00:00', seconds: 3600 },
    { label: '1:05:00', seconds: 3900 },
  ],
  'half': [
    { label: '1:15:00', seconds: 4500 },
    { label: '1:20:00', seconds: 4800 },
    { label: '1:25:00', seconds: 5100 },
    { label: '1:30:00', seconds: 5400 },
    { label: '1:35:00', seconds: 5700 },
    { label: '1:40:00', seconds: 6000 },
    { label: '1:45:00', seconds: 6300 },
    { label: '1:50:00', seconds: 6600 },
    { label: '1:55:00', seconds: 6900 },
    { label: '2:00:00', seconds: 7200 },
    { label: '2:05:00', seconds: 7500 },
    { label: '2:10:00', seconds: 7800 },
    { label: '2:15:00', seconds: 8100 },
    { label: '2:20:00', seconds: 8400 },
    { label: '2:30:00', seconds: 9000 },
  ],
  'marathon': [
    { label: '2:30:00', seconds: 9000 },
    { label: '2:40:00', seconds: 9600 },
    { label: '2:50:00', seconds: 10200 },
    { label: '3:00:00', seconds: 10800 },
    { label: '3:10:00', seconds: 11400 },
    { label: '3:15:00', seconds: 11700 },
    { label: '3:20:00', seconds: 12000 },
    { label: '3:30:00', seconds: 12600 },
    { label: '3:40:00', seconds: 13200 },
    { label: '3:45:00', seconds: 13500 },
    { label: '4:00:00', seconds: 14400 },
    { label: '4:15:00', seconds: 15300 },
    { label: '4:30:00', seconds: 16200 },
    { label: '4:45:00', seconds: 17100 },
    { label: '5:00:00', seconds: 18000 },
  ],
};

const DISTANCE_METERS = { '5k': 5000, '10k': 10000, 'half': 21097.5, 'marathon': 42195 };
const DISTANCE_LABELS = { '5k': '5K', '10k': '10K', 'half': 'Half Marathon', 'marathon': 'Marathon' };

async function fetchTrainingPaces(distanceMeters, timeSeconds) {
  const res = await fetch(`${API_BASE}/rpi/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ distance_meters: distanceMeters, time_seconds: timeSeconds }),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

async function generateTrainingPaceData() {
  const result = {};

  for (const [distKey, times] of Object.entries(RACE_TIMES)) {
    const dm = DISTANCE_METERS[distKey];
    console.log(`Fetching training paces for ${DISTANCE_LABELS[distKey]}...`);
    const rows = [];

    for (const { label, seconds } of times) {
      try {
        const data = await fetchTrainingPaces(dm, seconds);

        // Enhanced API returns training.per_mile_km with lowercase keys
        // Basic fallback returns training_paces with same structure
        const tp = data.training?.per_mile_km || data.training_paces;

        if (!tp || !tp.easy) {
          console.error(`  WARN: ${label} — no pace data in response (keys: ${Object.keys(data).join(', ')})`);
        }

        rows.push({
          raceTime: label,
          raceTimeSeconds: seconds,
          rpi: data.rpi,
          paces: {
            easy:       { mi: tp?.easy?.mi       || tp?.easy?.display_mi, km: tp?.easy?.km },
            marathon:   { mi: tp?.marathon?.mi,   km: tp?.marathon?.km },
            threshold:  { mi: tp?.threshold?.mi,  km: tp?.threshold?.km },
            interval:   { mi: tp?.interval?.mi,   km: tp?.interval?.km },
            repetition: { mi: tp?.repetition?.mi,  km: tp?.repetition?.km },
          },
        });

        // Delay to stay under 60/min rate limit
        await new Promise(r => setTimeout(r, 1100));
      } catch (err) {
        console.error(`  FAILED: ${label} — ${err.message}`);
        // Wait longer on error (likely rate limit)
        await new Promise(r => setTimeout(r, 5000));
      }
    }

    result[distKey] = {
      distance: DISTANCE_LABELS[distKey],
      distanceMeters: dm,
      rows,
    };
  }

  return result;
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  console.log('Generating age-grading tables...');
  const ageGrading = generateAgeGradingData();
  const ageFile = join(DATA_DIR, 'age-grading-tables.json');
  writeFileSync(ageFile, JSON.stringify(ageGrading, null, 2));
  console.log(`  Written to ${ageFile}`);

  // Validate a sample: 57-year-old male 10K at 60% should be a real time
  const sample = ageGrading['10k'].male.find(r => r.age === 57);
  if (sample) {
    console.log(`  Sample: 57M 10K, 60% = ${sample.levels[60].timeFormatted} (${sample.levels[60].pace}/mi)`);
    console.log(`  Sample: 57M 10K, 80% = ${sample.levels[80].timeFormatted} (${sample.levels[80].pace}/mi)`);
  }

  console.log('\nFetching training pace data from production API...');
  const trainingPaces = await generateTrainingPaceData();
  const paceFile = join(DATA_DIR, 'training-pace-tables.json');
  writeFileSync(paceFile, JSON.stringify(trainingPaces, null, 2));
  console.log(`  Written to ${paceFile}`);

  // Summary
  let totalPaceRows = 0;
  for (const d of Object.values(trainingPaces)) totalPaceRows += d.rows.length;
  console.log(`\nDone. Age-grading: ${Object.keys(ageGrading).length} distances. Training paces: ${totalPaceRows} rows.`);
}

main().catch(err => { console.error(err); process.exit(1); });
