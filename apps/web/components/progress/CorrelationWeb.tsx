'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';

const C = {
  bg: '#0d1321',
  card: '#141c2e',
  deep: '#111828',
  hover: '#192038',
  border: 'rgba(255,255,255,0.07)',
  bMed: 'rgba(255,255,255,0.12)',
  green: '#2ab87a',
  gFaint: 'rgba(42,184,122,0.09)',
  gBorder: 'rgba(42,184,122,0.22)',
  red: '#e05555',
  rFaint: 'rgba(224,85,85,0.1)',
  rBorder: 'rgba(224,85,85,0.25)',
  blue: '#4a90d9',
  oL: '#e07b20',
  oFaint: 'rgba(194,101,10,0.11)',
  oBorder: 'rgba(194,101,10,0.27)',
  t60: 'rgba(255,255,255,0.6)',
  t40: 'rgba(255,255,255,0.4)',
  t25: 'rgba(255,255,255,0.25)',
  t15: 'rgba(255,255,255,0.15)',
  t08: 'rgba(255,255,255,0.08)',
  w: '#fff',
};

interface WebNode {
  id: string;
  label: string;
  group: string;
}

interface WebEdge {
  source: string;
  target: string;
  r: number;
  direction: string;
  lag_days: number;
  times_confirmed: number;
  strength: string;
  note: string;
}

interface CorrelationWebProps {
  nodes: WebNode[];
  edges: WebEdge[];
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  group: string;
}

