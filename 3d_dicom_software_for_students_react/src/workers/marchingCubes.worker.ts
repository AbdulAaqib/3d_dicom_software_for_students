/// <reference lib="webworker" />

import { VertexInterp3 } from "@bitheral/marching-cubes/dist/MarchingCubes/util";
import lookup from "@bitheral/marching-cubes/dist/MarchingCubes/lookup.json";
import * as THREE from "three";

const edgeTable = lookup.edgeTable as number[];
const triTable = lookup.triTable as number[][];
const cornerIndexFromEdge = lookup.cornerIndexFromEdge as [number, number][];

const cornerOffsets: [number, number, number][] = [
  [0, 0, 0],
  [1, 0, 0],
  [1, 0, 1],
  [0, 0, 1],
  [0, 1, 0],
  [1, 1, 0],
  [1, 1, 1],
  [0, 1, 1],
];

const KEY_SCALE = 1e5;
const CHUNK_SIZE = 64;
const CHUNK_OVERLAP = 2;
const MAX_CHUNK_VERTEX_COUNT = 4_000_000;

interface GenerateMessage {
  voxels: Float32Array;
  dims: [number, number, number];
  isoValue: number;
  spacing?: [number, number, number];
  origin?: [number, number, number];
  direction?: number[];
  voxelMin?: number;
  voxelMax?: number;
}

interface ErrorMessage {
  error: string;
}

interface EmptyMessage {
  empty: true;
}

interface SuccessMessage {
  positions: ArrayBuffer;
  normals: ArrayBuffer;
  indices: ArrayBuffer;
  bbox: {
    min: [number, number, number];
    max: [number, number, number];
  };
}

interface ProgressMessage {
  progress: number;
}

interface ChunkResult {
  positions: Float32Array;
  normals: Float32Array;
  indices: Uint32Array;
}

type WorkerResponse = ErrorMessage | EmptyMessage | SuccessMessage | ProgressMessage;

function postMessageSafe(payload: WorkerResponse) {
  self.postMessage(payload);
}

function smoothMeshTaubin(
  positions: Float32Array,
  indices: Uint32Array,
  iterations = 2,
  lambda = 0.4,
  mu = -0.34
) {
  const vertexCount = positions.length / 3;
  if (vertexCount === 0 || indices.length === 0) {
    return;
  }

  const accum = new Float32Array(positions.length);
  const counts = new Uint32Array(vertexCount);

  const applyWeight = (weight: number) => {
    if (!Number.isFinite(weight) || weight === 0) return;

    accum.fill(0);
    counts.fill(0);

    for (let i = 0; i < indices.length; i += 3) {
      const ia = indices[i];
      const ib = indices[i + 1];
      const ic = indices[i + 2];

      if (ia >= vertexCount || ib >= vertexCount || ic >= vertexCount) {
        continue;
      }

      const aBase = ia * 3;
      const bBase = ib * 3;
      const cBase = ic * 3;

      accum[aBase] += positions[bBase] + positions[cBase];
      accum[aBase + 1] += positions[bBase + 1] + positions[cBase + 1];
      accum[aBase + 2] += positions[bBase + 2] + positions[cBase + 2];
      counts[ia] += 2;

      accum[bBase] += positions[aBase] + positions[cBase];
      accum[bBase + 1] += positions[aBase + 1] + positions[cBase + 1];
      accum[bBase + 2] += positions[aBase + 2] + positions[cBase + 2];
      counts[ib] += 2;

      accum[cBase] += positions[aBase] + positions[bBase];
      accum[cBase + 1] += positions[aBase + 1] + positions[bBase + 1];
      accum[cBase + 2] += positions[aBase + 2] + positions[bBase + 2];
      counts[ic] += 2;
    }

    for (let v = 0; v < vertexCount; v++) {
      const count = counts[v];
      if (count === 0) continue;
      const base = v * 3;
      const inv = 1 / count;
      const avgX = accum[base] * inv;
      const avgY = accum[base + 1] * inv;
      const avgZ = accum[base + 2] * inv;

      positions[base] += weight * (avgX - positions[base]);
      positions[base + 1] += weight * (avgY - positions[base + 1]);
      positions[base + 2] += weight * (avgZ - positions[base + 2]);
    }
  };

  for (let iter = 0; iter < iterations; iter++) {
    applyWeight(lambda);
    applyWeight(mu);
  }
}

