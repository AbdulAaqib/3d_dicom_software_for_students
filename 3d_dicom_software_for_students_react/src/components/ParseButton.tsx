"use client";

import React, { useCallback, useState } from 'react';
import { useAppState } from '@/state/AppState';
import { build8BitStack, parseDicomFiles, type ParsedSeries } from '@/lib/dicom/parseDicom';

async function fetchPublicFile(path: string): Promise<File> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to fetch ${path}`);
  const blob = await res.blob();
  return new File([blob], path.split('/').pop() || 'file.dcm');
}

function orientationToMatrix(orientation6?: number[]): number[] | undefined {
  if (!orientation6 || orientation6.length !== 6) return undefined;
  const r = orientation6.slice(0, 3) as [number, number, number];
  const c = orientation6.slice(3, 6) as [number, number, number];
  const norm = (v: [number, number, number]) => {
    const len = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / len, v[1] / len, v[2] / len] as [number, number, number];
  };
  const row = norm(r);
  const col = norm(c);
  const s: [number, number, number] = [
    row[1] * col[2] - row[2] * col[1],
    row[2] * col[0] - row[0] * col[2],
    row[0] * col[1] - row[1] * col[0],
  ];
  const slice = norm(s);
  return [...row, ...col, ...slice];
}

function computeAutoIso(data: Float32Array, min: number, max: number): number {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) {
    return (min + max) / 2 || 0;
  }
  const binCount = 512;
  const hist = new Float64Array(binCount);
  const range = max - min || 1;
  const scale = (binCount - 1) / range;
  for (let i = 0; i < data.length; i++) {
    const value = data[i];
    const idx = Math.max(0, Math.min(binCount - 1, Math.floor((value - min) * scale)));
    hist[idx] += 1;
  }

  const total = data.length;
  if (total === 0) {
    return (min + max) / 2 || 0;
  }

  let sumTotal = 0;
  for (let i = 0; i < binCount; i++) {
    sumTotal += i * hist[i];
  }

  let sumBackground = 0;
  let weightBackground = 0;
  let varMax = -1;
  let threshold = 0;

  for (let i = 0; i < binCount; i++) {
    weightBackground += hist[i];
    if (weightBackground === 0) continue;

    const weightForeground = total - weightBackground;
    if (weightForeground === 0) break;

    sumBackground += i * hist[i];

    const meanBackground = sumBackground / weightBackground;
    const meanForeground = (sumTotal - sumBackground) / weightForeground;

    const varianceBetween = weightBackground * weightForeground * (meanBackground - meanForeground) ** 2;

    if (varianceBetween > varMax) {
      varMax = varianceBetween;
      threshold = i;
    }
  }

  const iso = min + (threshold / (binCount - 1)) * range;
  return Number.isFinite(iso) ? iso : (min + max) / 2 || 0;
}

export default function ParseButton() {
  const { files, setFiles, setVolume, setVolumeData, setStudy, setParsedSeries, setGeneratedMesh } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const handleSeries = useCallback(async (series: ParsedSeries) => {
    setParsedSeries(series);
    const frames8 = await build8BitStack(series);
    const [cols, rows, depth] = series.dimensions;

    let rawVolume = new Float32Array(cols * rows * depth);
    let voxelMin = Number.POSITIVE_INFINITY;
    let voxelMax = Number.NEGATIVE_INFINITY;

    for (let z = 0; z < depth; z++) {
      const slice = series.slices[z];
      const slope = slice.rescaleSlope ?? 1;
      const intercept = slice.rescaleIntercept ?? 0;
      if (slice.pixelData) {
        let sliceArray: Float32Array;
        if (slice.bitsAllocated === 16) {
          const view = slice.pixelRepresentation === 1 ? new Int16Array(slice.pixelData) : new Uint16Array(slice.pixelData);
          sliceArray = new Float32Array(view.length);
          for (let i = 0; i < view.length; i++) {
            sliceArray[i] = view[i] * slope + intercept;
          }
        } else {
          const view = slice.pixelRepresentation === 1 ? new Int8Array(slice.pixelData) : new Uint8Array(slice.pixelData);
          sliceArray = new Float32Array(view.length);
          for (let i = 0; i < view.length; i++) {
            sliceArray[i] = view[i] * slope + intercept;
          }
        }
        rawVolume.set(sliceArray, z * cols * rows);
        for (let i = 0; i < sliceArray.length; i++) {
          const v = sliceArray[i];
          if (v < voxelMin) voxelMin = v;
          if (v > voxelMax) voxelMax = v;
        }
      } else {
        const frame = frames8[z];
        for (let i = 0; i < frame.length; i++) {
          const v = frame[i];
          rawVolume[z * cols * rows + i] = v;
          if (v < voxelMin) voxelMin = v;
          if (v > voxelMax) voxelMax = v;
        }
      }
    }

    const orientationMatrix = orientationToMatrix(series.orientation);

    if (!Number.isFinite(voxelMin) || !Number.isFinite(voxelMax)) {
      voxelMin = 0;
      voxelMax = 0;
    }

    const autoIso = computeAutoIso(rawVolume, voxelMin, voxelMax);

    setVolume({
      dimensions: [cols, rows, depth],
      spacing: series.spacing,
      orientation: orientationMatrix,
      origin: series.origin,
    });
    setVolumeData({
      width: cols,
      height: rows,
      depth,
      frames8,
      spacing: series.spacing,
      voxels: rawVolume,
      voxelMin,
      voxelMax,
      autoIso,
    });
    setStudy({
      patientId: series.patientId,
      studyInstanceUID: series.studyInstanceUID,
      seriesInstanceUID: series.seriesInstanceUID,
      modality: series.modality,
      studyDate: series.studyDate,
      frameOfReferenceUID: series.frameOfReferenceUID,
    });
    setGeneratedMesh(undefined);
  }, [setParsedSeries, setVolume, setVolumeData, setStudy, setGeneratedMesh]);

  const parseFromUploads = useCallback(async () => {
    if (!files || files.length === 0) {
      setError('Upload DICOM files before parsing.');
      return;
    }
    setError(undefined);
    setLoading(true);
    try {
      const rawFiles = files.map((f) => f.file);
      const series: ParsedSeries = await parseDicomFiles(rawFiles);
      await handleSeries(series);
    } catch (e: unknown) {
      console.error(e);
      const message = e instanceof Error ? e.message : 'Parse error';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [files, handleSeries]);

  const parseFromPublicExamples = useCallback(async () => {
    setError(undefined);
    setLoading(true);
    try {
      // Load the sample files we copied into public/dcm_examples
      const basenames = ['0002.DCM', '0003.DCM', '0004.DCM', '0009.DCM', '0012.DCM'];
      const filePromises = basenames.map((n) => fetchPublicFile(`/dcm_examples/${n}`));
      const publicFiles = await Promise.all(filePromises);
      setFiles(publicFiles);
      const series: ParsedSeries = await parseDicomFiles(publicFiles);
      await handleSeries(series);
    } catch (e: unknown) {
      console.error(e);
      const message = e instanceof Error ? e.message : 'Parse error';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [handleSeries, setFiles]);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Parse</h2>
        <div className="flex gap-2">
          <button
            onClick={parseFromUploads}
            disabled={loading || files.length === 0}
            className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {loading ? 'Parsing…' : 'Parse Uploads'}
          </button>
          <button
            onClick={parseFromPublicExamples}
            disabled={loading}
            className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {loading ? 'Parsing…' : 'Load Samples'}
          </button>
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">MVP supports uncompressed DICOM only; compressed PixelData will fail.</p>
    </div>
  );
}
