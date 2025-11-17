export type AnnotationType = 'marker' | 'arrow' | 'label';

export interface Annotation {
  id: string;
  type: AnnotationType;
  // normalized volume coordinates [0..1]
  position: [number, number, number];
  // optional arrow endpoint (normalized)
  arrowTo?: [number, number, number];
  // if created on a particular slice (slice-stack mode)
  sliceIndex?: number;
  labelText?: string;
  createdAt: string; // ISO timestamp
  // optional link: e.g., arrow start linked to a marker id
  linkedToId?: string;
}

export interface VolumeData {
  width: number;
  height: number;
  depth: number;
  frames8: Uint8ClampedArray[]; // each length = width*height
  spacing?: [number, number, number];
  voxels?: Float32Array; // flattened volume (width*height*depth) in modality units
  voxelMin?: number;
  voxelMax?: number;
  autoIso?: number;
}

export interface VolumeMeta {
  dimensions?: [number, number, number];
  spacing?: [number, number, number];
  origin?: [number, number, number];
  orientation?: number[];
}

export interface StudyMeta {
  patientId?: string;
  studyInstanceUID?: string;
  seriesInstanceUID?: string;
  modality?: string;
  studyDate?: string;
  frameOfReferenceUID?: string;
}

export interface AnnotationExport {
  version: '1.0';
  study?: StudyMeta;
  volume: VolumeMeta;
  volumeData?: VolumeData;
  annotations: Annotation[];
  exportedAt: string;
}

export interface MeshData {
  positions: Float32Array;
  normals: Float32Array;
  indices: Uint32Array;
}
