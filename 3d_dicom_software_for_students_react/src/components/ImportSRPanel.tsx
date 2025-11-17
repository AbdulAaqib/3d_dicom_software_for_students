"use client";

import React, { useCallback, useState } from "react";
import dcmjs from "dcmjs";
import { useAppState } from "@/state/AppState";
import { patientToVoxel, voxelToNormalized } from "@/lib/dicom/geometry";

const { DicomMessage, DicomMetaDictionary } = dcmjs.data;

function parseContentSequence(dataset: any): any[] {
  const seq = dataset.ContentSequence || [];
  return Array.isArray(seq) ? seq : [seq];
}

function clampNorm(coord: [number, number, number]): [number, number, number] {
  return [
    Math.min(Math.max(coord[0], 0), 1),
    Math.min(Math.max(coord[1], 0), 1),
    Math.min(Math.max(coord[2], 0), 1),
  ];
}

export default function ImportSRPanel() {
  const { volume, clearAnnotations, addAnnotation } = useAppState();
  const [error, setError] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    setError(undefined);
    if (!volume?.dimensions || !volume.spacing || !volume.origin || !volume.orientation) {
      setError("Load a DICOM series before importing SR.");
      return;
    }
    try {
      setLoading(true);
      const arrayBuffer = await file.arrayBuffer();
      const byteArray = new Uint8Array(arrayBuffer);
      const message = DicomMessage.readFile(byteArray);
      const dataset = DicomMetaDictionary.naturalizeDataset(message.dict);
      const items = parseContentSequence(dataset);

      const dims = volume.dimensions as [number, number, number];
      const annotations: { type: "marker" | "arrow" | "label"; position: [number, number, number]; arrowTo?: [number, number, number]; labelText?: string }[] = [];
      let lastIndex = -1;

      items.forEach((item: any) => {
        if (!item) return;
        if (item.ValueType === "SCOORD3D" && Array.isArray(item.GraphicData)) {
          const coords = item.GraphicData;
          const type = item.GraphicType === "POLYLINE" && coords.length >= 6 ? "arrow" : "marker";

          const startPatient: [number, number, number] = [coords[0], coords[1], coords[2]];
          const startVoxel = patientToVoxel(startPatient, volume) as [number, number, number];
          const startNorm = clampNorm(voxelToNormalized(startVoxel, dims) as [number, number, number]);

          let arrowTo: [number, number, number] | undefined;
          if (type === "arrow" && coords.length >= 6) {
            const endPatient: [number, number, number] = [coords[3], coords[4], coords[5]];
            const endVoxel = patientToVoxel(endPatient, volume) as [number, number, number];
            arrowTo = clampNorm(voxelToNormalized(endVoxel, dims) as [number, number, number]);
          }

          annotations.push({ type: type === "arrow" ? "arrow" : "marker", position: startNorm, arrowTo });
          lastIndex = annotations.length - 1;
        } else if (item.ValueType === "TEXT" && lastIndex >= 0 && item.TextValue) {
          annotations[lastIndex] = {
            ...annotations[lastIndex],
            type: "label",
            labelText: String(item.TextValue),
          };
        }
      });

      if (!annotations.length) {
        setError("No annotations found in SR.");
        return;
      }

      clearAnnotations();
      annotations.forEach((ann) => {
        addAnnotation({
          type: ann.type,
          position: ann.position,
          arrowTo: ann.arrowTo,
          labelText: ann.labelText,
        });
      });
    } catch (e: unknown) {
      console.error(e);
      const message = e instanceof Error ? e.message : "Failed to import SR";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [addAnnotation, clearAnnotations, volume]);

  const onChange: React.ChangeEventHandler<HTMLInputElement> = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      void handleFile(file);
      e.target.value = "";
    }
  }, [handleFile]);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="text-lg font-semibold">Import DICOM SR</h2>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Load a Structured Report to restore saved annotations.
      </p>
      <div className="mt-3">
        <input
          type="file"
          accept=".dcm,application/dicom"
          onChange={onChange}
          disabled={loading}
          className="block w-full text-sm text-zinc-700 file:mr-4 file:rounded-md file:border-0 file:bg-zinc-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-zinc-700 hover:file:bg-zinc-200 dark:text-zinc-300 dark:file:bg-zinc-900 dark:file:text-zinc-200 dark:hover:file:bg-zinc-800 disabled:opacity-60"
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
