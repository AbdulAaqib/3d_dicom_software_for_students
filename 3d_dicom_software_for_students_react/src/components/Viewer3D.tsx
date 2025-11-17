"use client";

import React, { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Html, Line } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import { useAppState } from "@/state/AppState";
import type { Annotation } from "@/types/annotation";

function rgbaFromGray(gray: Uint8ClampedArray, width: number, height: number): Uint8Array {
  const out = new Uint8Array(width * height * 4);
  for (let i = 0, j = 0; i < gray.length; i++, j += 4) {
    const v = gray[i];
    out[j] = v;
    out[j + 1] = v;
    out[j + 2] = v;
    out[j + 3] = 255;
  }
  return out;
}

function makeDataTexture(gray: Uint8ClampedArray, width: number, height: number): THREE.DataTexture {
  const rgba = rgbaFromGray(gray, width, height);
  const tex = new THREE.DataTexture(rgba, width, height, THREE.RGBAFormat, THREE.UnsignedByteType);
  tex.needsUpdate = true;
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  // Keep flipY=false and handle Y inversion via world mapping to align with normalized coordinates
  tex.flipY = false;
  return tex;
}

function mapNormToWorld(
  pos: [number, number, number],
  dims: [number, number, number],
  spacing: [number, number, number]
): [number, number, number] {
  const [w, h, d] = dims;
  const [sx, sy, sz] = spacing;
  const Wmm = w * sx;
  const Hmm = h * sy;
  const Dmm = d * sz;
  const offsetX = Wmm / 2;
  const offsetY = Hmm / 2;
  const offsetZ = Dmm / 2;
  const x = pos[0] * Wmm - offsetX;
  const y = (1 - pos[1]) * Hmm - offsetY; // invert Y to match canvas-style normalized coords
  const z = pos[2] * Dmm - offsetZ;
  return [x, y, z];
}

function mapWorldToNorm(
  world: [number, number, number],
  dims: [number, number, number],
  spacing: [number, number, number]
): [number, number, number] {
  const [w, h, d] = dims;
  const [sx, sy, sz] = spacing;
  const Wmm = w * sx;
  const Hmm = h * sy;
  const Dmm = d * sz;
  const offsetX = Wmm / 2;
  const offsetY = Hmm / 2;
  const offsetZ = Dmm / 2;
  const nx = Wmm ? (world[0] + offsetX) / Wmm : 0;
  const ny = Hmm ? 1 - (world[1] + offsetY) / Hmm : 0; // invert
  const nz = Dmm ? (world[2] + offsetZ) / Dmm : 0;
  return [nx, ny, nz];
}

function AxialSlice({
  frame,
  width,
  height,
  sliceIndex,
  spacing,
  dims,
  onAnnotClick,
  opacity,
}: {
  frame: Uint8ClampedArray;
  width: number;
  height: number;
  sliceIndex: number;
  spacing: [number, number, number];
  dims: [number, number, number];
  onAnnotClick: (norm: [number, number, number]) => void;
  opacity: number;
}) {
  const tex = useMemo(() => makeDataTexture(frame, width, height), [frame, width, height]);
  const [sx, sy, sz] = spacing;
  const Wmm = width * sx;
  const Hmm = height * sy;
  const Dmm = dims[2] * sz;
  const zmm = sliceIndex * sz - Dmm / 2;

  const handlePointerDown = useCallback((e: any) => {
    e.stopPropagation();
    // Use world coordinates to compute normalized volume position
    const p = e.point as THREE.Vector3;
    const world: [number, number, number] = [p.x, p.y, p.z];
    const norm = mapWorldToNorm(world, dims, spacing);
    onAnnotClick(norm);
  }, [dims, onAnnotClick, spacing]);

  return (
    <mesh position={[0, 0, zmm]} onPointerDown={handlePointerDown}>
      <planeGeometry args={[Wmm, Hmm]} />
      <meshBasicMaterial map={tex} toneMapped={false} transparent opacity={opacity} />
    </mesh>
  );
}

function Marker3D({ a, dims, spacing }: { a: Annotation; dims: [number, number, number]; spacing: [number, number, number] }) {
  const pos = a.position ?? [0, 0, 0];
  const world = mapNormToWorld(pos, dims, spacing);
  return (
    <group>
      <mesh position={world}>
        <sphereGeometry args={[Math.max(1.5, Math.min(spacing[0], spacing[1]) * 0.75), 16, 16]} />
        <meshStandardMaterial color={"#ff5252"} />
      </mesh>
      {a.labelText && (
        <Html position={world} style={{ pointerEvents: "none" }}>
          <div style={{
            background: "rgba(0,0,0,0.6)",
            color: "white",
            padding: "2px 6px",
            borderRadius: 4,
            fontSize: 12,
            whiteSpace: "nowrap",
          }}>
            {a.labelText}
          </div>
        </Html>
      )}
    </group>
  );
}

function Arrow3D({ a, dims, spacing }: { a: Annotation; dims: [number, number, number]; spacing: [number, number, number] }) {
  if (!a.arrowTo || !a.position) return null;
  const start = mapNormToWorld(a.position, dims, spacing);
  const end = mapNormToWorld(a.arrowTo, dims, spacing);
  return <Line points={[start, end]} color="#4f46e5" lineWidth={2} />;
}

