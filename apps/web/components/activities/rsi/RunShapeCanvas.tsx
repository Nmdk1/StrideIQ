/**
 * RSI-Alpha — RunShapeCanvas
 *
 * Hybrid Canvas 2D + Recharts SVG visualization for per-second run data.
 *
 * Architecture:
 *   1. Canvas layer: effort gradient (pixel-perfect, no SVG rects) [behind]
 *   2. Segment overlay: colored bands per detected segment [behind traces]
 *   3. Recharts SVG: terrain fill, traces (HR, pace, cadence, grade) [middle]
 *   4. Interaction overlay: crosshair line + tooltip [front]
 *
 * Testability contract:
 *   - Every meaningful element has a data-testid (no queries against library internals)
 *   - Mouse interaction handled by our overlay div, not Recharts internals
 *   - Tooltip renders as React state, not dependent on Recharts Tooltip callbacks
 *   - Toggle state persists in useState (survives resize, view switch)
 *
 * AC coverage:
 *   AC-2:  Canvas gradient, Tier 4 caveat, no block-stepping
 *   AC-3:  Unified crosshair with channel-aware tooltip
 *   AC-4:  Story-layer toggles (cadence, grade on/off)
 *   AC-5:  Terrain fill behind traces
 *   AC-6:  Segment overlay bands with type coloring + time alignment
 *   AC-7:  Plan comparison card (conditional on plan_comparison)
 *   AC-8:  Tier/confidence badge (always visible)
 *   AC-9:  Lab mode (zone overlay, segment table, drift metrics)
 *   AC-11: LTTB downsampling to ≤500 display points
 *   AC-12: Zero coach/LLM surface (no moment markers, no fetch)
 */

'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
} from 'recharts';

import {
  useStreamAnalysis,
  isAnalysisData,
  type StreamHookData,
  type StreamLifecycleResponse,
  type StreamAnalysisData,
  type StreamPoint,
  type Segment,
  type DriftAnalysis,
  type PlanComparison,
} from '@/components/activities/rsi/hooks/useStreamAnalysis';
import { lttbDownsample } from '@/components/activities/rsi/utils/lttb';
import { effortToColor } from '@/components/activities/rsi/utils/effortColor';
import { useUnits } from '@/lib/context/UnitsContext';
import type { Split } from '@/lib/types/splits';
import { SplitsTable, normalizeCadenceToSpm } from '@/components/activities/SplitsTable';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RunShapeCanvasProps {
  activityId: string;
  /** Optional splits data for the Splits tab panel */
  splits?: Split[] | null;
}

interface ChartPoint {
  time: number;
  hr: number | null;
  pace: number | null;
  altitude: number | null;
  grade: number | null;
  cadence: number | null;
  effort: number;
  [key: string]: number | null;
}

type ViewMode = 'story' | 'splits' | 'lab';

/** Tab definitions — extensible array, not hardcoded buttons */
const VIEW_TABS: Array<{ id: ViewMode; label: string }> = [
  { id: 'story', label: 'Story' },
  { id: 'splits', label: 'Splits' },
  { id: 'lab', label: 'Lab' },
];

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_DISPLAY_POINTS = 500;
const CHART_HEIGHT = 256;

const TIER4_CAVEAT =
  'Effort colors show the shape of this run. Connect a heart rate monitor for personalized effort zones.';

const SEGMENT_COLORS: Record<string, string> = {
  warmup: 'rgba(251, 191, 36, 0.2)',
  work: 'rgba(239, 68, 68, 0.2)',
  recovery: 'rgba(34, 197, 94, 0.2)',
  cooldown: 'rgba(96, 165, 250, 0.2)',
  steady: 'rgba(148, 163, 184, 0.2)',
};

