"""Snapshot-based 2D annotation canvas backed by a custom Streamlit component."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import streamlit as st
from PIL import Image

from .custom_canvas import render_snapshot_canvas

try:  # Pillow>=9
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for older Pillow
    RESAMPLE_LANCZOS = Image.LANCZOS  # type: ignore[attr-defined]

def _snapshot_base64(snapshot: dict[str, Any]) -> str:
    payload = snapshot.get("annotated_base64") or snapshot.get("data_base64")
    if not payload:
        raise ValueError("Snapshot is missing base64 payload.")
    return payload


def _load_snapshot_image(snapshot: dict[str, Any]) -> Image.Image:
    raw = _snapshot_base64(snapshot)
    data = base64.b64decode(raw)
    return Image.open(BytesIO(data)).convert("RGBA")


def _snapshot_frame_dimensions(snapshot: dict[str, Any], max_width: int = 900) -> tuple[int, int]:
    image = _load_snapshot_image(snapshot)
    width, height = image.size
    if width <= max_width:
        return width, height
    scale = max_width / width
    return max_width, int(height * scale)


def _prefer_existing_annotations(snapshot: dict[str, Any]) -> dict[str, Any]:
    annotations = snapshot.get("annotations2d")
    if isinstance(annotations, dict):
        return annotations
    if isinstance(annotations, list):
        return {"objects": annotations}
    return {"objects": []}


def _background_data_url(snapshot: dict[str, Any]) -> str:
    mime_type = snapshot.get("mime_type", "image/png")
    return f"data:{mime_type};base64,{_snapshot_base64(snapshot)}"


def _composite_with_background(snapshot: dict[str, Any], overlay_data_url: str) -> str:
    """Blend the user's drawing overlay with the snapshot background."""

    overlay_payload = overlay_data_url.split(",", 1)[-1]
    overlay = Image.open(BytesIO(base64.b64decode(overlay_payload))).convert("RGBA")

    background = _load_snapshot_image(snapshot)
    if background.size != overlay.size:
        background = background.resize(overlay.size, RESAMPLE_LANCZOS)

    combined = Image.alpha_composite(background, overlay)
    buffer = BytesIO()
    combined.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def render_snapshot_annotator(
    snapshot: dict[str, Any],
    *,
    key_prefix: str = "annotator",
) -> dict[str, Any] | None:
    """Render a drawable canvas for the given snapshot.

    Returns the updated annotation json payload when the user saves changes.
    """

    snapshot_id = snapshot.get("snapshot_id", "snapshot")
    frame_width, frame_height = _snapshot_frame_dimensions(snapshot)
    annotations = _prefer_existing_annotations(snapshot)
    data_url = _background_data_url(snapshot)

    canvas_result = render_snapshot_canvas(
        background_base64=data_url,
        mime_type=snapshot.get("mime_type", "image/png"),
        initial_annotations=annotations,
        stroke_color="#FF4136",
        default_tool="marker",
        label_text="",
        width=frame_width,
        height=frame_height,
        show_toolbar=True,
        key=f"{key_prefix}-canvas-{snapshot_id}",
    )

    if canvas_result is None:
        return None

    updated_annotations = canvas_result.annotations
    annotated_base64 = None
    if canvas_result.image_data_url:
        try:
            annotated_base64 = _composite_with_background(snapshot, canvas_result.image_data_url)
        except Exception:  # pragma: no cover - fallback if PIL merge fails
            image_data = canvas_result.image_data_url
            annotated_base64 = (
                image_data.split(",", 1)[-1] if "base64," in image_data else image_data
            )

    return {
        "annotations": updated_annotations,
        "annotated_base64": annotated_base64,
        "reason": canvas_result.reason,
    }

