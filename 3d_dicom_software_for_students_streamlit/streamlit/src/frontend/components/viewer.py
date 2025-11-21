"""STL viewer, annotations, and snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64
import math
import time
import uuid
from typing import Any

import numpy as np
import streamlit as st
try:  # pragma: no cover - optional dependency
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - optional dependency
    go = None
from backend import ConversionResult
from backend.annotation_store import (
    load_annotations,
    save_annotations,
    save_snapshots,
    list_all_snapshots,
)
from .annotator import render_snapshot_annotator
from .custom_canvas import render_model_capture

try:
    from stl import mesh as np_stl
except ImportError:  # pragma: no cover - optional dependency
    np_stl = None


SELECTED_POINT_STATE_KEY = "stl_selected_point"
ARROW_VECTOR_STATE_KEY = "stl_selected_vector"
ARROW_TIP_STATE_KEY = "stl_arrow_tip_point"
LAST_CLICK_POINT_STATE_KEY = "stl_last_click_point"
VIEWER_FLASH_MESSAGE_KEY = "stl_viewer_flash_message"
DEFAULT_MARKER_COLOR = "#FF4136"




class ViewerError(RuntimeError):
    """Raised when the STL viewer cannot render a mesh."""


@dataclass
class MeshData:
    vertices: np.ndarray
    faces: np.ndarray
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def _pop_flash_message() -> str | None:
    return st.session_state.pop(VIEWER_FLASH_MESSAGE_KEY, None)


def _set_flash_message(message: str) -> None:
    st.session_state[VIEWER_FLASH_MESSAGE_KEY] = message


def _normalize_point_payload(point: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(point, dict):
        return None
    try:
        normalized = {
            "x": float(point.get("x", 0.0)),
            "y": float(point.get("y", 0.0)),
            "z": float(point.get("z", 0.0)),
        }
    except (TypeError, ValueError):
        return None
    if "dataName" in point:
        normalized["dataName"] = point.get("dataName")
    if "curveNumber" in point:
        normalized["curveNumber"] = point.get("curveNumber")
    if "pointNumber" in point:
        normalized["pointNumber"] = point.get("pointNumber")
    return normalized


def _get_selected_point() -> dict[str, Any] | None:
    point = st.session_state.get(SELECTED_POINT_STATE_KEY)
    if isinstance(point, dict):
        return _normalize_point_payload(point)
    return None


def _set_selected_point(point: dict[str, Any]) -> dict[str, Any] | None:
    normalized = _normalize_point_payload(point)
    if normalized:
        st.session_state[SELECTED_POINT_STATE_KEY] = normalized
    return normalized


def _clear_selected_point() -> None:
    st.session_state.pop(SELECTED_POINT_STATE_KEY, None)


def _get_selected_vector() -> dict[str, float] | None:
    vector = st.session_state.get(ARROW_VECTOR_STATE_KEY)
    if not isinstance(vector, dict):
        return None
    try:
        return {
            "u": float(vector.get("u", 0.0)),
            "v": float(vector.get("v", 0.0)),
            "w": float(vector.get("w", 0.0)),
        }
    except (TypeError, ValueError):
        return None


def _set_selected_vector(vector: dict[str, Any]) -> dict[str, float] | None:
    normalized = _get_selected_vector_from_payload(vector)
    if normalized:
        st.session_state[ARROW_VECTOR_STATE_KEY] = normalized
    return normalized


def _clear_selected_vector() -> None:
    st.session_state.pop(ARROW_VECTOR_STATE_KEY, None)
    st.session_state.pop(ARROW_TIP_STATE_KEY, None)


def _get_selected_vector_from_payload(vector: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(vector, dict):
        return None
    try:
        return {
            "u": float(vector.get("u", 0.0)),
            "v": float(vector.get("v", 0.0)),
            "w": float(vector.get("w", 0.0)),
        }
    except (TypeError, ValueError):
        return None


def _get_arrow_tip_point() -> dict[str, Any] | None:
    tip = st.session_state.get(ARROW_TIP_STATE_KEY)
    if isinstance(tip, dict):
        return _normalize_point_payload(tip)
    return None


def _set_arrow_tip_point(point: dict[str, Any]) -> dict[str, Any] | None:
    normalized = _normalize_point_payload(point)
    if normalized:
        st.session_state[ARROW_TIP_STATE_KEY] = normalized
    return normalized


def _get_last_click_point() -> dict[str, Any] | None:
    point = st.session_state.get(LAST_CLICK_POINT_STATE_KEY)
    if isinstance(point, dict):
        return _normalize_point_payload(point)
    return None


def _set_last_click_point(point: dict[str, Any]) -> dict[str, Any] | None:
    normalized = _normalize_point_payload(point)
    if normalized:
        st.session_state[LAST_CLICK_POINT_STATE_KEY] = normalized
    return normalized


def _reset_selection_state(clear_last_click: bool = False) -> None:
    _clear_selected_point()
    _clear_selected_vector()
    if clear_last_click:
        st.session_state.pop(LAST_CLICK_POINT_STATE_KEY, None)


def _format_point(point: dict[str, Any] | None) -> str:
    if not isinstance(point, dict):
        return "X — · Y — · Z —"
    return (
        f"X {float(point.get('x', 0.0)):.2f} · "
        f"Y {float(point.get('y', 0.0)):.2f} · "
        f"Z {float(point.get('z', 0.0)):.2f}"
    )


def _format_vector(vector: dict[str, float] | None) -> str:
    if not isinstance(vector, dict):
        return "ΔX — · ΔY — · ΔZ —"
    return (
        f"ΔX {float(vector.get('u', 0.0)):.2f} · "
        f"ΔY {float(vector.get('v', 0.0)):.2f} · "
        f"ΔZ {float(vector.get('w', 0.0)):.2f}"
    )


@st.cache_resource(show_spinner=False)
def _cached_mesh(path_str: str, mtime: float) -> MeshData:
    path = Path(path_str)
    if np_stl is None:
        raise ViewerError(
            "The `numpy-stl` package is required for visualization. "
            "Install it via `pip install numpy-stl`."
        )
    stl_mesh = np_stl.Mesh.from_file(str(path))
    triangles = stl_mesh.vectors  # (n, 3, 3)
    points = triangles.reshape(-1, 3)
    vertices, inverse = np.unique(points, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(int)
    bounds = tuple(zip(vertices.min(axis=0), vertices.max(axis=0)))  # type: ignore[arg-type]
    return MeshData(vertices=vertices, faces=faces, bounds=bounds)


def load_mesh_data(stl_path: Path) -> MeshData:
    if not stl_path.exists():
        raise ViewerError(f"STL file not found: {stl_path}")
    return _cached_mesh(str(stl_path), stl_path.stat().st_mtime)



def _append_snapshot_entry(job: ConversionResult, entry: dict[str, Any]) -> None:
    snapshots = st.session_state.get("stl_snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(entry)
    st.session_state["stl_snapshots"] = snapshots
    _persist_snapshots(job.job.job_id)


def _make_snapshot_entry(
    job: ConversionResult,
    *,
    filename: str,
    mime_type: str,
    notes: str,
    image_bytes: bytes,
    captured_from_viewer: bool,
) -> dict[str, Any]:
    return {
        "snapshot_id": uuid.uuid4().hex,
        "job_id": job.job.job_id,
        "source_stl": str(job.job.output_stl),
        "filename": filename,
        "mime_type": mime_type,
        "notes": notes,
        "timestamp": time.time(),
        "data_base64": base64.b64encode(image_bytes).decode("ascii"),
        "captured_from_viewer": captured_from_viewer,
        "annotations2d": {"objects": []},
    }


def _persist_snapshots(job_id: str) -> None:
    snapshots = st.session_state.get("stl_snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    job_snaps = [snap for snap in snapshots if snap.get("job_id") == job_id]
    save_snapshots(job_id, job_snaps)


def _ensure_snapshot_cache() -> None:
    if st.session_state.get("snapshot_cache_loaded"):
        return
    st.session_state["stl_snapshots"] = list_all_snapshots()
    st.session_state["snapshot_cache_loaded"] = True


def build_plot(
    mesh: MeshData,
    color: str = "#1f77b4",
    annotations: list[dict] | None = None,
    selected_point: dict | None = None,
) -> go.Figure:
    if go is None:
        raise ViewerError(
            "Plotly is required for STL visualization. Install it via `pip install plotly`."
        )

    mesh3d = go.Mesh3d(
        x=mesh.vertices[:, 0],
        y=mesh.vertices[:, 1],
        z=mesh.vertices[:, 2],
        i=mesh.faces[:, 0],
        j=mesh.faces[:, 1],
        k=mesh.faces[:, 2],
        color=color,
        opacity=0.75,
        lighting=dict(ambient=0.3, diffuse=0.6, specular=0.3),
        name="Mesh",
    )

    fig = go.Figure(data=[mesh3d])
    fig.update_layout(
        scene=dict(
            xaxis=dict(showgrid=True, title="X"),
            yaxis=dict(showgrid=True, title="Y"),
            zaxis=dict(showgrid=True, title="Z"),
            aspectmode="data",
        ),
        height=640,
        margin=dict(l=0, r=0, t=24, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )

    if annotations:
        marker_x, marker_y, marker_z = [], [], []
        marker_labels, marker_colors = [], []
        arrow_x, arrow_y, arrow_z, arrow_u, arrow_v, arrow_w = [], [], [], [], [], []
        arrow_line_segments: list[tuple[float, float, float, float, float, float, str]] = []
        label_annotations: list[dict] = []

        for ann in annotations:
            point = ann.get("point") or {}
            px = float(point.get("x", 0.0))
            py = float(point.get("y", 0.0))
            pz = float(point.get("z", 0.0))
            kind = (ann.get("kind") or "marker").lower()

            if kind == "label":
                label_annotations.append(ann)
                continue

            marker_x.append(px)
            marker_y.append(py)
            marker_z.append(pz)
            marker_labels.append(ann.get("label") or "")
            marker_colors.append(ann.get("color", "#FF4136"))

            if kind == "arrow":
                direction = ann.get("direction") or {}
                raw_u = float(direction.get("u", 0.0))
                raw_v = float(direction.get("v", 0.0))
                raw_w = float(direction.get("w", 0.0))

                tip_point = ann.get("tip_point")
                if isinstance(tip_point, dict):
                    tip_x = float(tip_point.get("x", px))
                    tip_y = float(tip_point.get("y", py))
                    tip_z = float(tip_point.get("z", pz))
                    u = tip_x - px
                    v = tip_y - py
                    w = tip_z - pz
                else:
                    tip_x = px + raw_u
                    tip_y = py + raw_v
                    tip_z = pz + raw_w
                    u, v, w = raw_u, raw_v, raw_w

                magnitude = math.sqrt(u**2 + v**2 + w**2)
                if magnitude > 1e-6:
                    arrow_x.append(px)
                    arrow_y.append(py)
                    arrow_z.append(pz)
                    arrow_u.append(u)
                    arrow_v.append(v)
                    arrow_w.append(w)
                    arrow_line_segments.append(
                        (px, py, pz, tip_x, tip_y, tip_z, ann.get("color", "#FF4136"))
                    )

        if marker_x:
            fig.add_trace(
                go.Scatter3d(
                    x=marker_x,
                    y=marker_y,
                    z=marker_z,
                    mode="markers+text",
                    marker=dict(size=10, color=marker_colors, symbol="diamond"),
                    text=marker_labels,
                    textposition="top center",
                    name="Markers",
                )
            )

        if arrow_x:
            fig.add_trace(
                go.Cone(
                    x=arrow_x,
                    y=arrow_y,
                    z=arrow_z,
                    u=arrow_u,
                    v=arrow_v,
                    w=arrow_w,
                    colorscale=[[0, "#FF4136"], [1, "#FF4136"]],
                    showscale=False,
                    sizemode="absolute",
                    sizeref=10,
                    anchor="tail",
                    name="Arrows",
                )
            )
            for sx, sy, sz, tx, ty, tz, line_color in arrow_line_segments:
                fig.add_trace(
                    go.Scatter3d(
                        x=[sx, tx],
                        y=[sy, ty],
                        z=[sz, tz],
                        mode="lines",
                        line=dict(color=line_color, width=4),
                        name="Arrow path",
                        showlegend=False,
                    )
                )

        for ann in label_annotations:
            point = ann.get("point") or {}
            px = float(point.get("x", 0.0))
            py = float(point.get("y", 0.0))
            pz = float(point.get("z", 0.0))
            text_value = ann.get("text") or ann.get("label") or ""
            color = ann.get("color", "#FFD166")
            size = float(ann.get("size", 18.0))
            fig.add_trace(
                go.Scatter3d(
                    x=[px],
                    y=[py],
                    z=[pz],
                    mode="text",
                    text=[text_value],
                    textfont=dict(color=color, size=size),
                    name=f"Label: {text_value}",
                    hoverinfo="text",
                    showlegend=False,
                )
            )

    if selected_point:
        fig.add_trace(
            go.Scatter3d(
                x=[selected_point.get("x", 0.0)],
                y=[selected_point.get("y", 0.0)],
                z=[selected_point.get("z", 0.0)],
                mode="markers",
                marker=dict(size=14, color="#FFD166", symbol="diamond-open"),
                name="Current selection",
            )
        )

    return fig


def render_viewer_panel(latest_job: ConversionResult | None, *, enable_tools: bool = True) -> None:
    st.subheader("Interactive STL viewer")
    if not latest_job:
        st.write("Run a conversion to preview the generated mesh.")
        return

    if not latest_job.job.output_stl.exists():
        st.warning("Latest conversion does not have an STL file yet.")
        return

    flash_message = None
    try:
        mesh = load_mesh_data(latest_job.job.output_stl)
        annotations = load_annotations(latest_job.job.job_id)
        selected_point = _get_selected_point()
        fig = build_plot(
            mesh,
            annotations=annotations,
            selected_point=selected_point,
        )
        flash_message = _pop_flash_message()

        st.caption(
            "Use the interactive viewer below to orbit the mesh and capture exactly what you see."
        )

        (x_bounds, y_bounds, z_bounds) = mesh.bounds
        st.caption(
            f"Bounds X[{x_bounds[0]:.1f}, {x_bounds[1]:.1f}] · "
            f"Y[{y_bounds[0]:.1f}, {y_bounds[1]:.1f}] · "
            f"Z[{z_bounds[0]:.1f}, {z_bounds[1]:.1f}]"
        )
        if flash_message:
            st.success(flash_message)
    except ViewerError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # pragma: no cover - defensive
        st.error(f"Unexpected error while loading mesh: {exc}")
        return

    _render_capture_canvas(latest_job, fig)
    if enable_tools:
        _render_annotation_editor(latest_job, annotations)
    _render_snapshot_gallery(latest_job)


def _render_capture_canvas(job: ConversionResult, fig: go.Figure) -> None:
    st.markdown("#### Snapshot capture & 3D point selection")
    st.caption(
        "Rotate or zoom the live viewer below to the desired angle, then capture a still that exactly matches what you see. "
        "Click directly on the mesh to log a 3D point for marker creation. Snapshots stay local to this Streamlit session."
    )
    current_point = _get_selected_point()
    current_vector = _get_selected_vector()
    arrow_tip = _get_arrow_tip_point()

    if current_point and current_vector and arrow_tip:
        st.caption(
            f"Anchor: {_format_point(current_point)} · Tip: {_format_point(arrow_tip)} · { _format_vector(current_vector)}"
        )
    elif current_point:
        st.caption(
            f"Anchor set: {_format_point(current_point)} · Click a second point to define arrow direction."
        )
    else:
        st.caption("Tip: click any vertex/triangle to queue its coordinates for a new marker or label.")

    capture_payload = render_model_capture(
        figure=fig.to_plotly_json(),
        width=1024,
        height=768,
        key=f"capture-{job.job.job_id}",
    )
    if not capture_payload:
        return

    event_type = capture_payload.get("type")
    if event_type == "click":
        clicked_point = _normalize_point_payload(capture_payload.get("point"))
        if not clicked_point:
            st.warning("Point selection failed. Try clicking a different triangle.")
            return

        _set_last_click_point(clicked_point)
        anchor_point = _get_selected_point()
        existing_vector = _get_selected_vector()

        if anchor_point is None or existing_vector is not None:
            _set_selected_point(clicked_point)
            _clear_selected_vector()
            st.info(
                f"Anchor set at {_format_point(clicked_point)}. Click again to define arrow direction or open the forms below."
            )
        else:
            delta = {
                "u": clicked_point["x"] - anchor_point["x"],
                "v": clicked_point["y"] - anchor_point["y"],
                "w": clicked_point["z"] - anchor_point["z"],
            }
            _set_selected_vector(delta)
            _set_arrow_tip_point(clicked_point)
            st.success(
                f"Arrow tip selected at {_format_point(clicked_point)} · { _format_vector(delta)}"
            )
        return

    if capture_payload.get("image_data") or event_type == "capture":
        try:
            encoded = capture_payload.get("image_data") or ""
            if not encoded:
                return
            png_bytes = base64.b64decode(encoded.split(",", 1)[-1])
            filename = f"{job.job.job_id}-{int(time.time())}.png"
            entry = _make_snapshot_entry(
                job,
                filename=filename,
                mime_type="image/png",
                notes=capture_payload.get("notes") or "Captured from 3D viewer",
                image_bytes=png_bytes,
                captured_from_viewer=True,
            )
            _append_snapshot_entry(job, entry)
            st.success("Snapshot captured for annotation.")
        except Exception as exc:  # pragma: no cover - defensive
            st.error(f"Snapshot capture failed: {exc}")


def _render_annotation_editor(job: ConversionResult, annotations: list[dict]) -> None:
    st.markdown("#### 3D tools")
    st.caption(
        "Click the mesh to capture anchor points, then use the tabs below to place markers, arrows, or floating labels."
    )

    selected_point = _get_selected_point()
    selected_vector = _get_selected_vector()
    arrow_tip = _get_arrow_tip_point()
    last_label_point = _get_last_click_point()

    marker_tab, arrow_tab, label_tab = st.tabs(["Markers", "Arrows", "Labels"])

    # --- Markers tab ---
    with marker_tab:
        marker_prefix = f"marker-{job.job.job_id}"
        marker_label_key = f"{marker_prefix}-label"
        marker_color_key = f"{marker_prefix}-color"
        marker_notes_key = f"{marker_prefix}-notes"
        marker_reset_key = f"{marker_prefix}-reset"

        if st.session_state.pop(marker_reset_key, False):
            for state_key in (marker_label_key, marker_color_key, marker_notes_key):
                st.session_state.pop(state_key, None)

        st.session_state.setdefault(marker_label_key, "")
        st.session_state.setdefault(marker_color_key, DEFAULT_MARKER_COLOR)
        st.session_state.setdefault(marker_notes_key, "")

        if selected_point:
            st.success(f"Marker anchor: {_format_point(selected_point)}")
        else:
            st.info("Click the mesh to set a marker anchor point.")

        if selected_point and st.button("Clear marker anchor", key=f"{marker_prefix}-clear"):
            _reset_selection_state()
            st.rerun()

        with st.form(f"{marker_prefix}-form"):
            marker_label = st.text_input(
                "Marker label", key=marker_label_key, placeholder="e.g., Mandible ROI"
            )
            marker_color = st.color_picker("Marker color", key=marker_color_key)
            marker_notes = st.text_area("Notes (optional)", key=marker_notes_key, height=80)

            marker_submit = st.form_submit_button(
                "Save marker",
                disabled=selected_point is None,
            )

            if marker_submit:
                if not selected_point:
                    st.warning("Select a point on the mesh before saving a marker.")
                elif not (marker_label or "").strip():
                    st.warning("Marker label is required.")
                else:
                    annotation = {
                        "annotation_id": uuid.uuid4().hex,
                        "job_id": job.job.job_id,
                        "label": (marker_label or "").strip(),
                        "point": {
                            "x": float(selected_point["x"]),
                            "y": float(selected_point["y"]),
                            "z": float(selected_point["z"]),
                        },
                        "color": marker_color or DEFAULT_MARKER_COLOR,
                        "notes": (marker_notes or "").strip(),
                        "direction": {"u": 0.0, "v": 0.0, "w": 0.0},
                        "timestamp": time.time(),
                        "kind": "marker",
                    }
                    annotations.append(annotation)
                    save_annotations(job.job.job_id, annotations)
                    st.session_state[marker_reset_key] = True
                    _set_flash_message("Marker saved.")
                    st.rerun()

    # --- Arrows tab ---
    with arrow_tab:
        arrow_prefix = f"arrow-{job.job.job_id}"
        arrow_label_key = f"{arrow_prefix}-label"
        arrow_color_key = f"{arrow_prefix}-color"
        arrow_notes_key = f"{arrow_prefix}-notes"
        arrow_dir_u_key = f"{arrow_prefix}-dir-u"
        arrow_dir_v_key = f"{arrow_prefix}-dir-v"
        arrow_dir_w_key = f"{arrow_prefix}-dir-w"
        arrow_reset_key = f"{arrow_prefix}-reset"
        arrow_vector_sync_key = f"{arrow_prefix}-vector-sync"

        if st.session_state.pop(arrow_reset_key, False):
            for key in (
                arrow_label_key,
                arrow_color_key,
                arrow_notes_key,
                arrow_dir_u_key,
                arrow_dir_v_key,
                arrow_dir_w_key,
                arrow_vector_sync_key,
            ):
                st.session_state.pop(key, None)

        st.session_state.setdefault(arrow_label_key, "")
        st.session_state.setdefault(arrow_color_key, "#FF4136")
        st.session_state.setdefault(arrow_notes_key, "")
        st.session_state.setdefault(arrow_dir_u_key, 0.0)
        st.session_state.setdefault(arrow_dir_v_key, 0.0)
        st.session_state.setdefault(arrow_dir_w_key, 0.0)
        st.session_state.setdefault(arrow_vector_sync_key, None)

        if selected_point and selected_vector and arrow_tip:
            st.success(
                f"Anchor: {_format_point(selected_point)} · Tip: {_format_point(arrow_tip)} · {_format_vector(selected_vector)}"
            )
        elif selected_point:
            st.info(
                f"Anchor: {_format_point(selected_point)} · Click a second point to capture the arrow direction."
            )
        else:
            st.info("Click once on the mesh to set the arrow anchor, then click again for the tip.")

        if st.button("Reset arrow selection", key=f"{arrow_prefix}-clear-selection"):
            _reset_selection_state()
            st.rerun()

        vector_tuple = None
        if selected_vector:
            vector_tuple = (
                float(selected_vector.get("u", 0.0)),
                float(selected_vector.get("v", 0.0)),
                float(selected_vector.get("w", 0.0)),
            )
        if vector_tuple and st.session_state.get(arrow_vector_sync_key) != vector_tuple:
            st.session_state[arrow_vector_sync_key] = vector_tuple
            st.session_state[arrow_dir_u_key] = vector_tuple[0]
            st.session_state[arrow_dir_v_key] = vector_tuple[1]
            st.session_state[arrow_dir_w_key] = vector_tuple[2]

        with st.form(f"{arrow_prefix}-form"):
            arrow_label = st.text_input(
                "Arrow label", key=arrow_label_key, placeholder="e.g., Nerve path"
            )
            arrow_color = st.color_picker("Arrow color", key=arrow_color_key)
            arrow_notes = st.text_area("Notes (optional)", key=arrow_notes_key, height=80)
            dir_cols = st.columns(3)
            dir_u = dir_cols[0].number_input("Vector U (ΔX)", key=arrow_dir_u_key, format="%.3f")
            dir_v = dir_cols[1].number_input("Vector V (ΔY)", key=arrow_dir_v_key, format="%.3f")
            dir_w = dir_cols[2].number_input("Vector W (ΔZ)", key=arrow_dir_w_key, format="%.3f")

            vector_magnitude = math.sqrt(float(dir_u) ** 2 + float(dir_v) ** 2 + float(dir_w) ** 2)
            arrow_ready = selected_point is not None and vector_magnitude > 1e-6

            arrow_submit = st.form_submit_button(
                "Save arrow",
                disabled=not arrow_ready,
            )

            if arrow_submit:
                if not selected_point:
                    st.warning("Click the mesh to set the arrow anchor.")
                elif vector_magnitude <= 1e-6:
                    st.warning("Arrow vector must be non-zero. Click a tip or edit the Δ values.")
                elif not (arrow_label or "").strip():
                    st.warning("Arrow label is required.")
                else:
                    direction = {
                        "u": float(dir_u),
                        "v": float(dir_v),
                        "w": float(dir_w),
                    }
                    tip_payload = {
                        "x": float(selected_point["x"] + direction["u"]),
                        "y": float(selected_point["y"] + direction["v"]),
                        "z": float(selected_point["z"] + direction["w"]),
                    }
                    annotation = {
                        "annotation_id": uuid.uuid4().hex,
                        "job_id": job.job.job_id,
                        "label": (arrow_label or "").strip(),
                        "point": {
                            "x": float(selected_point["x"]),
                            "y": float(selected_point["y"]),
                            "z": float(selected_point["z"]),
                        },
                        "tip_point": tip_payload,
                        "color": arrow_color or "#FF4136",
                        "notes": (arrow_notes or "").strip(),
                        "direction": direction,
                        "timestamp": time.time(),
                        "kind": "arrow",
                    }
                    annotations.append(annotation)
                    save_annotations(job.job.job_id, annotations)
                    _reset_selection_state()
                    st.session_state[arrow_reset_key] = True
                    _set_flash_message("Arrow saved.")
                    st.rerun()

    # --- Labels tab ---
    with label_tab:
        label_prefix = f"label-{job.job.job_id}"
        label_text_key = f"{label_prefix}-text"
        label_color_key = f"{label_prefix}-color"
        label_size_key = f"{label_prefix}-size"
        label_reset_key = f"{label_prefix}-reset"

        if st.session_state.pop(label_reset_key, False):
            for label_state in (label_text_key, label_color_key, label_size_key):
                st.session_state.pop(label_state, None)

        st.session_state.setdefault(label_text_key, "")
        st.session_state.setdefault(label_color_key, "#FFD166")
        st.session_state.setdefault(label_size_key, 18)

        if last_label_point:
            st.success(f"Label anchor: {_format_point(last_label_point)}")
        else:
            st.info("Click anywhere on the mesh to place the next label.")

        label_cols = st.columns((3, 1))
        with label_cols[0]:
            with st.form(f"{label_prefix}-form"):
                label_text = st.text_input(
                    "Label text", key=label_text_key, placeholder="e.g., Tumor margin"
                )
                label_color = st.color_picker("Label color", key=label_color_key)
                label_size = st.slider(
                    "Text size",
                    min_value=8,
                    max_value=64,
                    value=int(st.session_state[label_size_key]),
                    key=label_size_key,
                )
                label_ready = last_label_point is not None
                label_submit = st.form_submit_button(
                    "Save label",
                    disabled=not label_ready,
                )

                if label_submit:
                    if not last_label_point:
                        st.warning("Click the viewer to choose a label position.")
                    elif not (label_text or "").strip():
                        st.warning("Label text is required.")
                    else:
                        annotation = {
                            "annotation_id": uuid.uuid4().hex,
                            "job_id": job.job.job_id,
                            "label": (label_text or "").strip(),
                            "text": (label_text or "").strip(),
                            "point": {
                                "x": float(last_label_point["x"]),
                                "y": float(last_label_point["y"]),
                                "z": float(last_label_point["z"]),
                            },
                            "color": label_color,
                            "size": float(st.session_state[label_size_key]),
                            "timestamp": time.time(),
                            "kind": "label",
                        }
                        annotations.append(annotation)
                        save_annotations(job.job.job_id, annotations)
                        st.session_state[label_reset_key] = True
                        _set_flash_message("Label saved.")
                        st.rerun()

        with label_cols[1]:
            if last_label_point:
                if st.button("Clear label anchor", key=f"{label_prefix}-clear"):
                    st.session_state.pop(LAST_CLICK_POINT_STATE_KEY, None)
                    st.rerun()
            else:
                st.caption(" ")

    if annotations:
        st.markdown("##### Saved annotations")
        for idx, ann in enumerate(annotations):
            point = ann.get("point") or {}
            label = ann.get("label") or f"Annotation {idx + 1}"
            color = ann.get("color") or DEFAULT_MARKER_COLOR
            notes = ann.get("notes") or ""
            ann_id = ann.get("annotation_id") or f"{job.job.job_id}-{idx}"
            kind = (ann.get("kind") or "marker").capitalize()
            info_col, action_col = st.columns([5, 1])
            info_col.write(f"**[{kind}] {label}** · {_format_point(point)}")
            info_col.caption(f"Color: `{color}`")
            if notes:
                info_col.caption(notes)
            if ann.get("kind") == "arrow":
                info_col.caption(f"Vector: {_format_vector(ann.get('direction'))}")
            if ann.get("kind") == "label":
                info_col.caption(f"Size: {float(ann.get('size', 18.0)):.1f}")
            if action_col.button("Delete", key=f"delete-ann-{ann_id}"):
                annotations.pop(idx)
                save_annotations(job.job.job_id, annotations)
                _set_flash_message(f'Deleted annotation "{label}".')
                st.rerun()
    else:
        st.caption("No 3D annotations saved yet.")


def _render_snapshot_gallery(job: ConversionResult) -> None:
    _ensure_snapshot_cache()

    st.markdown("#### Saved snapshots & annotation")
    snapshots = st.session_state.get("stl_snapshots", [])
    job_snapshots = [
        (idx, snap)
        for idx, snap in enumerate(snapshots)
        if snap.get("job_id") == job.job.job_id
    ]

    if job_snapshots:
        st.caption("Review prior captures, add 2D arrows or labels, and share them with the GPT assistant.")
        start_index = max(0, len(job_snapshots) - 5)
        for offset in reversed(range(start_index, len(job_snapshots))):
            snap_idx, snap = job_snapshots[offset]
            st.write(
                f"{snap['filename']} · id: {snap.get('snapshot_id','')[:8]} · "
                f"notes: {snap.get('notes') or '—'}"
            )
            try:
                encoded = snap.get("annotated_base64") or snap.get("data_base64")
                if not encoded:
                    raise ValueError("Snapshot missing image data.")
                image_bytes = base64.b64decode(encoded)
                st.image(image_bytes, width=320)
            except Exception:  # pragma: no cover - defensive
                st.caption("Preview unavailable.")
            with st.expander("Annotate / review", expanded=False):
                    annotations2d = snap.get("annotations2d") or {"objects": []}
                    if not isinstance(annotations2d, dict):
                        annotations2d = {"objects": annotations2d}
                    snap["annotations2d"] = annotations2d
                    updated = render_snapshot_annotator(
                        {**snap, "annotations2d": annotations2d},
                        key_prefix=f"annot-{snap.get('snapshot_id','')}",
                    )
                    if updated is not None:
                        snap["annotations2d"] = updated.get("annotations", {"objects": []})
                        annotated_base64 = updated.get("annotated_base64")
                        if annotated_base64:
                            snap["annotated_base64"] = annotated_base64
                            snap["data_base64"] = annotated_base64
                        snapshots[snap_idx] = snap
                        st.session_state["stl_snapshots"] = snapshots[:]
                        _persist_snapshots(snap.get("job_id", job.job.job_id))
                        if updated.get("reason") == "clear":
                            st.info("Snapshot annotations cleared.")
                        else:
                            st.success("Snapshot annotations saved.")
    else:
        st.caption("No snapshots captured yet.")
