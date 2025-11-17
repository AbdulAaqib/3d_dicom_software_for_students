"use client";

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { Annotation, VolumeMeta, AnnotationExport, StudyMeta, MeshData } from '@/types/annotation';
import type { ParsedSeries } from '@/lib/dicom/parseDicom';

export interface LoadedDicomFile {
  name: string;
  size: number;
  type: string;
  lastModified: number;
  file: File;
}

export interface VolumeData {
  width: number;
  height: number;
  depth: number;
  frames8: Uint8ClampedArray[]; // each length = width*height
  spacing?: [number, number, number];
  voxels?: Float32Array; // flattened volume (width*height*depth)
  voxelMin?: number;
  voxelMax?: number;
  autoIso?: number;
}

type Tool = 'select' | 'marker' | 'arrow' | 'label';

export interface ViewerSettings {
  axialOpacity: number;
  showSidebar: boolean;
}

interface AppState {
  files: LoadedDicomFile[];
  setFiles: (files: File[] | LoadedDicomFile[]) => void;

  annotations: Annotation[];
  addAnnotation: (a: Omit<Annotation, 'id' | 'createdAt'> & { id?: string }) => void;
  updateAnnotation: (id: string, patch: Partial<Annotation>) => void;
  deleteAnnotation: (id: string) => void;
  clearAnnotations: () => void;

  selectedAnnotationId?: string;
  setSelectedAnnotationId: (id?: string) => void;

  study?: StudyMeta;
  setStudy: (meta?: StudyMeta) => void;
  volume: VolumeMeta;
  setVolume: (v: Partial<VolumeMeta>) => void;

  parsedSeries?: ParsedSeries;
  setParsedSeries: (s?: ParsedSeries) => void;

  volumeData?: VolumeData;
  setVolumeData: (v?: VolumeData) => void;

  sliceIndex: number;
  setSliceIndex: (i: number) => void;

  tool: Tool;
  setTool: (t: Tool) => void;

  viewerSettings: ViewerSettings;
  updateViewerSettings: (patch: Partial<ViewerSettings>) => void;

  generatedMesh?: MeshData;
  setGeneratedMesh: (mesh?: MeshData) => void;

  exportAnnotations: () => string; // returns JSON string
}

const AppStateContext = createContext<AppState | undefined>(undefined);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [files, _setFiles] = useState<LoadedDicomFile[]>([]);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [volume, _setVolume] = useState<VolumeMeta>({});
  const [parsedSeries, _setParsedSeries] = useState<ParsedSeries | undefined>(undefined);
  const [volumeData, _setVolumeData] = useState<VolumeData | undefined>(undefined);
  const [sliceIndex, _setSliceIndex] = useState(0);
  const [tool, _setTool] = useState<Tool>('select');
  const [selectedAnnotationId, _setSelectedAnnotationId] = useState<string | undefined>(undefined);
  const [study, _setStudy] = useState<StudyMeta | undefined>(undefined);
  const [viewerSettings, setViewerSettings] = useState<ViewerSettings>({ axialOpacity: 0.9, showSidebar: true });
  const [generatedMesh, setGeneratedMeshState] = useState<MeshData | undefined>(undefined);

  const setFiles = useCallback((input: File[] | LoadedDicomFile[]) => {
    const arr = input as Array<LoadedDicomFile | File>;
    const mapped: LoadedDicomFile[] = arr.map((f) =>
      ('file' in f)
        ? (f as LoadedDicomFile)
        : {
            name: (f as File).name,
            size: (f as File).size,
            type: (f as File).type,
            lastModified: (f as File).lastModified,
            file: f as File,
          }
    );
    _setFiles(mapped);
  }, []);

  const addAnnotation: AppState['addAnnotation'] = useCallback((a) => {
    const id = a.id ?? crypto.randomUUID();
    const createdAt = new Date().toISOString();
    setAnnotations((prev) => [...prev, { ...a, id, createdAt } as Annotation]);
    _setSelectedAnnotationId(id);
  }, []);

  const updateAnnotation: AppState['updateAnnotation'] = useCallback((id, patch) => {
    setAnnotations((prev) => prev.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  }, []);

  const deleteAnnotation: AppState['deleteAnnotation'] = useCallback((id) => {
    setAnnotations((prev) => prev.filter((x) => x.id !== id));
    _setSelectedAnnotationId((sel) => (sel === id ? undefined : sel));
  }, []);

  const clearAnnotations = useCallback(() => {
    setAnnotations([]);
    _setSelectedAnnotationId(undefined);
  }, []);

  const setSelectedAnnotationId = useCallback((id?: string) => _setSelectedAnnotationId(id), []);

  const setStudy = useCallback((meta?: StudyMeta) => {
    _setStudy(meta);
  }, []);

  const setVolume = useCallback((v: Partial<VolumeMeta>) => {
    _setVolume((prev) => ({ ...prev, ...v }));
  }, []);

  const setParsedSeries = useCallback((s?: ParsedSeries) => _setParsedSeries(s), []);

  const setVolumeData = useCallback((v?: VolumeData) => {
    _setVolumeData(v);
    if (v) {
      _setSliceIndex(Math.min(Math.max(0, Math.floor(v.depth / 2)), v.depth - 1));
    } else {
      _setSliceIndex(0);
    }
  }, []);

  const setSliceIndex = useCallback((i: number) => {
    _setSliceIndex(() => (volumeData ? Math.max(0, Math.min(volumeData.depth - 1, i)) : 0));
  }, [volumeData]);

  const setTool = useCallback((t: Tool) => _setTool(t), []);

  const updateViewerSettings = useCallback((patch: Partial<ViewerSettings>) => {
    setViewerSettings((prev) => ({ ...prev, ...patch }));
  }, []);

  const setGeneratedMesh = useCallback((mesh?: MeshData) => {
    setGeneratedMeshState(mesh);
  }, []);

  const exportAnnotations = useCallback(() => {
    const payload: AnnotationExport = {
      version: '1.0',
      study,
      volume,
      annotations,
      exportedAt: new Date().toISOString(),
    };
    return JSON.stringify(payload, null, 2);
  }, [annotations, study, volume]);

  const value = useMemo<AppState>(() => ({
    files,
    setFiles,
    annotations,
    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    clearAnnotations,
    selectedAnnotationId,
    setSelectedAnnotationId,
    study,
    setStudy,
    volume,
    setVolume,
    parsedSeries,
    setParsedSeries,
    volumeData,
    setVolumeData,
    sliceIndex,
    setSliceIndex,
    tool,
    setTool,
    viewerSettings,
    updateViewerSettings,
    generatedMesh,
    setGeneratedMesh,
    exportAnnotations,
  }), [files, setFiles, annotations, addAnnotation, updateAnnotation, deleteAnnotation, clearAnnotations, selectedAnnotationId, setSelectedAnnotationId, study, setStudy, volume, setVolume, parsedSeries, setParsedSeries, volumeData, setVolumeData, sliceIndex, setSliceIndex, tool, setTool, viewerSettings, updateViewerSettings, generatedMesh, setGeneratedMesh, exportAnnotations]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error('useAppState must be used within AppStateProvider');
  return ctx;
}