function Tag({
  color = C.oL,
  bg = C.oFaint,
  border = C.oBorder,
  children,
}: {
  color?: string;
  bg?: string;
  border?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      style={{
        background: bg,
        color,
        border: `1px solid ${border}`,
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 8px',
        borderRadius: 20,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

export function CorrelationWeb({ nodes: rawNodes, edges: rawEdges }: CorrelationWebProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<Record<string, { x: number; y: number }>>({});
  const [active, setActive] = useState<{ s: string; t: string } | null>(null);
  const [dims, setDims] = useState({ w: 800, h: 260 });
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 }
    );
    if (wrapRef.current) observer.observe(wrapRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setDims({ w: e.contentRect.width, h: 260 }));
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!inView || rawNodes.length === 0) return;

    const { w, h } = dims;
    const simNodes: SimNode[] = rawNodes.map((n) => ({ ...n }));
    const inputs = simNodes.filter((n) => n.group === 'input');
    const outputs = simNodes.filter((n) => n.group === 'output');

    inputs.forEach((n, i, arr) => {
      n.x = w * 0.18;
      n.y = h * 0.08 + i * ((h * 0.85) / Math.max(arr.length - 1, 1));
    });
    outputs.forEach((n, i, arr) => {
      n.x = w * 0.82;
      n.y = h * 0.15 + i * ((h * 0.7) / Math.max(arr.length - 1, 1));
    });

    // For <= 5 nodes, fixed positions are more stable than force simulation
    if (simNodes.length <= 5) {
      const p: Record<string, { x: number; y: number }> = {};
      simNodes.forEach((n) => {
        p[n.id] = { x: n.x!, y: n.y! };
      });
      setPos(p);
      return;
    }

    const links = rawEdges.map((e) => ({ ...e, source: e.source, target: e.target }));
    let rafId: number | null = null;
    const lastPos = new Map<string, { x: number; y: number }>();

    const sim = d3
      .forceSimulation(simNodes)
      .force(
        'link',
        d3
          .forceLink(links)
          .id((d: any) => d.id)
          .distance((d: any) => 130 + 80 * (1 - Math.abs(d.r)))
      )
      .force('charge', d3.forceManyBody().strength(-60))
      .force(
        'x',
        d3.forceX((d: any) => (d.group === 'input' ? w * 0.18 : w * 0.82)).strength(0.7)
      )
      .force('y', d3.forceY(h / 2).strength(0.08))
      .force('col', d3.forceCollide(32))
      .alphaDecay(0.1);

    sim.on('tick', () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        let changed = false;
        const p: Record<string, { x: number; y: number }> = {};
        simNodes.forEach((n) => {
          const nx = Math.max(36, Math.min(w - 36, n.x!));
          const ny = Math.max(18, Math.min(h - 18, n.y!));
          const prev = lastPos.get(n.id);
          if (!prev || Math.abs(prev.x - nx) > 1 || Math.abs(prev.y - ny) > 1) {
            changed = true;
          }
          p[n.id] = { x: nx, y: ny };
          lastPos.set(n.id, { x: nx, y: ny });
        });
        if (changed) setPos({ ...p });
      });
    });

    sim.on('end', () => {
      const p: Record<string, { x: number; y: number }> = {};
      simNodes.forEach((n) => {
        p[n.id] = {
          x: Math.max(36, Math.min(w - 36, n.x!)),
          y: Math.max(18, Math.min(h - 18, n.y!)),
        };
      });
      setPos({ ...p });
    });

    return () => {
      sim.stop();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [inView, dims, rawNodes, rawEdges]);

  if (rawNodes.length === 0) return null;

  return (
    <div ref={wrapRef}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <p
          style={{
            color: C.t40,
            fontSize: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.16em',
            fontWeight: 600,
            margin: 0,
          }}
        >
          What Drives Your Performance
        </p>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, color: C.green, marginLeft: 8 }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: C.green, boxShadow: `0 0 6px ${C.green}` }} />
          Live data
        </span>
      </div>
      <p style={{ color: C.t60, fontSize: 14, lineHeight: 1.7, maxWidth: 600, marginBottom: 18 }}>
        Every connection here is statistically confirmed from your own data. Edge thickness is correlation
        strength. Dashed edges are inverse. Hover any connection for the evidence behind it.
      </p>
      <div style={{ display: 'flex', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        {[
          { c: C.green, l: 'Positive (more → better)', dash: false },
          { c: C.red, l: 'Inverse (more → worse)', dash: true },
          { c: C.t25, l: 'Stronger = thicker', dash: false },
        ].map((d) => (
          <div key={d.l} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div
              style={{
                width: 22,
                height: d.dash ? 0 : 2,
                background: d.c,
                borderRadius: 1,
                borderTop: d.dash ? `2px dashed ${d.c}` : 'none',
              }}
            />
            <span style={{ fontSize: 10, color: C.t40 }}>{d.l}</span>
          </div>
        ))}
      </div>

      <svg
        style={{ width: '100%', height: dims.h, display: 'block', overflow: 'visible' }}
        viewBox={`0 0 ${dims.w} ${dims.h}`}
      >
        <text x={dims.w * 0.18} y={10} textAnchor="middle" fill={C.t25} fontSize={9} fontWeight={600}>
          INPUTS
        </text>
        <text x={dims.w * 0.82} y={10} textAnchor="middle" fill={C.t25} fontSize={9} fontWeight={600}>
          OUTPUTS
        </text>
        {Object.keys(pos).length > 0 && (
          <>
            {rawEdges.map((e, i) => {
              const s = pos[e.source];
              const t = pos[e.target];
              if (!s || !t) return null;

              const isAct = active?.s === e.source && active?.t === e.target;
              const isDim = active && !isAct;
              const str = Math.abs(e.r);
              const neg = e.direction === 'negative';
              const color = isAct
                ? neg
                  ? C.red
                  : C.green
                : isDim
                  ? 'rgba(255,255,255,0.05)'
                  : neg
                    ? 'rgba(224,85,85,0.35)'
                    : 'rgba(42,184,122,0.3)';
              const sw = isAct ? str * 10 + 3 : str * 6 + 1;
              const mx = (s.x + t.x) / 2;
              const my = (s.y + t.y) / 2 - 30;

              return (
                <g
                  key={i}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setActive({ s: e.source, t: e.target })}
                  onMouseLeave={() => setActive(null)}
                >
                  <path
                    d={`M${s.x},${s.y} Q${mx},${my} ${t.x},${t.y}`}
                    fill="none"
                    stroke={color}
                    strokeWidth={sw}
                    strokeDasharray={neg ? '7,4' : 'none'}
                    strokeLinecap="round"
                    style={{ transition: 'all 0.18s ease' }}
                  />
                  <path
                    d={`M${s.x},${s.y} Q${mx},${my} ${t.x},${t.y}`}
                    fill="none"
                    stroke="transparent"
                    strokeWidth={typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches ? 40 : 20}
                  />
                </g>
              );
            })}
            {rawNodes.map((n) => {
              const p = pos[n.id];
              if (!p) return null;
              const isIn = n.group === 'input';
              const rel =
                active &&
                rawEdges.some(
                  (e) =>
                    e.source === active.s &&
                    e.target === active.t &&
                    (e.source === n.id || e.target === n.id)
                );
              const nodeColor = isIn ? C.blue : C.green;
              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`}>
                  <circle
                    r={26}
                    fill={rel ? C.hover : C.deep}
                    stroke={rel ? nodeColor : C.bMed}
                    strokeWidth={rel ? 2 : 1}
                    style={{ transition: 'all 0.18s ease' }}
                  />
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={rel ? nodeColor : C.t60}
                    fontSize={9}
                    fontWeight={rel ? 700 : 400}
                    style={{ userSelect: 'none', transition: 'fill 0.18s ease', pointerEvents: 'none' }}
                  >
                    {n.label.split(' ').map((w, wi, arr) => (
                      <tspan key={wi} x={0} dy={wi === 0 ? (arr.length > 1 ? -5 : 0) : 11}>
                        {w}
                      </tspan>
                    ))}
                  </text>
                  {rel && <circle r={28} fill="none" stroke={nodeColor} strokeWidth={1} opacity={0.3} />}
                </g>
              );
            })}
          </>
        )}
      </svg>

      <div style={{ minHeight: 80, marginTop: 4 }}>
        {active ? (
          (() => {
            const ae = rawEdges.find((e) => e.source === active.s && e.target === active.t);
            if (!ae) return null;
            const neg = ae.direction === 'negative';
            const srcNode = rawNodes.find((n) => n.id === ae.source);
            const tgtNode = rawNodes.find((n) => n.id === ae.target);
            return (
              <div
                style={{
                  background: C.hover,
                  border: `1px solid ${neg ? C.rBorder : C.gBorder}`,
                  borderRadius: 12,
                  padding: '16px 20px',
                  animation: 'fadeUp 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: neg ? C.red : C.green }}>
                    {srcNode?.label} → {tgtNode?.label}
                  </span>
                  <Tag
                    color={neg ? C.red : C.green}
                    bg={neg ? C.rFaint : C.gFaint}
                    border={neg ? C.rBorder : C.gBorder}
                  >
                    r = {ae.r > 0 ? '+' : ''}
                    {ae.r}
                  </Tag>
                  <Tag color={C.t60} bg={C.t08} border={C.border}>
                    lag {ae.lag_days} day{ae.lag_days !== 1 ? 's' : ''}
                  </Tag>
                  <Tag color={C.t60} bg={C.t08} border={C.border}>
                    confirmed {ae.times_confirmed}×
                  </Tag>
                </div>
                <p style={{ fontSize: 13, color: C.t60, lineHeight: 1.7, margin: 0 }}>{ae.note}</p>
              </div>
            );
          })()
        ) : (
          <div
            style={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: `1px dashed ${C.border}`,
              borderRadius: 12,
            }}
          >
            <span style={{ fontSize: 12, color: C.t25 }}>Hover any connection to see the evidence</span>
          </div>
        )}
      </div>
    </div>
  );
}
