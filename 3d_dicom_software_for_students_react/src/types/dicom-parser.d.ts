declare module 'dicom-parser' {
  export interface DicomElement {
    tag: string;
    dataOffset: number;
    length: number;
    items?: unknown[];
  }

  export interface DicomElements {
    [tag: string]: DicomElement | undefined;
  }

  export interface DicomDataSet {
    byteArray: Uint8Array;
    elements: DicomElements;
    uint16(tag: string): number;
    intString(tag: string): string | undefined;
    string(tag: string): string | undefined;
    floatString(tag: string): string | undefined;
  }

  export interface ParseDicomOptions {
    untilTag?: string;
    includePixelData?: boolean;
  }

  export function parseDicom(byteArray: Uint8Array, options?: ParseDicomOptions): DicomDataSet;
  export function readEncapsulatedImageFrame(
    dataset: DicomDataSet,
    element: DicomElement,
    frameIndex: number
  ): Uint8Array;

  const dicomParser: {
    parseDicom: typeof parseDicom;
    readEncapsulatedImageFrame: typeof readEncapsulatedImageFrame;
  };

  export default dicomParser;
  export = dicomParser;
}
