'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import {
  useRaceCandidates,
  useBrowseActivities,
  useConfirmRace,
  useAddRace,
} from '@/lib/hooks/queries/fingerprint';
import type { RaceCard, RacingLifeStripData, RacePin } from '@/lib/api/services/fingerprint';

const C = {
  bg: '#0d1321',
  card: '#141c2e',
  cardHover: '#1a2540',
  border: 'rgba(255,255,255,0.07)',
  borderActive: 'rgba(194,101,10,0.4)',
  orange: '#c2650a',
  oL: '#e07b20',
  green: '#2ab87a',
  greenFaint: 'rgba(42,184,122,0.15)',
  red: '#e04040',
  redFaint: 'rgba(224,64,64,0.12)',
  t40: 'rgba(255,255,255,0.4)',
  t60: 'rgba(255,255,255,0.6)',
  t80: 'rgba(255,255,255,0.8)',
  t25: 'rgba(255,255,255,0.25)',
  t08: 'rgba(255,255,255,0.08)',
  w: '#fff',
  pb: '#d4a017',
};

const DIST_LABELS: Record<string, string> = {
  mile: 'Mile',
  '5k': '5K',
  '10k': '10K',
  '15k': '15K',
  '25k': '25K',
  half_marathon: 'Half Marathon',
  marathon: 'Marathon',
  '50k': '50K',
};

function formatDate(d: string): string {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/* ─── Racing Life Strip (Canvas) ─────────────────────── */

function RacingLifeStrip({ data }: { data: RacingLifeStripData }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !data.weeks.length) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = 120;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const maxVol = Math.max(...data.weeks.map((wk) => wk.total_volume_km), 1);
    const barW = Math.max(2, (w - 40) / data.weeks.length - 1);
    const chartH = h - 30;

    data.weeks.forEach((wk, i) => {
      const x = 20 + i * (barW + 1);
      const barH = (wk.total_volume_km / maxVol) * chartH;
      ctx.fillStyle = 'rgba(42,184,122,0.3)';
      ctx.fillRect(x, chartH - barH, barW, barH);
    });

    data.pins.forEach((pin) => {
      const pinDate = new Date(pin.date + 'T00:00:00');
      const firstWeek = new Date(data.weeks[0].week_start + 'T00:00:00');
      const daysDiff = (pinDate.getTime() - firstWeek.getTime()) / (1000 * 60 * 60 * 24);
      const weekIdx = Math.floor(daysDiff / 7);
      if (weekIdx < 0 || weekIdx >= data.weeks.length) return;

      const x = 20 + weekIdx * (barW + 1) + barW / 2;
      const y = 8;

      ctx.beginPath();
      ctx.arc(x, y, pin.is_personal_best ? 6 : 4, 0, Math.PI * 2);
      ctx.fillStyle = pin.is_personal_best ? C.pb : C.orange;
      ctx.fill();
      ctx.strokeStyle = C.w;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(x, y + (pin.is_personal_best ? 6 : 4));
      ctx.lineTo(x, chartH);
      ctx.strokeStyle = 'rgba(194,101,10,0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
    });

    ctx.fillStyle = C.t40;
    ctx.font = '11px system-ui';
    if (data.weeks.length > 0) {
      ctx.fillText(
        formatDate(data.weeks[0].week_start),
        20,
        h - 4
      );
      ctx.textAlign = 'end';
      ctx.fillText(
        formatDate(data.weeks[data.weeks.length - 1].week_start),
        w - 20,
        h - 4
      );
      ctx.textAlign = 'start';
    }
  }, [data]);

  if (!data.weeks.length) return null;

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <canvas ref={canvasRef} style={{ display: 'block', borderRadius: 8 }} />
    </div>
  );
}

/* ─── Race Card Component ────────────────────────────── */

