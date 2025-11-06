"use client";

import React from 'react';
import { useAppState } from '@/state/AppState';

export default function AnnotationList() {
  const { annotations, deleteAnnotation } = useAppState();

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-3 text-lg font-semibold">Annotations</h2>
      {annotations.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">No annotations yet.</p>
      ) : (
        <ul className="space-y-2">
          {annotations.map((a) => (
            <li key={a.id} className="flex items-center justify-between rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
              <div className="flex flex-col">
                <span className="font-medium">{a.type}</span>
                <span className="text-xs text-zinc-500">pos: [{a.position.map((v) => v.toFixed(2)).join(', ')}]</span>
                {a.arrowTo && (
                  <span className="text-xs text-zinc-500">to: [{a.arrowTo.map((v) => v.toFixed(2)).join(', ')}]</span>
                )}
                {a.labelText && (
                  <span className="text-xs text-zinc-500">label: {a.labelText}</span>
                )}
              </div>
              <button
                onClick={() => deleteAnnotation(a.id)}
                className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
