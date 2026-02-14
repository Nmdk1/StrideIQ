/**
 * ADR-064 Spike — Runtime Benchmark Harness
 *
 * Measures:
 * 1. Initial render time (mount → first paint with gradient)
 * 2. Crosshair/tooltip interaction latency (p95 over 100 synthetic mousemoves)
 * 3. Resize latency (p95 over 20 resize cycles)
 * 4. Canvas/SVG synchronization proof (pixel alignment check after resize + DPR)
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface BenchmarkResults {
  initialRenderMs: number;
  tooltipP95Ms: number;
  resizeP95Ms: number;
  syncProof: SyncProofResult;
}

export interface SyncProofResult {
  resizeAligned: boolean;
  dprHandled: boolean;
  canvasLogicalWidth: number;
  svgLogicalWidth: number;
  canvasPhysicalWidth: number;
  expectedPhysicalWidth: number;
  details: string[];
}

/** Compute p95 from sorted array */
function p95(sorted: number[]): number {
  if (sorted.length === 0) return 0;
  const idx = Math.ceil(sorted.length * 0.95) - 1;
  return sorted[Math.min(idx, sorted.length - 1)];
}

export function useBenchmark(containerRef: React.RefObject<HTMLDivElement | null>) {
  const [results, setResults] = useState<BenchmarkResults | null>(null);
  const [running, setRunning] = useState(false);
  const startTimeRef = useRef<number>(0);

  const recordInitialRender = useCallback((renderMs: number) => {
    startTimeRef.current = renderMs;
  }, []);

  const runBenchmark = useCallback(async () => {
    if (!containerRef.current || running) return;
    setRunning(true);

    const initialRenderMs = startTimeRef.current;

    // --- Tooltip/crosshair interaction latency ---
    const tooltipLatencies: number[] = [];
    const chart = containerRef.current.querySelector('.recharts-wrapper');
    if (chart) {
      for (let i = 0; i < 100; i++) {
        const x = 50 + (i / 100) * (chart.clientWidth - 100);
        const y = chart.clientHeight / 2;

        const start = performance.now();
        chart.dispatchEvent(new MouseEvent('mousemove', {
          clientX: chart.getBoundingClientRect().left + x,
          clientY: chart.getBoundingClientRect().top + y,
          bubbles: true,
        }));
        // Wait for one frame to process the event
        await new Promise(r => requestAnimationFrame(r));
        tooltipLatencies.push(performance.now() - start);
      }
    }
    tooltipLatencies.sort((a, b) => a - b);

    // --- Resize latency ---
    const resizeLatencies: number[] = [];
    const container = containerRef.current;
    const originalWidth = container.style.width;

    for (let i = 0; i < 20; i++) {
      const newWidth = 600 + (i % 2 === 0 ? 200 : -200);
      const start = performance.now();
      container.style.width = `${newWidth}px`;
      window.dispatchEvent(new Event('resize'));
      await new Promise(r => requestAnimationFrame(r));
      await new Promise(r => requestAnimationFrame(r)); // wait 2 frames for reflow
      resizeLatencies.push(performance.now() - start);
    }
    container.style.width = originalWidth;
    window.dispatchEvent(new Event('resize'));
    await new Promise(r => requestAnimationFrame(r));
    resizeLatencies.sort((a, b) => a - b);

    // --- Synchronization proof ---
    const canvas = container.querySelector('canvas');
    const svgContainer = container.querySelector('.recharts-responsive-container');
    const syncDetails: string[] = [];
    let resizeAligned = false;
    let dprHandled = false;
    let canvasLogicalWidth = 0;
    let svgLogicalWidth = 0;
    let canvasPhysicalWidth = 0;
    let expectedPhysicalWidth = 0;

    if (canvas && svgContainer) {
      canvasLogicalWidth = parseFloat(canvas.style.width);
      svgLogicalWidth = svgContainer.clientWidth;
      canvasPhysicalWidth = canvas.width;
      const dpr = window.devicePixelRatio || 1;
      expectedPhysicalWidth = Math.round(canvasLogicalWidth * dpr);

      // Check 1: logical widths match (within 2px tolerance for rounding)
      resizeAligned = Math.abs(canvasLogicalWidth - svgLogicalWidth) <= 2;
      syncDetails.push(
        `Canvas logical: ${canvasLogicalWidth}px, SVG logical: ${svgLogicalWidth}px — ` +
        (resizeAligned ? 'ALIGNED' : `MISALIGNED by ${Math.abs(canvasLogicalWidth - svgLogicalWidth)}px`)
      );

      // Check 2: DPR scaling — canvas physical pixels = logical × DPR
      dprHandled = Math.abs(canvasPhysicalWidth - expectedPhysicalWidth) <= 2;
      syncDetails.push(
        `DPR: ${dpr}, Canvas physical: ${canvasPhysicalWidth}px, Expected: ${expectedPhysicalWidth}px — ` +
        (dprHandled ? 'CORRECT' : `MISMATCH`)
      );

      // Check 3: position alignment — canvas top-left matches container top-left
      const canvasRect = canvas.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      const posAligned = Math.abs(canvasRect.left - containerRect.left) <= 1 &&
                         Math.abs(canvasRect.top - containerRect.top) <= 1;
      syncDetails.push(
        `Position offset: (${(canvasRect.left - containerRect.left).toFixed(1)}px, ` +
        `${(canvasRect.top - containerRect.top).toFixed(1)}px) — ` +
        (posAligned ? 'ALIGNED' : 'OFFSET')
      );
    } else {
      syncDetails.push('Canvas or SVG container not found');
    }

    setResults({
      initialRenderMs,
      tooltipP95Ms: p95(tooltipLatencies),
      resizeP95Ms: p95(resizeLatencies),
      syncProof: {
        resizeAligned,
        dprHandled,
        canvasLogicalWidth,
        svgLogicalWidth,
        canvasPhysicalWidth,
        expectedPhysicalWidth,
        details: syncDetails,
      },
    });
    setRunning(false);
  }, [containerRef, running]);

  return { results, runBenchmark, running, recordInitialRender };
}

