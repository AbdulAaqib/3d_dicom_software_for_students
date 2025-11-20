import { useCallback, useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import type { PlotlyHTMLElement, PlotRelayoutEvent, SceneCamera } from "plotly.js";
import { Streamlit } from "streamlit-component-lib";
import "./styles.css";

interface FigureArgs {
  data: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
}

interface CaptureArgs {
  figure: FigureArgs;
  captureWidth?: number;
  captureHeight?: number;
  notes?: string;
}

interface Props {
  args?: CaptureArgs;
}

const ModelCapture = ({ args }: Props) => {
  const figure = args?.figure;
  const captureWidth = args?.captureWidth;
  const captureHeight = args?.captureHeight;

  const plotRef = useRef<HTMLDivElement | null>(null);
  const plotlyInstanceRef = useRef<PlotlyHTMLElement | null>(null);
  const cameraRef = useRef<Partial<SceneCamera> | null>(
    figure?.layout?.scene?.camera ?? null,
  );

  const [isCapturing, setIsCapturing] = useState(false);
  const notes = args?.notes ?? "";

  const handleRelayout = useCallback((eventData: PlotRelayoutEvent) => {
    if (!eventData) {
      return;
    }

    if ("scene.camera" in eventData) {
      const cameraPayload = eventData["scene.camera"] as Partial<SceneCamera>;
      cameraRef.current = {
        ...(cameraRef.current ?? {}),
        ...cameraPayload,
      };
      return;
    }

    const keys = Object.keys(eventData).filter((key) =>
      key.startsWith("scene.camera"),
    );
    if (!keys.length) {
      return;
    }

    if (!cameraRef.current) {
      cameraRef.current = {};
    }

    keys.forEach((key) => {
      const value = eventData[key];
      const path = key.split(".").slice(2); // drop "scene.camera"
      if (!path.length) {
        return;
      }
      let cursor = cameraRef.current as Record<string, unknown>;
      path.forEach((segment, index) => {
        if (index === path.length - 1) {
          cursor[segment] = value as unknown;
          return;
        }
        if (
          typeof cursor[segment] !== "object" ||
          cursor[segment] === null
        ) {
          cursor[segment] = {};
        }
        cursor = cursor[segment] as Record<string, unknown>;
      });
    });
  }, []);

  useEffect(() => {
    if (!plotRef.current || !figure) {
      return;
    }

    const layout: Partial<Plotly.Layout> = {
      ...(figure.layout ?? {}),
      scene: {
        ...(figure.layout?.scene ?? {}),
        camera:
          cameraRef.current ??
          (figure.layout?.scene?.camera as Partial<SceneCamera> | undefined) ??
          undefined,
      },
    };

    if (!cameraRef.current && layout.scene?.camera) {
      cameraRef.current = layout.scene.camera;
    }

    let isCancelled = false;

    const renderPlot = async () => {
      const target = plotRef.current as PlotlyHTMLElement | null;
      if (!target) {
        return;
      }

      const graphDiv = await Plotly.react(target, figure.data, layout, {
        displaylogo: false,
        responsive: true,
        scrollZoom: true,
        ...(figure.config ?? {}),
      });

      if (isCancelled) {
        return;
      }

      (graphDiv as unknown as {
        on?: (event: string, handler: (...args: unknown[]) => void) => void;
      }).on?.("plotly_relayout", handleRelayout as unknown as (...args: unknown[]) => void);

      plotlyInstanceRef.current = graphDiv;
    };

    renderPlot();

    return () => {
      isCancelled = true;
      const graphDiv = plotlyInstanceRef.current;
      (graphDiv as unknown as {
        removeListener?: (event: string, handler: (...args: unknown[]) => void) => void;
      })?.removeListener?.("plotly_relayout", handleRelayout as unknown as (...args: unknown[]) => void);
    };
  }, [figure, handleRelayout]);

  useEffect(() => {
    Streamlit.setFrameHeight(document.body.scrollHeight + 40);
  });

  const ensureCameraApplied = async () => {
    if (cameraRef.current && plotlyInstanceRef.current) {
      await Plotly.relayout(plotlyInstanceRef.current, {
        "scene.camera": cameraRef.current,
      });
    }
  };

  const handleCapture = async () => {
    const graphDiv =
      plotlyInstanceRef.current ??
      (plotRef.current as PlotlyHTMLElement | null);
    if (!graphDiv) {
      return;
    }

    setIsCapturing(true);
    try {
      await ensureCameraApplied();
      const dataUrl = await Plotly.toImage(graphDiv, {
        format: "png",
        width: captureWidth,
        height: captureHeight,
      });
      Streamlit.setComponentValue({
        imageData: dataUrl,
        notes,
      });
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to capture image", error);
    } finally {
      setIsCapturing(false);
    }
  };

  if (!figure) {
    return <div className="snapshot-shell">Missing figure payload.</div>;
  }

  return (
    <div className="snapshot-shell">
      <div className="canvas-wrap" style={{ minHeight: 480 }}>
        <div ref={plotRef} style={{ width: "100%", height: 480 }} />
      </div>
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={isCapturing}
          onClick={handleCapture}
        >
          {isCapturing ? "Capturing…" : "Capture snapshot"}
        </button>
      </div>
    </div>
  );
};

export default ModelCapture;



