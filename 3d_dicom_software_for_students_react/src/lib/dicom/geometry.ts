import type { VolumeMeta } from '@/types/annotation';

export type Vec3 = [number, number, number];

export function normalizedToVoxel(position: Vec3, dims: Vec3): Vec3 {
  const [cols, rows, depth] = dims;
  const x = position[0] * (cols - 1);
  const y = position[1] * (rows - 1);
  const z = position[2] * (depth - 1);
  return [x, y, z];
}

export function voxelToNormalized(voxel: Vec3, dims: Vec3): Vec3 {
  const [cols, rows, depth] = dims;
  return [
    cols > 1 ? voxel[0] / (cols - 1) : 0,
    rows > 1 ? voxel[1] / (rows - 1) : 0,
    depth > 1 ? voxel[2] / (depth - 1) : 0,
  ];
}

function orientationMatrix(volume: VolumeMeta): number[][] {
  if (!volume.orientation || volume.orientation.length !== 9) {
    throw new Error('Volume orientation must contain 9 elements.');
  }
  const [r0, r1, r2, c0, c1, c2, s0, s1, s2] = volume.orientation;
  return [
    [r0, c0, s0],
    [r1, c1, s1],
    [r2, c2, s2],
  ];
}

function invert3x3(m: number[][]): number[][] {
  const [a, b, c] = m;
  const det =
    a[0] * (b[1] * c[2] - b[2] * c[1]) -
    a[1] * (b[0] * c[2] - b[2] * c[0]) +
    a[2] * (b[0] * c[1] - b[1] * c[0]);
  if (Math.abs(det) < 1e-8) throw new Error('Orientation matrix not invertible.');
  const invDet = 1 / det;
  const inv = [
    [
      (b[1] * c[2] - b[2] * c[1]) * invDet,
      (a[2] * c[1] - a[1] * c[2]) * invDet,
      (a[1] * b[2] - a[2] * b[1]) * invDet,
    ],
    [
      (b[2] * c[0] - b[0] * c[2]) * invDet,
      (a[0] * c[2] - a[2] * c[0]) * invDet,
      (a[2] * b[0] - a[0] * b[2]) * invDet,
    ],
    [
      (b[0] * c[1] - b[1] * c[0]) * invDet,
      (a[1] * c[0] - a[0] * c[1]) * invDet,
      (a[0] * b[1] - a[1] * b[0]) * invDet,
    ],
  ];
  return inv;
}

export function voxelToPatient(voxel: Vec3, volume: VolumeMeta): Vec3 {
  if (!volume.spacing || !volume.origin) {
    throw new Error('Volume spacing/origin missing.');
  }
  const spacing = volume.spacing;
  const origin = volume.origin;
  const m = orientationMatrix(volume);

  const scaled = [
    voxel[0] * spacing[0],
    voxel[1] * spacing[1],
    voxel[2] * spacing[2],
  ];

  const x = origin[0] + m[0][0] * scaled[0] + m[0][1] * scaled[1] + m[0][2] * scaled[2];
  const y = origin[1] + m[1][0] * scaled[0] + m[1][1] * scaled[1] + m[1][2] * scaled[2];
  const z = origin[2] + m[2][0] * scaled[0] + m[2][1] * scaled[1] + m[2][2] * scaled[2];
  return [x, y, z];
}

export function patientToVoxel(patient: Vec3, volume: VolumeMeta): Vec3 {
  if (!volume.spacing || !volume.origin) {
    throw new Error('Volume spacing/origin missing.');
  }
  const spacing = volume.spacing;
  const origin = volume.origin;
  const m = orientationMatrix(volume);
  const inv = invert3x3(m);

  const diff = [patient[0] - origin[0], patient[1] - origin[1], patient[2] - origin[2]];

  const scaled = [
    inv[0][0] * diff[0] + inv[0][1] * diff[1] + inv[0][2] * diff[2],
    inv[1][0] * diff[0] + inv[1][1] * diff[1] + inv[1][2] * diff[2],
    inv[2][0] * diff[0] + inv[2][1] * diff[1] + inv[2][2] * diff[2],
  ];

  return [scaled[0] / spacing[0], scaled[1] / spacing[1], scaled[2] / spacing[2]];
}