export function BenchmarkPanel({ results, onRun, running }: {
  results: BenchmarkResults | null;
  onRun: () => void;
  running: boolean;
}) {
  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-200">
          Runtime Benchmark (Option B)
        </h2>
        <button
          onClick={onRun}
          disabled={running}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            running
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-orange-600 hover:bg-orange-500 text-white'
          }`}
        >
          {running ? 'Running...' : 'Run Benchmark'}
        </button>
      </div>

      {!results ? (
        <p className="text-slate-500 text-sm">
          Click &quot;Run Benchmark&quot; to capture runtime metrics.
          Measures initial render, p95 tooltip latency (100 synthetic mousemoves),
          p95 resize latency (20 cycles), and Canvas/SVG synchronization proof.
        </p>
      ) : (
        <div className="space-y-4">
          {/* Timing metrics */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-slate-800 rounded-lg p-3">
              <p className="text-slate-500 text-xs mb-1">Initial Render</p>
              <p className={`font-mono text-lg font-bold ${
                results.initialRenderMs < 200 ? 'text-green-400' :
                results.initialRenderMs < 500 ? 'text-amber-400' : 'text-red-400'
              }`}>
                {results.initialRenderMs.toFixed(0)}ms
              </p>
              <p className="text-slate-600 text-xs mt-1">Target: &lt; 2,000ms mobile</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-3">
              <p className="text-slate-500 text-xs mb-1">Tooltip p95</p>
              <p className={`font-mono text-lg font-bold ${
                results.tooltipP95Ms < 16.7 ? 'text-green-400' :
                results.tooltipP95Ms < 33.3 ? 'text-amber-400' : 'text-red-400'
              }`}>
                {results.tooltipP95Ms.toFixed(1)}ms
              </p>
              <p className="text-slate-600 text-xs mt-1">Target: &lt; 33ms (30fps)</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-3">
              <p className="text-slate-500 text-xs mb-1">Resize p95</p>
              <p className={`font-mono text-lg font-bold ${
                results.resizeP95Ms < 50 ? 'text-green-400' :
                results.resizeP95Ms < 100 ? 'text-amber-400' : 'text-red-400'
              }`}>
                {results.resizeP95Ms.toFixed(1)}ms
              </p>
              <p className="text-slate-600 text-xs mt-1">Target: &lt; 100ms</p>
            </div>
          </div>

          {/* Synchronization proof */}
          <div className="bg-slate-800 rounded-lg p-4">
            <h3 className="text-slate-300 font-medium text-sm mb-2">
              Canvas/SVG Synchronization Proof
            </h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${results.syncProof.resizeAligned ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-slate-400">
                  Resize alignment: {results.syncProof.resizeAligned ? 'PASS' : 'FAIL'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${results.syncProof.dprHandled ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-slate-400">
                  DPR scaling: {results.syncProof.dprHandled ? 'PASS' : 'FAIL'}
                </span>
              </div>
            </div>
            <div className="space-y-1">
              {results.syncProof.details.map((detail, i) => (
                <p key={i} className="text-xs text-slate-500 font-mono">{detail}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
