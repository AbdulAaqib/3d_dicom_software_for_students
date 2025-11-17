"use client";

import React, { useCallback, useState } from "react";
import { exportAnnotationsToSR } from "@/lib/dicom/exportSr";
import { useAppState } from "@/state/AppState";

export default function ExportDICOMSRButton() {
  const { annotations, volume, study, parsedSeries } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const onExport = useCallback(async () => {
    setError(undefined);
    if (annotations.length === 0) {
      setError("No annotations to export.");
      return;
    }
    try {
      setLoading(true);
      const blob = await exportAnnotationsToSR({ annotations, volume, study, parsedSeries });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `annotations-${new Date().toISOString().slice(0, 19)}.dcm`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      console.error(e);
      const msg = e instanceof Error ? e.message : "Failed to export DICOM SR";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [annotations, parsedSeries, study, volume]);

  return (
    <div className="space-y-2">
      <button
        onClick={onExport}
        disabled={loading}
        className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Exporting…" : "Export DICOM SR"}
      </button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}



