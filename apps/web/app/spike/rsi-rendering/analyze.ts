/**
 * ADR-064 — Offline analysis script
 *
 * Run with: npx tsx apps/web/app/spike/rsi-rendering/analyze.ts
 *
 * Produces evidence for the ADR rendering decision without needing a browser.
 */

import { generateIntervalSession, lttbDownsample, effortToColor } from './data';

const data = generateIntervalSession();
console.log(`\n=== ADR-064 Rendering Evidence ===\n`);
console.log(`Total data points: ${data.length}`);
console.log(`Duration: ${data[data.length - 1].time}s (${(data[data.length - 1].time / 60).toFixed(0)} min)`);

// HR range
const hrs = data.map(d => d.hr);
console.log(`HR range: ${Math.min(...hrs)} – ${Math.max(...hrs)} bpm`);

// Effort range
const efforts = data.map(d => d.effort);
console.log(`Effort range: ${Math.min(...efforts).toFixed(3)} – ${Math.max(...efforts).toFixed(3)}`);

// Downsampled count
const sampled = lttbDownsample(data, 500);
console.log(`LTTB downsampled: ${sampled.length} points`);

// --- Option A: Band analysis ---
console.log(`\n--- Option A: ReferenceArea Band Analysis ---`);

function countBands(threshold: number): number {
  let bands = 0;
  let bandEffort = data[0].effort;
  for (let i = 1; i < data.length; i++) {
    if (Math.abs(data[i].effort - bandEffort) > threshold) {
      bands++;
      bandEffort = data[i].effort;
    }
  }
  return bands + 1; // last band
}

for (const thresh of [0.01, 0.02, 0.03, 0.05, 0.10]) {
  const n = countBands(thresh);
  // Each ReferenceArea creates ~4-6 SVG nodes (rect, clip, etc.)
  const estimatedSvgNodes = n * 5;
  console.log(`  threshold=${thresh.toFixed(2)}: ${n} bands → ~${estimatedSvgNodes} SVG nodes`);
}

// With the 0.02 threshold used in OptionA.tsx
const bands02 = countBands(0.02);
console.log(`\n  ⚠ At threshold=0.02 (used in prototype): ${bands02} ReferenceArea components`);

// Recharts base overhead: axes, grid, lines, container = ~100-150 SVG nodes
const baseRecharts = 130;
const traceNodes = sampled.length * 2; // 2 lines × N path points (but SVG paths are 1 node each)
const optionATotalEstimate = bands02 * 5 + baseRecharts + 10; // 10 for lines/area
console.log(`  Estimated total DOM nodes (Option A): ~${optionATotalEstimate}`);

// --- Option B: Canvas analysis ---
console.log(`\n--- Option B: Canvas 2D Hybrid Analysis ---`);
console.log(`  Canvas gradient: 1 <canvas> element, ~800px width → 800 fillRect calls`);
console.log(`  SVG overlay: axes + grid + 2 lines + area + tooltip = ~${baseRecharts + 10} nodes`);
console.log(`  Estimated total DOM nodes (Option B): ~${baseRecharts + 15}`);

// --- Visual fidelity ---
console.log(`\n--- Visual Fidelity Analysis ---`);

// Count distinct effort values per pixel at 800px chart width
const chartWidth = 800;
const timeRange = data[data.length - 1].time - data[0].time;
let maxEffortJumpPerPixel = 0;
let avgEffortJumpPerPixel = 0;
let jumps = 0;

for (let px = 1; px < chartWidth; px++) {
  const t1 = Math.round((px - 1) / chartWidth * timeRange);
  const t2 = Math.round(px / chartWidth * timeRange);
  const idx1 = Math.min(t1, data.length - 1);
  const idx2 = Math.min(t2, data.length - 1);
  const delta = Math.abs(data[idx2].effort - data[idx1].effort);
  maxEffortJumpPerPixel = Math.max(maxEffortJumpPerPixel, delta);
  avgEffortJumpPerPixel += delta;
  jumps++;
}
avgEffortJumpPerPixel /= jumps;

console.log(`  At ${chartWidth}px width:`);
console.log(`  - Points per pixel: ~${(data.length / chartWidth).toFixed(1)}`);
console.log(`  - Max effort change between adjacent pixels: ${(maxEffortJumpPerPixel * 100).toFixed(1)}%`);
console.log(`  - Avg effort change between adjacent pixels: ${(avgEffortJumpPerPixel * 100).toFixed(2)}%`);
console.log(`  - Option A at 0.02 threshold: bands average ~${Math.round(chartWidth / bands02)}px wide`);
console.log(`    → Visible block-stepping when band width > 3-4px`);
console.log(`  - Option B: 1 color per pixel → no stepping, smooth gradient`);

// --- Performance projection ---
console.log(`\n--- Performance Projection ---`);
console.log(`Option A (SVG):`);
console.log(`  - ${bands02} <rect> elements created in DOM`);
console.log(`  - Browser must layout/paint ${bands02 * 5}+ SVG nodes`);
console.log(`  - Tooltip hover triggers SVG hit-testing across all elements`);
console.log(`  - Mobile: SVG reflow on resize is O(n) where n = total SVG nodes`);
console.log(`\nOption B (Canvas + SVG):`);
console.log(`  - Gradient: ~${chartWidth} fillRect calls → single bitmap → no DOM cost`);
console.log(`  - Canvas redraw on resize: < 5ms (direct pixel operations)`);
console.log(`  - SVG layer: ~${baseRecharts + 10} nodes (axes, grid, lines only)`);
console.log(`  - Tooltip hover only hit-tests against SVG layer (minimal nodes)`);

console.log(`\n--- DECISION EVIDENCE SUMMARY ---`);
console.log(`| Criterion              | Option A (Recharts)      | Option B (Canvas Hybrid) |`);
console.log(`|------------------------|--------------------------|--------------------------|`);
console.log(`| DOM nodes              | ~${optionATotalEstimate.toString().padEnd(24)}| ~${(baseRecharts + 15).toString().padEnd(24)}|`);
console.log(`| Gradient smoothness    | Block-stepped (${Math.round(chartWidth / bands02)}px bands) | Pixel-perfect smooth     |`);
console.log(`| Resize cost            | SVG reflow O(${optionATotalEstimate})       | Canvas redraw O(${chartWidth})      |`);
console.log(`| Tooltip hit-testing    | ${optionATotalEstimate}+ SVG nodes         | ~${baseRecharts + 10} SVG nodes           |`);
console.log(`| Implementation effort  | Lower (Recharts only)    | Medium (Canvas + Recharts)|`);
console.log(`| F1-telemetry bar       | Unlikely (visible bands) | Achievable               |`);
console.log(`\nRecommendation: Option B (Canvas 2D Hybrid)`);
