/**
 * RSI Contract Test — Frontend ↔ Backend Shape Alignment
 *
 * Loads the SHARED contract fixture from contracts/stream_analysis_response.json
 * (single source of truth for both backend and frontend tests).
 *
 * If the backend changes field names, this test MUST break and force a
 * corresponding frontend type update.
 *
 * Canonical source: apps/api/services/run_stream_analysis.py
 */

import * as fs from 'fs';
import * as path from 'path';

import {
  isAnalysisData,
  isLifecycleResponse,
  type StreamAnalysisData,
  type StreamLifecycleResponse,
  type Segment,
  type DriftAnalysis,
  type PlanComparison,
  type Moment,
  type StreamPoint,
} from '@/components/activities/rsi/hooks/useStreamAnalysis';

// ── Load shared contract fixture ──

const CONTRACT_PATH = path.resolve(__dirname, '../../../contracts/stream_analysis_response.json');
const CONTRACT = JSON.parse(fs.readFileSync(CONTRACT_PATH, 'utf-8'));

const REAL_BACKEND_PAYLOAD = CONTRACT.success_response;
const REAL_PLAN_COMPARISON = CONTRACT.success_with_plan_response.plan_comparison;
const REAL_PENDING_RESPONSE = CONTRACT.pending_response;
const REAL_UNAVAILABLE_RESPONSE = CONTRACT.unavailable_response;

// Expected/forbidden key arrays from the shared fixture (readonly to prevent mutation)
const EXPECTED_TOP_LEVEL_KEYS: readonly string[] = CONTRACT.expected_top_level_keys;
const EXPECTED_SEGMENT_KEYS: readonly string[] = CONTRACT.expected_segment_keys;
const EXPECTED_DRIFT_KEYS: readonly string[] = CONTRACT.expected_drift_keys;
const EXPECTED_PLAN_KEYS: readonly string[] = CONTRACT.expected_plan_comparison_keys;
const EXPECTED_MOMENT_KEYS: readonly string[] = CONTRACT.expected_moment_keys;
const EXPECTED_STREAM_POINT_KEYS: readonly string[] = CONTRACT.expected_stream_point_keys;
const FORBIDDEN_OLD_SEGMENT_KEYS: readonly string[] = CONTRACT.forbidden_old_segment_keys;
const FORBIDDEN_OLD_DRIFT_KEYS: readonly string[] = CONTRACT.forbidden_old_drift_keys;
const FORBIDDEN_OLD_PLAN_KEYS: readonly string[] = CONTRACT.forbidden_old_plan_keys;
const FORBIDDEN_OLD_MOMENT_KEYS: readonly string[] = CONTRACT.forbidden_old_moment_keys;

// ── Tests ──

describe('RSI Contract: shared fixture loaded', () => {
  test('contract fixture file exists and loads', () => {
    expect(REAL_BACKEND_PAYLOAD).toBeDefined();
    expect(REAL_BACKEND_PAYLOAD.segments).toBeInstanceOf(Array);
    expect(CONTRACT._version).toBe('2026-02-14');
  });
});

describe('RSI Contract: backend payload → frontend types', () => {
  test('isAnalysisData correctly identifies a full analysis payload', () => {
    expect(isAnalysisData(REAL_BACKEND_PAYLOAD as unknown as StreamAnalysisData)).toBe(true);
  });

  test('isAnalysisData rejects lifecycle responses', () => {
    expect(isAnalysisData(REAL_PENDING_RESPONSE as unknown as StreamLifecycleResponse)).toBe(false);
    expect(isAnalysisData(REAL_UNAVAILABLE_RESPONSE as unknown as StreamLifecycleResponse)).toBe(false);
    expect(isAnalysisData(null)).toBe(false);
  });

  test('isLifecycleResponse identifies pending/unavailable', () => {
    expect(isLifecycleResponse(REAL_PENDING_RESPONSE as unknown as StreamLifecycleResponse)).toBe(true);
    expect(isLifecycleResponse(REAL_UNAVAILABLE_RESPONSE as unknown as StreamLifecycleResponse)).toBe(true);
  });

  test('isLifecycleResponse rejects full analysis payload', () => {
    expect(isLifecycleResponse(REAL_BACKEND_PAYLOAD as unknown as StreamAnalysisData)).toBe(false);
    expect(isLifecycleResponse(null)).toBe(false);
  });
});

