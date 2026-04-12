'use client';

import React, { useCallback, useState } from 'react';
import { useStreamHover } from '@/lib/context/StreamHoverContext';
import { useUnits } from '@/lib/context/UnitsContext';
import RouteContext from '@/components/activities/map/RouteContext';
import ElevationProfile from '@/components/activities/map/ElevationProfile';
import { SplitsTable } from '@/components/activities/SplitsTable';
import { IntervalsView } from '@/components/activities/IntervalsView';
import { splitMidStreamIndex } from '@/lib/splits/splitStreamIndex';
import type { Split, IntervalSummary } from '@/lib/types/splits';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';

export interface ActivitySplitsTabPanelProps {
  activityId: string;
  gpsTrack: [number, number][] | null | undefined;
  startCoords: [number, number] | null | undefined;
  sportType: string;
  startTime: string;
  distanceM: number;
  durationS: number;
  temperatureF: number | null;
  weatherCondition: string | null;
  humidityPct: number | null;
  heatAdjustmentPct: number | null;
  splits: Split[] | null;
  intervalSummary: IntervalSummary | null;
  provider?: string | null;
  deviceName?: string | null;
  stream: StreamPoint[] | null | undefined;
  splitTableRowRefs: React.MutableRefObject<Map<number, HTMLTableRowElement>>;
  showMap: boolean;
}

export function ActivitySplitsTabPanel({
  activityId,
  gpsTrack,
  startCoords,
  sportType,
  startTime,
  distanceM,
  durationS,
  temperatureF,
  weatherCondition,
  humidityPct,
  heatAdjustmentPct,
  splits,
  intervalSummary,
  provider,
  deviceName,
  stream,
  splitTableRowRefs,
  showMap,
}: ActivitySplitsTabPanelProps) {
  const { setHoveredIndex } = useStreamHover();
  const { units } = useUnits();
  const structured = Boolean(intervalSummary?.is_structured);
  const [splitsMode, setSplitsMode] = useState<'intervals' | 'miles'>(() =>
    structured ? 'intervals' : 'miles',
  );

  const handleSplitHover = useCallback(
    (index: number | null) => {
      if (index == null) {
        setHoveredIndex(null);
        return;
      }
      const mid = splitMidStreamIndex(splits, stream ?? null, index);
      if (mid != null) setHoveredIndex(mid);
    },
    [splits, stream, setHoveredIndex],
  );

  let splitsBlock: React.ReactNode;
  if (!splits?.length) {
    splitsBlock = (
      <p className="text-slate-500 text-sm py-6 px-2">No split data for this activity.</p>
    );
  } else {
    const toggle =
      structured && intervalSummary ? (
        <div className="flex gap-2 mb-2" role="group" aria-label="Splits view mode">
          <button
            type="button"
            onClick={() => setSplitsMode('intervals')}
            className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${
              splitsMode === 'intervals'
                ? 'bg-orange-500/20 border-orange-500/50 text-orange-200'
                : 'border-slate-600/50 text-slate-400 hover:border-slate-500'
            }`}
          >
            Intervals
          </button>
          <button
            type="button"
            onClick={() => setSplitsMode('miles')}
            className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${
              splitsMode === 'miles'
                ? 'bg-orange-500/20 border-orange-500/50 text-orange-200'
                : 'border-slate-600/50 text-slate-400 hover:border-slate-500'
            }`}
          >
            Mile splits
          </button>
        </div>
      ) : null;

    if (structured && intervalSummary && splitsMode === 'intervals') {
      splitsBlock = (
        <>
          {toggle}
          <IntervalsView
            splits={splits}
            intervalSummary={intervalSummary}
            provider={provider}
            deviceName={deviceName}
            onRowHover={handleSplitHover}
            rowRefs={splitTableRowRefs}
          />
        </>
      );
    } else {
      splitsBlock = (
        <>
          {toggle}
          <SplitsTable
            splits={splits}
            provider={provider}
            deviceName={deviceName}
            onRowHover={handleSplitHover}
            rowRefs={splitTableRowRefs}
          />
        </>
      );
    }
  }

  const hasTrack = Boolean(gpsTrack && gpsTrack.length > 1);
  const mapElevation =
    hasTrack && showMap ? (
      <div className="space-y-1">
        <RouteContext
          activityId={activityId}
          track={gpsTrack!}
          startCoords={startCoords}
          sportType={sportType || 'run'}
          startTime={startTime}
          streamPoints={stream}
          weather={{
            temperature_f: temperatureF,
            weather_condition: weatherCondition,
            humidity_pct: humidityPct,
            heat_adjustment_pct: heatAdjustmentPct,
          }}
          distanceM={distanceM}
          durationS={durationS}
          heatAdjustmentPct={heatAdjustmentPct}
          mapAspectRatio="16 / 9"
        />
        {stream && stream.length > 1 && (
          <ElevationProfile points={stream} unitSystem={units} />
        )}
      </div>
    ) : null;

  return (
    <div
      className={
        hasTrack && showMap
          ? 'flex flex-col md:flex-row gap-4 md:items-start'
          : ''
      }
    >
      {hasTrack && showMap ? (
        <>
          <div className="w-full md:w-[60%] min-w-0 order-2 md:order-1 md:max-h-[min(70vh,720px)] md:overflow-y-auto pr-0 md:pr-1">
            {splitsBlock}
          </div>
          <div className="w-full md:w-[40%] shrink-0 order-1 md:order-2">{mapElevation}</div>
        </>
      ) : (
        <div className="w-full">{splitsBlock}</div>
      )}
    </div>
  );
}
