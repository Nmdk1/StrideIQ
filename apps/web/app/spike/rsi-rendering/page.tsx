/**
 * ADR-064 Rendering Spike — Comparison Page
 *
 * Side-by-side (or stacked) comparison of:
 * - Option A: Pure Recharts (ReferenceArea gradient)
 * - Option B: Canvas 2D gradient + SVG overlay (Hybrid)
 *
 * Measures: render time, DOM node count, visual fidelity.
 * URL: /spike/rsi-rendering
 */

'use client';

import { useState, useMemo, useCallback, useRef } from 'react';
import { generateIntervalSession, StreamPoint, effortToColor } from './data';
import OptionAChart from './OptionA';
import OptionBChart from './OptionB';
import { useBenchmark, BenchmarkPanel } from './Benchmark';

interface Metrics {
  renderMs: number;
  domNodes: number;
}

function MetricsCard({ label, metrics }: { label: string; metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-slate-300 font-semibold mb-2">{label}</h3>
        <p className="text-slate-500 text-sm">Rendering...</p>
      </div>
    );
  }
  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <h3 className="text-slate-300 font-semibold mb-2">{label}</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-slate-500">Render time</p>
          <p className={`font-mono font-bold ${metrics.renderMs < 100 ? 'text-green-400' : metrics.renderMs < 300 ? 'text-amber-400' : 'text-red-400'}`}>
            {metrics.renderMs.toFixed(0)}ms
          </p>
        </div>
        <div>
          <p className="text-slate-500">DOM nodes</p>
          <p className={`font-mono font-bold ${metrics.domNodes < 500 ? 'text-green-400' : metrics.domNodes < 2000 ? 'text-amber-400' : 'text-red-400'}`}>
            {metrics.domNodes.toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

function ColorScalePreview() {
  const steps = 50;
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="text-slate-500 text-xs">0%</span>
      <div className="flex flex-1 h-4 rounded overflow-hidden">
        {Array.from({ length: steps }, (_, i) => {
          const effort = i / (steps - 1);
          return (
            <div
              key={i}
              className="flex-1"
              style={{ backgroundColor: effortToColor(effort) }}
            />
          );
        })}
      </div>
      <span className="text-slate-500 text-xs">100%</span>
    </div>
  );
}

export default function RsiRenderingSpike() {
  const [metricsA, setMetricsA] = useState<Metrics | null>(null);
  const [metricsB, setMetricsB] = useState<Metrics | null>(null);
  const optionBContainerRef = useRef<HTMLDivElement>(null);

  // Generate data once
  const data = useMemo<StreamPoint[]>(() => generateIntervalSession(), []);

  const handleMetricsA = useCallback((m: Metrics) => setMetricsA(m), []);
  const handleMetricsB = useCallback((m: Metrics) => setMetricsB(m), []);

  // Benchmark harness for Option B runtime evidence
  const { results: benchResults, runBenchmark, running: benchRunning, recordInitialRender } = useBenchmark(optionBContainerRef);

  // Wire initial render time from Option B metrics
  const handleMetricsBWithBench = useCallback((m: Metrics) => {
    setMetricsB(m);
    recordInitialRender(m.renderMs);
  }, [recordInitialRender]);

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6">
      <div className="max-w-[1400px] mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-100 mb-2">
            ADR-064 Rendering Spike
          </h1>
          <p className="text-slate-400">
            Comparing Recharts ReferenceArea (Option A) vs Canvas 2D Hybrid (Option B)
            for the RSI-Alpha effort gradient canvas.
          </p>
          <p className="text-slate-500 text-sm mt-1">
            Data: synthetic 6×800m interval session · {data.length.toLocaleString()} points ·
            Tier 1 effort (HR/threshold_hr)
          </p>
        </div>

        {/* Color scale */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">
            Effort Color Scale
          </h2>
          <ColorScalePreview />
        </div>

        {/* Metrics comparison */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <MetricsCard label="Option A: Recharts ReferenceArea" metrics={metricsA} />
          <MetricsCard label="Option B: Canvas 2D Hybrid" metrics={metricsB} />
        </div>

        {/* Tier 4 Caveat Preview */}
        <div className="mb-8 bg-slate-900 rounded-lg p-4 border border-slate-700">
          <h2 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">
            Tier 4 Caveat Badge Preview
          </h2>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-slate-800 rounded-full px-3 py-1.5 border border-slate-600">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-xs font-medium text-slate-300">Tier 4 · Relative to this run</span>
            </div>
            <p className="text-xs text-slate-500">
              Effort colors show the shape of this run. Connect a heart rate monitor for personalized effort zones.
            </p>
          </div>
          <div className="mt-3 flex items-center gap-4">
            <div className="flex items-center gap-2 bg-slate-800 rounded-full px-3 py-1.5 border border-slate-600">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-xs font-medium text-slate-300">Tier 1 · Threshold HR</span>
            </div>
            <p className="text-xs text-slate-500">
              Confidence: 87% · Cross-run comparable
            </p>
          </div>
        </div>

        {/* Charts */}
        <div className="space-y-8">
          {/* Option A */}
          <div className="bg-slate-900 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-200">
                Option A: Recharts ReferenceArea
              </h2>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">
                SVG-based · Batched color bands
              </span>
            </div>
            <OptionAChart data={data} onMetrics={handleMetricsA} />
          </div>

          {/* Option B */}
          <div ref={optionBContainerRef} className="bg-slate-900 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-200">
                Option B: Canvas 2D Hybrid
              </h2>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">
                Canvas gradient · SVG traces &amp; interaction
              </span>
            </div>
            <OptionBChart data={data} onMetrics={handleMetricsBWithBench} />
          </div>
        </div>

        {/* Runtime Benchmark */}
        <div className="mt-8">
          <BenchmarkPanel results={benchResults} onRun={runBenchmark} running={benchRunning} />
        </div>

        {/* Decision criteria */}
        <div className="mt-8 bg-slate-900 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-slate-200 mb-4">Decision Criteria</h2>
          <div className="grid grid-cols-3 gap-6 text-sm">
            <div>
              <h3 className="text-slate-400 font-medium mb-2">Visual Fidelity</h3>
              <ul className="text-slate-500 space-y-1">
                <li>• Gradient smoothness (blocks vs smooth)</li>
                <li>• Color accuracy at transitions</li>
                <li>• F1-telemetry aesthetic bar</li>
              </ul>
            </div>
            <div>
              <h3 className="text-slate-400 font-medium mb-2">Performance</h3>
              <ul className="text-slate-500 space-y-1">
                <li>• Initial render &lt; 2s (mobile target)</li>
                <li>• Interaction FPS ≥ 30 (mobile)</li>
                <li>• DOM nodes &lt; 2,000</li>
              </ul>
            </div>
            <div>
              <h3 className="text-slate-400 font-medium mb-2">Implementation</h3>
              <ul className="text-slate-500 space-y-1">
                <li>• Crosshair synchronization cost</li>
                <li>• Resize/responsive behavior</li>
                <li>• Accessibility (screen readers)</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
