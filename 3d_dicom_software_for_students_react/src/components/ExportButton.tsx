"use client";

import React, { useCallback } from 'react';
import { useAppState } from '@/state/AppState';

export default function ExportButton() {
  const { annotations, exportAnnotations } = useAppState();
  const disabled = annotations.length === 0;

  const onExport = useCallback(() => {
    const json = exportAnnotations();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `annotations-${new Date().toISOString().slice(0, 19)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [exportAnnotations]);

  return (
    <button
      disabled={disabled}
      onClick={onExport}
      className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-400 hover:bg-emerald-700"
    >
      Export JSON
    </button>
  );
}
