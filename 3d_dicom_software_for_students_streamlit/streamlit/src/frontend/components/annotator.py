"""Snapshot-based 2D annotation canvas."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from streamlit.elements import image as st_image


def _ensure_image_to_url() -> None:
    if hasattr(st_image, "image_to_url"):
        return

    def image_to_url(image, width, clamp, channels, output_format, image_id):
        fmt = (output_format or "PNG").upper()
        buffer = BytesIO()
        image.save(buffer, format=fmt)
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/{fmt.lower()};base64,{data}"

    st_image.image_to_url = image_to_url


_ensure_image_to_url()


def _load_background_image(snapshot: dict[str, Any], max_width: int = 900) -> Image.Image:
    data = base64.b64decode(snapshot["data_base64"])
    image = Image.open(BytesIO(data)).convert("RGBA")
    if image.width <= max_width:
        return image
    scale = max_width / image.width
    new_size = (max_width, int(image.height * scale))
    return image.resize(new_size)


def render_snapshot_annotator(snapshot: dict[str, Any], *, key_prefix: str = "annotator") -> dict[str, Any] | None:
    """Render a drawable canvas for the given snapshot.

    Returns the updated annotation json payload when the user saves changes.
    """

    snapshot_id = snapshot.get("snapshot_id", "snapshot")
    container = st.container()
    with container:
        st.markdown("##### Annotate snapshot")
        col_mode, col_color, col_text = st.columns([1.2, 1, 1.4])
        mode = col_mode.selectbox(
            "Tool",
            options=["Marker", "Arrow", "Label"],
            key=f"{key_prefix}-mode-{snapshot_id}",
        )
        color = col_color.color_picker(
            "Color",
            value="#FF4136",
            key=f"{key_prefix}-color-{snapshot_id}",
        )
        label_text = col_text.text_input(
            "Label text",
            key=f"{key_prefix}-text-{snapshot_id}",
            placeholder="Label content (used when tool=Label)",
        )

        drawing_mode_map = {
            "Marker": "circle",
            "Arrow": "line",
            "Label": "rect",
        }
        drawing_mode = drawing_mode_map[mode]

        bg_image = _load_background_image(snapshot)
        canvas_json = snapshot.get("annotations2d")

        canvas_result = st_canvas(
            fill_color=f"{color}55",
            stroke_width=3,
            stroke_color=color,
            background_color="#ffffff",
            background_image=bg_image,
            update_streamlit=True,
            height=bg_image.height,
            width=bg_image.width,
            drawing_mode=drawing_mode,
            initial_drawing=canvas_json,
            key=f"{key_prefix}-canvas-{snapshot_id}",
        )

        col_actions = st.columns([1, 1, 2])
        save_pressed = col_actions[0].button(
            "Save annotations",
            key=f"{key_prefix}-save-{snapshot_id}",
            type="primary",
        )
        clear_pressed = col_actions[1].button(
            "Clear",
            key=f"{key_prefix}-clear-{snapshot_id}",
        )

        if clear_pressed:
            return {"objects": []}

        if save_pressed:
            data = {"objects": []}
            if canvas_result and canvas_result.json_data:
                data = canvas_result.json_data
            if mode == "Label" and label_text:
                for obj in data.get("objects", []):
                    if obj.get("type") == "rect" and not obj.get("labelText"):
                        obj["labelText"] = label_text
            return data

    return None

