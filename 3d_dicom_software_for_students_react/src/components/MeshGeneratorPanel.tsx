"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAppState } from "@/state/AppState";

interface WorkerMessage {
  positions?: ArrayBuffer;
  normals?: ArrayBuffer;
  indices?: ArrayBuffer;
  error?: string;
  empty?: boolean;
  progress?: number;
  bbox?: {
    min: [number, number, number];
    max: [number, number, number];
  };
}

export default function MeshGeneratorPanel() {
  const { volumeData, volume, generatedMesh, setGeneratedMesh } = useAppState();
  const [isoValue, setIsoValue] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [progress, setProgress] = useState<number | null>(null);
  const [logText, setLogText] = useState<string>("");

  const worker = useMemo(() => {
    if (typeof window === "undefined") return undefined;
    return new Worker(new URL("../workers/marchingCubes.worker.ts", import.meta.url));
  }, []);

  const minIso = volumeData?.voxelMin ?? 0;
  const maxIso = volumeData?.voxelMax ?? 1;

  useEffect(() => {
    if (!worker) return;
    const handler = (event: MessageEvent<WorkerMessage>) => {
      const { progress: progressValue } = event.data;
      if (typeof progressValue === "number") {
        setProgress(progressValue);
        setLogText((prev) => {
          const pct = Math.min(100, Math.max(0, progressValue * 100));
          return `${prev}Progress: ${pct.toFixed(1)}%\n`;
        });
        return;
      }
      if (event.data.error) {
        setError(event.data.error);
        setLoading(false);
        setProgress(null);
        setLogText((prev) => `${prev}Error: ${event.data.error}\n`);
        return;
      }
      if ((event.data as any).empty) {
        setGeneratedMesh(undefined);
        setError("No surface found at this iso-value. Try a lower threshold or adjust windowing.");
        setLoading(false);
        setProgress(null);
        setLogText((prev) => `${prev}Result: No surface found at this iso-value.\n`);
        return;
      }
      if (event.data.positions && event.data.indices && event.data.normals) {
        const positions = new Float32Array(event.data.positions);
        const normals = new Float32Array(event.data.normals);
        const indices = new Uint32Array(event.data.indices);
        setGeneratedMesh({ positions, normals, indices });
        setLoading(false);
        setError(undefined);
        setProgress(null);
        if (event.data.bbox) {
          const { min, max } = event.data.bbox;
          setLogText(
            (prev) =>
              `${prev}Completed. Bounding box:\n  min = (${min.map((v) => v.toFixed(2)).join(", ")})\n  max = (${max
                .map((v) => v.toFixed(2))
                .join(", ")})\n`
          );
        } else {
          setLogText((prev) => `${prev}Completed.\n`);
        }
        if (event.data.bbox) {
          console.info("[mesh bbox]", event.data.bbox);
        }
      }
    };
    worker.addEventListener("message", handler);
    return () => {
      worker.removeEventListener("message", handler);
      worker.terminate();
    };
  }, [worker, setGeneratedMesh]);

  useEffect(() => {
    if (!volumeData?.voxels || volumeData.voxelMin == null || volumeData.voxelMax == null) {
      setIsoValue(null);
      return;
    }
    const initial = volumeData.autoIso ?? (volumeData.voxelMin + volumeData.voxelMax) / 2;
    setIsoValue(initial);
  }, [volumeData?.voxels, volumeData?.voxelMin, volumeData?.voxelMax, volumeData?.autoIso]);

  const disabled =
    !volumeData?.voxels ||
    !volumeData.width ||
    !volumeData.height ||
    !volumeData.depth ||
    volumeData.voxelMin == null ||
    volumeData.voxelMax == null ||
    isoValue == null ||
    !worker ||
    loading;

  const onGenerate = useCallback(() => {
    if (!volumeData?.voxels || isoValue == null || !worker) return;
    setLoading(true);
    setProgress(0);
    setError(undefined);
    const isoDisplay = isoValue.toFixed(2);
    setLogText(`Starting mesh generation (iso ${isoDisplay})...\n`);
    setGeneratedMesh(undefined);
    worker.postMessage({
      voxels: volumeData.voxels,
      dims: [volumeData.width, volumeData.height, volumeData.depth],
      isoValue,
      spacing: volumeData.spacing ?? [1, 1, 1],
      origin: volume.origin ?? [0, 0, 0],
      direction: volume.orientation,
      voxelMin: volumeData.voxelMin,
      voxelMax: volumeData.voxelMax,
    });
  }, [volumeData, volume, worker, isoValue, setGeneratedMesh]);

  const onClear = useCallback(() => {
    setGeneratedMesh(undefined);
    setProgress(null);
    setLogText("");
  }, [setGeneratedMesh]);

  const handleIsoChange: React.ChangeEventHandler<HTMLInputElement> = useCallback((e) => {
    setIsoValue(Number(e.target.value));
  }, []);

  const handleIsoInputChange: React.ChangeEventHandler<HTMLInputElement> = useCallback(
    (e) => {
      const raw = e.target.value;
      if (raw === "") {
        setIsoValue(null);
        return;
      }
      const parsed = Number(raw);
      if (!Number.isFinite(parsed)) return;
      const clamped = Math.min(maxIso, Math.max(minIso, parsed));
      setIsoValue(clamped);
    },
    [minIso, maxIso]
  );

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Mesh Generator</h2>
        <button
          onClick={onClear}
          disabled={!generatedMesh}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Clear Mesh
        </button>
      </div>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Generate a 3D surface from the loaded volume using marching cubes.
      </p>
      <div className="mt-3">
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Iso-value ({volumeData?.voxelMin?.toFixed(1) ?? "?"} to {volumeData?.voxelMax?.toFixed(1) ?? "?"})
        </label>
        <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
          Suggested: {volumeData?.autoIso?.toFixed(1) ?? "n/a"}
          {" "}
          <button
            type="button"
            onClick={() => {
              if (volumeData?.autoIso != null) {
                setIsoValue(volumeData.autoIso);
              }
            }}
            className="ml-2 rounded border border-emerald-500 px-2 py-0.5 text-xs font-medium text-emerald-600 hover:bg-emerald-50 dark:text-emerald-300"
            disabled={volumeData?.autoIso == null}
          >
            Use Auto
          </button>
        </div>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <input
            type="range"
            min={Math.floor(minIso)}
            max={Math.ceil(maxIso)}
            value={isoValue ?? minIso}
            step={Math.max(0.1, Math.abs(maxIso - minIso) / 200)}
            onChange={handleIsoChange}
            className="flex-1"
            disabled={volumeData?.voxelMin == null || volumeData?.voxelMax == null}
          />
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={isoValue ?? ""}
              onChange={handleIsoInputChange}
              min={volumeData?.voxelMin ?? undefined}
              max={volumeData?.voxelMax ?? undefined}
              step={Math.max(0.1, Math.abs(maxIso - minIso) / 200)}
              className="w-28 rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-700 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
              placeholder="Type value"
              disabled={volumeData?.voxelMin == null || volumeData?.voxelMax == null}
            />
            <span className="text-sm text-zinc-600 dark:text-zinc-400">HU</span>
          </div>
        </div>
      </div>
      <button
        onClick={onGenerate}
        disabled={disabled}
        className="mt-3 w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Generating…" : "Generate Mesh"}
      </button>
      {loading && (
        <div className="mt-3">
          <div className="h-2 w-full rounded-full bg-zinc-200 dark:bg-zinc-800">
            <div
              className="h-2 rounded-full bg-emerald-500 transition-[width]"
              style={{ width: `${Math.min(100, Math.max(0, Math.round((progress ?? 0) * 100)))}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
            Generating mesh… {Math.min(100, Math.max(0, Math.round((progress ?? 0) * 100)))}%
          </p>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Mesh Logs</h3>
          <button
            type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(logText || "No logs yet.");
              } catch {
                // fallback: no-op
              }
            }}
            className="text-xs font-medium text-emerald-600 hover:underline disabled:opacity-60"
            disabled={!logText}
          >
            Copy
          </button>
        </div>
        <pre className="mt-2 max-h-40 overflow-y-auto rounded-md border border-zinc-200 bg-zinc-50 p-2 text-xs font-mono text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
          {logText || "No logs yet."}
        </pre>
      </div>
      {!volumeData?.voxels && (
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">Load a DICOM series first.</p>
      )}
      {volumeData?.voxelMin != null && volumeData?.voxelMax != null && (
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
          Range: {volumeData.voxelMin.toFixed(1)}
          {" – "}
          {volumeData.voxelMax.toFixed(1)}
        </p>
      )}
    </div>
  );
}
