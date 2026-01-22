/**
 * Load-Response Chart Component
 * 
 * Shows weekly load vs efficiency delta to identify productive vs wasted vs harmful load.
 */

'use client';

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import type { EfficiencyTrendsResponse } from '@/lib/api/services/analytics';
import { useUnits } from '@/lib/context/UnitsContext';
import { useQuery } from '@tanstack/react-query';
import { analyticsService, type LoadResponseExplainResponse } from '@/lib/api/services/analytics';
import { AlertCircle, Info, TrendingDown, TrendingUp } from 'lucide-react';

interface LoadResponseChartProps {
  data: EfficiencyTrendsResponse['load_response'];
  className?: string;
}

const LOAD_TYPE_COLORS = {
  productive: '#10B981', // green
  neutral: '#6B7280', // gray
  wasted: '#F59E0B', // yellow
  harmful: '#EF4444', // red
};

export function LoadResponseChart({ data, className = '' }: LoadResponseChartProps) {
  const { formatDistance, units } = useUnits();
  const [selectedWeekStart, setSelectedWeekStart] = React.useState<string | null>(null);
  const drilldownRef = React.useRef<HTMLDivElement | null>(null);

  const hasData = !!data && data.length > 0;

  const chartData = React.useMemo(() => {
    if (!hasData) return [];
    return data.map((week) => ({
      weekStart: week.week_start,
      week: new Date(week.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      // API returns miles, convert to meters for formatDistance
      distanceMeters: week.total_distance_miles * 1609.34,
      efficiencyDelta: week.efficiency_delta || 0,
      loadType: week.load_type,
      activityCount: week.activity_count,
    }));
  }, [data, hasData]);

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-3 shadow-lg">
          <p className="text-sm font-semibold mb-2 text-slate-100">{data.week}</p>
          <div className="space-y-1 text-xs">
            <p>
              <span className="text-slate-400">Distance:</span>{' '}
              <span className="text-white">{formatDistance(data.distanceMeters, 1)}</span>
            </p>
            <p>
              <span className="text-slate-400">Efficiency Δ:</span>{' '}
              <span
                className={
                  data.efficiencyDelta < 0
                    ? 'text-green-400'
                    : data.efficiencyDelta > 0
                    ? 'text-red-400'
                    : 'text-slate-400'
                }
              >
                {data.efficiencyDelta > 0 ? '+' : ''}
                {data.efficiencyDelta.toFixed(2)}
              </span>
            </p>
            <p>
              <span className="text-slate-400">Load Type:</span>{' '}
              <span
                className="text-white capitalize"
                style={{ color: LOAD_TYPE_COLORS[data.loadType as keyof typeof LOAD_TYPE_COLORS] }}
              >
                {data.loadType}
              </span>
            </p>
            <p>
              <span className="text-slate-400">Activities:</span>{' '}
              <span className="text-white">{data.activityCount}</span>
            </p>
            <p className="pt-1 text-[11px] text-slate-500">
              Click bar to explain
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  const legendChips: Array<{ key: keyof typeof LOAD_TYPE_COLORS; label: string }> = [
    { key: 'productive', label: 'Productive' },
    { key: 'neutral', label: 'Neutral' },
    { key: 'wasted', label: 'Wasted' },
    { key: 'harmful', label: 'Harmful' },
  ];

  const selected = selectedWeekStart
    ? chartData.find((w) => w.weekStart === selectedWeekStart) ?? null
    : null;

  const explainQuery = useQuery<LoadResponseExplainResponse>({
    queryKey: ['load-response-explain', selectedWeekStart],
    queryFn: () => analyticsService.explainLoadResponseWeek(selectedWeekStart as string),
    enabled: hasData && !!selectedWeekStart,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const loadTypeLabel = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

  const loadTypePillClass = (t: string) => {
    if (t === 'productive') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    if (t === 'harmful') return 'bg-red-500/15 text-red-300 border-red-500/30';
    if (t === 'wasted') return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  };

  React.useEffect(() => {
    if (!selectedWeekStart) return;
    const t = setTimeout(() => {
      drilldownRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
    return () => clearTimeout(t);
  }, [selectedWeekStart]);

  if (!hasData) {
    return null;
  }

  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700/50 p-6 ${className} [&_.recharts-bar-rectangle]:cursor-pointer`}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-semibold">Load → Response</h3>
          <p className="text-sm text-slate-400 mt-1">
            Weekly distance vs efficiency change. <span className="text-slate-300">Negative</span> Δ = improvement.
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Click any week to explain what drove it.
          </p>
          {selectedWeekStart ? (
            <p className="text-xs text-slate-400 mt-2">
              Selected:{' '}
              <span className="text-slate-200 font-medium">
                {new Date(selectedWeekStart).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            </p>
          ) : null}
        </div>
        <div className="hidden md:flex flex-wrap justify-end gap-2">
          {legendChips.map((c) => (
            <div
              key={c.key}
              className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-slate-700/60 bg-slate-900/30 text-xs text-slate-300"
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: LOAD_TYPE_COLORS[c.key] }}
              />
              {c.label}
            </div>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={chartData}
          margin={{ top: 8, right: 16, left: 8, bottom: 16 }}
          barCategoryGap="22%"
        >
          <CartesianGrid strokeDasharray="2 8" stroke="#374151" opacity={0.45} />
          <XAxis
            dataKey="week"
            stroke="#9CA3AF"
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            style={{ fontSize: '12px' }}
            angle={-35}
            textAnchor="end"
            height={70}
          />
          <YAxis
            stroke="#9CA3AF"
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            style={{ fontSize: '12px' }}
            tickFormatter={(v) => (typeof v === 'number' ? `${v > 0 ? '+' : ''}${v.toFixed(2)}` : `${v}`)}
            label={{ value: 'Efficiency Δ', angle: -90, position: 'insideLeft', fill: '#94A3B8' }}
          />

          {/* Baseline: improvement vs regression */}
          <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 6" />

          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
          />

          {/* Keep legend off (chips above are cleaner) */}
          <Legend wrapperStyle={{ display: 'none' }} />

          <Bar
            dataKey="efficiencyDelta"
            name="Efficiency Change"
            radius={[8, 8, 2, 2]}
            maxBarSize={46}
            fillOpacity={0.9}
            onClick={(barData: any) => {
              // Recharts reliably passes the clicked bar's payload here.
              const wk = barData?.payload?.weekStart;
              if (wk) setSelectedWeekStart(wk);
            }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={LOAD_TYPE_COLORS[entry.loadType as keyof typeof LOAD_TYPE_COLORS]}
                stroke={entry.weekStart === selectedWeekStart ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.08)'}
                strokeWidth={1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-4 md:hidden flex flex-wrap gap-2">
        {legendChips.map((c) => (
          <div
            key={c.key}
            className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-slate-700/60 bg-slate-900/30 text-xs text-slate-300"
          >
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: LOAD_TYPE_COLORS[c.key] }} />
            {c.label}
          </div>
        ))}
      </div>

      {/* Click-to-explain drilldown */}
      {selected && (
        <div ref={drilldownRef} className="mt-5 border-t border-slate-700/50 pt-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm text-slate-300 font-semibold">
                Week of {new Date(selected.weekStart).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Click a different bar to compare weeks.
              </div>
            </div>
            <div className={`px-2.5 py-1 rounded-full border text-xs ${loadTypePillClass(selected.loadType)}`}>
              {loadTypeLabel(selected.loadType)}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-3">
              <div className="text-[11px] text-slate-500">Distance</div>
              <div className="text-sm font-semibold text-slate-100">{formatDistance(selected.distanceMeters, 1)}</div>
            </div>
            <div className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-3">
              <div className="text-[11px] text-slate-500">Activities</div>
              <div className="text-sm font-semibold text-slate-100">{selected.activityCount}</div>
            </div>
            <div className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-3">
              <div className="text-[11px] text-slate-500">Efficiency Δ</div>
              <div className={`text-sm font-semibold ${selected.efficiencyDelta < 0 ? 'text-emerald-300' : selected.efficiencyDelta > 0 ? 'text-red-300' : 'text-slate-200'}`}>
                {selected.efficiencyDelta > 0 ? '+' : ''}{selected.efficiencyDelta.toFixed(2)}
              </div>
            </div>
            <div className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-3">
              <div className="text-[11px] text-slate-500">Meaning</div>
              <div className="text-xs text-slate-300 leading-snug mt-0.5">
                {selected.loadType === 'harmful'
                  ? 'Efficiency got worse vs last week.'
                  : selected.loadType === 'productive'
                    ? 'Efficiency improved vs last week.'
                    : selected.loadType === 'wasted'
                      ? 'Efficiency stayed flat vs last week.'
                      : 'No strong signal this week.'}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Info className="w-4 h-4 text-slate-400" />
              What drove this week?
            </div>
            {explainQuery.data?.confidence ? (
              <div className="text-xs text-slate-400 mt-1">
                Signal confidence: <span className="text-slate-200 font-medium">{explainQuery.data.confidence}</span>
                {typeof explainQuery.data.metrics.volume_change_pct === 'number' ? (
                  <span className="text-slate-500">
                    {' '}
                    • Volume change: {explainQuery.data.metrics.volume_change_pct > 0 ? '+' : ''}
                    {explainQuery.data.metrics.volume_change_pct}%
                  </span>
                ) : null}
              </div>
            ) : null}
            <div className="text-xs text-slate-500 mt-1">
              Rule: harmful if ΔEF &gt; {explainQuery.data?.rule.harmful_if_delta_gt ?? 0.5}, productive if ΔEF &lt; {explainQuery.data?.rule.productive_if_delta_lt ?? -0.5}, wasted if |ΔEF| &lt; {explainQuery.data?.rule.wasted_if_abs_delta_lt ?? 0.1}.
            </div>
            {explainQuery.data?.interpretation?.taper_cutback_note ? (
              <div className="mt-2 text-xs text-slate-500">
                {explainQuery.data.interpretation.taper_cutback_note}
              </div>
            ) : null}

            {explainQuery.isLoading && (
              <div className="mt-3 text-sm text-slate-400">Analyzing drivers…</div>
            )}

            {explainQuery.isError && (
              <div className="mt-3 text-sm text-red-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                Unable to explain this week.
              </div>
            )}

            {explainQuery.data && (
              <div className="mt-3">
                {/* Always show activity-derived drivers (week vs prior week). */}
                <div className="text-xs text-slate-500 mb-2">
                  Based on {explainQuery.data.data_sources.activities_week} runs this week vs {explainQuery.data.data_sources.activities_previous_week} last week.
                </div>

                {explainQuery.data.week_vs_prev_activity_signals?.length ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {explainQuery.data.week_vs_prev_activity_signals.map((s) => {
                      const icon =
                        s.is_worse === null ? <Info className="w-4 h-4 text-slate-400" /> : s.is_worse ? <TrendingDown className="w-4 h-4 text-red-300" /> : <TrendingUp className="w-4 h-4 text-emerald-300" />;
                      const deltaColor =
                        s.is_worse === null ? 'text-slate-300' : s.is_worse ? 'text-red-300' : 'text-emerald-300';
                      return (
                        <div key={s.factor} className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2">
                              {icon}
                              <div className="text-sm font-medium text-slate-200">{s.label}</div>
                            </div>
                          </div>
                          <div className="mt-1 text-xs text-slate-500">
                            Week avg <span className="text-slate-200">{s.week_avg}</span> vs last week <span className="text-slate-200">{s.previous_week_avg}</span>
                            <span className={`ml-2 font-semibold ${deltaColor}`}>
                              ({s.delta > 0 ? '+' : ''}{s.delta})
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-sm text-slate-400">
                    Not enough activity context to explain this week (very small sample).
                  </div>
                )}

                {/* Optional: show check-in drivers only when present. */}
                {explainQuery.data.signals?.length ? (
                  <div className="mt-4">
                    <div className="text-xs text-slate-500 mb-2">
                      Extra context from check-ins ({explainQuery.data.data_sources.checkins_week} logged this week):
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {explainQuery.data.signals.map((s) => {
                        const icon = s.is_worse === null ? <Info className="w-4 h-4 text-slate-400" /> : s.is_worse ? <TrendingDown className="w-4 h-4 text-red-300" /> : <TrendingUp className="w-4 h-4 text-emerald-300" />;
                        const deltaColor =
                          s.is_worse === null ? 'text-slate-300' : s.is_worse ? 'text-red-300' : 'text-emerald-300';
                        return (
                          <div key={s.factor} className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-center gap-2">
                                {icon}
                                <div className="text-sm font-medium text-slate-200">{s.label}</div>
                              </div>
                              {s.z !== null && (
                                <div className="text-[11px] text-slate-500">z {s.z > 0 ? '+' : ''}{s.z.toFixed(2)}</div>
                              )}
                            </div>
                            <div className="mt-1 text-xs text-slate-500">
                              Week avg <span className="text-slate-200">{s.week_avg}</span> vs baseline <span className="text-slate-200">{s.baseline_avg}</span>
                              <span className={`ml-2 font-semibold ${deltaColor}`}>
                                ({s.delta > 0 ? '+' : ''}{s.delta})
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


