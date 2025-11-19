"""Main DICOM → STL workspace view."""

from __future__ import annotations

import json
import streamlit as st

from backend import (
    ConversionOptions,
    ConversionResult,
    PipelineError,
    ingest_uploaded_files,
    list_sample_series,
    push_job_to_session,
    run_conversion_job,
    stage_sample_series,
)
from .intro import render_intro_page


def render_workspace_page() -> None:
    """Render the primary workflow surface (upload + conversion)."""

    st.title("3D DICOM Workspace")
    st.caption("Upload CT slices, convert with dicom2stl, and prep assets for ChatGPT.")

    render_intro_page()
    st.divider()

    col_upload, col_samples = st.columns(2)
    upload_result = _render_upload_card(col_upload)
    sample_result = _render_sample_card(col_samples)

    result = upload_result or sample_result

    if result:
        _render_conversion_banner(result)

    st.divider()
    _render_conversion_status()


def _render_upload_card(container: "st.delta_generator.DeltaGenerator") -> ConversionResult | None:
    with container:
        st.subheader("Upload a DICOM series")
        st.info(
            "Drag-and-drop a `.zip` containing an entire study, or multiple `.dcm` files. "
            "Files stay local to this Streamlit session."
        )
        files = st.file_uploader(
            "Upload DICOM slices or zip archives",
            type=["zip", "dcm"],
            accept_multiple_files=True,
            key="dicom-upload",
        )
        options = _render_option_controls(prefix="upload")
        if files:
            st.caption(f"{len(files)} file(s) attached · ready to convert.")
        submitted = st.button(
            "Convert uploaded study",
            type="primary",
            disabled=not files,
            width="stretch",
            key="convert-uploaded-study",
        )

        if submitted:
            if not files:
                st.warning("Please add at least one DICOM slice or zip archive.")
                return None
            try:
                progress_bar = st.progress(0.0, text="Uploading DICOM files…")
                progress_status = st.empty()

                def _update_progress(processed: int, total: int) -> None:
                    fraction = processed / max(total, 1)
                    progress_bar.progress(fraction, text=f"Staging {processed}/{total} uploads…")
                    progress_status.caption(f"Copied {processed} of {total} uploads")

                with st.spinner("Staging upload and running dicom2stl..."):
                    job = ingest_uploaded_files(files, progress_callback=_update_progress)
                    progress_bar.progress(1.0, text="Upload complete.")
                    progress_status.caption("Upload complete")
                    result = run_conversion_job(job, options)
                    push_job_to_session(result)
                    st.session_state["pending_workspace_redirect"] = True
                progress_status.empty()
                return result
            except PipelineError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive
                st.exception(exc)

    return None


def _render_sample_card(container: "st.delta_generator.DeltaGenerator") -> ConversionResult | None:
    samples = list_sample_series()
    with container:
        st.subheader("Or start from a bundled sample")
        if not samples:
            st.info("No sample datasets were found under `dcm_examples/big_dicom`.")
            return None

        sample_names = [sample.name for sample in samples]
        index = st.selectbox(
            "Choose a sample series",
            options=range(len(samples)),
            format_func=lambda idx: f"{sample_names[idx]} ({samples[idx].file_count} slices)",
            key="sample-selector",
        )
        options = _render_option_controls(prefix="samples")

        run_now = st.button(
            "Convert sample study",
            key="sample-run",
            type="secondary",
            width="stretch",
        )

        if run_now:
            try:
                with st.spinner(f"Copying {samples[index].name} and running dicom2stl..."):
                    job = stage_sample_series(samples[index].path)
                    result = run_conversion_job(job, options)
                    push_job_to_session(result)
                    st.session_state["pending_workspace_redirect"] = True
                return result
            except PipelineError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive
                st.exception(exc)

    return None


def _render_option_controls(prefix: str) -> ConversionOptions:
    tissue = st.selectbox(
        "Tissue preset",
        ("soft_tissue", "bone", "skin", "fat"),
        index=0,
        key=f"{prefix}-tissue",
        help="dicom2stl --type flag",
    )
    keep_largest = st.checkbox(
        "Keep only the largest component",
        value=True,
        key=f"{prefix}-largest",
        help="Adds --largest to dicom2stl",
    )
    smooth = st.slider(
        "Smoothing iterations",
        min_value=0,
        max_value=100,
        value=25,
        step=5,
        key=f"{prefix}-smooth",
    )
    reduce = st.slider(
        "Mesh reduction factor",
        min_value=0.2,
        max_value=0.99,
        value=0.9,
        step=0.05,
        key=f"{prefix}-reduce",
    )
    clean_small = st.slider(
        "Remove parts smaller than (%)",
        min_value=0.0,
        max_value=0.5,
        value=0.05,
        step=0.01,
        key=f"{prefix}-clean",
        help="--clean-small threshold",
    )
    anisotropic = st.checkbox(
        "Apply anisotropic smoothing",
        value=False,
        key=f"{prefix}-anisotropic",
    )

    return ConversionOptions(
        tissue_type=tissue,
        keep_largest=keep_largest,
        smooth_iterations=smooth,
        reduce_factor=reduce,
        clean_small_factor=clean_small,
        anisotropic_volume=anisotropic,
    )


def _render_conversion_status() -> list[ConversionResult]:
    st.subheader("Recent conversions")

    jobs: list[ConversionResult] = st.session_state.get("dicom_jobs", [])

    if not jobs:
        st.write("No conversions yet. Upload a study or run a sample to begin.")
        return []

    for job in reversed(jobs[-5:]):
        _render_job_card(job)
    return jobs


def _render_job_card(result: ConversionResult) -> None:
    status = "✅ Success" if result.success else "⚠️ Failed"
    with st.expander(f"{status} · {result.job.label} · {result.elapsed_seconds:.1f}s"):
        st.write(f"STL: `{result.job.output_stl}`")
        if result.job.output_meta.exists():
            with result.job.output_meta.open() as meta_file:
                try:
                    meta_json = json.load(meta_file)
                    st.json(meta_json, expanded=False)
                except Exception:
                    st.caption("Metadata file could not be parsed.")
        st.code(result.stdout or "(no stdout)", language="text")
        if result.stderr:
            st.code(result.stderr, language="text")


def _render_conversion_banner(result: ConversionResult) -> None:
    if result.success:
        st.success(
            f"dicom2stl completed in {result.elapsed_seconds:.1f}s · STL saved to {result.job.output_stl}"
        )
    else:
        st.error(
            f"dicom2stl failed (exit {result.return_code}). Check logs below for details."
        )

