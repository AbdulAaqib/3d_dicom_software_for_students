"use client";

import React, { useCallback } from "react";
import { useAppState } from "@/state/AppState";

export default function ViewerSettingsPanel() {
  const { viewerSettings, updateViewerSettings } = useAppState();

  const onOpacityChange: React.ChangeEventHandler<HTMLInputElement> = useCallback((e) => {
    const value = Number(e.target.value) / 100;
    updateViewerSettings({ axialOpacity: value });
  }, [updateViewerSettings]);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="text-lg font-semibold">Viewer Settings</h2>
      <label className="mt-3 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Axial Slice Opacity
      </label>
      <div className="mt-2 flex items-center gap-3">
        <input
          type="range"
          min={20}
          max={100}
          value={Math.round(viewerSettings.axialOpacity * 100)}
          onChange={onOpacityChange}
          className="flex-1"
        />
        <span className="w-10 text-right text-sm text-zinc-600 dark:text-zinc-400">
          {Math.round(viewerSettings.axialOpacity * 100)}%
        </span>
      </div>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        Lower opacity makes annotations behind the current slice easier to see.
      </p>
    </div>
  );
}



