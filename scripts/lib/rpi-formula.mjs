/**
 * Daniels/Gilbert Running Formula — pure JS implementation.
 *
 * Ported from apps/api/services/rpi_calculator.py.
 * No external dependencies. Fully deterministic — no network calls.
 *
 * Source: Daniels, J. & Gilbert, J. (1979). Oxygen Power.
 * Formulas are published exercise-physiology research (physics-based).
 * NOT a port of the copyrighted lookup tables — only the public equations.
 */

// ============================================================================
// INTENSITY TABLE
// Copied verbatim from rpi_calculator.py :: INTENSITY_TABLE
// Indices: 0=easy_fast, 1=easy_slow(0.55), 2=marathon, 3=threshold,
//          4=interval, 5=repetition
// ============================================================================

const INTENSITY_TABLE = {
  30: [0.656310, 0.55, 0.857530, 0.923901, 1.113017, 1.244426],
  35: [0.694032, 0.55, 0.884464, 0.951698, 1.135265, 1.259791],
  40: [0.694401, 0.55, 0.872771, 0.938283, 1.108994, 1.226613],
  45: [0.689502, 0.55, 0.847517, 0.910706, 1.072698, 1.178602],
  50: [0.676021, 0.55, 0.819635, 0.887196, 1.046102, 1.148391],
  55: [0.669899, 0.55, 0.806541, 0.866426, 1.013673, 1.105520],
  60: [0.660404, 0.55, 0.794224, 0.848246, 0.993932, 1.085095],
  65: [0.658450, 0.55, 0.791007, 0.854612, 0.993399, 1.086487],
  70: [0.659559, 0.55, 0.787847, 0.845433, 0.982708, 1.070224],
};

const INTENSITY_RPIS = Object.keys(INTENSITY_TABLE).map(Number).sort((a, b) => a - b);

// ============================================================================
// CORE FORMULA
// ============================================================================

/**
 * Calculate RPI from a race time and distance.
 * Mirrors: rpi_calculator.py :: calculate_rpi_from_race_time
 *
 * @param {number} distanceMeters
 * @param {number} timeSeconds
 * @returns {number|null} RPI rounded to 1 decimal, or null on invalid input
 */
export function calculateRpi(distanceMeters, timeSeconds) {
  if (distanceMeters <= 0 || timeSeconds <= 0) return null;

  const timeMinutes = timeSeconds / 60;
  const velocity = distanceMeters / timeMinutes; // m/min

  const vo2 = -4.6 + 0.182258 * velocity + 0.000104 * velocity * velocity;

  const pctMax =
    0.8 +
    0.1894393 * Math.exp(-0.012778 * timeMinutes) +
    0.2989558 * Math.exp(-0.1932605 * timeMinutes);

  if (pctMax <= 0) return null;

  return Math.round((vo2 / pctMax) * 10) / 10;
}

/**
 * Internal: calculate RPI for a given distance and time (used by binary search).
 * Mirrors: rpi_calculator.py :: _calculate_rpi_for_time
 */
function calcRpiForTime(distanceMeters, timeSeconds) {
  const velocity = (distanceMeters / timeSeconds) * 60; // m/min
  const timeMinutes = timeSeconds / 60;

  const vo2 = -4.6 + 0.182258 * velocity + 0.000104 * velocity * velocity;

  const pctMax =
    0.8 +
    0.1894393 * Math.exp(-0.012778 * timeMinutes) +
    0.2989558 * Math.exp(-0.1932605 * timeMinutes);

  return pctMax > 0 ? vo2 / pctMax : 0;
}

// ============================================================================
// TRAINING PACES
// ============================================================================

/**
 * Linearly interpolate intensity at a given RPI for a given pace-type index.
 * Mirrors: rpi_calculator.py :: interpolate_intensity
 */
function interpolateIntensity(rpi, idx) {
  if (rpi <= INTENSITY_RPIS[0]) return INTENSITY_TABLE[INTENSITY_RPIS[0]][idx];
  if (rpi >= INTENSITY_RPIS[INTENSITY_RPIS.length - 1])
    return INTENSITY_TABLE[INTENSITY_RPIS[INTENSITY_RPIS.length - 1]][idx];

  for (let i = 0; i < INTENSITY_RPIS.length - 1; i++) {
    const r1 = INTENSITY_RPIS[i];
    const r2 = INTENSITY_RPIS[i + 1];
    if (rpi >= r1 && rpi <= r2) {
      const t = (rpi - r1) / (r2 - r1);
      return INTENSITY_TABLE[r1][idx] + t * (INTENSITY_TABLE[r2][idx] - INTENSITY_TABLE[r1][idx]);
    }
  }

  return INTENSITY_TABLE[50][idx];
}

/**
 * Reverse-solve oxygen cost equation for velocity given a target VO2.
 * Mirrors: rpi_calculator.py :: vo2_to_velocity
 *
 * Equation: VO2 = -4.6 + 0.182258*v + 0.000104*v^2
 * Rearranged: 0.000104*v^2 + 0.182258*v - (4.6 + VO2) = 0
 */