function RaceCardUI({
  card,
  onConfirm,
  onReject,
  onAdd,
  mode,
}: {
  card: RaceCard;
  onConfirm?: () => void;
  onReject?: () => void;
  onAdd?: () => void;
  mode: 'confirmed' | 'candidate' | 'browse';
}) {
  const [hover, setHover] = useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? C.cardHover : C.card,
        border: `1px solid ${card.is_personal_best ? C.pb : mode === 'confirmed' ? C.borderActive : C.border}`,
        borderRadius: 14,
        padding: '20px 22px',
        transition: 'all 0.2s',
        cursor: mode === 'browse' ? 'pointer' : undefined,
        position: 'relative',
      }}
    >
      {card.is_personal_best && (
        <div style={{
          position: 'absolute', top: -1, right: 16,
          background: C.pb, color: '#000', fontSize: 10, fontWeight: 700,
          padding: '2px 8px', borderRadius: '0 0 6px 6px', letterSpacing: 0.5,
        }}>
          PB
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ color: C.orange, fontSize: 12, fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 }}>
            {DIST_LABELS[card.distance_category] || card.distance_category}
          </div>
          <div style={{ color: C.w, fontSize: 16, fontWeight: 600 }}>
            {card.name || formatDate(card.date)}
          </div>
          {card.name && (
            <div style={{ color: C.t60, fontSize: 13, marginTop: 2 }}>
              {formatDate(card.date)}
              {card.day_of_week && ` · ${card.day_of_week}`}
              {card.time_of_day && ` · ${card.time_of_day}`}
            </div>
          )}
          {!card.name && card.day_of_week && (
            <div style={{ color: C.t40, fontSize: 13, marginTop: 2 }}>
              {card.day_of_week}
              {card.time_of_day && ` · ${card.time_of_day}`}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 20, marginBottom: mode !== 'confirmed' ? 14 : 0 }}>
        <div>
          <div style={{ color: C.t40, fontSize: 11, marginBottom: 2 }}>Pace</div>
          <div style={{ color: C.w, fontSize: 15, fontWeight: 600 }}>{card.pace_display}</div>
        </div>
        <div>
          <div style={{ color: C.t40, fontSize: 11, marginBottom: 2 }}>Time</div>
          <div style={{ color: C.t80, fontSize: 15 }}>{card.duration_display}</div>
        </div>
        {card.avg_hr && (
          <div>
            <div style={{ color: C.t40, fontSize: 11, marginBottom: 2 }}>Avg HR</div>
            <div style={{ color: C.t80, fontSize: 15 }}>{card.avg_hr}</div>
          </div>
        )}
        <div>
          <div style={{ color: C.t40, fontSize: 11, marginBottom: 2 }}>Distance</div>
          <div style={{ color: C.t80, fontSize: 15 }}>{(card.distance_meters / 1000).toFixed(1)} km</div>
        </div>
      </div>

      {mode === 'candidate' && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={onConfirm}
            style={{
              flex: 1, padding: '10px 16px', borderRadius: 8,
              border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13,
              background: C.greenFaint, color: C.green,
              transition: 'all 0.15s',
            }}
          >
            Yes, this was a race
          </button>
          <button
            onClick={onReject}
            style={{
              padding: '10px 16px', borderRadius: 8,
              border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13,
              background: C.redFaint, color: C.red,
              transition: 'all 0.15s',
            }}
          >
            Not a race
          </button>
        </div>
      )}

      {mode === 'browse' && (
        <button
          onClick={onAdd}
          style={{
            width: '100%', padding: '10px 16px', borderRadius: 8,
            border: `1px solid ${C.border}`, cursor: 'pointer',
            fontWeight: 600, fontSize: 13,
            background: 'transparent', color: C.t60,
            transition: 'all 0.15s',
          }}
        >
          Mark as race
        </button>
      )}
    </div>
  );
}

/* ─── Tier Section ───────────────────────────────────── */

function TierSection({
  title,
  subtitle,
  children,
  count,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  count: number;
}) {
  if (count === 0) return null;
  return (
    <div style={{ marginBottom: 36 }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ color: C.w, fontSize: 18, fontWeight: 600, margin: 0, marginBottom: 4 }}>
          {title}
          <span style={{ color: C.t40, fontWeight: 400, fontSize: 14, marginLeft: 8 }}>
            {count}
          </span>
        </h2>
        <p style={{ color: C.t40, fontSize: 13, margin: 0 }}>{subtitle}</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
        {children}
      </div>
    </div>
  );
}

/* ─── Browse Section ─────────────────────────────────── */

function BrowseSection() {
  const [distFilter, setDistFilter] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [showBrowse, setShowBrowse] = useState(false);
  const { data, isLoading } = useBrowseActivities({
    distance_category: distFilter,
    offset,
    limit: 20,
    enabled: showBrowse,
  });
  const addRace = useAddRace();

  if (!showBrowse) {
    return (
      <div style={{ marginBottom: 36 }}>
        <button
          onClick={() => setShowBrowse(true)}
          style={{
            width: '100%', padding: '16px 20px', borderRadius: 12,
            border: `1px dashed ${C.border}`, cursor: 'pointer',
            background: 'transparent', color: C.t60, fontSize: 14,
            fontWeight: 500, transition: 'all 0.2s',
          }}
        >
          Any races we missed? Browse your activity history
        </button>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 36 }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ color: C.w, fontSize: 18, fontWeight: 600, margin: 0, marginBottom: 4 }}>
          Any races we missed?
        </h2>
        <p style={{ color: C.t40, fontSize: 13, margin: 0 }}>
          Browse your activities sorted by pace — fastest first. The races are usually near the top.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <FilterChip
          label="All distances"
          active={!distFilter}
          onClick={() => { setDistFilter(undefined); setOffset(0); }}
        />
        {Object.entries(DIST_LABELS).map(([key, label]) => (
          <FilterChip
            key={key}
            label={label}
            active={distFilter === key}
            onClick={() => { setDistFilter(key); setOffset(0); }}
          />
        ))}
      </div>

      {isLoading && (
        <div style={{ color: C.t40, padding: 24, textAlign: 'center' }}>Loading...</div>
      )}

      {data && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
            {data.items.map((card) => (
              <RaceCardUI
                key={card.activity_id}
                card={card}
                mode="browse"
                onAdd={() => addRace.mutate(card.activity_id)}
              />
            ))}
          </div>

          {data.total > 20 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 16 }}>
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 20))}
                style={{
                  padding: '8px 20px', borderRadius: 8, border: `1px solid ${C.border}`,
                  background: 'transparent', color: offset === 0 ? C.t25 : C.t60,
                  cursor: offset === 0 ? 'default' : 'pointer', fontSize: 13,
                }}
              >
                Previous
              </button>
              <span style={{ color: C.t40, fontSize: 13, alignSelf: 'center' }}>
                {offset + 1}–{Math.min(offset + 20, data.total)} of {data.total}
              </span>
              <button
                disabled={offset + 20 >= data.total}
                onClick={() => setOffset(offset + 20)}
                style={{
                  padding: '8px 20px', borderRadius: 8, border: `1px solid ${C.border}`,
                  background: 'transparent', color: offset + 20 >= data.total ? C.t25 : C.t60,
                  cursor: offset + 20 >= data.total ? 'default' : 'pointer', fontSize: 13,
                }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '6px 14px', borderRadius: 20,
        border: `1px solid ${active ? C.orange : C.border}`,
        background: active ? 'rgba(194,101,10,0.15)' : 'transparent',
        color: active ? C.oL : C.t60,
        fontSize: 12, fontWeight: 500, cursor: 'pointer',
        transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  );
}