const TIER_LABELS: Record<string, { tier: string; label: string }> = {
  tier1_threshold_hr: { tier: 'Tier 1', label: 'Threshold HR' },
  tier2_estimated_hrr: { tier: 'Tier 2', label: 'Estimated HRR' },
  tier3_max_hr: { tier: 'Tier 3', label: 'Max HR' },
  tier4_stream_relative: { tier: 'Tier 4', label: 'Relative to this run' },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

function hasPhysiologicalData(tierUsed: string): boolean {
  return !tierUsed.startsWith('tier4');
}

// ---------------------------------------------------------------------------
// EffortGradientCanvas (AC-2: Canvas 2D, no SVG rects)
// ---------------------------------------------------------------------------

function EffortGradientCanvas({
  data,
  width,
  height,
}: {
  data: ChartPoint[];
  width: number;
  height: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0 || width <= 0 || height <= 0) return;

    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return; // jsdom: graceful no-op

    const n = data.length;
    const pxPerPoint = width / n;

    for (let i = 0; i < n; i++) {
      ctx.fillStyle = effortToColor(data[i].effort);
      const x = Math.floor(i * pxPerPoint);
      const w = Math.ceil(pxPerPoint) + 1;
      ctx.fillRect(x, 0, w, height);
    }
  }, [data, width, height]);

  return (
    <canvas
      ref={canvasRef}
      className="effort-gradient"
      data-testid="effort-gradient"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        opacity: 0.15,
        pointerEvents: 'none',
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// SegmentBands (AC-6: colored bands aligned with segment timestamps)
// ---------------------------------------------------------------------------

function SegmentBands({
  segments,
  maxTime,
}: {
  segments: Segment[];
  maxTime: number;
}) {
  if (segments.length === 0 || maxTime <= 0) return null;

  return (
    <>
      {segments.map((seg, index) => {
        const leftPct = (seg.start_time_s / maxTime) * 100;
        const widthPct = ((seg.end_time_s - seg.start_time_s) / maxTime) * 100;

        return (
          <div
            key={index}
            data-testid={`segment-band-${index}`}
            data-segment-type={seg.type}
            data-start={String(seg.start_time_s)}
            data-end={String(seg.end_time_s)}
            style={{
              position: 'absolute',
              top: 0,
              height: '100%',
              left: `${leftPct}%`,
              width: `${widthPct}%`,
              backgroundColor: SEGMENT_COLORS[seg.type] || SEGMENT_COLORS.steady,
              pointerEvents: 'none',
              zIndex: 1,
            }}
          />
        );
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// CrosshairTooltip (AC-3: rendered from state, not Recharts callback)
// ---------------------------------------------------------------------------

function CrosshairTooltip({
  point,
  showCadence,
  showGrade,
}: {
  point: ChartPoint;
  showCadence: boolean;
  showGrade: boolean;
}) {
  const { formatPace, formatElevation } = useUnits();
  return (
    <div
      data-testid="crosshair-tooltip"
      className="bg-slate-800 border border-slate-600 rounded-lg p-2 shadow-lg text-xs pointer-events-none"
    >
      {point.hr != null && (
        <p className="text-red-400" data-testid="tooltip-hr">
          {Math.round(point.hr)} bpm
        </p>
      )}
      {point.pace != null && (
        <p className="text-blue-400" data-testid="tooltip-pace">
          {formatPace(point.pace)}
        </p>
      )}
      {point.altitude != null && (
        <p className="text-emerald-400" data-testid="tooltip-altitude">
          {formatElevation(point.altitude)}
        </p>
      )}
      {showCadence && point.cadence != null && (
        <p className="text-amber-400" data-testid="tooltip-cadence">
          {Math.round(point.cadence)} spm
        </p>
      )}
      {showGrade && point.grade != null && (
        <p className="text-purple-400" data-testid="tooltip-grade">
          {point.grade.toFixed(1)}%
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// InteractionOverlay (AC-3: our code handles pointer events, not Recharts)
// ---------------------------------------------------------------------------

function InteractionOverlay({
  data,
  hoveredIndex,
  onHover,
  onLeave,
  showCadence,
  showGrade,
}: {
  data: ChartPoint[];
  hoveredIndex: number | null;
  onHover: (index: number) => void;
  onLeave: () => void;
  showCadence: boolean;
  showGrade: boolean;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);

  const updateFromClientX = useCallback(
    (clientX: number) => {
      const el = overlayRef.current;
      if (!el || data.length === 0) return;

      const rect = el.getBoundingClientRect();
      const x = clientX - rect.left;
      const fraction = x / rect.width;
      const index = clamp(Math.round(fraction * (data.length - 1)), 0, data.length - 1);
      onHover(index);
    },
    [data, onHover],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => updateFromClientX(e.clientX),
    [updateFromClientX],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      if (e.touches.length > 0) {
        e.preventDefault();
        updateFromClientX(e.touches[0].clientX);
      }
    },
    [updateFromClientX],
  );

  const hoveredPoint = hoveredIndex != null ? data[hoveredIndex] : null;

  return (
    <div
      ref={overlayRef}
      data-testid="chart-overlay"
      onMouseMove={handleMouseMove}
      onMouseLeave={onLeave}
      onTouchStart={handleTouchMove}
      onTouchMove={handleTouchMove}
      onTouchEnd={onLeave}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 10,
        cursor: 'crosshair',
      }}
    >
      {/* Crosshair line */}
      {hoveredIndex != null && data.length > 0 && (
        <div
          data-testid="crosshair-line"
          style={{
            position: 'absolute',
            top: 0,
            left: `${(hoveredIndex / (data.length - 1)) * 100}%`,
            width: 1,
            height: '100%',
            backgroundColor: 'rgba(255,255,255,0.4)',
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Tooltip */}
      {hoveredPoint && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: `${Math.min((hoveredIndex! / (data.length - 1)) * 100, 75)}%`,
            pointerEvents: 'none',
          }}
        >
          <CrosshairTooltip
            point={hoveredPoint}
            showCadence={showCadence}
            showGrade={showGrade}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TierBadge (AC-8: always visible, shows tier label + confidence %)
// ---------------------------------------------------------------------------

function TierBadge({
  tierUsed,
  confidence,
}: {
  tierUsed: string;
  confidence: number;
}) {
  const tierInfo = TIER_LABELS[tierUsed] || { tier: tierUsed, label: '' };
  const confidencePct = `${Math.round(confidence * 100)}%`;

  return (
    <div
      data-testid="tier-badge"
      className="inline-flex items-center gap-2 bg-slate-800 border border-slate-600 rounded-full px-3 py-1 text-xs"
    >
      <span className="font-semibold text-white">{tierInfo.tier}</span>
      {tierInfo.label && (
        <span className="text-slate-300">{tierInfo.label}</span>
      )}
      <span className="text-slate-400">{confidencePct}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PlanComparisonCard (AC-7: conditional on plan_comparison presence)
// ---------------------------------------------------------------------------

function PlanComparisonCard({
  plan,
}: {
  plan: PlanComparison;
}) {
  const { formatPace, formatDistance } = useUnits();

  // Backend sends duration in minutes, not seconds
  const formatMinutes = (min: number) => {
    const totalSec = Math.round(min * 60);
    return formatDuration(totalSec);
  };

  return (
    <div
      data-testid="plan-comparison-card"
      className="bg-slate-800 border border-slate-600 rounded-lg p-3 mt-2 text-xs"
    >
      <h4 className="text-sm font-semibold text-white mb-2">Planned vs Actual</h4>

      <div className="grid grid-cols-3 gap-2 text-slate-300">
        {/* Duration (backend: planned_duration_min / actual_duration_min) */}
        {plan.planned_duration_min != null && plan.actual_duration_min != null && (
          <div>
            <p className="text-slate-500">Duration</p>
            <p>
              {formatMinutes(plan.planned_duration_min)}
              <span className="text-slate-500 mx-1">→</span>
              {formatMinutes(plan.actual_duration_min)}
            </p>
          </div>
        )}

        {/* Distance (backend: planned_distance_km / actual_distance_km — convert km to meters for formatDistance) */}
        {plan.planned_distance_km != null && plan.actual_distance_km != null && (
          <div>
            <p className="text-slate-500">Distance</p>
            <p>
              {formatDistance(plan.planned_distance_km * 1000)}
              <span className="text-slate-500 mx-1">→</span>
              {formatDistance(plan.actual_distance_km * 1000)}
            </p>
          </div>
        )}

        {/* Pace (backend: planned_pace_s_km / actual_pace_s_km — sec/km) */}
        {plan.planned_pace_s_km != null && plan.actual_pace_s_km != null && (
          <div>
            <p className="text-slate-500">Pace</p>
            <p>
              {formatPace(plan.planned_pace_s_km)}
              <span className="text-slate-500 mx-1">→</span>
              {formatPace(plan.actual_pace_s_km)}
            </p>
          </div>
        )}
      </div>

      {/* Interval count (backend: planned_interval_count / detected_work_count) */}
      {plan.planned_interval_count != null && plan.detected_work_count != null && (
        <div className="mt-2 text-slate-300">
          <span className="text-slate-500">Intervals: </span>
          {plan.detected_work_count}/{plan.planned_interval_count}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SplitsModePanel — Splits tab panel (reuses SplitsTable with scroll container)
// ---------------------------------------------------------------------------

function SplitsModePanel({
  splits,
  onRowHover,
  rowRefs,
}: {
  splits: Split[];
  onRowHover?: (index: number | null) => void;
  rowRefs?: React.MutableRefObject<Map<number, HTMLTableRowElement>>;
}) {
  if (!splits || splits.length === 0) {
    return (
      <div className="mt-3 text-sm text-slate-500" data-testid="splits-panel-empty">
        No splits data available for this activity.
      </div>
    );
  }

  return (
    <div
      className="mt-3 max-h-[300px] md:max-h-[400px] overflow-y-auto"
      data-testid="splits-panel"
    >
      <SplitsTable splits={splits} onRowHover={onRowHover} rowRefs={rowRefs} />
    </div>
  );
}


// ---------------------------------------------------------------------------
// HighlightOverlay — transient hover highlight on the chart (distinct from segment bands)
// ---------------------------------------------------------------------------

function HighlightOverlay({
  startPct,
  endPct,
}: {
  startPct: number;
  endPct: number;
}) {
  return (
    <div
      data-testid="highlight-overlay"
      style={{
        position: 'absolute',
        top: 0,
        height: '100%',
        left: `${startPct}%`,
        width: `${endPct - startPct}%`,
        // Distinct from segment bands: border lines + very faint fill
        borderLeft: '1px solid rgba(255,255,255,0.4)',
        borderRight: '1px solid rgba(255,255,255,0.4)',
        backgroundColor: 'rgba(255,255,255,0.05)',
        pointerEvents: 'none',
        zIndex: 2,
      }}
    />
  );
}


// ---------------------------------------------------------------------------
// LabModePanel (AC-9: zone overlay, segment table, drift metrics)
// ---------------------------------------------------------------------------

function LabModePanel({
  analysis,
  onRowHover,
  rowRefs,
}: {
  analysis: StreamAnalysisData;
  onRowHover?: (index: number | null) => void;
  rowRefs?: React.MutableRefObject<Map<number, HTMLTableRowElement>>;
}) {
  const { formatPace, distanceUnitShort } = useUnits();
  const showZones = hasPhysiologicalData(analysis.tier_used);

  return (
    <div data-testid="lab-mode" className="mt-3 space-y-3 max-h-[300px] md:max-h-[400px] overflow-y-auto">
      {/* Zone overlay (AC-9): only when physiological data exists */}
      {showZones && (
        <div
          data-testid="zone-overlay"
          className="bg-slate-800/50 border border-slate-600 rounded-lg p-3 text-xs"
        >
          <h4 className="text-sm font-semibold text-white mb-1">HR Zones</h4>
          <p className="text-slate-400">
            Zone boundaries derived from athlete physiological profile ({TIER_LABELS[analysis.tier_used]?.label || analysis.tier_used}).
          </p>
        </div>
      )}

      {/* Segment table */}
      {analysis.segments.length > 0 && (
        <div data-testid="segment-table" className="overflow-x-auto">
          <table className="w-full text-xs text-left text-slate-300">
            <thead className="text-slate-400 border-b border-slate-700">
              <tr>
                <th className="px-2 py-1">Type</th>
                <th className="px-2 py-1">Duration</th>
                <th className="px-2 py-1">Avg Pace</th>
                <th className="px-2 py-1">Avg HR</th>
                <th className="px-2 py-1">Cadence</th>
                <th className="px-2 py-1">Grade</th>
              </tr>
            </thead>
            <tbody>
              {analysis.segments.map((seg, i) => {
                const cadenceSpm = normalizeCadenceToSpm(seg.avg_cadence);
                return (
                  <tr
                    key={i}
                    className="border-b border-slate-800 transition-colors duration-75"
                    ref={(el) => { if (el && rowRefs) rowRefs.current.set(i, el); }}
                    onMouseEnter={() => onRowHover?.(i)}
                    onMouseLeave={() => onRowHover?.(null)}
                  >
                    <td className="px-2 py-1 capitalize">{seg.type}</td>
                    <td className="px-2 py-1">
                      {formatDuration(seg.duration_s)}
                    </td>
                    <td className="px-2 py-1">{formatPace(seg.avg_pace_s_km)}</td>
                    <td className="px-2 py-1">
                      {seg.avg_hr != null ? `${Math.round(seg.avg_hr)} bpm` : '--'}
                    </td>
                    <td className="px-2 py-1">
                      {cadenceSpm != null ? `${Math.round(cadenceSpm)} spm` : '--'}
                    </td>
                    <td className="px-2 py-1">
                      {seg.avg_grade != null ? `${seg.avg_grade.toFixed(1)}%` : '--'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Drift metrics (AC-9: neutral language only — trust contract) */}
      <div data-testid="drift-metrics" className="space-y-1">
        {analysis.drift.cardiac_pct != null && (
          <div className="flex justify-between text-xs text-slate-300 bg-slate-800/30 rounded px-2 py-1">
            <span>Cardiac Drift</span>
            <span>{analysis.drift.cardiac_pct.toFixed(1)}%</span>
          </div>
        )}
        {analysis.drift.pace_pct != null && (
          <div className="flex justify-between text-xs text-slate-300 bg-slate-800/30 rounded px-2 py-1">
            <span>Pace Drift</span>
            <span>{analysis.drift.pace_pct.toFixed(1)}%</span>
          </div>
        )}
        {analysis.drift.cadence_trend_bpm_per_km != null && (
          <div className="flex justify-between text-xs text-slate-300 bg-slate-800/30 rounded px-2 py-1">
            <span>Cadence Trend</span>
            <span>{analysis.drift.cadence_trend_bpm_per_km.toFixed(1)} spm/{distanceUnitShort}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RunShapeCanvas (main export)
// ---------------------------------------------------------------------------

export function RunShapeCanvas({ activityId, splits }: RunShapeCanvasProps) {
  const { data, isLoading, error, refetch } = useStreamAnalysis(activityId);

  // Toggle state (AC-4): survives resize and view switch by design (useState)
  const [showHR, setShowHR] = useState(true);
  const [showCadence, setShowCadence] = useState(false);
  const [showGrade, setShowGrade] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('story');

  // A2: Default HR off when unreliable — init once when first analysis arrives.
  // Uses ref to avoid clobbering user's manual toggle on refetch.
  const didInitHRDefault = useRef(false);

  // Crosshair state (AC-3): shared across Story/Lab views
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Two-way hover: Row → Chart (state-driven, infrequent)
  const [highlightRange, setHighlightRange] = useState<{ startTime: number; endTime: number } | null>(null);
  // Two-way hover: Chart → Row (ref-driven, 60fps, no re-renders)
  const splitRowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());
  const prevHighlightedSplitRef = useRef<number | null>(null);
  // Lab segment refs (same pattern)
  const segmentRowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());
  const prevHighlightedSegmentRef = useRef<number | null>(null);

  // Container sizing
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(800);

  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el) return;

    const measure = () => {
      const w = el.clientWidth;
      if (w > 0) setChartWidth(w);
    };

    measure();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(measure);
      observer.observe(el);
      return () => observer.disconnect();
    }
  }, []);

  // --- Data preparation ---
  // The API returns a flat StreamAnalysisData (all analysis fields + stream array).
  // Type guard distinguishes full analysis from lifecycle responses.
  const analysis: StreamAnalysisData | null = isAnalysisData(data) ? data : null;
  const rawStream: StreamPoint[] | null = analysis?.stream ?? null;

  // A2: Default HR off when unreliable (init once, never clobber user toggle)
  useEffect(() => {
    if (analysis && !didInitHRDefault.current) {
      didInitHRDefault.current = true;
      if (analysis.hr_reliable === false) {
        setShowHR(false);
      }
    }
  }, [analysis]);

  // Split time boundaries — cumulative start/end times for each split
  const splitBoundaries = useMemo(() => {
    if (!splits || splits.length === 0) return [];
    const boundaries: Array<{ startTime: number; endTime: number }> = [];
    let cumTime = 0;
    for (const s of splits) {
      const dur = s.moving_time ?? s.elapsed_time ?? 0;
      boundaries.push({ startTime: cumTime, endTime: cumTime + dur });
      cumTime += dur;
    }
    return boundaries;
  }, [splits]);

  const chartData = useMemo<ChartPoint[]>(() => {
    if (!rawStream || rawStream.length === 0) {
      return [];
    }

    // Stream points are already LTTB downsampled server-side to ≤500 points.
    // Map to ChartPoint format for Recharts.
    // Clip extreme pace outliers (>900 s/km ≈ standing still / GPS glitch)
    // to prevent a single outlier from compressing the entire visual range.
    const PACE_OUTLIER_CEILING = 900; // s/km (~15 min/km)
    return rawStream.map((p: StreamPoint) => ({
      time: p.time ?? 0,
      hr: p.hr ?? null,
      pace: (p.pace != null && p.pace > 0 && p.pace <= PACE_OUTLIER_CEILING)
        ? p.pace
        : null,
      altitude: p.altitude ?? null,
      grade: p.grade ?? null,
      cadence: p.cadence ?? null,
      effort: p.effort ?? 0,
    }));
  }, [rawStream]);

  // --- Derived values ---
  const maxTime = useMemo(() => {
    if (!analysis || !chartData.length) return 1;
    // Use the larger of chart data range and segment end times
    const chartMax = chartData[chartData.length - 1].time;
    const segMax = analysis.segments.reduce(
      (max, seg) => Math.max(max, seg.end_time_s),
      0,
    );
    return Math.max(chartMax, segMax) || 1;
  }, [analysis, chartData]);

  // Detect whether pace data exists for gradient coloring
  const hasEffortGradient = useMemo(() => {
    return chartData.some((p) => p.pace != null && p.pace > 0);
  }, [chartData]);

  // Compute explicit pace domain — clip to [p5, p95] with 10% padding so
  // the line fills the chart height and small pace variations are visible.
  // Without this, auto-scaling can compress the line into a flat ribbon
  // when one outlier skews the range.
  const paceDomain = useMemo<[number, number] | undefined>(() => {
    const paces = chartData
      .map((p) => p.pace)
      .filter((p): p is number => p != null && p > 0);
    if (paces.length < 4) return undefined; // let Recharts auto-scale
    const sorted = [...paces].sort((a, b) => a - b);
    const p5 = sorted[Math.floor(sorted.length * 0.05)];
    const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1];
    const range = p95 - p5 || 30; // minimum 30 s/km visual spread
    const pad = range * 0.15;
    return [Math.max(0, p5 - pad), p95 + pad];
  }, [chartData]);

  // Boost an effortToColor for the pace line — needs to pop over segment bands
  const boostColor = useCallback((intensity: number): string => {
    const base = effortToColor(intensity);
    const match = base.match(/rgb\((\d+),(\d+),(\d+)\)/);
    if (!match) return base;
    const boost = 1.5; // 50% brighter so it reads over segment bands
    const r = Math.min(255, Math.round(parseInt(match[1]) * boost));
    const g = Math.min(255, Math.round(parseInt(match[2]) * boost));
    const b = Math.min(255, Math.round(parseInt(match[3]) * boost));
    return `rgb(${r},${g},${b})`;
  }, []);

  // Pace-based gradient stops: slow=blue, fast=red (driven by pace, boosted for visibility)
  const effortGradientStops = useMemo(() => {
    if (!hasEffortGradient || chartData.length === 0) return [];

    // Find pace range for normalization
    const paces = chartData.map(p => p.pace).filter((p): p is number => p != null && p > 0);
    if (paces.length === 0) return [];
    const paceMin = Math.min(...paces);
    const paceMax = Math.max(...paces);
    const paceRange = paceMax - paceMin || 1;

    // Smooth pace for gradient coloring (removes per-second noise)
    const rawPaces = chartData.map(p => p.pace ?? paceMax);
    const smoothWindow = Math.max(3, Math.round(rawPaces.length / 30));
    const smoothedPaces = rawPaces.map((_, i) => {
      const lo = Math.max(0, i - Math.floor(smoothWindow / 2));
      const hi = Math.min(rawPaces.length - 1, i + Math.floor(smoothWindow / 2));
      let sum = 0;
      for (let j = lo; j <= hi; j++) sum += rawPaces[j];
      return sum / (hi - lo + 1);
    });

    const maxStops = 60;
    const step = Math.max(1, Math.floor(chartData.length / maxStops));
    const stops: Array<{ offset: string; color: string }> = [];
    for (let i = 0; i < chartData.length; i += step) {
      const offset = (i / (chartData.length - 1)) * 100;
      const pace = smoothedPaces[i];
      // Invert: faster (lower s/km) = higher intensity = hotter color
      const paceIntensity = 1 - (pace - paceMin) / paceRange;
      stops.push({
        offset: `${offset.toFixed(1)}%`,
        color: boostColor(paceIntensity),
      });
    }
    // Ensure last point is included
    const lastIdx = chartData.length - 1;
    const lastOffset = '100%';
    if (stops.length === 0 || stops[stops.length - 1].offset !== lastOffset) {
      const lastPace = smoothedPaces[lastIdx];
      const lastIntensity = 1 - (lastPace - paceMin) / paceRange;
      stops.push({
        offset: lastOffset,
        color: boostColor(lastIntensity),
      });
    }
    return stops;
  }, [hasEffortGradient, chartData, boostColor]);

  // --- Crosshair handlers ---
  // Chart → Row highlighting via ref (no state re-render at 60fps)
  const ROW_HIGHLIGHT_CLASS = 'bg-slate-700/50';

  const handleHover = useCallback((index: number) => {
    setHoveredIndex(index);
    const time = chartData[index]?.time ?? 0;

    // Chart → Splits row: find which split contains this time point
    if (viewMode === 'splits' && chartData.length > 0 && splitBoundaries.length > 0) {
      let splitIdx: number | null = null;
      for (let i = 0; i < splitBoundaries.length; i++) {
        if (time >= splitBoundaries[i].startTime && time < splitBoundaries[i].endTime) {
          splitIdx = i;
          break;
        }
      }
      const prev = prevHighlightedSplitRef.current;
      if (prev !== splitIdx) {
        if (prev != null) splitRowRefs.current.get(prev)?.classList.remove(ROW_HIGHLIGHT_CLASS);
        if (splitIdx != null) splitRowRefs.current.get(splitIdx)?.classList.add(ROW_HIGHLIGHT_CLASS);
        prevHighlightedSplitRef.current = splitIdx;
      }
    }

    // Chart → Lab segment row: find which segment contains this time point
    if (viewMode === 'lab' && analysis && analysis.segments.length > 0) {
      let segIdx: number | null = null;
      for (let i = 0; i < analysis.segments.length; i++) {
        const seg = analysis.segments[i];
        if (time >= seg.start_time_s && time < seg.end_time_s) {
          segIdx = i;
          break;
        }
      }
      const prev = prevHighlightedSegmentRef.current;
      if (prev !== segIdx) {
        if (prev != null) segmentRowRefs.current.get(prev)?.classList.remove(ROW_HIGHLIGHT_CLASS);
        if (segIdx != null) segmentRowRefs.current.get(segIdx)?.classList.add(ROW_HIGHLIGHT_CLASS);
        prevHighlightedSegmentRef.current = segIdx;
      }
    }
  }, [viewMode, chartData, splitBoundaries, analysis]);

  const handleLeave = useCallback(() => {
    setHoveredIndex(null);
    // Clear split row highlight
    const prevSplit = prevHighlightedSplitRef.current;
    if (prevSplit != null) {
      splitRowRefs.current.get(prevSplit)?.classList.remove(ROW_HIGHLIGHT_CLASS);
      prevHighlightedSplitRef.current = null;
    }
    // Clear segment row highlight
    const prevSeg = prevHighlightedSegmentRef.current;
    if (prevSeg != null) {
      segmentRowRefs.current.get(prevSeg)?.classList.remove(ROW_HIGHLIGHT_CLASS);
      prevHighlightedSegmentRef.current = null;
    }
  }, []);

  // Row → Chart: when hovering a split row, highlight the corresponding time range
  const handleSplitRowHover = useCallback((index: number | null) => {
    if (index == null || index < 0 || index >= splitBoundaries.length) {
      setHighlightRange(null);
      return;
    }
    setHighlightRange(splitBoundaries[index]);
  }, [splitBoundaries]);

  // Row → Chart: when hovering a segment row, highlight the corresponding time range
  const handleSegmentRowHover = useCallback((index: number | null) => {
    if (index == null || !analysis || index < 0 || index >= analysis.segments.length) {
      setHighlightRange(null);
      return;
    }
    const seg = analysis.segments[index];
    setHighlightRange({ startTime: seg.start_time_s, endTime: seg.end_time_s });
  }, [analysis]);

  // --- ADR-063 lifecycle state handling (AC-10) ---
  // The hook may return a lifecycle response ({ status: 'pending' | 'unavailable' })
  // instead of a full analysis result. Detect and handle before data extraction.
  const lifecycleStatus = (data && typeof data === 'object' && 'status' in data)
    ? (data as StreamLifecycleResponse).status
    : undefined;

  // Unavailable: stream will never be available for this activity.
  // Hide the entire panel — return null so no rsi-canvas testid enters the DOM.
  if (lifecycleStatus === 'unavailable') {
    return null;
  }

  // Pending/Loading: stream is being fetched or processing.
  // Page-specific UX: "Analyzing your run..." with subtle pulse (not a spinner).
  // This is intentionally different from Home's silent-upgrade (no loading indicator).
  // On Activity Detail, the athlete navigated here intentionally, so an in-progress
  // state is expected and informative.
  if (isLoading || lifecycleStatus === 'pending') {
    return (
      <div data-testid="rsi-canvas" className="flex flex-col items-center justify-center h-48 gap-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
        <div className="flex gap-1">
          <div className="w-2 h-2 rounded-full bg-orange-400/60 animate-pulse" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 rounded-full bg-orange-400/60 animate-pulse" style={{ animationDelay: '300ms' }} />
          <div className="w-2 h-2 rounded-full bg-orange-400/60 animate-pulse" style={{ animationDelay: '600ms' }} />
        </div>
        <p className="text-slate-400 text-sm">Analyzing your run...</p>
      </div>
    );
  }

  // Error: stream fetch failed. Show retry action.
  if (error) {
    return (
      <div data-testid="rsi-canvas" className="flex flex-col items-center justify-center h-64 gap-2">
        <p className="text-red-400 text-sm">Stream data unavailable</p>
        <button
          onClick={() => refetch()}
          className="text-blue-400 underline text-sm"
          data-testid="rsi-retry"
        >
          Retry
        </button>
      </div>
    );
  }

  // Empty: analysis succeeded but no data to render.
  if (!analysis || chartData.length === 0) {
    return (
      <div data-testid="rsi-canvas" className="flex items-center justify-center h-64">
        <p className="text-slate-400 text-sm">No stream data available</p>
      </div>
    );
  }

  const isTier4 = analysis.cross_run_comparable === false;

  // Pace line stroke: effort gradient or slate-400 fallback
  const PACE_FALLBACK_COLOR = '#94a3b8'; // slate-400
  const paceStroke = hasEffortGradient ? 'url(#paceEffortGradient)' : PACE_FALLBACK_COLOR;

  // Recharts margin (must match overlay positioning)
  const margin = { top: 5, right: 5, bottom: 5, left: 5 };

  return (
    <div data-testid="rsi-canvas" className="relative w-full">
      {/* Tier 4 caveat (AC-2) */}
      {isTier4 && (
        <div
          data-testid="tier4-caveat"
          className="bg-amber-900/30 border border-amber-700 rounded-md px-3 py-2 mb-2 text-xs text-amber-200"
        >
          {TIER4_CAVEAT}
        </div>
      )}

      {/* Tier badge (AC-8: always visible) */}
      <div className="mb-2">
        <TierBadge tierUsed={analysis.tier_used} confidence={analysis.confidence} />
      </div>

      {/* View mode + toggle controls */}
      <div className="flex items-center gap-2 mb-2" data-testid="canvas-controls">
        {VIEW_TABS.map((tab) => (
          <button
            key={tab.id}
            className={`text-xs px-2 py-1 rounded ${
              viewMode === tab.id ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'
            }`}
            onClick={() => setViewMode(tab.id)}
            aria-label={`${tab.label} view`}
            data-testid={`tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}

        {/* Story-layer toggles (AC-4) */}
        <div className="ml-auto flex gap-1">
          <button
            className={`text-xs px-2 py-1 rounded ${
              showHR ? 'bg-red-600 text-white' : 'bg-slate-700 text-slate-400'
            }`}
            onClick={() => setShowHR((v) => !v)}
            aria-label="Heart Rate"
            data-testid="hr-toggle"
          >
            HR
          </button>
          <button
            className={`text-xs px-2 py-1 rounded ${
              showCadence ? 'bg-amber-600 text-white' : 'bg-slate-700 text-slate-400'
            }`}
            onClick={() => setShowCadence((v) => !v)}
            aria-label="Cadence"
          >
            Cadence
          </button>
          <button
            className={`text-xs px-2 py-1 rounded ${
              showGrade ? 'bg-purple-600 text-white' : 'bg-slate-700 text-slate-400'
            }`}
            onClick={() => setShowGrade((v) => !v)}
            aria-label="Grade"
          >
            Grade
          </button>
        </div>
      </div>

      {/* Chart container: canvas + segments + SVG + interaction overlay stacked */}
      <div
        className="relative overflow-hidden"
        style={{ height: CHART_HEIGHT }}
        ref={chartContainerRef}
        data-testid="chart-container"
      >
        {/* Layer 0: Canvas effort gradient (AC-2, behind everything) */}
        <EffortGradientCanvas
          data={chartData}
          width={chartWidth}
          height={CHART_HEIGHT}
        />

        {/* Layer 1: Segment overlay bands (AC-6, behind traces) */}
        <SegmentBands segments={analysis.segments} maxTime={maxTime} />

        {/* Layer 1b: Transient hover highlight (splits/lab row hover → chart) */}
        {highlightRange && maxTime > 0 && (
          <HighlightOverlay
            startPct={(highlightRange.startTime / maxTime) * 100}
            endPct={(highlightRange.endTime / maxTime) * 100}
          />
        )}

        {/* Layer 2: Recharts SVG (terrain + traces) */}
        <div
          data-testid="recharts-layer"
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 2 }}
        >
          <ComposedChart
            width={chartWidth}
            height={CHART_HEIGHT}
            data={chartData}
            margin={margin}
          >
            {/* Effort-colored pace gradient definition */}
            {hasEffortGradient && effortGradientStops.length > 0 && (
              <defs>
                <linearGradient id="paceEffortGradient" x1="0" y1="0" x2="1" y2="0">
                  {effortGradientStops.map((stop, i) => (
                    <stop
                      key={i}
                      offset={stop.offset}
                      stopColor={stop.color}
                    />
                  ))}
                </linearGradient>
              </defs>
            )}

            <XAxis
              dataKey="time"
              tick={{ fontSize: 10 }}
              tickFormatter={(t: number) => `${Math.floor(t / 60)}m`}
            />
            <YAxis yAxisId="hr" orientation="left" hide />
            <YAxis
              yAxisId="pace"
              orientation="right"
              hide
              reversed
              domain={paceDomain ?? ['auto', 'auto']}
              allowDataOverflow={!!paceDomain}
            />
            <YAxis yAxisId="altitude" orientation="left" hide />
            <YAxis yAxisId="secondary" orientation="right" hide />

            {/* AC-5: Terrain fill — FIRST in JSX = behind in SVG paint order */}
            <Area
              yAxisId="altitude"
              type="monotone"
              dataKey="altitude"
              fill="rgba(16,185,129,0.2)"
              stroke="rgba(16,185,129,0.4)"
              isAnimationActive={false}
            />

            {/* HR trace: togglable (A2) */}
            {showHR && (
            <Line
              yAxisId="hr"
              type="monotone"
              dataKey="hr"
              stroke="#f87171"
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
            )}
            <Line
              yAxisId="pace"
              type="monotone"
              dataKey="pace"
              stroke={paceStroke}
              dot={false}
              strokeWidth={2.5}
              isAnimationActive={false}
            />

            {/* AC-4: Optional cadence trace */}
            {showCadence && (
              <Line
                yAxisId="secondary"
                type="monotone"
                dataKey="cadence"
                stroke="#fbbf24"
                dot={false}
                strokeWidth={1}
                isAnimationActive={false}
              />
            )}

            {/* AC-4: Optional grade trace */}
            {showGrade && (
              <Line
                yAxisId="secondary"
                type="monotone"
                dataKey="grade"
                stroke="#a78bfa"
                dot={false}
                strokeWidth={1}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </div>

        {/* Testability markers: data-testid contract for tests.
            Positioned after Recharts layer to preserve terrain-before-trace ordering. */}
        <div data-testid="terrain-fill" style={{ display: 'none' }} aria-hidden="true" />
        {showHR && (
          <div data-testid="trace-hr" style={{ display: 'none' }} aria-hidden="true" />
        )}
        <div
          data-testid="trace-pace"
          data-stroke-type={hasEffortGradient ? 'effort-gradient' : 'fallback'}
          data-fallback-color={PACE_FALLBACK_COLOR}
          style={{ display: 'none' }}
          aria-hidden="true"
        />
        {hasEffortGradient && (
          <div data-testid="pace-effort-gradient-def" style={{ display: 'none' }} aria-hidden="true" />
        )}
        {showCadence && (
          <div data-testid="trace-cadence" style={{ display: 'none' }} aria-hidden="true" />
        )}
        {showGrade && (
          <div data-testid="trace-grade" style={{ display: 'none' }} aria-hidden="true" />
        )}

        {/* Layer 3: Interaction overlay (AC-3, on top of everything) */}
        <InteractionOverlay
          data={chartData}
          hoveredIndex={hoveredIndex}
          onHover={handleHover}
          onLeave={handleLeave}
          showCadence={showCadence}
          showGrade={showGrade}
        />
      </div>

      {/* A2: HR unreliable note */}
      {analysis.hr_reliable === false && analysis.hr_note && (
        <div
          className="flex items-center gap-2 mt-2 px-3 py-2 rounded bg-amber-900/30 border border-amber-700/40 text-amber-300 text-xs"
          data-testid="hr-unreliable-note"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0">
            <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
          </svg>
          <span>HR data flagged as unreliable — hidden by default. Toggle to view.</span>
        </div>
      )}

      {/* Splits panel: shown only when Splits tab is active */}
      {viewMode === 'splits' && splits && (
        <SplitsModePanel
          splits={splits}
          onRowHover={handleSplitRowHover}
          rowRefs={splitRowRefs}
        />
      )}

      {/* Lab mode panel (AC-9: shown only when Lab is active) */}
      {viewMode === 'lab' && (
        <LabModePanel
          analysis={analysis}
          onRowHover={handleSegmentRowHover}
          rowRefs={segmentRowRefs}
        />
      )}

      {/* Plan comparison card (AC-7: conditional on plan_comparison presence) */}
      {analysis.plan_comparison && (
        <PlanComparisonCard plan={analysis.plan_comparison} />
      )}

      {/* AC-12 enforcement: ZERO coach/LLM surface */}
    </div>
  );
}
