"""STL viewer and snapshot annotation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64
import math
import time
import uuid

import numpy as np
import streamlit as st

try:  # pragma: no cover - optional dependency
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - optional dependency
    go = None

from backend import ConversionResult

try:
    from stl import mesh as np_stl
except ImportError:  # pragma: no cover - optional dependency
    np_stl = None


ANNOTATION_STATE_KEY = "stl_annotations"
ANNOTATION_SELECTION_KEY = "stl_annotation_candidate"


class ViewerError(RuntimeError):
    """Raised when the STL viewer cannot render a mesh."""


@dataclass
class MeshData:
    vertices: np.ndarray
    faces: np.ndarray
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def load_mesh_data(stl_path: Path) -> MeshData:
    if np_stl is None:
        raise ViewerError(
            "The `numpy-stl` package is required for visualization. "
            "Install it in your Streamlit environment: `pip install numpy-stl`."
        )

    if not stl_path.exists():
        raise ViewerError(f"STL file not found: {stl_path}")

    stl_mesh = np_stl.Mesh.from_file(str(stl_path))
    triangles = stl_mesh.vectors  # (n, 3, 3)
    points = triangles.reshape(-1, 3)

    vertices, inverse = np.unique(points, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(int)

    bounds = tuple(zip(vertices.min(axis=0), vertices.max(axis=0)))  # type: ignore[arg-type]

    return MeshData(vertices=vertices, faces=faces, bounds=bounds)


def build_plot(mesh: MeshData, color: str = "#1f77b4", annotations: list[dict] | None = None) -> go.Figure:
    if go is None:
        raise ViewerError(
            "Plotly is required for STL visualization. Install it via `pip install plotly`."
        )

    # Create a simple mesh plot
    mesh3d = go.Mesh3d(
        x=mesh.vertices[:, 0],
        y=mesh.vertices[:, 1],
        z=mesh.vertices[:, 2],
        i=mesh.faces[:, 0],
        j=mesh.faces[:, 1],
        k=mesh.faces[:, 2],
        color=color,
        opacity=0.9,
        name="3D Mesh"
    )
    
    fig = go.Figure(data=[mesh3d])

    # Simple layout
    fig.update_layout(
        scene=dict(
            xaxis=dict(showgrid=True, title="X"),
            yaxis=dict(showgrid=True, title="Y"),
            zaxis=dict(showgrid=True, title="Z"),
            aspectmode="data"
        ),
        height=700,
        width=None,
        title=dict(text="3D STL Model", x=0.5, xanchor='center'),
        showlegend=False
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
                name="Annotations",
            )
        )

        arrow_x, arrow_y, arrow_z, arrow_u, arrow_v, arrow_w, arrow_color = [], [], [], [], [], [], []
        for ann in annotations:
            direction = ann.get("direction", {"u": 0.0, "v": 0.0, "w": 0.0})
            magnitude = math.sqrt(direction.get("u", 0.0) ** 2 + direction.get("v", 0.0) ** 2 + direction.get("w", 0.0) ** 2)
            if magnitude <= 1e-6:
                continue
            arrow_x.append(ann["point"]["x"])
            arrow_y.append(ann["point"]["y"])
            arrow_z.append(ann["point"]["z"])
            arrow_u.append(direction.get("u", 0.0))
            arrow_v.append(direction.get("v", 0.0))
            arrow_w.append(direction.get("w", 0.0))
            arrow_color.append(ann.get("color", "#FF4136"))

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
                    name="Annotation arrows",
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

    # Debug info
    with st.expander("Debug Information", expanded=False):
        st.info(f"STL file: {latest_job.job.output_stl}")
        file_size = latest_job.job.output_stl.stat().st_size / (1024 * 1024)  # Convert to MB
        st.info(f"File size: {file_size:.2f} MB")

    try:
        with st.spinner("Loading 3D mesh..."):
            mesh = load_mesh_data(latest_job.job.output_stl)
            st.success(f"Mesh loaded: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
        
        annotations = _get_annotations(latest_job.job.job_id)
        fig = build_plot(mesh, annotations=annotations)
        
        # Render using the standard Plotly chart (most stable across Streamlit releases)
        st.plotly_chart(fig, use_container_width=True, key=f"plotly-{latest_job.job.job_id}")
        
        (x_bounds, y_bounds, z_bounds) = mesh.bounds
        st.caption(
            f"Bounds X[{x_bounds[0]:.1f}, {x_bounds[1]:.1f}] · "
            f"Y[{y_bounds[0]:.1f}, {y_bounds[1]:.1f}] · "
            f"Z[{z_bounds[0]:.1f}, {z_bounds[1]:.1f}]"
        )
    except ViewerError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Unexpected error while loading mesh: {str(exc)}")
        import traceback
        st.code(traceback.format_exc())
        return

    _render_annotation_tools(latest_job)
    _render_snapshot_section(latest_job)


def _render_snapshot_section(job: ConversionResult) -> None:
    st.markdown("#### Snapshot & annotation")
    st.caption(
        "Capture a photo of the physical print, upload annotated renders, or jot down notes. "
        "Snapshots are stored locally and will be exposed to the ChatGPT tools."
    )

    with st.form("snapshot-form"):
        uploaded_file = st.file_uploader(
            "Upload an annotated image",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=False,
            key="snapshot-upload",
            help="Attach renders or photos you've already captured (camera optional).",
        )
        notes = st.text_area(
            "Annotation / context",
            placeholder="Describe what this snapshot highlights...",
            key="snapshot-notes",
        )
        submitted = st.form_submit_button("Save snapshot", type="secondary")

    if submitted:
        file_obj = uploaded_file
        if not file_obj:
            st.warning("Upload an image to save a snapshot.")
            return

        entry = {
            "snapshot_id": uuid.uuid4().hex,
            "job_id": job.job.job_id,
            "source_stl": str(job.job.output_stl),
            "filename": file_obj.name,
            "mime_type": file_obj.type,
            "notes": notes,
            "timestamp": time.time(),
            "data_base64": base64.b64encode(file_obj.getvalue()).decode("ascii"),
        }
        snapshots = st.session_state.get("stl_snapshots", [])
        if not isinstance(snapshots, list):
            snapshots = []
        snapshots.append(entry)
        st.session_state["stl_snapshots"] = snapshots
        st.success("Snapshot saved for the chatbot.")

    snapshots = st.session_state.get("stl_snapshots", [])
    if snapshots:
        st.markdown("##### Saved snapshots")
        for idx, snap in enumerate(reversed(snapshots[-5:]), start=1):
            st.write(
                f"{idx}. {snap['filename']} · id: {snap.get('snapshot_id','')[:8]} · "
                f"notes: {snap.get('notes') or '—'}"
            )
            try:
                image_bytes = base64.b64decode(snap["data_base64"])
                st.image(image_bytes, width=240)
            except Exception:  # pragma: no cover - defensive
                st.caption("Preview unavailable.")


def _render_annotation_tools(job: ConversionResult) -> None:
    st.markdown("#### Annotations")
    st.caption(
        "Click any region of the mesh to capture coordinates, then add a label and optional arrow direction."
    )

    selection = _get_selection(job.job.job_id)
    if selection:
        st.success(
            f"Selected point at ({selection['x']:.1f}, {selection['y']:.1f}, {selection['z']:.1f})"
        )
    else:
        st.info("Click on the mesh to choose a point for your next marker (coming soon).")

    with st.form(f"annotation-form-{job.job.job_id}"):
        label = st.text_input("Label", key=f"annotation-label-{job.job.job_id}")
        color = st.color_picker("Marker color", "#FF4136", key=f"annotation-color-{job.job.job_id}")
        col_dx, col_dy, col_dz = st.columns(3)
        dx = col_dx.number_input("Arrow X", value=0.0, step=0.5, key=f"annotation-dx-{job.job.job_id}")
        dy = col_dy.number_input("Arrow Y", value=0.0, step=0.5, key=f"annotation-dy-{job.job.job_id}")
        dz = col_dz.number_input("Arrow Z", value=10.0, step=0.5, key=f"annotation-dz-{job.job.job_id}")
        submitted = st.form_submit_button("Add annotation", type="secondary")

    if submitted:
        if not selection:
            st.warning("Select a point on the mesh before saving an annotation.")
        elif not label.strip():
            st.warning("Provide a label for this annotation.")
        else:
            _add_annotation(
                job.job.job_id,
                label=label.strip(),
                color=color,
                point=selection,
                direction={"u": dx, "v": dy, "w": dz},
            )
            st.success("Annotation saved to this study.")

    annotations = _get_annotations(job.job.job_id)
    if annotations:
        st.markdown("##### Existing annotations")
        for annotation in reversed(annotations):
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(
                    f"{annotation['label']} @ "
                    f"({annotation['point']['x']:.1f}, {annotation['point']['y']:.1f}, {annotation['point']['z']:.1f})"
                )
            with cols[1]:
                if st.button(
                    "Delete",
                    key=f"delete-annotation-{annotation['annotation_id']}",
                    use_container_width=True,
                ):
                    _delete_annotation(job.job.job_id, annotation["annotation_id"])
                    st.experimental_rerun()


def _get_annotations(job_id: str) -> list[dict]:
    store = st.session_state.get(ANNOTATION_STATE_KEY, {})
    if not isinstance(store, dict):
        store = {}
    return list(store.get(job_id, []))


def _add_annotation(job_id: str, *, label: str, color: str, point: dict, direction: dict) -> None:
    store = st.session_state.get(ANNOTATION_STATE_KEY, {})
    if not isinstance(store, dict):
        store = {}
    annotations = list(store.get(job_id, []))
    annotations.append(
        {
            "annotation_id": uuid.uuid4().hex,
            "job_id": job_id,
            "label": label,
            "color": color,
            "point": point,
            "direction": direction,
            "timestamp": time.time(),
        }
    )
    store[job_id] = annotations
    st.session_state[ANNOTATION_STATE_KEY] = store


def _delete_annotation(job_id: str, annotation_id: str) -> None:
    store = st.session_state.get(ANNOTATION_STATE_KEY, {})
    if not isinstance(store, dict):
        store = {}
    annotations = [
        ann for ann in store.get(job_id, []) if ann.get("annotation_id") != annotation_id
    ]
    store[job_id] = annotations
    st.session_state[ANNOTATION_STATE_KEY] = store


def _store_selection(job_id: str, event: dict) -> None:
    selection_store = st.session_state.get(ANNOTATION_SELECTION_KEY, {})
    if not isinstance(selection_store, dict):
        selection_store = {}
    selection_store[job_id] = {
        "x": event.get("x", 0.0),
        "y": event.get("y", 0.0),
        "z": event.get("z", 0.0),
    }
    st.session_state[ANNOTATION_SELECTION_KEY] = selection_store


def _get_selection(job_id: str) -> dict | None:
    selection_store = st.session_state.get(ANNOTATION_SELECTION_KEY, {})
    if not isinstance(selection_store, dict):
        return None
    return selection_store.get(job_id)

