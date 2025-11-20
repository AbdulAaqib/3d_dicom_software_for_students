import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Streamlit } from "streamlit-component-lib";
import { ReactSketchCanvas, ReactSketchCanvasRef } from "react-sketch-canvas";
import { Palette, Undo, Redo, Eraser, Save, Trash2 } from "./Icons";
import "./styles.css";

export type Tool = "pen" | "eraser";

export interface SnapshotArgs {
  backgroundImage: string;
  initialObjects?: Record<string, unknown>;
  strokeColor?: string;
  defaultTool?: Tool;
  labelText?: string;
  frameWidth?: number;
  frameHeight?: number;
  showToolbar?: boolean;
}

interface Props {
  args?: SnapshotArgs;
}

const PRESET_COLORS = [
  "#000000", // Black
  "#FF0000", // Red
  "#00FF00", // Green
  "#0000FF", // Blue
  "#FFFF00", // Yellow
  "#FFA500", // Orange
  "#800080", // Purple
  "#FF69B4", // Pink
  "#FFFFFF", // White
];

const SnapshotCanvas = ({ args }: Props) => {
  const {
    backgroundImage,
    initialObjects,
    strokeColor = "#FF0000",
    frameWidth,
    frameHeight,
    showToolbar = true,
  } = args ?? {};

  const canvasRef = useRef<ReactSketchCanvasRef>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<Tool>("pen");
  const [color, setColor] = useState<string>(strokeColor);
  const [brushSize, setBrushSize] = useState<number>(4);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const canvasWidth = useMemo(() => frameWidth ?? 900, [frameWidth]);
  const canvasHeight = useMemo(() => frameHeight ?? 600, [frameHeight]);
  const canvasStyle = useMemo(
    () => ({
      width: `${canvasWidth}px`,
      height: `${canvasHeight}px`,
    }),
    [canvasWidth, canvasHeight],
  );

  const handleUndo = useCallback(() => {
    if (canvasRef.current) {
      canvasRef.current.undo();
    }
  }, []);

  const handleRedo = useCallback(() => {
    if (canvasRef.current) {
      canvasRef.current.redo();
    }
  }, []);

  const handleClearCanvas = useCallback(() => {
    if (canvasRef.current) {
      canvasRef.current.clearCanvas();
    }
  }, []);

  const toggleEraser = useCallback(() => {
    if (canvasRef.current) {
      if (tool === "pen") {
        setTool("eraser");
        canvasRef.current.eraseMode(true);
      } else {
        setTool("pen");
        canvasRef.current.eraseMode(false);
      }
    }
  }, [tool]);

  const handleColorSelect = useCallback((newColor: string) => {
    setColor(newColor);
    setShowColorPicker(false);
    setTool("pen");
    if (canvasRef.current) {
      canvasRef.current.eraseMode(false);
    }
  }, []);

  const exportCanvas = useCallback(
    async (reason: "save" | "clear") => {
      if (!canvasRef.current) return;

      try {
        setIsSaving(true);
        const imageData = await canvasRef.current.exportImage("png");
        const paths = await canvasRef.current.exportPaths();

        Streamlit.setComponentValue({
          objects: { paths },
          imageData,
          reason,
        });
      } catch (error) {
        console.error("Failed to export canvas:", error);
      } finally {
        setTimeout(() => setIsSaving(false), 500);
      }
    },
    []
  );

  const handleSaveAndClear = useCallback(async () => {
    await exportCanvas("clear");
    setTimeout(() => {
      handleClearCanvas();
    }, 100);
  }, [exportCanvas, handleClearCanvas]);

  // Load initial paths if provided
  useEffect(() => {
    if (!canvasRef.current || !initialObjects) return;

    try {
      const paths = (initialObjects as any)?.paths;
      if (paths && Array.isArray(paths)) {
        canvasRef.current.loadPaths(paths);
      }
    } catch (error) {
      console.warn("Failed to load initial annotations:", error);
    }
  }, [initialObjects]);

  // Update frame height for Streamlit
  useEffect(() => {
    Streamlit.setFrameHeight(
      (containerRef.current?.scrollHeight ?? 0) + 40
    );
  });

  return (
    <div className="snapshot-shell" ref={containerRef}>
      {/* Drawing Area with Background */}
      <div className="canvas-container" style={canvasStyle}>
        {/* Background Image */}
        {backgroundImage && (
          <div
            className="canvas-background"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: `${canvasWidth}px`,
              height: `${canvasHeight}px`,
              backgroundImage: `url(${backgroundImage})`,
              backgroundSize: "100% 100%",
              backgroundRepeat: "no-repeat",
              backgroundPosition: "center",
              pointerEvents: "none",
              zIndex: 0,
            }}
          />
        )}

        {/* Drawing Canvas */}
        <div className="canvas-layer" style={canvasStyle}>
          <ReactSketchCanvas
            ref={canvasRef}
            width={`${canvasWidth}px`}
            height={`${canvasHeight}px`}
            strokeWidth={brushSize}
            strokeColor={tool === "eraser" ? "rgba(0,0,0,0)" : color}
            canvasColor="transparent"
            className="drawing-canvas"
          />
        </div>

        {/* Floating Toolbar - Top Center */}
        {showToolbar && (
          <div className="floating-toolbar">
            {/* Top Toolbar - Color & Brush */}
            <div className="toolbar-section">
              <button
                onClick={() => setShowColorPicker(!showColorPicker)}
                className="toolbar-btn"
                title="Color Picker"
              >
                <div className="relative">
                  <Palette className="w-4 h-4" />
                  <div
                    className="color-indicator"
                    style={{ backgroundColor: color }}
                  />
                </div>
              </button>
              <div className="toolbar-divider" />
              <div className="brush-size-container">
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={brushSize}
                  onChange={(e) => setBrushSize(Number(e.target.value))}
                  className="brush-slider"
                  title="Brush Size"
                />
                <span className="brush-size-label">{brushSize}px</span>
              </div>
            </div>

            {/* Bottom Toolbar - Actions */}
            <div className="toolbar-section">
              <button
                onClick={handleUndo}
                className="toolbar-btn"
                title="Undo"
              >
                <Undo className="w-4 h-4" />
              </button>
              <button
                onClick={handleRedo}
                className="toolbar-btn"
                title="Redo"
              >
                <Redo className="w-4 h-4" />
              </button>
              <div className="toolbar-divider" />
              <button
                onClick={toggleEraser}
                className={`toolbar-btn ${tool === "eraser" ? "active" : ""}`}
                title="Eraser"
              >
                <Eraser className="w-4 h-4" />
              </button>
              <button
                onClick={handleClearCanvas}
                className="toolbar-btn"
                title="Clear All"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            {/* Color Picker Popup */}
            {showColorPicker && (
              <div className="color-picker-popup">
                <div className="color-grid">
                  {PRESET_COLORS.map((presetColor) => (
                    <button
                      key={presetColor}
                      onClick={() => handleColorSelect(presetColor)}
                      className="color-swatch"
                      style={{ backgroundColor: presetColor }}
                      title={presetColor}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Save Actions */}
      <div className="actions">
        <button
          type="button"
          className={`btn-primary ${isSaving ? "saving" : ""}`}
          onClick={() => exportCanvas("save")}
          disabled={isSaving}
        >
          {isSaving ? (
            <>
              <div className="spinner" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save Annotations
            </>
          )}
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={handleSaveAndClear}
          disabled={isSaving}
        >
          <Trash2 className="w-4 h-4" />
          Save & Clear
        </button>
        <button
          type="button"
          className="btn-clear"
          onClick={handleClearCanvas}
          disabled={isSaving}
        >
          <Trash2 className="w-4 h-4" />
          Clear Canvas
        </button>
      </div>
    </div>
  );
};

export default SnapshotCanvas;
