'use client';

import dynamic from 'next/dynamic';
import { ComponentProps } from 'react';

const ActivityMapInner = dynamic(() => import('./ActivityMapInner'), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg overflow-hidden border border-slate-700/30 bg-slate-800/30 animate-pulse" style={{ aspectRatio: '4 / 3', maxHeight: 340 }} />
  ),
});

type ActivityMapProps = ComponentProps<typeof ActivityMapInner>;

export default function ActivityMap(props: ActivityMapProps) {
  return <ActivityMapInner {...props} />;
}
