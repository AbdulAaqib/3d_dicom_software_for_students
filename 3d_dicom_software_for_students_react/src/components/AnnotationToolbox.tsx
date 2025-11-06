"use client";

import React from 'react';
import { useAppState } from '@/state/AppState';

export default function AnnotationToolbox() {
  const { files, tool, setTool, clearAnnotations } = useAppState();
  const disabled = files.length === 0;

  const btn = (key: Parameters<typeof setTool>[0], label: string) => (
    <button
      disabled={disabled}
      onClick={() => setTool(key)}
      className={`rounded-md px-3 py-2 text-sm font-medium transition-all duration-200 ${
        tool === key
          ? 'bg-black text-white shadow-sm dark:bg-white dark:text-black'
          : 'bg-zinc-200 text-black hover:bg-zinc-300 dark:bg-zinc-800 dark:text-white dark:hover:bg-zinc-700'
      } disabled:cursor-not-allowed disabled:opacity-60`}
    >
      {label}
    </button>
  );

  return (
    <div className="rounded-lg border border-zinc-200 p-4 shadow-sm dark:border-zinc-800">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Annotation Tools</h2>
        <button
          disabled={disabled}
          onClick={clearAnnotations}
          className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-60"
        >
          Clear All
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {btn('select', 'Select')}
        {btn('marker', 'Marker')}
        {btn('arrow', 'Arrow')}
        {btn('label', 'Label')}
      </div>
      <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
        Tip: choose a tool, then click on the slice to place it. Arrows: click start, then end.
      </p>
    </div>
  );
}