function ControlsLayer({
  controlsRef,
  target,
  cameraPosition,
  minDistance,
  maxDistance,
}: {
  controlsRef: React.MutableRefObject<OrbitControlsImpl | null>;
  target: [number, number, number];
  cameraPosition: [number, number, number];
  minDistance: number;
  maxDistance: number;
}) {
  const controls = useRef<OrbitControlsImpl | null>(null);
  const { camera } = useThree();

  useEffect(() => {
    camera.position.set(...cameraPosition);
    camera.lookAt(...target);
  }, [camera, cameraPosition, target]);

  useEffect(() => {
    if (!controls.current) return;
    controlsRef.current = controls.current;
    controls.current.enableDamping = true;
    controls.current.dampingFactor = 0.1;
    controls.current.target.set(...target);
    controls.current.saveState();
    controls.current.update();
    return () => {
      controlsRef.current = null;
    };
  }, [target, controlsRef]);

  return (
    <OrbitControls
      ref={(instance) => {
        controls.current = instance ?? null;
      }}
      enablePan
      enableZoom
      enableRotate
      minDistance={minDistance}
      maxDistance={maxDistance}
    />
  );
}

export default function Viewer3D() {
  const {
    volumeData,
    annotations,
    tool,
    addAnnotation,
    viewerSettings,
    generatedMesh,
  } = useAppState();

  const [arrowDraftStart, setArrowDraftStart] = useState<[number, number, number] | null>(null);

  const depth = volumeData?.depth ?? 0;

  const onAnnotClick = useCallback((norm: [number, number, number]) => {
    // Convert normalized z to sliceIndex for consistency with 2D annotations
    const zNorm = norm[2];
    const inferredSlice = Math.min(depth - 1, Math.max(0, Math.round(zNorm * depth)));

    if (tool === "select") {
      // setSelectedAnnotationId(undefined); // This line was removed from the new_code, so it's removed here.
      return;
    }

    if (tool === "marker") {
      addAnnotation({ type: "marker", position: norm, sliceIndex: inferredSlice });
      return;
    }

    if (tool === "label") {
      const text = prompt("Label text?") || "";
      addAnnotation({ type: "label", position: norm, labelText: text, sliceIndex: inferredSlice });
      return;
    }

    if (tool === "arrow") {
      if (!arrowDraftStart) {
        setArrowDraftStart(norm);
        // setSelectedAnnotationId(undefined); // This line was removed from the new_code, so it's removed here.
      } else {
        // finalize arrow
        addAnnotation({ type: "arrow", position: arrowDraftStart, arrowTo: norm, sliceIndex: inferredSlice });
        setArrowDraftStart(null);
      }
      return;
    }
  }, [addAnnotation, arrowDraftStart, depth, setArrowDraftStart, tool]);

  const hasVolume = !!volumeData;
  const width = volumeData?.width ?? 0;
  const height = volumeData?.height ?? 0;
  const spacing: [number, number, number] = volumeData?.spacing ?? [1, 1, 1];
  const dims: [number, number, number] = [width, height, depth];

  const [sx, sy, sz] = spacing;
  const Wmm = width * sx;
  const Hmm = height * sy;
  const Dmm = depth * sz;
  const opacity = Math.min(1, Math.max(0.1, viewerSettings.axialOpacity));
  const volumeHalf = useMemo<[number, number, number]>(() => [Wmm / 2, Hmm / 2, Dmm / 2], [Wmm, Hmm, Dmm]);
  const volumeCenter = useMemo<[number, number, number]>(() => [0, 0, 0], []);
  const meshOffset = useMemo<[number, number, number]>(() => [-volumeHalf[0], -volumeHalf[1], -volumeHalf[2]], [volumeHalf]);
  const longestDimension = Math.max(Wmm, Hmm, Dmm) || 1;
  const defaultCameraPosition = useMemo<[number, number, number]>(() => {
    return [volumeCenter[0] + longestDimension * 0.6, volumeCenter[1] + longestDimension, volumeCenter[2] + longestDimension * 0.8];
  }, [volumeCenter, longestDimension]);

  const controlsRef = useRef<OrbitControlsImpl | null>(null);

  const updateCamera = useCallback(
    (position: [number, number, number], target: [number, number, number]) => {
      const controls = controlsRef.current;
      if (!controls) return;
      const cam = controls.object as THREE.PerspectiveCamera;
      cam.position.set(...position);
      controls.target.set(...target);
      controls.update();
    },
    []
  );

  const handleResetView = useCallback(() => {
    updateCamera(defaultCameraPosition, volumeCenter);
  }, [defaultCameraPosition, updateCamera, volumeCenter]);

  const handleTopView = useCallback(() => {
    const topPosition: [number, number, number] = [volumeCenter[0], volumeCenter[1] + longestDimension * 1.5, volumeCenter[2]];
    updateCamera(topPosition, volumeCenter);
  }, [volumeCenter, longestDimension, updateCamera]);

  const handleFrontView = useCallback(() => {
    const frontPosition: [number, number, number] = [volumeCenter[0], volumeCenter[1], volumeCenter[2] + longestDimension * 1.5];
    updateCamera(frontPosition, volumeCenter);
  }, [volumeCenter, longestDimension, updateCamera]);

  const rotateStep = Math.PI / 12;
  const handleRotateLeft = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const azimuth = controls.getAzimuthalAngle();
    controls.setAzimuthalAngle(azimuth + rotateStep);
    controls.update();
  }, [rotateStep]);

  const handleRotateRight = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const azimuth = controls.getAzimuthalAngle();
    controls.setAzimuthalAngle(azimuth - rotateStep);
    controls.update();
  }, [rotateStep]);

  const handleTiltUp = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const polar = controls.getPolarAngle();
    controls.setPolarAngle(polar - rotateStep);
    controls.update();
  }, [rotateStep]);

  const handleTiltDown = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const polar = controls.getPolarAngle();
    controls.setPolarAngle(polar + rotateStep);
    controls.update();
  }, [rotateStep]);

  const handleZoomIn = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    controls.dollyIn(0.9);
    controls.update();
  }, []);

  const handleZoomOut = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    controls.dollyOut(0.9);
    controls.update();
  }, []);

  const [showControls, setShowControls] = useState(true);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 shadow-sm dark:border-zinc-800">
      <h2 className="mb-2 text-lg font-semibold">3D Viewer</h2>
      {!hasVolume ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Load a DICOM series to view the 3D scene.</p>
      ) : (
        <div className="relative" style={{ width: "100%", height: 640 }}>
          <Canvas
            camera={{ position: defaultCameraPosition, near: 0.1, far: longestDimension * 5 }}
            gl={{ preserveDrawingBuffer: true }}
            style={{ background: "linear-gradient(180deg, #f7fafc 0%, #e2e8f0 100%)" }}
          >
            <ambientLight intensity={0.6} />
            <directionalLight position={[volumeHalf[0], volumeHalf[1], volumeHalf[2]]} intensity={0.7} />

            <ControlsLayer
              controlsRef={controlsRef}
              target={volumeCenter}
              cameraPosition={defaultCameraPosition}
              minDistance={longestDimension * 0.2}
              maxDistance={longestDimension * 4}
            />

            {annotations.map((a) => (
              <React.Fragment key={a.id}>
                {(a.type === "marker" || a.type === "label") && <Marker3D a={a} dims={dims} spacing={spacing} />}
                {a.type === "arrow" && <Arrow3D a={a} dims={dims} spacing={spacing} />}
              </React.Fragment>
            ))}

            <gridHelper
              args={[Math.max(Wmm, Hmm, Dmm), 20]}
              position={volumeCenter}
            />
            <primitive object={new THREE.AxesHelper(Math.min(Wmm, Hmm, Dmm) * 0.25)} position={volumeCenter} />

            {generatedMesh && (
              <mesh position={meshOffset}>
                <bufferGeometry
                  attach="geometry"
                  onUpdate={(geom) => {
                    geom.computeVertexNormals();
                  }}
                >
                  <bufferAttribute attach="attributes-position" args={[generatedMesh.positions, 3]} needsUpdate />
                  <bufferAttribute attach="attributes-normal" args={[generatedMesh.normals, 3]} needsUpdate />
                  <bufferAttribute attach="index" args={[generatedMesh.indices, 1]} needsUpdate />
                </bufferGeometry>
                <meshStandardMaterial color="#93c5fd" transparent opacity={0.6} side={THREE.DoubleSide} />
              </mesh>
            )}
          </Canvas>

          {showControls && (
            <div className="pointer-events-none absolute right-4 top-4 flex flex-col gap-2">
              <div className="pointer-events-auto rounded-md border border-zinc-300 bg-white/90 p-2 shadow-md backdrop-blur dark:border-zinc-700 dark:bg-zinc-900/90">
                <div className="flex flex-col gap-2 text-xs">
                  <span className="font-semibold text-zinc-700 dark:text-zinc-200">View Controls</span>
                  <div className="grid grid-cols-2 gap-2">
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleResetView}>
                      Reset
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleTopView}>
                      Top
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleFrontView}>
                      Front
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleRotateLeft}>
                      Rotate ←
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleRotateRight}>
                      Rotate →
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleTiltUp}>
                      Tilt ↑
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleTiltDown}>
                      Tilt ↓
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleZoomIn}>
                      Zoom +
                    </button>
                    <button className="rounded bg-zinc-200 px-2 py-1 font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100" onClick={handleZoomOut}>
                      Zoom -
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
          <button
            type="button"
            onClick={() => setShowControls((prev) => !prev)}
            className="absolute left-4 top-4 rounded-md border border-zinc-300 bg-white/90 px-3 py-1 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-white dark:border-zinc-700 dark:bg-zinc-900/80 dark:text-zinc-200"
          >
            {showControls ? "Hide controls" : "Show controls"}
          </button>
        </div>
      )}
      <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
        Tip: Use the buttons or drag with the mouse/touch to explore the mesh. Scroll or pinch to zoom.
      </p>
    </div>
  );
}