/* ─── Main Page ──────────────────────────────────────── */

export default function FingerprintPage() {
  const { data, isLoading, error } = useRaceCandidates();
  const confirmRace = useConfirmRace();

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div style={{ minHeight: '100vh', background: C.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ color: C.t40, fontSize: 16 }}>Scanning your race history...</div>
        </div>
      </ProtectedRoute>
    );
  }

  if (error) {
    return (
      <ProtectedRoute>
        <div style={{ minHeight: '100vh', background: C.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ color: C.red, fontSize: 16 }}>Failed to load race data</div>
        </div>
      </ProtectedRoute>
    );
  }

  if (!data) return null;

  const totalConfirmed = data.confirmed.length;
  const stripData = data.strip_data;

  return (
    <ProtectedRoute>
      <div style={{ minHeight: '100vh', background: C.bg }}>
        {/* Hero */}
        <div style={{
          background: 'linear-gradient(135deg, #1a1e2e 0%, #0d1321 50%, #1a1510 100%)',
          padding: '48px 20px 32px',
          borderBottom: `1px solid ${C.border}`,
        }}>
          <div style={{ maxWidth: 900, margin: '0 auto' }}>
            <h1 style={{ color: C.w, fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 8 }}>
              Your Racing History
            </h1>
            <p style={{ color: C.t60, fontSize: 15, margin: 0, lineHeight: 1.5 }}>
              {totalConfirmed > 0
                ? `${totalConfirmed} race${totalConfirmed !== 1 ? 's' : ''} identified. Confirm candidates below to build your complete racing fingerprint.`
                : 'Help us find your races. Confirm the ones we detected and add any we missed.'}
            </p>

            {stripData.pins.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <div style={{ color: C.t40, fontSize: 11, fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 8 }}>
                  Racing Life Strip
                </div>
                <RacingLifeStrip data={stripData} />
              </div>
            )}
          </div>
        </div>

        {/* Content */}
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 20px 64px' }}>
          <TierSection
            title="Races we found"
            subtitle="These are confirmed or high-confidence race detections"
            count={data.confirmed.length}
          >
            {data.confirmed.map((card) => (
              <RaceCardUI key={card.event_id || card.activity_id} card={card} mode="confirmed" />
            ))}
          </TierSection>

          <TierSection
            title="Were these races?"
            subtitle="These activities look like they could be races — you tell us"
            count={data.candidates.length}
          >
            {data.candidates.map((card) => (
              <RaceCardUI
                key={card.event_id || card.activity_id}
                card={card}
                mode="candidate"
                onConfirm={() => card.event_id && confirmRace.mutate({ eventId: card.event_id, confirmed: true })}
                onReject={() => card.event_id && confirmRace.mutate({ eventId: card.event_id, confirmed: false })}
              />
            ))}
          </TierSection>

          <BrowseSection />

          {totalConfirmed > 0 && data.candidates.length === 0 && (
            <div style={{
              background: C.card,
              border: `1px solid ${C.borderActive}`,
              borderRadius: 14,
              padding: '28px 24px',
              textAlign: 'center',
            }}>
              <div style={{ color: C.orange, fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
                {totalConfirmed} race{totalConfirmed !== 1 ? 's' : ''} confirmed
              </div>
              <p style={{ color: C.t60, fontSize: 14, margin: 0, lineHeight: 1.5 }}>
                Your racing fingerprint is being analyzed.
                The system is now comparing your training blocks to find what produced your best performances.
              </p>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