function recomputeNormals(positions: Float32Array, indices: Uint32Array, normals: Float32Array) {
  const vertexCount = positions.length / 3;
  if (vertexCount === 0 || indices.length === 0) {
    normals.fill(0);
    return;
  }

  normals.fill(0);

  for (let i = 0; i < indices.length; i += 3) {
    const ia = indices[i];
    const ib = indices[i + 1];
    const ic = indices[i + 2];

    const aBase = ia * 3;
    const bBase = ib * 3;
    const cBase = ic * 3;

    const ax = positions[aBase];
    const ay = positions[aBase + 1];
    const az = positions[aBase + 2];

    const bx = positions[bBase];
    const by = positions[bBase + 1];
    const bz = positions[bBase + 2];

    const cx = positions[cBase];
    const cy = positions[cBase + 1];
    const cz = positions[cBase + 2];

    const ux = bx - ax;
    const uy = by - ay;
    const uz = bz - az;

    const vx = cx - ax;
    const vy = cy - ay;
    const vz = cz - az;

    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;

    normals[aBase] += nx;
    normals[aBase + 1] += ny;
    normals[aBase + 2] += nz;

    normals[bBase] += nx;
    normals[bBase + 1] += ny;
    normals[bBase + 2] += nz;

    normals[cBase] += nx;
    normals[cBase + 1] += ny;
    normals[cBase + 2] += nz;
  }

  for (let v = 0; v < vertexCount; v++) {
    const base = v * 3;
    const nx = normals[base];
    const ny = normals[base + 1];
    const nz = normals[base + 2];
    const len = Math.hypot(nx, ny, nz);
    if (len > 1e-6) {
      const inv = 1 / len;
      normals[base] = nx * inv;
      normals[base + 1] = ny * inv;
      normals[base + 2] = nz * inv;
    } else {
      normals[base] = 0;
      normals[base + 1] = 0;
      normals[base + 2] = 1;
    }
  }
}

function sampleScalar(
  data: Float32Array,
  width: number,
  height: number,
  depth: number,
  x: number,
  y: number,
  z: number
): number {
  if (x < 0 || x >= width || y < 0 || y >= height || z < 0 || z >= depth) {
    return 0;
  }
  const idx = z * width * height + y * width + x;
  return data[idx];
}

