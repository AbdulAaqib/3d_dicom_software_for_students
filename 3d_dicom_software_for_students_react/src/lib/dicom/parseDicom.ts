import dicomParser, { type DicomDataSet } from 'dicom-parser';

export interface ParsedSlice {
  fileName?: string;
  rows: number;
  cols: number;
  bitsAllocated: number;
  pixelRepresentation?: number; // 0 unsigned, 1 signed
  // Exactly one of the following will be provided depending on transfer syntax:
  pixelData?: ArrayBuffer; // raw frame data (uncompressed)
  encapsulatedJPEG?: Uint8Array; // JPEG baseline compressed frame
  transferSyntaxUID?: string;

  // Display and geometry metadata
  rescaleSlope?: number;
  rescaleIntercept?: number;
  windowCenter?: number;
  windowWidth?: number;
  imagePosition?: [number, number, number];
  imageOrientation?: number[]; // 6 numbers
  pixelSpacing?: [number, number];
  instanceNumber?: number;
  sliceLocation?: number;
}

export interface ParsedSeries {
  slices: ParsedSlice[]; // sorted
  spacing?: [number, number, number]; // x,y,z (mm)
  dimensions: [number, number, number]; // cols (x), rows (y), depth (z)
}

// ------------------ helpers ------------------
function has(ds: DicomDataSet, tag: string): boolean {
  return !!ds.elements[tag];
}

function getUS(ds: DicomDataSet, tag: string): number | undefined {
  try {
    if (!has(ds, tag)) return undefined;
    const n = ds.uint16(tag);
    return Number.isFinite(n) ? n : undefined;
  } catch {
    return undefined;
  }
}

function getIS(ds: DicomDataSet, tag: string): number | undefined {
  try {
    const s = ds.intString(tag);
    if (s == null || s === '') return undefined;
    const n = Number(s);
    return Number.isFinite(n) ? n : undefined;
  } catch {
    try {
      const v = ds.string(tag);
      if (!v) return undefined;
      const n = Number(v);
      return Number.isFinite(n) ? n : undefined;
    } catch {
      return undefined;
    }
  }
}

function getDS(ds: DicomDataSet, tag: string): number | undefined {
  try {
    const s = ds.floatString(tag);
    if (s == null || s === '') return undefined;
    const n = Number(s);
    return Number.isFinite(n) ? n : undefined;
  } catch {
    try {
      const v = ds.string(tag);
      if (!v) return undefined;
      const n = Number(v);
      return Number.isFinite(n) ? n : undefined;
    } catch {
      return undefined;
    }
  }
}

function getDSArray(ds: DicomDataSet, tag: string, expectedLen?: number): number[] | undefined {
  try {
    const v = ds.string(tag);
    if (!v) return undefined;
    const arr = v
      .split(/[\\, ]+/)
      .map((x: string) => Number(x))
      .filter((n: number) => Number.isFinite(n));
    if (expectedLen != null && arr.length !== expectedLen) return undefined;
    return arr;
  } catch {
    return undefined;
  }
}

function firstNumberFromMulti(ds: DicomDataSet, tag: string): number | undefined {
  try {
    const v = ds.string(tag);
    if (!v) return undefined;
    const first = v.split('\\')[0]?.trim();
    const n = Number(first);
    return Number.isFinite(n) ? n : undefined;
  } catch {
    return undefined;
  }
}

function bySlicePosition(a: ParsedSlice, b: ParsedSlice) {
  // Prefer ImagePositionPatient Z if present, fallback to InstanceNumber
  const az = a.imagePosition?.[2];
  const bz = b.imagePosition?.[2];
  if (az != null && bz != null && az !== bz) return az - bz;
  const ai = a.instanceNumber ?? 0;
  const bi = b.instanceNumber ?? 0;
  return ai - bi;
}

export function parseUncompressedPixelData(ds: DicomDataSet): ArrayBuffer {
  const pixelDataEl = ds.elements['x7fe00010'];
  if (!pixelDataEl) throw new Error('No PixelData (7FE0,0010) found');
  const byteArray = ds.byteArray as Uint8Array;
  const start = pixelDataEl.dataOffset;
  const end = start + pixelDataEl.length;
  const frameBuffer = new ArrayBuffer(pixelDataEl.length);
  const frameView = new Uint8Array(frameBuffer);
  frameView.set(byteArray.subarray(start, end));
  return frameBuffer;
}

