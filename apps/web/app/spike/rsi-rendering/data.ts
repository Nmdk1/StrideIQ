/**
 * ADR-064 Rendering Spike — Synthetic stream data generator
 *
 * Generates a realistic 1-hour interval session (6×800m) with:
 * - Warmup, work intervals, recovery jogs, cooldown
 * - Rolling terrain with two moderate hills
 * - HR, pace, cadence, altitude, grade, effort intensity
 */

export interface StreamPoint {
  time: number;          // seconds from start
  hr: number;            // bpm
  pace: number;          // seconds per km
  velocity: number;      // m/s
  altitude: number;      // meters
  grade: number;         // percent
  cadence: number;       // spm
  effort: number;        // 0.0–1.0 (Tier 1: HR / threshold_hr, clamped)
}

const THRESHOLD_HR = 165;
const RESTING_HR = 48;
const MAX_HR = 186;

function clamp(min: number, max: number, v: number): number {
  return Math.min(max, Math.max(min, v));
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// Smoothed noise
function noise(i: number, scale: number = 1): number {
  return Math.sin(i * 0.1) * 0.3 + Math.sin(i * 0.037) * 0.5 + Math.cos(i * 0.071) * 0.2;
}

export function generateIntervalSession(): StreamPoint[] {
  const points: StreamPoint[] = [];
  const totalSeconds = 3600;

  // Terrain: two hills centered at ~1200s and ~2400s
  function getAltitude(t: number): number {
    const base = 100;
    const hill1 = 25 * Math.exp(-((t - 1200) ** 2) / (2 * 200 ** 2));
    const hill2 = 35 * Math.exp(-((t - 2400) ** 2) / (2 * 250 ** 2));
    const undulation = 3 * Math.sin(t / 80) + 2 * Math.sin(t / 200);
    return base + hill1 + hill2 + undulation;
  }

  // Interval structure:
  // 0–480: warmup (easy)
  // 480–3120: 6 × (240s work + 180s recovery) = 6 × 420 = 2520s
  // 3120–3600: cooldown
  function getPhase(t: number): 'warmup' | 'work' | 'recovery' | 'cooldown' {
    if (t < 480) return 'warmup';
    if (t >= 3120) return 'cooldown';
    const inBlock = (t - 480) % 420;
    return inBlock < 240 ? 'work' : 'recovery';
  }

  function getIntervalIndex(t: number): number {
    if (t < 480 || t >= 3120) return -1;
    return Math.floor((t - 480) / 420);
  }

  let prevAlt = getAltitude(0);
  let accumulatedHR = 130; // starting HR after pre-jog

  for (let t = 0; t <= totalSeconds; t++) {
    const phase = getPhase(t);
    const repIdx = getIntervalIndex(t);
    const alt = getAltitude(t);
    const grade = t > 0 ? ((alt - prevAlt) / 1.0) * 100 : 0; // 1m per second at ~running speed
    prevAlt = alt;

    // Target HR and pace by phase
    let targetHR: number;
    let targetPace: number; // sec/km
    let targetCadence: number;

    switch (phase) {
      case 'warmup': {
        const progress = t / 480;
        targetHR = lerp(125, 142, progress);
        targetPace = lerp(360, 330, progress); // 6:00 → 5:30/km
        targetCadence = lerp(168, 174, progress);
        break;
      }
      case 'work': {
        // Progressive fatigue: later intervals are harder
        const fatigueFactor = repIdx >= 0 ? repIdx * 2 : 0;
        const inRep = ((t - 480) % 420) / 240; // 0→1 within rep
        targetHR = 168 + fatigueFactor + inRep * 6;
        targetPace = 210 + fatigueFactor * 1.5; // ~3:30/km, drifting slightly
        targetCadence = 188 + (repIdx >= 4 ? 4 : 0); // cadence shift in later reps
        break;
      }
      case 'recovery': {
        const inRecovery = ((t - 480) % 420 - 240) / 180; // 0→1 within recovery
        const fatigueFactor = repIdx >= 0 ? repIdx * 1.5 : 0;
        // HR drops but recovery slows in later intervals
        targetHR = lerp(170 + fatigueFactor, 148 + fatigueFactor * 0.5, inRecovery);
        targetPace = lerp(340, 360, inRecovery); // ~5:40→6:00/km
        targetCadence = lerp(178, 170, inRecovery);
        break;
      }
      case 'cooldown': {
        const progress = (t - 3120) / 480;
        targetHR = lerp(148, 118, progress);
        targetPace = lerp(340, 380, progress); // 5:40 → 6:20/km
        targetCadence = lerp(172, 165, progress);
        break;
      }
    }

    // Grade effects on HR and pace
    const gradeSmooth = grade * 0.3 + (points.length > 0 ? points[points.length - 1].grade * 0.7 : 0);
    targetHR += gradeSmooth * 1.5; // uphill → higher HR
    targetPace += gradeSmooth * 3; // uphill → slower pace

    // Smooth HR (cardiac lag)
    const hrLag = phase === 'work' ? 0.03 : 0.015; // faster HR rise during work
    accumulatedHR = accumulatedHR + (targetHR - accumulatedHR) * hrLag;
    const hr = clamp(90, MAX_HR, Math.round(accumulatedHR + noise(t, 2) * 2));

    // Add small per-second noise
    const pace = clamp(180, 420, targetPace + noise(t + 1000, 1) * 5);
    const velocity = 1000 / pace; // m/s
    const cadence = clamp(155, 200, Math.round(targetCadence + noise(t + 2000, 1) * 1.5));

    // Effort intensity: Tier 1 formula (HR / threshold_hr, clamped 0–1)
    const effort = clamp(0, 1, hr / THRESHOLD_HR);

    points.push({
      time: t,
      hr,
      pace: Math.round(pace),
      velocity: Math.round(velocity * 100) / 100,
      altitude: Math.round(alt * 10) / 10,
      grade: Math.round(gradeSmooth * 10) / 10,
      cadence,
      effort: Math.round(effort * 1000) / 1000,
    });
  }

  return points;
}

/** Downsample using Largest-Triangle-Three-Buckets (LTTB) */
export function lttbDownsample(data: StreamPoint[], targetCount: number): StreamPoint[] {
  if (data.length <= targetCount) return data;

  const sampled: StreamPoint[] = [data[0]]; // always keep first
  const bucketSize = (data.length - 2) / (targetCount - 2);

  let prevSelected = 0;

  for (let i = 0; i < targetCount - 2; i++) {
    const bucketStart = Math.floor((i + 1) * bucketSize) + 1;
    const bucketEnd = Math.min(Math.floor((i + 2) * bucketSize) + 1, data.length - 1);

    // Average of next bucket (for triangle calculation)
    const nextBucketStart = Math.min(Math.floor((i + 2) * bucketSize) + 1, data.length - 1);
    const nextBucketEnd = Math.min(Math.floor((i + 3) * bucketSize) + 1, data.length - 1);
    let avgX = 0, avgY = 0;
    const nextLen = nextBucketEnd - nextBucketStart + 1;
    for (let j = nextBucketStart; j <= nextBucketEnd; j++) {
      avgX += data[j].time;
      avgY += data[j].effort;
    }
    avgX /= nextLen;
    avgY /= nextLen;

    // Find point in current bucket with max triangle area
    let maxArea = -1;
    let maxIdx = bucketStart;
    const prevX = data[prevSelected].time;
    const prevY = data[prevSelected].effort;

    for (let j = bucketStart; j < bucketEnd; j++) {
      const area = Math.abs(
        (prevX - avgX) * (data[j].effort - prevY) -
        (prevX - data[j].time) * (avgY - prevY)
      );
      if (area > maxArea) {
        maxArea = area;
        maxIdx = j;
      }
    }

    sampled.push(data[maxIdx]);
    prevSelected = maxIdx;
  }

  sampled.push(data[data.length - 1]); // always keep last
  return sampled;
}

/** Map effort intensity (0–1) to HSL color string */
export function effortToColor(effort: number): string {
  // 0.0–0.3: cool blue
  // 0.3–0.6: teal → warm amber
  // 0.6–0.8: amber → orange
  // 0.8–0.95: orange → red
  // 0.95–1.0: deep crimson
  const e = clamp(0, 1, effort);

  let h: number, s: number, l: number;

  if (e <= 0.3) {
    const t = e / 0.3;
    h = lerp(200, 180, t);
    s = lerp(70, 60, t);
    l = lerp(60, 50, t);
  } else if (e <= 0.6) {
    const t = (e - 0.3) / 0.3;
    h = lerp(180, 40, t);
    s = lerp(60, 80, t);
    l = lerp(50, 55, t);
  } else if (e <= 0.8) {
    const t = (e - 0.6) / 0.2;
    h = lerp(40, 20, t);
    s = lerp(80, 90, t);
    l = lerp(55, 50, t);
  } else if (e <= 0.95) {
    const t = (e - 0.8) / 0.15;
    h = lerp(20, 0, t);
    s = lerp(90, 85, t);
    l = lerp(50, 45, t);
  } else {
    const t = (e - 0.95) / 0.05;
    h = lerp(0, 350, t);
    s = lerp(85, 90, t);
    l = lerp(45, 35, t);
  }

  return `hsl(${Math.round(h)}, ${Math.round(s)}%, ${Math.round(l)}%)`;
}

/** Format seconds to MM:SS */
export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/** Format pace (sec/km) to M:SS */
export function formatPace(secPerKm: number): string {
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