self.onmessage = (event: MessageEvent<GenerateMessage>) => {
  const { voxels, dims, isoValue, spacing = [1, 1, 1], origin = [0, 0, 0], direction, voxelMin, voxelMax } = event.data;
  const [width, height, depth] = dims;

  if (!voxels || width < 2 || height < 2 || depth < 2) {
    postMessageSafe({ error: "Volume data missing or dimensions too small for marching cubes." });
    return;
  }

  if (!Number.isFinite(isoValue)) {
    postMessageSafe({ error: "Iso-value must be a finite number." });
    return;
  }

  const volume = voxels;
  let rangeMin = voxelMin;
  let rangeMax = voxelMax;
  if (rangeMin == null || rangeMax == null) {
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (let i = 0; i < volume.length; i++) {
      const v = volume[i];
      if (v < min) min = v;
      if (v > max) max = v;
    }
    rangeMin = Number.isFinite(min) ? min : 0;
    rangeMax = Number.isFinite(max) ? max : 0;
  }

  if (
    Number.isFinite(rangeMin) &&
    Number.isFinite(rangeMax) &&
    rangeMin <= rangeMax &&
    (isoValue < rangeMin || isoValue > rangeMax)
  ) {
    postMessageSafe({
      error: `Iso-value ${isoValue.toFixed(2)} is outside the volume range [${rangeMin.toFixed(2)}, ${rangeMax.toFixed(2)}].`,
    });
      return;
    }

  const dir = direction && direction.length === 9 ? direction : [1, 0, 0, 0, 1, 0, 0, 0, 1];
  const rowDir = dir.slice(0, 3) as [number, number, number];
  const colDir = dir.slice(3, 6) as [number, number, number];
  const sliceDir = dir.slice(6, 9) as [number, number, number];

  const [sx, sy, sz] = spacing;
  const [ox, oy, oz] = origin;

  const gridToWorld = (gx: number, gy: number, gz: number): [number, number, number] => [
    ox + rowDir[0] * (gx * sx) + colDir[0] * (gy * sy) + sliceDir[0] * (gz * sz),
    oy + rowDir[1] * (gx * sx) + colDir[1] * (gy * sy) + sliceDir[1] * (gz * sz),
    oz + rowDir[2] * (gx * sx) + colDir[2] * (gy * sy) + sliceDir[2] * (gz * sz),
  ];

  const corners = new Array<THREE.Vector4>(8);
  for (let i = 0; i < 8; i++) {
    corners[i] = new THREE.Vector4();
  }
  const tempCornerA = new THREE.Vector4();
  const tempCornerB = new THREE.Vector4();

  const stepX = Math.max(1, CHUNK_SIZE - CHUNK_OVERLAP);
  const stepY = Math.max(1, CHUNK_SIZE - CHUNK_OVERLAP);
  const stepZ = Math.max(1, CHUNK_SIZE - CHUNK_OVERLAP);
  const xSteps = Math.max(1, Math.ceil((width - 1) / stepX));
  const ySteps = Math.max(1, Math.ceil((height - 1) / stepY));
  const zSteps = Math.max(1, Math.ceil((depth - 1) / stepZ));
  const totalChunks = Math.max(1, xSteps * ySteps * zSteps);
  let processedChunks = 0;

  const chunkResults: ChunkResult[] = [];
  let globalMinX = Number.POSITIVE_INFINITY;
  let globalMinY = Number.POSITIVE_INFINITY;
  let globalMinZ = Number.POSITIVE_INFINITY;
  let globalMaxX = Number.NEGATIVE_INFINITY;
  let globalMaxY = Number.NEGATIVE_INFINITY;
  let globalMaxZ = Number.NEGATIVE_INFINITY;

  const edgeVertices: (THREE.Vector4 | undefined)[] = new Array(12);

  function processChunk(xStart: number, yStart: number, zStart: number) {
    const xEnd = Math.min(width, xStart + CHUNK_SIZE);
    const yEnd = Math.min(height, yStart + CHUNK_SIZE);
    const zEnd = Math.min(depth, zStart + CHUNK_SIZE);
    if (xEnd - xStart < 2 || yEnd - yStart < 2 || zEnd - zStart < 2) {
      processedChunks++;
      postMessageSafe({ progress: Math.min(1, processedChunks / totalChunks) });
      return;
    }

    const positions: number[] = [];
    const normals: number[] = [];
    const indices: number[] = [];
    const vertexMap = new Map<string, number>();

    function getVertexIndex(
      gridX: number,
      gridY: number,
      gridZ: number,
      worldX: number,
      worldY: number,
      worldZ: number
    ): number {
      const key = `${Math.round(gridX * KEY_SCALE)}|${Math.round(gridY * KEY_SCALE)}|${Math.round(gridZ * KEY_SCALE)}`;
      const existing = vertexMap.get(key);
      if (existing != null) {
        const idx = existing * 3;
        if (
          Math.abs(positions[idx] - worldX) < 1e-4 &&
          Math.abs(positions[idx + 1] - worldY) < 1e-4 &&
          Math.abs(positions[idx + 2] - worldZ) < 1e-4
        ) {
          return existing;
        }
      }

      const index = positions.length / 3;
      if (index >= MAX_CHUNK_VERTEX_COUNT) {
        throw new Error("Chunk mesh exceeds vertex budget; consider lowering the iso-value.");
      }

      positions.push(worldX, worldY, worldZ);
      normals.push(0, 0, 0);
      vertexMap.set(key, index);

      if (worldX < globalMinX) globalMinX = worldX;
      if (worldX > globalMaxX) globalMaxX = worldX;
      if (worldY < globalMinY) globalMinY = worldY;
      if (worldY > globalMaxY) globalMaxY = worldY;
      if (worldZ < globalMinZ) globalMinZ = worldZ;
      if (worldZ > globalMaxZ) globalMaxZ = worldZ;

      return index;
    }

    for (let z = zStart; z < zEnd - 1; z++) {
      for (let y = yStart; y < yEnd - 1; y++) {
        for (let x = xStart; x < xEnd - 1; x++) {
          let cubeIndex = 0;

          for (let i = 0; i < 8; i++) {
            const [dx, dy, dz] = cornerOffsets[i];
            const cx = x + dx;
            const cy = y + dy;
            const cz = z + dz;
            const value = sampleScalar(volume, width, height, depth, cx, cy, cz);
            corners[i].set(cx, cy, cz, value);
            if (value < isoValue) {
              cubeIndex |= 1 << i;
            }
          }

          const edges = edgeTable[cubeIndex];
          if (edges === 0) {
            continue;
          }

          for (let e = 0; e < 12; e++) {
            if (edges & (1 << e)) {
              const [a, b] = cornerIndexFromEdge[e];
              const ca = corners[a];
              const cb = corners[b];
              tempCornerA.set(ca.x, ca.y, ca.z, ca.w);
              tempCornerB.set(cb.x, cb.y, cb.z, cb.w);
              const interp = VertexInterp3(isoValue as any, tempCornerA as any, tempCornerB as any) as unknown as THREE.Vector4;
              if (!edgeVertices[e]) edgeVertices[e] = new THREE.Vector4();
              edgeVertices[e]!.set(interp.x, interp.y, interp.z, interp.w);
            } else {
              edgeVertices[e] = undefined;
            }
          }

          const tri = triTable[cubeIndex];
          for (let t = 0; t < tri.length && tri[t] !== -1; t += 3) {
            const v0Idx = tri[t];
            const v1Idx = tri[t + 1];
            const v2Idx = tri[t + 2];
            const vert0 = edgeVertices[v0Idx];
            const vert1 = edgeVertices[v1Idx];
            const vert2 = edgeVertices[v2Idx];
            if (!vert0 || !vert1 || !vert2) {
              continue;
            }

            const v0x = vert0.x;
            const v0y = vert0.y;
            const v0z = vert0.z;
            const v1x = vert1.x;
            const v1y = vert1.y;
            const v1z = vert1.z;
            const v2x = vert2.x;
            const v2y = vert2.y;
            const v2z = vert2.z;

            const [p0x, p0y, p0z] = gridToWorld(v0x, v0y, v0z);
            const [p1x, p1y, p1z] = gridToWorld(v1x, v1y, v1z);
            const [p2x, p2y, p2z] = gridToWorld(v2x, v2y, v2z);

            const ux = p1x - p0x;
            const uy = p1y - p0y;
            const uz = p1z - p0z;
            const vx = p2x - p0x;
            const vy = p2y - p0y;
            const vz = p2z - p0z;

            let nx = uy * vz - uz * vy;
            let ny = uz * vx - ux * vz;
            let nz = ux * vy - uy * vx;
            const length = Math.hypot(nx, ny, nz) || 1;
            nx /= length;
            ny /= length;
            nz /= length;

            const i0 = getVertexIndex(v0x, v0y, v0z, p0x, p0y, p0z);
            const i1 = getVertexIndex(v1x, v1y, v1z, p1x, p1y, p1z);
            const i2 = getVertexIndex(v2x, v2y, v2z, p2x, p2y, p2z);

            normals[i0 * 3 + 0] += nx;
            normals[i0 * 3 + 1] += ny;
            normals[i0 * 3 + 2] += nz;
            normals[i1 * 3 + 0] += nx;
            normals[i1 * 3 + 1] += ny;
            normals[i1 * 3 + 2] += nz;
            normals[i2 * 3 + 0] += nx;
            normals[i2 * 3 + 1] += ny;
            normals[i2 * 3 + 2] += nz;

            indices.push(i0, i1, i2);
          }
        }
      }
    }

    if (positions.length > 0) {
      for (let i = 0; i < positions.length / 3; i++) {
        const nx = normals[i * 3 + 0];
        const ny = normals[i * 3 + 1];
        const nz = normals[i * 3 + 2];
        const len = Math.hypot(nx, ny, nz) || 1;
        normals[i * 3 + 0] = nx / len;
        normals[i * 3 + 1] = ny / len;
        normals[i * 3 + 2] = nz / len;
      }

      chunkResults.push({
        positions: Float32Array.from(positions),
        normals: Float32Array.from(normals),
        indices: Uint32Array.from(indices),
      });
    }

    processedChunks++;
    postMessageSafe({ progress: Math.min(1, processedChunks / totalChunks) });
  }

  try {
    for (let z = 0; z < depth - 1; z += stepZ) {
      for (let y = 0; y < height - 1; y += stepY) {
        for (let x = 0; x < width - 1; x += stepX) {
          processChunk(x, y, z);
        }
      }
    }

    if (chunkResults.length === 0) {
      postMessageSafe({ empty: true });
      return;
    }

    let totalPositions = 0;
    let totalNormals = 0;
    let totalIndices = 0;
    for (const chunk of chunkResults) {
      totalPositions += chunk.positions.length;
      totalNormals += chunk.normals.length;
      totalIndices += chunk.indices.length;
    }

    const positionsArray = new Float32Array(totalPositions);
    const normalsArray = new Float32Array(totalNormals);
    const indicesArray = new Uint32Array(totalIndices);

    let posOffset = 0;
    let normOffset = 0;
    let idxOffset = 0;
    let vertexBase = 0;
    for (const chunk of chunkResults) {
      positionsArray.set(chunk.positions, posOffset);
      normalsArray.set(chunk.normals, normOffset);
      for (let i = 0; i < chunk.indices.length; i++) {
        indicesArray[idxOffset + i] = chunk.indices[i] + vertexBase;
      }
      posOffset += chunk.positions.length;
      normOffset += chunk.normals.length;
      idxOffset += chunk.indices.length;
      vertexBase += chunk.positions.length / 3;
    }

    smoothMeshTaubin(positionsArray, indicesArray);
    recomputeNormals(positionsArray, indicesArray, normalsArray);

    if (!Number.isFinite(globalMinX)) {
      globalMinX = globalMinY = globalMinZ = 0;
      globalMaxX = globalMaxY = globalMaxZ = 0;
    }

    postMessageSafe({ progress: 1 });

    const transfers: ArrayBuffer[] = [positionsArray.buffer, normalsArray.buffer, indicesArray.buffer];
    self.postMessage(
      {
        positions: positionsArray.buffer,
        normals: normalsArray.buffer,
        indices: indicesArray.buffer,
        bbox: {
          min: [globalMinX, globalMinY, globalMinZ],
          max: [globalMaxX, globalMaxY, globalMaxZ],
        },
      },
      transfers
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : typeof err === "string" ? err : JSON.stringify(err);
    postMessageSafe({ error: message || "Mesh generation failed" });
  }
};
