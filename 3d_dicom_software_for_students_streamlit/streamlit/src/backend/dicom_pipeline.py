"""Utilities for staging DICOM studies and running dicom2stl conversions."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Sequence
import io
import json
import shutil
import subprocess
import time
import uuid
import zipfile

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from . import config


class PipelineError(RuntimeError):
    """Raised when a conversion job cannot be completed."""


@dataclass
class ConversionOptions:
    """High-level conversion knobs exposed in the UI."""

    tissue_type: str = "soft_tissue"
    keep_largest: bool = True
    smooth_iterations: int = 25
    reduce_factor: float | None = 0.9
    clean_small_factor: float | None = 0.05
    anisotropic_volume: bool = False
    extra_cli_flags: list[str] = field(default_factory=list)

    def to_cli_args(self) -> list[str]:
        args: list[str] = []
        if self.tissue_type:
            args += ["--type", self.tissue_type]
        if self.keep_largest:
            args += ["--enable", "largest"]
        if self.smooth_iterations is not None:
            args += ["--smooth", str(self.smooth_iterations)]
        if self.reduce_factor:
            args += ["--reduce", str(self.reduce_factor)]
        if self.clean_small_factor:
            args += ["--clean-small", str(self.clean_small_factor)]
        if self.anisotropic_volume:
            args.append("--anisotropic")
        args += self.extra_cli_flags
        return args


@dataclass
class ConversionJob:
    """Filesystem layout for a staged conversion."""

    job_id: str
    label: str
    job_dir: Path
    dicom_dir: Path
    output_stl: Path
    output_meta: Path


@dataclass
class ConversionResult:
    """Outcome of running dicom2stl."""

    job: ConversionJob
    options: ConversionOptions
    success: bool
    return_code: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timestamp: float

    def as_dict(self) -> dict:
        data = {
            "job": {
                "job_id": self.job.job_id,
                "label": self.job.label,
                "job_dir": str(self.job.job_dir),
                "dicom_dir": str(self.job.dicom_dir),
                "output_stl": str(self.job.output_stl),
                "output_meta": str(self.job.output_meta),
            },
            "options": asdict(self.options),
            "success": self.success,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "elapsed_seconds": self.elapsed_seconds,
            "timestamp": self.timestamp,
        }
        if self.job.output_meta.exists():
            try:
                data["metadata"] = json.loads(self.job.output_meta.read_text())
            except json.JSONDecodeError:
                data["metadata"] = None
        else:
            data["metadata"] = None
        return data


def _create_job(label: str) -> ConversionJob:
    config.ensure_cache_dirs()
    job_id = uuid.uuid4().hex
    job_dir = config.CONVERSIONS_ROOT / job_id
    dicom_dir = job_dir / "dicom"
    dicom_dir.mkdir(parents=True, exist_ok=True)

    return ConversionJob(
        job_id=job_id,
        label=label,
        job_dir=job_dir,
        dicom_dir=dicom_dir,
        output_stl=job_dir / "output.stl",
        output_meta=job_dir / "metadata.json",
    )


def _safe_path_from_zip(name: str) -> Path:
    path = Path(name)
    parts = [part for part in path.parts if part not in ("..", ".")]
    return Path(*parts) if parts else Path("file.dcm")


def ingest_uploaded_files(
    files: Sequence[UploadedFile],
    progress_callback: Callable[[int, int], None] | None = None,
) -> ConversionJob:
    """Persist UploadedFile objects into a conversion job directory."""

    if not files:
        raise PipelineError("No files were uploaded.")

    job = _create_job("Uploaded Study")

    total = len(files) or 1
    processed = 0

    for uploaded in files:
        file_bytes = uploaded.getvalue()
        buffer = io.BytesIO(file_bytes)
        buffer.seek(0)

        if zipfile.is_zipfile(buffer):
            buffer.seek(0)
            with zipfile.ZipFile(buffer) as archive:
                for member in archive.namelist():
                    if member.endswith("/"):
                        continue
                    target = job.dicom_dir / _safe_path_from_zip(member)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, open(target, "wb") as dest:
                        shutil.copyfileobj(source, dest)
        else:
            sanitized = Path(uploaded.name).name or f"slice-{uuid.uuid4().hex}.dcm"
            target = job.dicom_dir / sanitized
            target.write_bytes(file_bytes)

        processed += 1
        if progress_callback:
            progress_callback(processed, total)

    return job


def stage_sample_series(series_path: Path) -> ConversionJob:
    """Copy a bundled sample series into a fresh job directory."""

    if not series_path.exists():
        raise PipelineError(f"Sample path not found: {series_path}")

    job = _create_job(series_path.name)
    shutil.copytree(series_path, job.dicom_dir, dirs_exist_ok=True)
    return job


def run_conversion_job(job: ConversionJob, options: ConversionOptions) -> ConversionResult:
    """Invoke dicom2stl for the prepared job."""

    dicom2stl_bin = config.resolve_dicom2stl_bin()
    if not dicom2stl_bin:
        raise PipelineError(
            "dicom2stl binary was not found. Install it inside the Streamlit virtualenv."
        )

    cmd = [
        dicom2stl_bin,
        "--output",
        str(job.output_stl),
        "--meta",
        str(job.output_meta),
    ]
    cmd += options.to_cli_args()
    cmd.append(str(job.dicom_dir))

    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start

    success = proc.returncode == 0 and job.output_stl.exists()

    return ConversionResult(
        job=job,
        options=options,
        success=success,
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        elapsed_seconds=elapsed,
        timestamp=time.time(),
    )


def list_sample_series() -> list[config.SampleSeries]:
    """Convenience passthrough for the UI."""

    return config.discover_samples()


def load_recent_jobs(limit: int = 5) -> list[ConversionResult]:
    """Pull cached jobs from session state."""

    key = "dicom_jobs"
    jobs: list[ConversionResult] = st.session_state.get(key, [])

    if not isinstance(jobs, list):
        jobs = []

    return jobs[-limit:]


def push_job_to_session(result: ConversionResult) -> None:
    """Append the completed job so other pages (chatbot) can reference it."""

    key = "dicom_jobs"
    jobs: list[ConversionResult] = st.session_state.get(key, [])
    if not isinstance(jobs, list):
        jobs = []
    jobs.append(result)
    st.session_state[key] = jobs

