/**
 * Extract exact values needed for BLUF and FAQ content.
 * Verifies all 5 data files for integrity: no null paces, key coverage, sample outputs.
 * Run: node scripts/verify-bluf-data.mjs
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'apps', 'web', 'data');

const ag = JSON.parse(readFileSync(join(DATA_DIR, 'age-grading-tables.json'), 'utf8'));
const tp = JSON.parse(readFileSync(join(DATA_DIR, 'training-pace-tables.json'), 'utf8'));
const gp = JSON.parse(readFileSync(join(DATA_DIR, 'goal-pace-tables.json'), 'utf8'));
const demo = JSON.parse(readFileSync(join(DATA_DIR, 'age-gender-tables.json'), 'utf8'));
const eq = JSON.parse(readFileSync(join(DATA_DIR, 'equivalency-tables.json'), 'utf8'));

console.log('=== AGE-GRADING DATA FOR BLUF/FAQ ===\n');

for (const [distKey, data] of Object.entries(ag)) {
  console.log(`--- ${data.distance} ---`);
  for (const gender of ['male', 'female']) {
    for (const row of data[gender]) {
      if ([30, 40, 50, 55, 60, 65, 70].includes(row.age)) {
        const l = row.levels;
        console.log(`  ${gender} ${row.age}: 50%=${l['50'].timeFormatted} 60%=${l['60'].timeFormatted} 70%=${l['70'].timeFormatted} 80%=${l['80'].timeFormatted} 90%=${l['90'].timeFormatted}`);
      }
    }
  }
  console.log();
}

console.log('\n=== TRAINING PACE DATA FOR BLUF/FAQ ===\n');

for (const [distKey, data] of Object.entries(tp)) {
  console.log(`--- ${data.distance} ---`);
  for (const row of data.rows) {
    const p = row.paces;
    console.log(`  ${row.raceTime} RPI=${row.rpi} E=${p.easy?.mi} M=${p.marathon?.mi} T=${p.threshold?.mi} I=${p.interval?.mi} R=${p.repetition?.mi}`);
  }
  console.log();
}

// Specific calculations for FAQ answers
console.log('\n=== SPECIFIC FAQ CALCULATIONS ===\n');

// Sub-20 5K age grading for various ages
const fiveK = ag['5k'];
for (const gender of ['male']) {
  for (const row of fiveK[gender]) {
    if ([25, 30, 35, 40, 45, 50, 55, 60, 70].includes(row.age)) {
      const pct = (row.ageStandardSeconds / 1200) * 100;
      console.log(`Sub-20:00 5K ${gender} age ${row.age}: ${pct.toFixed(1)}%`);
    }
  }
}
console.log();

// 50:00 10K age grading for various ages
const tenK = ag['10k'];
for (const gender of ['male']) {
  for (const row of tenK[gender]) {
    if ([30, 40, 50, 60, 70].includes(row.age)) {
      const pct = (row.ageStandardSeconds / 3000) * 100;
      console.log(`50:00 10K ${gender} age ${row.age}: ${pct.toFixed(1)}%`);
    }
  }
}
console.log();

// Sub-2hr half age grading  
const half = ag['half'];
for (const gender of ['male']) {
  for (const row of half[gender]) {
    if ([30, 45, 60, 70].includes(row.age)) {
      const pct = (row.ageStandardSeconds / 7200) * 100;
      console.log(`2:00:00 Half ${gender} age ${row.age}: ${pct.toFixed(1)}%`);
    }
  }
}
console.log();

// 4hr marathon age grading
const marathon = ag['marathon'];
for (const gender of ['male']) {
  for (const row of marathon[gender]) {
    if ([30, 40, 55, 65].includes(row.age)) {
      const pct = (row.ageStandardSeconds / 14400) * 100;
      console.log(`4:00:00 Marathon ${gender} age ${row.age}: ${pct.toFixed(1)}%`);
    }
  }
}

// ============================================================================
// NEW FILE CHECKS — goal-pace-tables.json
// ============================================================================

console.log('\n\n=== GOAL-PACE DATA INTEGRITY ===\n');

let errors = 0;

const EXPECTED_GOAL_SLUGS = [
  'sub-20-minute-5k',
  'sub-25-minute-5k',
  'sub-40-minute-10k',
  'sub-50-minute-10k',
  'sub-2-hour-half-marathon',
  'sub-4-hour-marathon',
];

const PACE_FIELDS = ['easy', 'marathon', 'threshold', 'interval', 'repetition'];

console.log('--- Key coverage ---');
for (const slug of EXPECTED_GOAL_SLUGS) {
  if (!gp[slug]) {
    console.error(`  MISSING: ${slug}`);
    errors++;
    continue;
  }
  const g = gp[slug];

  // Check all paces non-null
  for (const field of PACE_FIELDS) {
    if (!g.paces?.[field]?.mi) {
      console.error(`  NULL PACE: ${slug}.paces.${field}.mi`);
      errors++;
    }
  }

  // Check rpi present
  if (!g.rpi) {
    console.error(`  NULL RPI: ${slug}`);
    errors++;
  }

  // Check at least one equivalent
  if (!g.equivalents || Object.keys(g.equivalents).length === 0) {
    console.error(`  NO EQUIVALENTS: ${slug}`);
    errors++;
  }

  console.log(`  ✓ ${slug}: RPI=${g.rpi} easy=${g.paces.easy.mi} threshold=${g.paces.threshold.mi} interval=${g.paces.interval.mi}`);
}

console.log('\n--- Sample BLUF values for goal pages ---');
for (const slug of EXPECTED_GOAL_SLUGS) {
  if (!gp[slug]) continue;
  const g = gp[slug];
  const equivKeys = Object.keys(g.equivalents);
  const equivSample = equivKeys.length > 0
    ? `${equivKeys[0]}=${g.equivalents[equivKeys[0]].timeFormatted}`
    : 'no equiv';
  console.log(`  ${slug}: goal=${g.goalTimeLabel} rpi=${g.rpi} easy=${g.paces.easy.mi} T=${g.paces.threshold.mi} I=${g.paces.interval.mi} [${equivSample}]`);
}

// ============================================================================
// NEW FILE CHECKS — age-gender-tables.json
// ============================================================================

console.log('\n\n=== AGE-GENDER DEMOGRAPHIC DATA INTEGRITY ===\n');

const EXPECTED_DEMO_SLUGS = [
  '5k-times-women-age-40s',
  '5k-times-women-age-50s',
  'marathon-times-men-age-50s',
  'marathon-times-women-age-50s',
  '10k-times-men-age-60s',
  'marathon-times-men-age-60s',
];

const DEMO_PERF_PCTS = [50, 60, 70, 80];

console.log('--- Key coverage ---');
for (const slug of EXPECTED_DEMO_SLUGS) {
  if (!demo[slug]) {
    console.error(`  MISSING: ${slug}`);
    errors++;
    continue;
  }
  const d = demo[slug];
  if (!d.rows || d.rows.length === 0) {
    console.error(`  NO ROWS: ${slug}`);
    errors++;
    continue;
  }

  let slugOk = true;
  for (const row of d.rows) {
    for (const pct of DEMO_PERF_PCTS) {
      const lvl = row.levels?.[pct];
      if (!lvl?.timeFormatted) {
        console.error(`  NULL TIME: ${slug} age=${row.age} pct=${pct}`);
        errors++;
        slugOk = false;
      }
      if (!lvl?.trainingPaces?.easy?.mi) {
        console.error(`  NULL TRAINING PACE: ${slug} age=${row.age} pct=${pct}`);
        errors++;
        slugOk = false;
      }
    }
  }

  if (slugOk) {
    const r0 = d.rows[0];
    const l70 = r0.levels[70];
    console.log(`  ✓ ${slug}: age=${r0.age} 70%=${l70.timeFormatted} easy=${l70.trainingPaces.easy.mi} T=${l70.trainingPaces.threshold.mi}`);
  }
}

console.log('\n--- Sample BLUF values for demographic pages ---');
for (const slug of EXPECTED_DEMO_SLUGS) {
  if (!demo[slug]) continue;
  const d = demo[slug];
  console.log(`  ${slug} (${d.genderLabel}, ${d.distance}, ${d.ageRange}):`);
  for (const row of d.rows) {
    const l60 = row.levels[60];
    const l70 = row.levels[70];
    console.log(`    age ${row.age}: 60%=${l60.timeFormatted} (easy ${l60.trainingPaces?.easy.mi}, T ${l60.trainingPaces?.threshold.mi}) | 70%=${l70.timeFormatted} (easy ${l70.trainingPaces?.easy.mi}, T ${l70.trainingPaces?.threshold.mi})`);
  }
}

// ============================================================================
// NEW FILE CHECKS — equivalency-tables.json
// ============================================================================

console.log('\n\n=== EQUIVALENCY DATA INTEGRITY ===\n');

const EXPECTED_EQUIV_SLUGS = ['5k-to-marathon', '10k-to-half-marathon'];

console.log('--- Key coverage ---');
for (const slug of EXPECTED_EQUIV_SLUGS) {
  if (!eq[slug]) {
    console.error(`  MISSING: ${slug}`);
    errors++;
    continue;
  }
  const e = eq[slug];
  if (!e.rows || e.rows.length !== 12) {
    console.error(`  ROW COUNT WRONG: ${slug} has ${e.rows?.length} rows, expected 12`);
    errors++;
    continue;
  }

  let slugOk = true;
  for (const row of e.rows) {
    if (!row.outputTime) { console.error(`  NULL outputTime: ${slug} ${row.inputTime}`); errors++; slugOk = false; }
    if (!row.outputPaceMi) { console.error(`  NULL outputPaceMi: ${slug} ${row.inputTime}`); errors++; slugOk = false; }
    if (!row.rpi) { console.error(`  NULL rpi: ${slug} ${row.inputTime}`); errors++; slugOk = false; }
  }

  if (slugOk) {
    console.log(`  ✓ ${slug}: ${e.rows.length} rows, ${e.inputDistance} → ${e.outputDistance}`);
  }
}

console.log('\n--- Sample BLUF values for equivalency pages ---');
for (const slug of EXPECTED_EQUIV_SLUGS) {
  if (!eq[slug]) continue;
  const e = eq[slug];
  console.log(`  ${slug} (${e.inputDistance} → ${e.outputDistance}):`);
  for (const row of e.rows) {
    console.log(`    ${row.inputTime} (RPI ${row.rpi}) → ${e.outputDistance} ${row.outputTime} @ ${row.outputPaceMi}/mi`);
  }
}

// ============================================================================
// FINAL VERDICT
// ============================================================================

console.log(`\n${'='.repeat(60)}`);
if (errors === 0) {
  console.log(`ALL CHECKS PASSED (5 data files verified, 0 errors)`);
} else {
  console.error(`FAILED: ${errors} error(s) found. Fix before building pages.`);
  process.exit(1);
}
