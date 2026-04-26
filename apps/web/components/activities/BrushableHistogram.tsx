/**
 * BrushableHistogram — a compact distribution histogram with a draggable
 * range brush. Used in the activities-list filter strip.
 *
 * Design rationale:
 *   The athlete sees the distribution of their own data in this dimension
 *   and brushes the range they care about directly on it. They never type
 *   a number; the histogram IS the filter.
 *
 *   The component renders nothing when the dimension is unavailable
 *   (suppression rule). The parent decides availability and skips
 *   instantiation entirely.
 */

'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { FilterHistogramBucket } from '@/lib/api/services/activities';

const WIDTH = 200;
const HEIGHT = 64;
const BAR_HEIGHT = 44;
const HANDLE_WIDTH = 6;

export interface BrushRange {
  min: number | null;
  max: number | null;
}

interface BrushableHistogramProps {
  label: string;
  buckets: FilterHistogramBucket[];
  domainMin: number;
  domainMax: number;
  value: BrushRange;
  onChange: (range: BrushRange) => void;
  formatRange: (lo: number, hi: number) => string;
  formatBucketCount?: (count: number) => string;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

export function BrushableHistogram({
  label,
  buckets,
  domainMin,
  domainMax,
  value,
  onChange,
  formatRange,
  formatBucketCount,
}: BrushableHistogramProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragState = useRef<{
    edge: 'min' | 'max' | 'whole' | null;
    startX: number;
    startMin: number;
    startMax: number;
  }>({ edge: null, startX: 0, startMin: 0, startMax: 0 });
  const [hoverBucket, setHoverBucket] = useState<number | null>(null);

  // Effective brush range (default to full domain when unset)
  const min = value.min ?? domainMin;
  const max = value.max ?? domainMax;

  // Log-scaled bar heights for distribution visibility (long-tailed dimensions
  // like distance need it; short-tailed like dew don't suffer from it)
  const maxCount = useMemo(
    () => Math.max(1, ...buckets.map((b) => b.count)),
    [buckets],
  );
  const barH = (count: number) => {
    if (count <= 0) return 0;
    return Math.max(2, (Math.log1p(count) / Math.log1p(maxCount)) * BAR_HEIGHT);
  };

  const xScale = (v: number) => {
    if (domainMax === domainMin) return 0;
    return ((v - domainMin) / (domainMax - domainMin)) * WIDTH;
  };
  const xInverse = (px: number) => {
    return domainMin + (px / WIDTH) * (domainMax - domainMin);
  };

  const minX = xScale(min);
  const maxX = xScale(max);

  const onPointerDown = (
    e: React.PointerEvent<SVGElement>,
    edge: 'min' | 'max' | 'whole',
  ) => {
    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    dragState.current = {
      edge,
      startX: e.clientX,
      startMin: min,
      startMax: max,
    };
  };

  const onPointerMove = (e: React.PointerEvent<SVGElement>) => {
    if (!dragState.current.edge || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = e.clientX - dragState.current.startX;
    const dxData = (dx / rect.width) * (domainMax - domainMin);

    let newMin = dragState.current.startMin;
    let newMax = dragState.current.startMax;

    if (dragState.current.edge === 'min') {
      newMin = clamp(dragState.current.startMin + dxData, domainMin, newMax);
    } else if (dragState.current.edge === 'max') {
      newMax = clamp(dragState.current.startMax + dxData, newMin, domainMax);
    } else {
      const span = newMax - newMin;
      newMin = clamp(dragState.current.startMin + dxData, domainMin, domainMax - span);
      newMax = newMin + span;
    }

    onChange({
      min: newMin <= domainMin + 1e-9 ? null : newMin,
      max: newMax >= domainMax - 1e-9 ? null : newMax,
    });
  };

  const onPointerUp = (e: React.PointerEvent<SVGElement>) => {
    if (dragState.current.edge) {
      try {
        (e.currentTarget as Element).releasePointerCapture(e.pointerId);
      } catch {
        // ignore — capture may already have ended
      }
    }
    dragState.current.edge = null;
  };

  const onBackgroundClick = (e: React.MouseEvent<SVGRectElement>) => {
    if (dragState.current.edge) return; // ignore click after drag
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
    // Click selects the bucket clicked
    for (const b of buckets) {
      if (px >= xScale(b.lo) && px <= xScale(b.hi)) {
        onChange({
          min: b.lo <= domainMin + 1e-9 ? null : b.lo,
          max: b.hi >= domainMax - 1e-9 ? null : b.hi,
        });
        return;
      }
    }
  };

  const onDoubleClick = () => {
    onChange({ min: null, max: null });
  };

  // Persist a Reset link semantically — keyboard accessible
  const isActive = value.min != null || value.max != null;

  // Bucket labels for tooltip (formatted ranges)
  const bucketLabels = useMemo(
    () => buckets.map((b) => `${formatRange(b.lo, b.hi)}: ${b.count}`),
    [buckets, formatRange],
  );

  // Cleanup pointer listeners
  useEffect(() => {
    return () => {
      dragState.current.edge = null;
    };
  }, []);

  return (
    <div className="flex flex-col gap-1.5 select-none">
      <div className="flex items-baseline justify-between text-[11px] uppercase tracking-wide text-slate-400">
        <span>{label}</span>
        {isActive && (
          <button
            type="button"
            onClick={onDoubleClick}
            className="text-orange-400 hover:text-orange-300 normal-case tracking-normal text-[10px]"
          >
            reset
          </button>
        )}
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full h-12 cursor-pointer"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={onDoubleClick}
        role="slider"
        aria-label={`${label} filter`}
        aria-valuemin={domainMin}
        aria-valuemax={domainMax}
        aria-valuenow={min}
      >
        <rect
          x={0}
          y={0}
          width={WIDTH}
          height={BAR_HEIGHT}
          fill="transparent"
          onClick={onBackgroundClick}
        />
        {/* Bars */}
        {buckets.map((b, i) => {
          const x = xScale(b.lo);
          const w = Math.max(1, xScale(b.hi) - x);
          const h = barH(b.count);
          const insideBrush = b.hi >= min && b.lo <= max;
          return (
            <g key={i}>
              <rect
                x={x + 0.5}
                y={BAR_HEIGHT - h}
                width={Math.max(0, w - 1)}
                height={h}
                fill={insideBrush ? '#f97316' /* orange-500 */ : '#475569' /* slate-600 */}
                opacity={insideBrush ? 0.95 : 0.6}
                onMouseEnter={() => setHoverBucket(i)}
                onMouseLeave={() => setHoverBucket(null)}
              >
                <title>
                  {formatBucketCount
                    ? formatBucketCount(b.count)
                    : `${b.count} activities`}{' '}
                  · {formatRange(b.lo, b.hi)}
                </title>
              </rect>
            </g>
          );
        })}
        {/* Brush band (overlay between handles) */}
        <rect
          x={minX}
          y={0}
          width={Math.max(0, maxX - minX)}
          height={BAR_HEIGHT}
          fill="rgba(249, 115, 22, 0.08)"
          stroke="rgba(249, 115, 22, 0.45)"
          strokeWidth={1}
          pointerEvents={isActive ? 'auto' : 'none'}
          style={{ cursor: 'grab' }}
          onPointerDown={(e) => onPointerDown(e, 'whole')}
        />
        {/* Min handle */}
        <rect
          x={minX - HANDLE_WIDTH / 2}
          y={0}
          width={HANDLE_WIDTH}
          height={BAR_HEIGHT}
          fill="rgba(249, 115, 22, 0.85)"
          style={{ cursor: 'ew-resize' }}
          onPointerDown={(e) => onPointerDown(e, 'min')}
        />
        {/* Max handle */}
        <rect
          x={maxX - HANDLE_WIDTH / 2}
          y={0}
          width={HANDLE_WIDTH}
          height={BAR_HEIGHT}
          fill="rgba(249, 115, 22, 0.85)"
          style={{ cursor: 'ew-resize' }}
          onPointerDown={(e) => onPointerDown(e, 'max')}
        />
      </svg>
      <div className="text-[11px] text-slate-300 tabular-nums">
        {hoverBucket != null
          ? bucketLabels[hoverBucket]
          : formatRange(min, max)}
      </div>
    </div>
  );
}
