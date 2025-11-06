"use client";

import React, { useMemo } from 'react';
import { useAppState } from '@/state/AppState';

export default function SliceControls() {
  const { volumeData, sliceIndex, setSliceIndex } = useAppState();

  const max = useMemo(() => (volumeData ? volumeData.depth - 1 : 0), [volumeData]);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Slice Controls</h2>
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-md border px-2 py-1 dark:border-zinc-700">Slice {sliceIndex + 1}{volumeData ? ` / ${volumeData.depth}` : ''}</span>
        </div>
      </div>
      <div className="mt-3">
        <input
          type="range"
          min={0}
          max={max}
          value={sliceIndex}
          onChange={(e) => setSliceIndex(Number(e.target.value))}
          className="w-full"
        />
      </div>

    </div>
  );
}
