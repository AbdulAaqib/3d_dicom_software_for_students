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

export default function ParseButton() {
  const { files, setFiles, setVolume, setVolumeData } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const parseFromUploads = useCallback(async () => {
    setError(undefined);
    setLoading(true);
    try {
      const rawFiles = files.map((f) => f.file);
      const series: ParsedSeries = await parseDicomFiles(rawFiles);
      const frames8 = await build8BitStack(series);
      const [cols, rows, depth] = series.dimensions;
      setVolume({ dimensions: [cols, rows, depth], spacing: series.spacing });
      setVolumeData({ width: cols, height: rows, depth, frames8, spacing: series.spacing });
    } catch (e: unknown) {
      console.error(e);
      const message = e instanceof Error ? e.message : 'Parse error';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [files, setVolume, setVolumeData]);

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
      const frames8 = await build8BitStack(series);
      const [cols, rows, depth] = series.dimensions;
      setVolume({ dimensions: [cols, rows, depth], spacing: series.spacing });
      setVolumeData({ width: cols, height: rows, depth, frames8, spacing: series.spacing });
    } catch (e: unknown) {
      console.error(e);
      const message = e instanceof Error ? e.message : 'Parse error';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [setFiles, setVolume, setVolumeData]);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Parse</h2>
        <div className="flex gap-2">
          <button
            onClick={parseFromUploads}
            disabled={loading}
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
