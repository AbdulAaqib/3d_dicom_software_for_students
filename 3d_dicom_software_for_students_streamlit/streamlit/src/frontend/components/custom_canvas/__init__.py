from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

import streamlit.components.v1 as components

ComponentReturn = dict[str, Any]

# Determine if we're in development mode
_RELEASE = True  # Set to False and run `npm run dev` in frontend/ for development

_COMPONENT_ROOT = Path(__file__).parent / "frontend" / "dist"

# Declare component with proper mode handling
if not _RELEASE:
    # Development mode: frontend dev server must be running on port 5173
    _SNAPSHOT_CANVAS = components.declare_component(
        "snapshot_canvas",
        url="http://localhost:5173",
    )
else:
    # Production mode: use built files
    _SNAPSHOT_CANVAS = components.declare_component(
        "snapshot_canvas",
        path=str(_COMPONENT_ROOT),
    )


@dataclass
class SnapshotCanvasResult:
    """Return payload for the snapshot canvas component."""

    annotations: dict[str, Any]
    image_data_url: str | None
    reason: str


def render_snapshot_canvas(
    *,
    background_base64: str,
    mime_type: str = "image/png",
    initial_annotations: dict[str, Any] | None = None,
    stroke_color: str = "#FF4136",
    default_tool: str = "marker",
    label_text: str = "",
    width: int | None = None,
    height: int | None = None,
    show_toolbar: bool = True,
    key: str | None = None,
) -> SnapshotCanvasResult | None:
    """Render the custom canvas component and return edits when available."""

    if not background_base64:
        raise ValueError("background_base64 is required.")

    if not background_base64.startswith("data:"):
        data_url = f"data:{mime_type};base64,{background_base64}"
    else:
        data_url = background_base64

    payload: ComponentReturn | None = _SNAPSHOT_CANVAS(
        component="annotator",
        backgroundImage=data_url,
        initialObjects=initial_annotations or {"objects": []},
        strokeColor=stroke_color,
        defaultTool=default_tool,
        labelText=label_text,
        frameWidth=width,
        frameHeight=height,
        showToolbar=show_toolbar,
        key=key,
    )

    if payload is None:
        return None

    annotations = payload.get("objects") or {"objects": []}
    image_data = payload.get("imageData")
    reason = payload.get("reason", "save")

    return SnapshotCanvasResult(
        annotations=annotations,
        image_data_url=image_data,
        reason=reason,
    )


def render_model_capture(
    *,
    figure: dict[str, Any],
    width: int | None = None,
    height: int | None = None,
    key: str | None = None,
) -> dict[str, Any] | None:
    """Render the custom capture component that returns user interactions."""

    payload: ComponentReturn | None = _SNAPSHOT_CANVAS(
        component="capture",
        figure=figure,
        captureWidth=width,
        captureHeight=height,
        key=key,
    )
    if payload is None:
        return None

    event_type = payload.get("type")
    if not event_type:
        if "imageData" in payload or "image_data" in payload:
            event_type = "capture"
        elif "point" in payload:
            event_type = "click"

    if event_type == "click":
        point = payload.get("point")
        if isinstance(point, dict):
            return {"type": "click", "point": point}
        return {"type": "click", "point": None}

    if event_type == "capture":
        image_data = payload.get("imageData") or payload.get("image_data")
        return {
            "type": "capture",
            "image_data": image_data,
            "notes": payload.get("notes"),
        }

    return payload


__all__ = ["render_snapshot_canvas", "render_model_capture", "SnapshotCanvasResult"]