export interface Build8BitOptions {
  windowCenter?: number;
  windowWidth?: number;
  rescaleSlope?: number;
  rescaleIntercept?: number;
  signed?: boolean; // pixelRepresentation===1
}

export function to8BitGray(
  src: ArrayBuffer,
  rows: number,
  cols: number,
  bitsAllocated: number,
  opts: Build8BitOptions = {}
): Uint8ClampedArray {
  const npx = rows * cols;
  const out = new Uint8ClampedArray(npx);

  const slope = opts.rescaleSlope ?? 1;
  const intercept = opts.rescaleIntercept ?? 0;

  if (bitsAllocated === 16) {
    const view = opts.signed ? new Int16Array(src) : new Uint16Array(src);

    // dynamic window if none provided
    let minVal = Infinity;
    let maxVal = -Infinity;
    for (let i = 0; i < npx; i++) {
      const val = view[i] * slope + intercept;
      if (val < minVal) minVal = val;
      if (val > maxVal) maxVal = val;
    }
    const wc = opts.windowCenter ?? (minVal + maxVal) / 2;
    const ww = opts.windowWidth ?? Math.max(1, maxVal - minVal);
    const low = wc - ww / 2;
    const high = wc + ww / 2;
    const scale = 255 / (high - low);

    for (let i = 0; i < npx; i++) {
      const val = view[i] * slope + intercept;
      const v = Math.max(0, Math.min(255, Math.round((val - low) * scale)));
      out[i] = v;
    }
  } else if (bitsAllocated === 8) {
    if (opts.signed) {
      const view = new Int8Array(src);
      // map [-128..127] to [0..255]
      for (let i = 0; i < npx; i++) out[i] = view[i] + 128;
    } else {
      const view = new Uint8Array(src);
      out.set(view.subarray(0, npx));
    }
  } else {
    throw new Error(`bitsAllocated=${bitsAllocated} not supported in MVP`);
  }

  return out;
}

function isUncompressedTransferSyntax(uid?: string): boolean {
  if (!uid) return true; // default to implicit little
  return (
    uid === '1.2.840.10008.1.2' || // Implicit VR Little Endian
    uid === '1.2.840.10008.1.2.1' // Explicit VR Little Endian
  );
}

function isJPEGBaseline(uid?: string): boolean {
  return uid === '1.2.840.10008.1.2.4.50'; // JPEG Baseline (Process 1)
}

async function decodeJPEGBaselineToGray(
  jpegBytes: Uint8Array,
  width: number,
  height: number
): Promise<Uint8ClampedArray> {
  const jpegBuffer = new ArrayBuffer(jpegBytes.byteLength);
  new Uint8Array(jpegBuffer).set(jpegBytes);
  const blob = new Blob([jpegBuffer], { type: 'image/jpeg' });
  // Prefer ImageBitmap when available for performance
  let bmp: ImageBitmap | undefined;
  try {
    bmp = await createImageBitmap(blob);
  } catch {
    bmp = undefined;
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context not available');

  if (bmp) {
    ctx.drawImage(bmp, 0, 0, width, height);
  } else {
    // Fallback via HTMLImageElement
    const url = URL.createObjectURL(blob);
    try {
      await new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          try {
            ctx.drawImage(img, 0, 0, width, height);
            resolve();
          } catch (e) {
            reject(e);
          }
        };
        img.onerror = () => reject(new Error('Image decode error'));
        img.src = url;
      });
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  const imageData = ctx.getImageData(0, 0, width, height);
  const rgba = imageData.data;
  const gray = new Uint8ClampedArray(width * height);
  for (let i = 0, j = 0; i < gray.length; i++, j += 4) {
    const r = rgba[j];
    const g = rgba[j + 1];
    const b = rgba[j + 2];
    // luminance weights
    gray[i] = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }
  return gray;
}

