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

export interface VolumeMeta {
  dimensions?: [number, number, number]; // width,height,depth (voxels)
  spacing?: [number, number, number]; // mm per voxel
  orientation?: number[]; // 3x3 direction cosines (row/col/slice)
  window?: { center?: number; width?: number };
}

export interface StudyMeta {
  patientId?: string;
  studyInstanceUID?: string;
  seriesInstanceUID?: string;
  modality?: string;
  studyDate?: string;
}

export interface AnnotationExport {
  version: '1.0';
  study?: StudyMeta;
  volume: VolumeMeta;
  annotations: Annotation[];
  exportedAt: string;
}
