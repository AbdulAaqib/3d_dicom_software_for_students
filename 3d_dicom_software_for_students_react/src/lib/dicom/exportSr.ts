import dcmjs from 'dcmjs';
import type { Annotation, VolumeMeta, StudyMeta } from '@/types/annotation';
import type { ParsedSeries } from './parseDicom';
import { normalizedToVoxel, voxelToPatient } from './geometry';

const { DicomMetaDictionary } = dcmjs.data;

const COMPREHENSIVE_3D_SR = '1.2.840.10008.5.1.4.1.1.88.34';
const DEFAULT_IMAGE_SOP_CLASS = '1.2.840.10008.5.1.4.1.1.2'; // CT Image Storage fallback

export interface ExportSrOptions {
  annotations: Annotation[];
  volume: VolumeMeta;
  study?: StudyMeta;
  parsedSeries?: ParsedSeries;
}

function ensureMeta({ annotations, volume }: ExportSrOptions) {
  if (!annotations.length) throw new Error('No annotations to export.');
  if (!volume.spacing || !volume.dimensions) throw new Error('Volume spacing/dimensions missing.');
  if (!volume.origin || !volume.orientation) throw new Error('Volume origin/orientation missing.');
}

function annotationToContentItem(
  annotation: Annotation,
  opts: ExportSrOptions
): any[] {
  const { volume, parsedSeries } = opts;
  const dims = volume.dimensions!;
  const voxel = normalizedToVoxel(annotation.position, dims);
  const pt = voxelToPatient(voxel, volume);

  const depth = dims[2];
  const sliceIdx = typeof annotation.sliceIndex === 'number'
    ? Math.min(Math.max(annotation.sliceIndex, 0), depth - 1)
    : Math.min(Math.max(Math.round(annotation.position[2] * (depth - 1)), 0), depth - 1);
  const refSlice = parsedSeries?.slices[sliceIdx];

  const baseContent: any = {
    RelationshipType: 'CONTAINS',
    ValueType: 'SCOORD3D',
    ConceptNameCodeSequence: [
      annotation.type === 'arrow'
        ? { CodeValue: '112003', CodingSchemeDesignator: 'DCM', CodeMeaning: 'Arrow annotation' }
        : { CodeValue: '112001', CodingSchemeDesignator: 'DCM', CodeMeaning: 'Point annotation' },
    ],
    GraphicType: annotation.type === 'arrow' ? 'POLYLINE' : 'POINT',
    GraphicData:
      annotation.type === 'arrow' && annotation.arrowTo
        ? [...pt, ...voxelToPatient(normalizedToVoxel(annotation.arrowTo, dims), volume)]
        : pt,
    CoordinateSystem: 'PATIENT',
  };

  if (refSlice?.sopInstanceUID) {
    baseContent.ReferencedSOPSequence = [
      {
        ReferencedSOPClassUID: DEFAULT_IMAGE_SOP_CLASS,
        ReferencedSOPInstanceUID: refSlice.sopInstanceUID,
      },
    ];
  }

  const items = [baseContent];

  if (annotation.labelText) {
    items.push({
      RelationshipType: 'CONTAINS',
      ValueType: 'TEXT',
      ConceptNameCodeSequence: [
        { CodeValue: '121106', CodingSchemeDesignator: 'DCM', CodeMeaning: 'Annotation label' },
      ],
      TextValue: annotation.labelText,
    });
  }

  return items;
}

export async function exportAnnotationsToSR(opts: ExportSrOptions): Promise<Blob> {
  ensureMeta(opts);
  const { annotations, study, volume } = opts;

  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;

  const sopInstanceUID = DicomMetaDictionary.uid();
  const seriesInstanceUID = DicomMetaDictionary.uid();

  const dataset: any = {
    SOPClassUID: COMPREHENSIVE_3D_SR,
    SOPInstanceUID: sopInstanceUID,
    StudyInstanceUID: study?.studyInstanceUID ?? DicomMetaDictionary.uid(),
    SeriesInstanceUID: seriesInstanceUID,
    Modality: 'SR',
    PatientID: study?.patientId ?? 'UNKNOWN',
    SeriesNumber: '1',
    InstanceNumber: '1',
    ContentDate: date,
    ContentTime: time,
    ContentLabel: 'ANNOTATIONS',
    ContentDescription: '3D annotations exported from 3D DICOM Annotator',
    Manufacturer: '3D DICOM Annotator',
    CompletionFlag: 'COMPLETE',
    VerificationFlag: 'UNVERIFIED',
    ValueType: 'CONTAINER',
    ContinuityOfContent: 'SEPARATE',
    ConceptNameCodeSequence: [
      { CodeValue: '121071', CodingSchemeDesignator: 'DCM', CodeMeaning: 'Imaging Measurements' },
    ],
    ContentTemplateSequence: [
      { MappingResource: 'DCMR', TemplateIdentifier: '1500' },
    ],
    ContentSequence: [],
  };

  annotations.forEach((annotation) => {
    const items = annotationToContentItem(annotation, opts);
    dataset.ContentSequence.push(...items);
  });

  const meta = DicomMetaDictionary.createMeta(dataset);
  const dict = DicomMetaDictionary.dictify(dataset);
  const metaDict = DicomMetaDictionary.dictify(meta);
  const part10Buffer = DicomMetaDictionary.write({ meta: metaDict, dict });

  return new Blob([part10Buffer], { type: 'application/dicom' });
}