describe('RSI Contract: top-level keys', () => {
  test('all expected keys present in response', () => {
    const actual = Object.keys(REAL_BACKEND_PAYLOAD);
    const missing = EXPECTED_TOP_LEVEL_KEYS.filter(k => !actual.includes(k));
    expect(missing).toEqual([]);
  });
});

describe('RSI Contract: Segment fields', () => {
  const seg = REAL_BACKEND_PAYLOAD.segments[0] as unknown as Segment;

  test('has all required fields from shared fixture', () => {
    const actual = Object.keys(seg);
    const missing = EXPECTED_SEGMENT_KEYS.filter(k => !actual.includes(k));
    expect(missing).toEqual([]);
  });

  test('does NOT have forbidden old field names', () => {
    const actual = Object.keys(seg);
    const present = FORBIDDEN_OLD_SEGMENT_KEYS.filter(k => actual.includes(k));
    expect(present).toEqual([]);
  });

  test('values are correct types', () => {
    expect(seg.type).toBe('warmup');
    expect(typeof seg.start_index).toBe('number');
    expect(typeof seg.duration_s).toBe('number');
    expect(typeof seg.avg_pace_s_km).toBe('number');
  });
});

describe('RSI Contract: DriftAnalysis fields', () => {
  const drift = REAL_BACKEND_PAYLOAD.drift as unknown as DriftAnalysis;

  test('has all required fields from shared fixture', () => {
    const actual = Object.keys(drift);
    const missing = EXPECTED_DRIFT_KEYS.filter(k => !actual.includes(k));
    expect(missing).toEqual([]);
  });

  test('does NOT have forbidden old field names', () => {
    const actual = Object.keys(drift);
    const present = FORBIDDEN_OLD_DRIFT_KEYS.filter(k => actual.includes(k));
    expect(present).toEqual([]);
  });

  test('values match expected', () => {
    expect(drift.cardiac_pct).toBe(4.2);
    expect(drift.pace_pct).toBe(1.8);
  });
});

describe('RSI Contract: Moment fields', () => {
  const moment = REAL_BACKEND_PAYLOAD.moments[0] as unknown as Moment;

  test('has all required fields from shared fixture', () => {
    const actual = Object.keys(moment);
    const missing = EXPECTED_MOMENT_KEYS.filter(k => !actual.includes(k));
    expect(missing).toEqual([]);
  });

  test('does NOT have forbidden old field names', () => {
    const actual = Object.keys(moment);
    const present = FORBIDDEN_OLD_MOMENT_KEYS.filter(k => actual.includes(k));
    expect(present).toEqual([]);
  });

  test('values are correct', () => {
    expect(moment.type).toBe('cardiac_drift_onset');
    expect(moment.index).toBe(2400);
    expect(moment.context).toBeNull();
  });
});

describe('RSI Contract: PlanComparison fields', () => {
  const plan = REAL_PLAN_COMPARISON as unknown as PlanComparison;

  test('has all required fields from shared fixture', () => {
    const actual = Object.keys(plan);
    const missing = EXPECTED_PLAN_KEYS.filter(k => !actual.includes(k));
    expect(missing).toEqual([]);
  });

  test('does NOT have forbidden old field names', () => {
    const actual = Object.keys(plan);
    const present = FORBIDDEN_OLD_PLAN_KEYS.filter(k => actual.includes(k));
    expect(present).toEqual([]);
  });

  test('uses minutes/km/s-per-km (not seconds/meters)', () => {
    expect(plan.planned_duration_min).toBe(60.0);
    expect(plan.planned_distance_km).toBe(10.0);
    expect(plan.planned_pace_s_km).toBe(360.0);
    expect(plan.detected_work_count).toBe(5);
  });
});

describe('RSI Contract: StreamPoint fields', () => {
  const pt = REAL_BACKEND_PAYLOAD.stream[0] as unknown as StreamPoint;

  test('has all required fields from shared fixture', () => {
    const actual = Object.keys(pt);
    const missing = EXPECTED_STREAM_POINT_KEYS.filter(k => !actual.includes(k));
    expect(missing).toEqual([]);
  });

  test('values are correct types', () => {
    expect(typeof pt.time).toBe('number');
    expect(typeof pt.hr).toBe('number');
    expect(typeof pt.effort).toBe('number');
  });
});
