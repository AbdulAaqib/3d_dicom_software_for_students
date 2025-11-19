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
import plotly.io as pio

try:  # pragma: no cover - optional dependency
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - optional dependency
    go = None

try:  # pragma: no cover - optional dependency
    from streamlit_plotly_events import plotly_events
except ImportError:  # pragma: no cover - optional dependency
    plotly_events = None  # type: ignore

from backend import ConversionResult
from backend.annotation_store import (
    load_annotations,
    save_annotations,
    save_snapshots,
    list_all_snapshots,
)
from .annotator import render_snapshot_annotator

try:
    from stl import mesh as np_stl
except ImportError:  # pragma: no cover - optional dependency
    np_stl = None




class ViewerError(RuntimeError):
    """Raised when the STL viewer cannot render a mesh."""


@dataclass
class MeshData:
    vertices: np.ndarray
    faces: np.ndarray
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


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


def _figure_to_png(fig: "go.Figure", width: int = 1024, height: int = 768) -> bytes | None:
    try:
        return pio.to_image(fig, format="png", width=width, height=height, engine="kaleido")  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - runtime guard
        st.warning(f"Snapshot failed: {exc}")
        return None


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
        xs = [ann["point"]["x"] for ann in annotations]
        ys = [ann["point"]["y"] for ann in annotations]
        zs = [ann["point"]["z"] for ann in annotations]
        labels = [ann["label"] for ann in annotations]
        colors = [ann.get("color", "#FF4136") for ann in annotations]

        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers+text",
                marker=dict(size=6, color=colors, symbol="diamond"),
                text=labels,
                textposition="top center",
                name="Markers",
            )
        )

        arrow_x, arrow_y, arrow_z, arrow_u, arrow_v, arrow_w = [], [], [], [], [], []
        for ann in annotations:
            direction = ann.get("direction", {"u": 0.0, "v": 0.0, "w": 0.0})
            magnitude = math.sqrt(
                direction.get("u", 0.0) ** 2
                + direction.get("v", 0.0) ** 2
                + direction.get("w", 0.0) ** 2
            )
            if magnitude <= 1e-6:
                continue
            arrow_x.append(ann["point"]["x"])
            arrow_y.append(ann["point"]["y"])
            arrow_z.append(ann["point"]["z"])
            arrow_u.append(direction.get("u", 0.0))
            arrow_v.append(direction.get("v", 0.0))
            arrow_w.append(direction.get("w", 0.0))

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

    if selected_point:
        fig.add_trace(
            go.Scatter3d(
                x=[selected_point.get("x", 0.0)],
                y=[selected_point.get("y", 0.0)],
                z=[selected_point.get("z", 0.0)],
                mode="markers",
                marker=dict(size=10, color="#FFD166", symbol="diamond-open"),
                name="Current selection",
            )
        )

    return fig


def render_viewer_panel(latest_job: ConversionResult | None) -> None:
    st.subheader("Interactive STL viewer")
    if not latest_job:
        st.write("Run a conversion to preview the generated mesh.")
        return

    if not latest_job.job.output_stl.exists():
        st.warning("Latest conversion does not have an STL file yet.")
        return

    try:
        mesh = load_mesh_data(latest_job.job.output_stl)
        annotations = load_annotations(latest_job.job.job_id)
        fig = build_plot(mesh, annotations=annotations, selected_point=None)

        st.plotly_chart(
            fig,
            key=f"plotly-{latest_job.job.job_id}",
            width="stretch",
        )

        st.caption("Capture snapshots below to add 2D markers, arrows, or labels.")

        (x_bounds, y_bounds, z_bounds) = mesh.bounds
        st.caption(
            f"Bounds X[{x_bounds[0]:.1f}, {x_bounds[1]:.1f}] · "
            f"Y[{y_bounds[0]:.1f}, {y_bounds[1]:.1f}] · "
            f"Z[{z_bounds[0]:.1f}, {z_bounds[1]:.1f}]"
        )
    except ViewerError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # pragma: no cover - defensive
        st.error(f"Unexpected error while loading mesh: {exc}")
        return

    _render_snapshot_section(latest_job, fig)


def _render_snapshot_section(job: ConversionResult, fig: go.Figure) -> None:
    _ensure_snapshot_cache()
    st.markdown("#### Snapshot & annotation")
    st.caption(
        "Capture stills of the 3D mesh, annotate them directly below, and share them with the GPT assistant. "
        "Snapshots stay local to this Streamlit session."
    )

    capture_cols = st.columns([1, 3])
    with capture_cols[0]:
        capture = st.button("Capture current 3D view", key=f"capture-{job.job.job_id}")
    if capture:
        png_bytes = _figure_to_png(fig)
        if png_bytes:
            filename = f"{job.job.job_id}-{int(time.time())}.png"
            entry = _make_snapshot_entry(
                job,
                filename=filename,
                mime_type="image/png",
                notes="Captured from 3D viewer",
                image_bytes=png_bytes,
                captured_from_viewer=True,
            )
            _append_snapshot_entry(job, entry)
            st.success("Snapshot captured for annotation.")

    snapshots = st.session_state.get("stl_snapshots", [])
    job_snapshots = [
        (idx, snap)
        for idx, snap in enumerate(snapshots)
        if snap.get("job_id") == job.job.job_id
    ]

    if job_snapshots:
        st.markdown("##### Saved snapshots")
        start_index = max(0, len(job_snapshots) - 5)
        for offset in reversed(range(start_index, len(job_snapshots))):
            snap_idx, snap = job_snapshots[offset]
            st.write(
                f"{snap['filename']} · id: {snap.get('snapshot_id','')[:8]} · "
                f"notes: {snap.get('notes') or '—'}"
            )
            preview_col, annot_col = st.columns([1, 2])
            with preview_col:
                try:
                    image_bytes = base64.b64decode(snap["data_base64"])
                    st.image(image_bytes, width=200)
                except Exception:  # pragma: no cover - defensive
                    st.caption("Preview unavailable.")
            with annot_col:
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
                        snap["annotations2d"] = updated
                        snapshots[snap_idx] = snap
                        st.session_state["stl_snapshots"] = snapshots
                        _persist_snapshots(snap.get("job_id", job.job.job_id))
                        st.success("Snapshot annotations saved.")
    else:
        st.caption("No snapshots captured yet.")