export async function parseDicomFiles(files: File[]): Promise<ParsedSeries> {
  const slices: ParsedSlice[] = [];

  if (!files || files.length === 0) {
    throw new Error('No DICOM files provided');
  }

  for (const f of files) {
    const buf = await f.arrayBuffer();
    const byteArray = new Uint8Array(buf);
    const ds = dicomParser.parseDicom(byteArray);

    const tsuid = ds.string('x00020010');

    const rows = getUS(ds, 'x00280010'); // Rows (US)
    const cols = getUS(ds, 'x00280011'); // Columns (US)
    const bitsAllocated = getUS(ds, 'x00280100') ?? 8; // BitsAllocated (US)

    if (!rows || !cols || !bitsAllocated) {
      throw new Error('Missing Rows/Cols/BitsAllocated');
    }

    const pixelRepresentation = getUS(ds, 'x00280103'); // 0=unsigned,1=signed
    const instanceNumber = getIS(ds, 'x00200013');
    const sliceLocation = getDS(ds, 'x00201041');
    const imagePositionArr = getDSArray(ds, 'x00200032', 3) as [number, number, number] | undefined;
    const imageOrientationArr = getDSArray(ds, 'x00200037', 6);
    const pixelSpacingArr = getDSArray(ds, 'x00280030', 2) as [number, number] | undefined;

    // window center/width can be multi-valued; take first
    const windowCenter = firstNumberFromMulti(ds, 'x00281050');
    const windowWidth = firstNumberFromMulti(ds, 'x00281051');

    const rescaleSlope = getDS(ds, 'x00281053');
    const rescaleIntercept = getDS(ds, 'x00281052');

    let pixelData: ArrayBuffer | undefined;
    let encapsulatedJPEG: Uint8Array | undefined;

    if (isUncompressedTransferSyntax(tsuid)) {
      pixelData = parseUncompressedPixelData(ds);
    } else if (isJPEGBaseline(tsuid)) {
      const pixelDataEl = ds.elements['x7fe00010'];
      if (!pixelDataEl) throw new Error('No PixelData (7FE0,0010) found');
      // Read the first (and usually only) frame per file
      encapsulatedJPEG = dicomParser.readEncapsulatedImageFrame(ds, pixelDataEl, 0);
    } else {
      throw new Error(`Unsupported Transfer Syntax UID: ${tsuid}. Only uncompressed Little Endian and JPEG Baseline are supported in current MVP.`);
    }

    slices.push({
      fileName: f.name,
      rows,
      cols,
      bitsAllocated,
      pixelRepresentation,
      pixelData,
      encapsulatedJPEG,
      transferSyntaxUID: tsuid,
      rescaleSlope,
      rescaleIntercept,
      windowCenter,
      windowWidth,
      imagePosition: imagePositionArr,
      imageOrientation: imageOrientationArr,
      pixelSpacing: pixelSpacingArr,
      instanceNumber,
      sliceLocation,
    });
  }

  if (slices.length === 0) {
    throw new Error('No supported frames found (unsupported transfer syntax or missing PixelData).');
  }

  // sort slices
  slices.sort(bySlicePosition);

  // estimate spacing (x,y from PixelSpacing; z from distance between positions)
  let spacing: [number, number, number] | undefined = undefined;
  if (slices.length > 1) {
    const ps = slices[0].pixelSpacing;
    const z0 = slices[0].imagePosition?.[2];
    const z1 = slices[1].imagePosition?.[2];
    const dz = z0 != null && z1 != null ? Math.abs(z1 - z0) : 1;
    spacing = [ps?.[1] ?? 1, ps?.[0] ?? 1, dz]; // cols x rows x depth
  } else {
    const ps = slices[0].pixelSpacing;
    spacing = [ps?.[1] ?? 1, ps?.[0] ?? 1, 1];
  }

  const rows0 = slices[0].rows;
  const cols0 = slices[0].cols;
  return {
    slices,
    spacing,
    dimensions: [cols0, rows0, slices.length],
  };
}

export async function build8BitStack(series: ParsedSeries, override?: { windowCenter?: number; windowWidth?: number }): Promise<Uint8ClampedArray[]> {
  const { slices } = series;
  const frames: Uint8ClampedArray[] = [];

  for (const s of slices) {
    if (s.encapsulatedJPEG) {
      // Decode JPEG via browser and convert to grayscale (WL not applied for JPEG baseline)
      const frame8 = await decodeJPEGBaselineToGray(s.encapsulatedJPEG, s.cols, s.rows);
      frames.push(frame8);
    } else if (s.pixelData) {
      const wc = override?.windowCenter ?? s.windowCenter;
      const ww = override?.windowWidth ?? s.windowWidth;
      const frame8 = to8BitGray(s.pixelData, s.rows, s.cols, s.bitsAllocated, {
        windowCenter: wc,
        windowWidth: ww,
        rescaleSlope: s.rescaleSlope,
        rescaleIntercept: s.rescaleIntercept,
        signed: s.pixelRepresentation === 1,
      });
      frames.push(frame8);
    } else {
      throw new Error('Slice lacks pixel data');
    }
  }

  return frames;
}
