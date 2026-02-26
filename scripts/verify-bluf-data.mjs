/**
 * Extract exact values needed for BLUF and FAQ content.
 * Run: node scripts/verify-bluf-data.mjs
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'apps', 'web', 'data');

const ag = JSON.parse(readFileSync(join(DATA_DIR, 'age-grading-tables.json'), 'utf8'));
const tp = JSON.parse(readFileSync(join(DATA_DIR, 'training-pace-tables.json'), 'utf8'));

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