function vo2ToVelocity(targetVo2) {
  const a = 0.000104;
  const b = 0.182258;
  const c = -(4.6 + targetVo2);
  const discriminant = b * b - 4 * a * c;
  if (discriminant < 0) return 200;
  return (-b + Math.sqrt(discriminant)) / (2 * a);
}

/**
 * Calculate training pace in integer seconds/mile from RPI + intensity fraction.
 * Mirrors: rpi_calculator.py :: calculate_pace_from_intensity
 */
function calcPaceFromIntensity(rpi, intensityPct) {
  const targetVo2 = rpi * intensityPct;
  const velocity = vo2ToVelocity(targetVo2); // m/min
  if (velocity <= 0) return 600;
  return Math.round((1609.34 / velocity) * 60); // sec/mile
}

/**
 * Calculate all 5 training paces from RPI.
 * Returns { easy, marathon, threshold, interval, repetition } each with { mi, km, secPerMile }.
 * Mirrors: rpi_calculator.py :: calculate_training_paces
 *
 * @param {number} rpi
 * @returns {{ easy, marathon, threshold, interval, repetition }}
 */
export function calculateTrainingPaces(rpi) {
  const easySec      = calcPaceFromIntensity(rpi, interpolateIntensity(rpi, 0));
  const marathonSec  = calcPaceFromIntensity(rpi, interpolateIntensity(rpi, 2));
  const threshSec    = calcPaceFromIntensity(rpi, interpolateIntensity(rpi, 3));
  const intervalSec  = calcPaceFromIntensity(rpi, interpolateIntensity(rpi, 4));
  const repSec       = calcPaceFromIntensity(rpi, interpolateIntensity(rpi, 5));

  const fmt = (sec) => ({ mi: formatPaceMi(sec), km: formatPaceKm(sec), secPerMile: sec });

  return {
    easy:       fmt(easySec),
    marathon:   fmt(marathonSec),
    threshold:  fmt(threshSec),
    interval:   fmt(intervalSec),
    repetition: fmt(repSec),
  };
}

// ============================================================================
// EQUIVALENCY (binary search)
// ============================================================================

/**
 * Calculate equivalent race time for a target distance given an RPI.
 * Uses binary search to find the time that produces the target RPI for
 * the given distance — same algorithm as rpi_calculator.py :: calculate_equivalent_race_time.
 *
 * @param {number} rpi
 * @param {number} targetDistanceMeters
 * @returns {{ timeSeconds, timeFormatted, paceMi, paceKm } | null}
 */
export function calculateEquivalentRaceTime(rpi, targetDistanceMeters) {
  if (rpi <= 0 || targetDistanceMeters <= 0) return null;

  const distKm = targetDistanceMeters / 1000;
  let minTime = 2.5 * 60 * distKm;  // elite bound
  let maxTime = 12.0 * 60 * distKm; // slow bound

  let timeSeconds = (minTime + maxTime) / 2;
  const tolerance = 0.01;

  for (let i = 0; i < 50; i++) {
    const mid = (minTime + maxTime) / 2;
    const calcRpi = calcRpiForTime(targetDistanceMeters, mid);

    if (Math.abs(calcRpi - rpi) < tolerance) {
      timeSeconds = mid;
      break;
    }

    // Higher RPI = faster time. If calculated > target → need slower (longer) time.
    if (calcRpi > rpi) {
      minTime = mid;
    } else {
      maxTime = mid;
    }
    timeSeconds = mid;
  }

  timeSeconds = Math.round(timeSeconds);
  const paceSecPerMile = (timeSeconds / targetDistanceMeters) * 1609.34;

  return {
    timeSeconds,
    timeFormatted: formatTime(timeSeconds),
    paceMi: formatPaceMi(Math.round(paceSecPerMile)),
    paceKm: formatPaceKm(Math.round(paceSecPerMile)),
  };
}

// ============================================================================
// FORMAT UTILITIES
// ============================================================================

/**
 * Format seconds/mile as "MM:SS".
 * @param {number} paceSecPerMile
 * @returns {string}
 */
export function formatPaceMi(paceSecPerMile) {
  const mins = Math.floor(paceSecPerMile / 60);
  const secs = paceSecPerMile % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

/**
 * Format seconds/mile as "MM:SS" per km.
 * @param {number} paceSecPerMile
 * @returns {string}
 */
export function formatPaceKm(paceSecPerMile) {
  const secPerKm = Math.round(paceSecPerMile / 1.60934);
  const mins = Math.floor(secPerKm / 60);
  const secs = secPerKm % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

/**
 * Format total seconds as "H:MM:SS" or "MM:SS".
 * Mirrors: generate-pseo-data.mjs :: formatTime
 * @param {number} totalSeconds
 * @returns {string}
 */
export function formatTime(totalSeconds) {
  totalSeconds = Math.round(totalSeconds);
  const hours = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hours > 0)
    return `${hours}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}
