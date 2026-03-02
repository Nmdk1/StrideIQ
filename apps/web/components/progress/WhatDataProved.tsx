'use client';

import React, { useState, useRef, useEffect } from 'react';

const C = {
  deep: '#111828',
  hover: '#192038',
  border: 'rgba(255,255,255,0.07)',
  bMed: 'rgba(255,255,255,0.12)',
  green: '#2ab87a',
  gFaint: 'rgba(42,184,122,0.09)',
  gBorder: 'rgba(42,184,122,0.22)',
  oL: '#e07b20',
  oFaint: 'rgba(194,101,10,0.11)',
  oBorder: 'rgba(194,101,10,0.27)',
  t80: 'rgba(255,255,255,0.8)',
  t60: 'rgba(255,255,255,0.6)',
  t40: 'rgba(255,255,255,0.4)',
  t25: 'rgba(255,255,255,0.25)',
  w: '#fff',
};

interface ProvedFactItem {
  input_metric: string;
  output_metric: string;
  headline: string;
  evidence: string;
  implication: string;
  times_confirmed: number;
  confidence_tier: string;
  direction: string;
  correlation_coefficient: number;
  lag_days: number;
}

interface WhatDataProvedProps {
  facts: ProvedFactItem[];
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

export function WhatDataProved({ facts }: WhatDataProvedProps) {
  const [open, setOpen] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
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
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  if (facts.length === 0) return null;

  return (
    <div ref={ref}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
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
          What the Data Has Proved About You
        </p>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 10,
            color: C.green,
            marginLeft: 8,
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: '50%',
              background: C.green,
              boxShadow: `0 0 6px ${C.green}`,
            }}
          />
          Live data
        </span>
      </div>
      <p style={{ color: C.t60, fontSize: 14, lineHeight: 1.7, maxWidth: 580, marginBottom: 16 }}>
        These started as hypotheses. Your data confirmed them. They are permanent facts about how your
        body works — stored and growing.
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <Tag color={C.green} bg={C.gFaint} border={C.gBorder}>
          ✓ Confirmed
        </Tag>
        <span style={{ fontSize: 11, color: C.t40, alignSelf: 'center' }}>= proven by repeated confirmation</span>
        <Tag color={C.oL} bg={C.oFaint} border={C.oBorder}>
          ~ Emerging
        </Tag>
        <span style={{ fontSize: 11, color: C.t40, alignSelf: 'center' }}>= pattern forming</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {facts.map((p, i) => {
          const isOpen = open === i;
          const isStrong = p.confidence_tier === 'strong' || p.confidence_tier === 'confirmed';
          const icon = isStrong ? '✓' : '~';
          const color = isStrong ? C.green : C.oL;
          const statusLabel =
            p.confidence_tier === 'strong'
              ? 'Strong'
              : p.confidence_tier === 'confirmed'
                ? 'Confirmed'
                : 'Emerging';

          return (
            <div
              key={i}
              onClick={() => setOpen(isOpen ? null : i)}
              style={{
                background: isOpen ? C.hover : C.deep,
                border: `1px solid ${isOpen ? C.bMed : C.border}`,
                borderRadius: 12,
                padding: '14px 18px',
                cursor: 'pointer',
                opacity: inView ? 1 : 0,
                transform: inView ? 'none' : 'translateY(10px)',
                transition: `all 0.4s ease ${i * 45}ms`,
              }}
            >
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 14, color, fontWeight: 800, marginTop: 1, flexShrink: 0 }}>
                  {icon}
                </span>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 12,
                      flexWrap: 'wrap',
                    }}
                  >
                    <span style={{ fontSize: 13, fontWeight: 600, color: isOpen ? C.w : C.t80, lineHeight: 1.4 }}>
                      {p.headline}
                    </span>
                    <div style={{ display: 'flex', gap: 7, alignItems: 'center', flexShrink: 0 }}>
                      <Tag color={color} bg={`${color}18`} border={`${color}44`}>
                        {statusLabel} {p.times_confirmed}×
                      </Tag>
                      <span
                        style={{
                          fontSize: 10,
                          color: C.t25,
                          transform: isOpen ? 'rotate(180deg)' : 'none',
                          transition: 'transform 0.2s ease',
                          display: 'inline-block',
                        }}
                      >
                        ▾
                      </span>
                    </div>
                  </div>
                  {isOpen && (
                    <div
                      style={{
                        marginTop: 14,
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 14,
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: C.t25,
                            textTransform: 'uppercase',
                            letterSpacing: '0.12em',
                            marginBottom: 5,
                          }}
                        >
                          The Evidence
                        </div>
                        <p style={{ fontSize: 12, color: C.t60, lineHeight: 1.65, margin: 0 }}>{p.evidence}</p>
                      </div>
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color,
                            textTransform: 'uppercase',
                            letterSpacing: '0.12em',
                            marginBottom: 5,
                          }}
                        >
                          What It Means Now
                        </div>
                        <p style={{ fontSize: 12, color: C.t60, lineHeight: 1.65, margin: 0 }}>
                          {p.implication || 'The system will generate a personalized insight here as more data accumulates.'}
                        </p>
                        <div style={{ display: 'flex', gap: 3, marginTop: 10, alignItems: 'center' }}>
                          <span style={{ fontSize: 9, color: C.t25, marginRight: 4 }}>Confirmations</span>
                          {Array.from({ length: p.times_confirmed }).map((_, ci) => (
                            <div
                              key={ci}
                              style={{ width: 7, height: 7, borderRadius: '50%', background: color }}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
