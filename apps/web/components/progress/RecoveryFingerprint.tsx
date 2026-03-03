'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import type { RecoveryCurveData } from '@/lib/hooks/queries/progress';

const C = {
  bg: '#0d1321',
  card: '#141c2e',
  green: '#2ab87a',
  t20: 'rgba(255,255,255,0.2)',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  t08: 'rgba(255,255,255,0.08)',
  w: '#fff',
};

interface Props {
  data: RecoveryCurveData;
}

export function RecoveryFingerprint({ data }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const drawn = useRef(false);
  const [inView, setInView] = useState(false);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    day: string;
    before: number | null;
    now: number | null;
  } | null>(null);

  const before = data.before ?? [];
  const now = data.now ?? [];
  const days = data.days ?? [];
  const isFallback = !!data.fallback;

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
    if (isFallback) return;
    if (!inView || drawn.current || !canvasRef.current) return;
    if (!before.length || !now.length) return;
    drawn.current = true;

    const canvas = canvasRef.current;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth;
    const H = 160;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext('2d')!;
    ctx.scale(dpr, dpr);

    const pad = { t: 16, r: 20, b: 32, l: 44 };
    const iw = W - pad.l - pad.r;
    const ih = H - pad.t - pad.b;
    const n = before.length;
    const xScale = (i: number) => (i / (n - 1)) * iw + pad.l;
    const yScale = (v: number) => pad.t + ih - ((v - 60) / 45) * ih;

    const drawGrid = () => {
      ctx.strokeStyle = 'rgba(255,255,255,0.04)';
      ctx.lineWidth = 1;
      [70, 80, 90, 100].forEach((v) => {
        ctx.beginPath();
        ctx.moveTo(pad.l, yScale(v));
        ctx.lineTo(pad.l + iw, yScale(v));
        ctx.stroke();
        ctx.fillStyle = C.t20;
        ctx.font = '9px system-ui';
        ctx.textAlign = 'right';
        ctx.fillText(v + '%', pad.l - 6, yScale(v) + 3);
      });
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.setLineDash([3, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.l, yScale(100));
      ctx.lineTo(pad.l + iw, yScale(100));
      ctx.stroke();
      ctx.setLineDash([]);
      days.forEach((d, i) => {
        ctx.fillStyle = C.t20;
        ctx.font = '9px system-ui';
        ctx.textAlign = 'center';
        ctx.fillText(d, xScale(i), H - 8);
      });
    };

    const bPts = before.map((v, i) => ({ x: xScale(i), y: yScale(v ?? 60) }));
    const aPts = now.map((v, i) => ({ x: xScale(i), y: yScale(v ?? 60) }));
    const totalLen = aPts.reduce((acc, pt, i) => {
      if (i === 0) return 0;
      return acc + Math.hypot(pt.x - aPts[i - 1].x, pt.y - aPts[i - 1].y);
    }, 0);
    let p = 0;

    const tick = () => {
      ctx.clearRect(0, 0, W, H);
      drawGrid();

      ctx.beginPath();
      ctx.moveTo(bPts[0].x, H - pad.b);
      bPts.forEach((pt) => ctx.lineTo(pt.x, pt.y));
      ctx.lineTo(bPts[bPts.length - 1].x, H - pad.b);
      ctx.closePath();
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(bPts[0].x, bPts[0].y);
      for (let i = 1; i < bPts.length - 1; i++) {
        const mx = (bPts[i].x + bPts[i + 1].x) / 2;
        const my = (bPts[i].y + bPts[i + 1].y) / 2;
        ctx.quadraticCurveTo(bPts[i].x, bPts[i].y, mx, my);
      }
      ctx.lineTo(bPts[bPts.length - 1].x, bPts[bPts.length - 1].y);
      ctx.strokeStyle = 'rgba(255,255,255,0.2)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      const fillProg = Math.min(p / totalLen, 1);
      const visA = Math.floor(fillProg * (n - 1));
      const frac = fillProg * (n - 1) - visA;
      const visApts: { x: number; y: number }[] = [];
      for (let i = 0; i <= visA && i < n; i++) visApts.push(aPts[i]);
      if (visA < n - 1) {
        visApts.push({
          x: aPts[visA].x + (aPts[visA + 1].x - aPts[visA].x) * frac,
          y: aPts[visA].y + (aPts[visA + 1].y - aPts[visA].y) * frac,
        });
      }

      if (visApts.length > 1) {
        const grad = ctx.createLinearGradient(0, yScale(100), 0, H - pad.b);
        grad.addColorStop(0, 'rgba(42,184,122,0.15)');
        grad.addColorStop(1, 'rgba(42,184,122,0.02)');
        ctx.beginPath();
        ctx.moveTo(visApts[0].x, H - pad.b);
        visApts.forEach((pt) => ctx.lineTo(pt.x, pt.y));
        ctx.lineTo(visApts[visApts.length - 1].x, H - pad.b);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        const lg = ctx.createLinearGradient(
          visApts[0].x, 0,
          visApts[visApts.length - 1].x, 0
        );
        lg.addColorStop(0, C.green + '88');
        lg.addColorStop(1, C.green);
        ctx.beginPath();
        ctx.moveTo(visApts[0].x, visApts[0].y);
        for (let i = 1; i < visApts.length - 1; i++) {
          const mx = (visApts[i].x + visApts[i + 1].x) / 2;
          const my = (visApts[i].y + visApts[i + 1].y) / 2;
          ctx.quadraticCurveTo(visApts[i].x, visApts[i].y, mx, my);
        }
        ctx.lineTo(visApts[visApts.length - 1].x, visApts[visApts.length - 1].y);
        ctx.strokeStyle = lg;
        ctx.lineWidth = 2.5;
        ctx.stroke();

        const last = visApts[visApts.length - 1];
        const glow = ctx.createRadialGradient(last.x, last.y, 0, last.x, last.y, 8);
        glow.addColorStop(0, C.green);
        glow.addColorStop(1, 'transparent');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(last.x, last.y, 8, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = C.green;
        ctx.beginPath();
        ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      if (p < totalLen) {
        p += totalLen / 60;
        requestAnimationFrame(tick);
      }
    };

    requestAnimationFrame(tick);
  }, [isFallback, inView, before, now, days]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const W = rect.width;
      const pad = { l: 44, r: 20 };
      const iw = W - pad.l - pad.r;
      const n = before.length;
      const idx = Math.round(((mx - pad.l) / iw) * (n - 1));
      if (idx >= 0 && idx < n) {
        setTooltip({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top - 50,
          day: days[idx],
          before: before[idx],
          now: now[idx],
        });
      } else {
        setTooltip(null);
      }
    },
    [before, now, days]
  );

  if (isFallback) {
    return (
      <div ref={wrapRef}>
        <p
          style={{
            color: C.t40,
            fontSize: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.16em',
            fontWeight: 600,
            marginBottom: 8,
          }}
        >
          Recovery Fingerprint
        </p>
        <p style={{ color: C.t60, fontSize: 13, lineHeight: 1.7 }}>
          {data.message}
        </p>
      </div>
    );
  }

  return (
    <div ref={wrapRef}>
      <p
        style={{
          color: C.t40,
          fontSize: 10,
          textTransform: 'uppercase',
          letterSpacing: '0.16em',
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        Recovery Fingerprint
      </p>
      <p style={{ color: C.t60, fontSize: 14, lineHeight: 1.7, maxWidth: 600, marginBottom: 14 }}>
        How your body bounces back from hard efforts — now vs 90 days ago.
        The gap between the curves is your adaptation.
      </p>
      <div
        style={{
          display: 'flex',
          gap: 20,
          marginBottom: 10,
          fontSize: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 20,
              height: 0,
              borderTop: '2px dashed rgba(255,255,255,0.2)',
            }}
          />
          <span style={{ color: C.t40 }}>90 days ago ({data.hard_sessions_before} hard sessions)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 20, height: 2, background: C.green, borderRadius: 1 }} />
          <span style={{ color: C.t40 }}>Now ({data.hard_sessions_now} hard sessions)</span>
        </div>
      </div>
      <div style={{ position: 'relative' }}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: 160, display: 'block', cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(null)}
        />
        {tooltip && (
          <div
            style={{
              position: 'absolute',
              left: tooltip.x,
              top: tooltip.y,
              transform: 'translateX(-50%)',
              background: '#1a2236',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 11,
              color: C.w,
              pointerEvents: 'none',
              whiteSpace: 'nowrap',
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{tooltip.day}</div>
            <div style={{ color: C.t40 }}>
              Before: {tooltip.before != null ? tooltip.before + '%' : '—'}
            </div>
            <div style={{ color: C.green }}>
              Now: {tooltip.now != null ? tooltip.now + '%' : '—'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
