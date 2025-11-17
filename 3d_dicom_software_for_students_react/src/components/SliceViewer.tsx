"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppState } from '@/state/AppState';

function clamp01(n: number) {
  return Math.max(0, Math.min(1, n));
}

export default function SliceViewer() {
  const {
    volumeData,
    sliceIndex,
    tool,
    addAnnotation,
    annotations,
    selectedAnnotationId,
    setSelectedAnnotationId,
    updateAnnotation,
    deleteAnnotation,
  } = useAppState();

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });

  // Arrow drafting state (start point in normalized coords and optional marker link)
  const [arrowDraftStart, setArrowDraftStart] = useState<[number, number] | null>(null);
  const [arrowFromMarkerId, setArrowFromMarkerId] = useState<string | undefined>(undefined);
  const [cursorNorm, setCursorNorm] = useState<[number, number] | null>(null);

  // dragging state
  const dragRef = useRef<{
    id?: string;
    kind?: 'marker' | 'label' | 'arrow-start' | 'arrow-end';
  }>({});

  const frame = useMemo(() => {
    if (!volumeData) return undefined;
    return volumeData.frames8[sliceIndex];
  }, [sliceIndex, volumeData]);

  // draw pixel data to canvas
  useEffect(() => {
    if (!volumeData || !frame) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const { width, height } = volumeData;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const imageData = ctx.createImageData(width, height);
    const data = imageData.data; // RGBA
    const gray = frame;
    for (let i = 0, j = 0; i < gray.length; i++, j += 4) {
      const v = gray[i];
      data[j] = v;
      data[j + 1] = v;
      data[j + 2] = v;
      data[j + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
  }, [frame, volumeData]);

  // responsive container sizing to keep aspect ratio
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    function onResize() {
      const el = wrapperRef.current;
      if (!el || !volumeData) return;
      const bounds = el.getBoundingClientRect();
      const ar = volumeData.width / volumeData.height;
      let w = bounds.width;
      let h = w / ar;
      const maxH = 640;
      if (h > maxH) {
        h = maxH;
        w = h * ar;
      }
      setContainerSize({ w: Math.round(w), h: Math.round(h) });
    }
    onResize();
    const ro = new ResizeObserver(onResize);
    if (wrapperRef.current) ro.observe(wrapperRef.current);
    return () => ro.disconnect();
  }, [volumeData]);

  // Shortcuts: Delete to delete selected, Esc to cancel arrow draft or selection
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedAnnotationId) deleteAnnotation(selectedAnnotationId);
      } else if (e.key === 'Escape') {
        setArrowDraftStart(null);
        setArrowFromMarkerId(undefined);
        setCursorNorm(null);
        setSelectedAnnotationId(undefined);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [deleteAnnotation, selectedAnnotationId, setSelectedAnnotationId]);

  const getNormFromEvent = useCallback((clientX: number, clientY: number) => {
    if (!overlayRef.current) return null as [number, number] | null;
    const rect = overlayRef.current.getBoundingClientRect();
    const nx = clamp01((clientX - rect.left) / rect.width);
    const ny = clamp01((clientY - rect.top) / rect.height);
    return [nx, ny] as [number, number];
  }, []);

  const handleOverlayMove = useCallback((e: React.MouseEvent) => {
    if (!arrowDraftStart) return;
    const n = getNormFromEvent(e.clientX, e.clientY);
    if (n) setCursorNorm(n);
  }, [arrowDraftStart, getNormFromEvent]);

  const handleOverlayClick = useCallback((e: React.MouseEvent) => {
    if (!volumeData) return;

    // Select tool just clears selection on background click
    if (tool === 'select') {
      setSelectedAnnotationId(undefined);
      return;
    }

    // Marker and label handled via separate click-to-place
    if (tool === 'marker' || tool === 'label') {
      const n = getNormFromEvent(e.clientX, e.clientY);
      if (!n) return;
      const pos: [number, number, number] = [n[0], n[1], volumeData.depth <= 1 ? 0.0 : sliceIndex / (volumeData.depth - 1)];
      if (tool === 'marker') {
        addAnnotation({ type: 'marker', position: pos, sliceIndex });
      } else {
        const text = prompt('Label text?') || '';
        addAnnotation({ type: 'label', position: pos, labelText: text, sliceIndex });
      }
      return;
    }

    // Arrow tool: robust draft state with optional marker link
    if (tool === 'arrow') {
      let start: [number, number] | null = arrowDraftStart;
      let startLink: string | undefined = arrowFromMarkerId;

      // If no draft yet, initialize start (prefer selected marker)
      if (!start) {
        // If a marker is selected on this slice, snap to it and link
        const sel = annotations.find((a) => a.id === selectedAnnotationId && a.type === 'marker' && a.sliceIndex === sliceIndex);
        if (sel) {
          start = [sel.position[0], sel.position[1]];
          startLink = sel.id;
        } else {
          const n = getNormFromEvent(e.clientX, e.clientY);
          if (!n) return;
          start = n;
          startLink = undefined;
        }
        setArrowDraftStart(start);
        setArrowFromMarkerId(startLink);
        setCursorNorm(null);
        return; // Wait for end click
      }

      // We have a draft start; finalize end
      const endN = getNormFromEvent(e.clientX, e.clientY);
      if (!endN) return;
      const z = volumeData.depth <= 1 ? 0.0 : sliceIndex / (volumeData.depth - 1);
      const dx = endN[0] - start[0];
      const dy = endN[1] - start[1];
      const dist2 = dx * dx + dy * dy;
      if (dist2 < 1e-6) {
        // Too short; cancel draft
        setArrowDraftStart(null);
        setArrowFromMarkerId(undefined);
        setCursorNorm(null);
        return;
      }
      addAnnotation({
        type: 'arrow',
        position: [start[0], start[1], z],
        arrowTo: [endN[0], endN[1], z],
        sliceIndex,
        linkedToId: startLink,
      });
      setArrowDraftStart(null);
      setArrowFromMarkerId(undefined);
      setCursorNorm(null);
      return;
    }
  }, [addAnnotation, annotations, arrowDraftStart, arrowFromMarkerId, getNormFromEvent, selectedAnnotationId, setSelectedAnnotationId, sliceIndex, tool, volumeData]);

  const visibleAnnotations = useMemo(() => {
    if (!volumeData) return [] as typeof annotations;
    const currentZ = volumeData.depth <= 1 ? 0 : sliceIndex / (volumeData.depth - 1);
    const tol = 1e-3;
    return annotations.filter((a) => {
      if (typeof a.sliceIndex === 'number') return a.sliceIndex === sliceIndex;
      // fallback to z match if sliceIndex missing
      return Math.abs((a.position?.[2] ?? currentZ) - currentZ) < tol;
    });
  }, [annotations, sliceIndex, volumeData]);

  // Drag handlers
  const onMouseDownMarker = useCallback((aId: string, kind: 'marker' | 'label') => (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedAnnotationId(aId);
    dragRef.current = { id: aId, kind };

    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current?.id || !overlayRef.current || !volumeData) return;
      const n = getNormFromEvent(ev.clientX, ev.clientY);
      if (!n) return;
      const a = annotations.find((x) => x.id === dragRef.current!.id);
      if (!a) return;
      const nz = a.position?.[2] ?? (volumeData.depth <= 1 ? 0 : sliceIndex / (volumeData.depth - 1));
      // Move the marker/label itself
      updateAnnotation(a.id, { position: [n[0], n[1], nz] as [number, number, number] });
      // If this is a marker, move any linked arrows' start
      if (a.type === 'marker') {
        const linked = annotations.filter((x) => x.type === 'arrow' && x.linkedToId === a.id && x.sliceIndex === sliceIndex);
        linked.forEach((arr) => {
          updateAnnotation(arr.id, { position: [n[0], n[1], nz] as [number, number, number] });
        });
      }
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      dragRef.current = {};
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [annotations, getNormFromEvent, setSelectedAnnotationId, sliceIndex, updateAnnotation, volumeData]);

  const onMouseDownArrowHandle = useCallback((aId: string, endpoint: 'start' | 'end') => (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedAnnotationId(aId);
    dragRef.current = { id: aId, kind: endpoint === 'start' ? 'arrow-start' : 'arrow-end' };

    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current?.id || !overlayRef.current || !volumeData) return;
      const n = getNormFromEvent(ev.clientX, ev.clientY);
      if (!n) return;
      const a = annotations.find((x) => x.id === dragRef.current!.id);
      if (!a) return;
      const nz = a.position?.[2] ?? (volumeData.depth <= 1 ? 0 : sliceIndex / (volumeData.depth - 1));
      if (dragRef.current.kind === 'arrow-start') {
        updateAnnotation(a.id, { position: [n[0], n[1], nz] as [number, number, number], linkedToId: undefined });
      } else if (dragRef.current.kind === 'arrow-end') {
        updateAnnotation(a.id, { arrowTo: [n[0], n[1], nz] as [number, number, number] });
      }
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      dragRef.current = {};
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [annotations, getNormFromEvent, setSelectedAnnotationId, sliceIndex, updateAnnotation, volumeData]);

  if (!volumeData) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-dashed border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        Upload and parse DICOM to view slices
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-200 p-2 shadow-sm dark:border-zinc-800">
      <div ref={wrapperRef} className="relative mx-auto w-full">
        <div
          className="relative mx-auto overflow-hidden rounded-md shadow-sm transition-all duration-300 hover:shadow-md"
          style={{ width: containerSize.w || '100%', height: containerSize.h || 0 }}
        >
          <canvas
            ref={canvasRef}
            className="block h-full w-full select-none pixelated"
          />

          {/* overlay for annotations and interactions */}
          <div
            ref={overlayRef}
            className="pointer-events-auto absolute inset-0 cursor-crosshair"
            onMouseMove={handleOverlayMove}
            onClick={handleOverlayClick}
          >
            {/* SVG for arrows to get nice arrowheads & draggable handles */}
            <svg className="absolute inset-0 h-full w-full" width={containerSize.w} height={containerSize.h}>
              <defs>
                <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto">
                  <polygon points="0 0, 7 3.5, 0 7" fill="currentColor" />
                </marker>
              </defs>
              {/* Existing arrows */}
              {visibleAnnotations.map((a) => {
                if (a.type !== 'arrow' || !a.arrowTo) return null;
                const x1 = (a.position[0] ?? 0) * containerSize.w;
                const y1 = (a.position[1] ?? 0) * containerSize.h;
                const x2 = (a.arrowTo[0] ?? 0) * containerSize.w;
                const y2 = (a.arrowTo[1] ?? 0) * containerSize.h;
                const selected = a.id === selectedAnnotationId;
                return (
                  <g key={`arrow-${a.id}`} className={selected ? 'text-emerald-400' : 'text-emerald-500'}>
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke="currentColor"
                      strokeWidth={selected ? 3 : 2}
                      className="drop-shadow-[0_1px_1px_rgba(0,0,0,0.4)]"
                      markerEnd="url(#arrowhead)"
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        setSelectedAnnotationId(a.id);
                      }}
                    />
                    {/* drag handles */}
                    <circle
                      cx={x1}
                      cy={y1}
                      r={6}
                      className="fill-emerald-500 opacity-80 hover:opacity-100 cursor-grab"
                      onMouseDown={onMouseDownArrowHandle(a.id, 'start')}
                    >
                      <title>Drag start</title>
                    </circle>
                    <circle
                      cx={x2}
                      cy={y2}
                      r={6}
                      className="fill-emerald-500 opacity-80 hover:opacity-100 cursor-grab"
                      onMouseDown={onMouseDownArrowHandle(a.id, 'end')}
                    >
                      <title>Drag end</title>
                    </circle>
                  </g>
                );
              })}

              {/* Ghost arrow while drafting */}
              {tool === 'arrow' && arrowDraftStart && cursorNorm && (
                <g className="text-emerald-400/70">
                  <line
                    x1={arrowDraftStart[0] * containerSize.w}
                    y1={arrowDraftStart[1] * containerSize.h}
                    x2={cursorNorm[0] * containerSize.w}
                    y2={cursorNorm[1] * containerSize.h}
                    stroke="currentColor"
                    strokeDasharray="4 4"
                    strokeWidth={2}
                    markerEnd="url(#arrowhead)"
                  />
                </g>
              )}
            </svg>

            {/* HTML overlay for marker dots and labels (draggable) */}
            {visibleAnnotations.map((a) => {
              const left = `${(a.position[0] ?? 0) * 100}%`;
              const top = `${(a.position[1] ?? 0) * 100}%`;
              const selected = a.id === selectedAnnotationId;
              return (
                <div
                  key={a.id}
                  className="absolute"
                  style={{ left, top, transform: 'translate(-50%, -50%)' }}
                  onMouseDown={(e) => {
                    if (a.type === 'marker' || a.type === 'label') onMouseDownMarker(a.id, a.type)(e);
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedAnnotationId(a.id);
                  }}
                >
                  <div
                    className={`h-3 w-3 rounded-full bg-emerald-500 shadow-md ring-2 transition-transform duration-200 hover:scale-110 ${
                      selected ? 'ring-emerald-400' : 'ring-white/70'
                    }`}
                    title={a.type}
                  />
                  {a.labelText && (
                    <div className="mt-1 max-w-[220px] rounded-md bg-black/80 px-2 py-1 text-xs text-white shadow backdrop-blur">
                      {a.labelText}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        {/* Arrow pending hint */}
        {tool === 'arrow' && (
          <p className="mt-2 text-xs text-indigo-600 dark:text-indigo-400">
            {arrowDraftStart ? 'Arrow: click end point…' : 'Arrow: click start (or select a marker first to link)'}
          </p>
        )}
      </div>
    </div>
  );
}
