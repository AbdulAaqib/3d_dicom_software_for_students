"use client";

import React, { useCallback } from 'react';
import { useAppState } from '@/state/AppState';

export default function UploadPanel() {
  const { files, setFiles } = useAppState();

  const onChange = useCallback<React.ChangeEventHandler<HTMLInputElement>>(
    (e) => {
      const fl = e.target.files;
      if (!fl || fl.length === 0) return;
      setFiles(Array.from(fl));
    },
    [setFiles]
  );

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-2 text-lg font-semibold">Upload DICOM Files</h2>
      <input
        type="file"
        multiple
        accept=".dcm,application/dicom,application/dicom+json"
        onChange={onChange}
        className="block w-full text-sm text-zinc-700 file:mr-4 file:rounded-md file:border-0 file:bg-zinc-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-zinc-700 hover:file:bg-zinc-200 dark:text-zinc-300 dark:file:bg-zinc-900 dark:file:text-zinc-200 dark:hover:file:bg-zinc-800"
      />
      {files.length > 0 && (
        <div className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
          Selected: {files.length} file(s)
        </div>
      )}
    </div>
  );
}
