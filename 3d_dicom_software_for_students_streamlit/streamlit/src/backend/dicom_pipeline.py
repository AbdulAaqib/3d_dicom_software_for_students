"""Upload ingestion + dicom2stl orchestration helpers."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .config import (
    CONVERSIONS_ROOT,
    ensure_cache_dirs,
    discover_samples,
    resolve_dicom2stl_bin,
    SampleSeries,
)

try:  # pragma: no cover - optional import when Streamlit is unavailable
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - optional import
    st = None  # type: ignore

try:  # pragma: no cover - optional import for richer type hints
    from streamlit.runtime.uploaded_file_manager import UploadedFile
except Exception:  # pragma: no cover - fallback for type checking
    UploadedFile = Any  # type: ignore


ProgressCallback = Callable[[int, int], None]


class PipelineError(RuntimeError):
    """Raised for recoverable ingestion/processing failures."""


@dataclass
class ConversionOptions:
    """User-selected dicom2stl flags."""

    tissue_type: str = "soft_tissue"
    keep_largest: bool = True
    smooth_iterations: int = 25
    reduce_factor: float = 0.9
    clean_small_factor: float = 0.05
    anisotropic_volume: bool = False

    def to_cli_args(self) -> list[str]:
        """Render CLI arguments for dicom2stl."""

        args: list[str] = []
        if self.tissue_type:
            args.extend(["--type", self.tissue_type])
        args.extend(["--smooth", str(int(self.smooth_iterations))])
        args.extend(["--reduce", f"{self.reduce_factor:.3f}"])
        args.extend(["--clean-small", f"{self.clean_small_factor:.3f}"])
        if self.keep_largest:
            args.extend(["--enable", "largest"])
        if self.anisotropic_volume:
            args.append("--anisotropic")
        return args

    def as_dict(self) -> dict[str, Any]:
        return {
            "tissue_type": self.tissue_type,
            "keep_largest": self.keep_largest,
            "smooth_iterations": self.smooth_iterations,
            "reduce_factor": self.reduce_factor,
            "clean_small_factor": self.clean_small_factor,
            "anisotropic_volume": self.anisotropic_volume,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversionOptions":
        return cls(
            tissue_type=payload.get("tissue_type", "soft_tissue"),
            keep_largest=payload.get("keep_largest", True),
            smooth_iterations=int(payload.get("smooth_iterations", 25)),
            reduce_factor=float(payload.get("reduce_factor", 0.9)),
            clean_small_factor=float(payload.get("clean_small_factor", 0.05)),
            anisotropic_volume=payload.get("anisotropic_volume", False),
        )


@dataclass
class ConversionJob:
    """On-disk staging metadata for a dicom2stl run."""

    job_id: str
    label: str
    job_dir: Path
    dicom_dir: Path
    output_dir: Path
    output_stl: Path
    output_meta: Path
    dicom_metadata_txt: Path
    created_at: float
    source_kind: str
    source_details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "label": self.label,
            "job_dir": str(self.job_dir),
            "dicom_dir": str(self.dicom_dir),
            "output_dir": str(self.output_dir),
            "output_stl": str(self.output_stl),
            "output_meta": str(self.output_meta),
            "dicom_metadata_txt": str(self.dicom_metadata_txt),
            "created_at": self.created_at,
            "source_kind": self.source_kind,
            "source_details": self.source_details,
        }


@dataclass
class ConversionResult:
    """Outcome of a dicom2stl invocation."""

    job: ConversionJob
    options: ConversionOptions
    success: bool
    return_code: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timestamp: float
    command: list[str]
    dicom_metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job": self.job.as_dict(),
            "options": self.options.as_dict(),
            "success": self.success,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "elapsed_seconds": self.elapsed_seconds,
            "timestamp": self.timestamp,
            "command": self.command,
            "dicom_metadata": self.dicom_metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversionResult":
        job_data = payload.get("job", {})
        job = ConversionJob(
            job_id=job_data.get("job_id", "unknown"),
            label=job_data.get("label", "Unknown job"),
            job_dir=Path(job_data.get("job_dir", CONVERSIONS_ROOT)),
            dicom_dir=Path(job_data.get("dicom_dir", CONVERSIONS_ROOT)),
            output_dir=Path(job_data.get("output_dir", CONVERSIONS_ROOT)),
            output_stl=Path(job_data.get("output_stl", "")),
            output_meta=Path(job_data.get("output_meta", "")),
            dicom_metadata_txt=Path(job_data.get("dicom_metadata_txt", "")),
            created_at=float(job_data.get("created_at", 0.0)),
            source_kind=job_data.get("source_kind", "unknown"),
            source_details=job_data.get("source_details", {}),
        )
        options = ConversionOptions.from_dict(payload.get("options", {}))
        return cls(
            job=job,
            options=options,
            success=payload.get("success", False),
            return_code=int(payload.get("return_code", 1)),
            stdout=payload.get("stdout", ""),
            stderr=payload.get("stderr", ""),
            elapsed_seconds=float(payload.get("elapsed_seconds", 0.0)),
            timestamp=float(payload.get("timestamp", 0.0)),
            command=list(payload.get("command", [])),
            dicom_metadata=payload.get("dicom_metadata", {}),
        )


def ingest_uploaded_files(
    files: Sequence[UploadedFile],
    *,
    progress_callback: ProgressCallback | None = None,
) -> ConversionJob:
    """Copy Streamlit uploads into a staging directory."""

    if not files:
        raise PipelineError("No files were provided for upload.")

    label = _infer_upload_label(files)
    job = _create_job(label=label, source_kind="upload")

    staged_files = 0
    total = len(files)
    for index, uploaded in enumerate(files, start=1):
        data = _read_uploaded_file(uploaded)
        filename = getattr(uploaded, "name", f"upload-{index}")
        if filename.lower().endswith(".zip"):
            staged_files += _extract_zip(data, job.dicom_dir)
        else:
            staged_files += _write_file(data, job.dicom_dir, filename, index)

        if progress_callback:
            progress_callback(index, total)

    dicom_count = _count_dicom_files(job.dicom_dir)
    if dicom_count == 0:
        raise PipelineError("No DICOM slices were detected in the uploaded payload.")

    job.source_details = {
        "source": "upload",
        "uploaded_files": [getattr(file, "name", "upload") for file in files],
        "staged_files": staged_files,
        "dicom_count": dicom_count,
    }

    return job


def stage_sample_series(sample_path: Path | str) -> ConversionJob:
    """Copy a bundled dataset into staging."""

    sample_path = Path(sample_path)
    if not sample_path.exists():
        raise PipelineError(f"Sample dataset not found: {sample_path}")

    job = _create_job(label=f"Sample · {sample_path.name}", source_kind="sample")

    file_count = 0
    for source in sample_path.rglob("*"):
        if source.is_file():
            relative = source.relative_to(sample_path)
            target = job.dicom_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            file_count += 1

    dicom_count = _count_dicom_files(job.dicom_dir)
    if file_count == 0 or dicom_count == 0:
        raise PipelineError(f"Sample dataset {sample_path.name} does not contain DICOM files.")

    job.source_details = {
        "source": "sample",
        "sample_path": str(sample_path),
        "copied_files": file_count,
        "dicom_count": dicom_count,
    }

    return job


def list_sample_series() -> list[SampleSeries]:
    """Surface bundled datasets for the UI."""

    return discover_samples()


def run_conversion_job(job: ConversionJob, options: ConversionOptions) -> ConversionResult:
    """Invoke dicom2stl for a staged job."""

    ensure_cache_dirs()

    if _count_dicom_files(job.dicom_dir) == 0:
        raise PipelineError("No DICOM slices found in staging directory.")

    executable = resolve_dicom2stl_bin()
    if not executable:
        raise PipelineError(
            "dicom2stl executable not found. Install requirements or activate the project virtualenv."
        )

    command = [
        executable,
        str(job.dicom_dir),
        "--output",
        str(job.output_stl),
        "--meta",
        str(job.dicom_metadata_txt),
        "--clean",
    ]
    command.extend(options.to_cli_args())

    start = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=job.job_dir,
        )
    except OSError as exc:  # pragma: no cover - defensive
        raise PipelineError(f"Failed to execute dicom2stl: {exc}") from exc
    elapsed = time.perf_counter() - start

    success = process.returncode == 0 and job.output_stl.exists()
    dicom_meta = _parse_dicom_metadata(job.dicom_metadata_txt)

    result = ConversionResult(
        job=job,
        options=options,
        success=success,
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        elapsed_seconds=elapsed,
        timestamp=time.time(),
        command=command,
        dicom_metadata=dicom_meta,
    )

    _write_metadata(result)
    return result


def push_job_to_session(result: ConversionResult) -> None:
    """Persist a conversion result in Streamlit's session_state."""

    if st is None:  # pragma: no cover - Streamlit not available
        return

    jobs = st.session_state.get("dicom_jobs", [])
    if not isinstance(jobs, list):
        jobs = []

    jobs.append(result)
    st.session_state["dicom_jobs"] = jobs[-10:]


def load_recent_jobs(limit: int = 5) -> list[ConversionResult]:
    """Return recent conversions from session or disk."""

    session_jobs = _session_jobs()
    if session_jobs:
        return session_jobs[-limit:]

    return _load_jobs_from_disk(limit)


def list_sample_names() -> list[str]:  # pragma: no cover - backwards compatibility shim
    """Deprecated helper kept for compatibility."""

    return [sample.name for sample in list_sample_series()]


def _create_job(*, label: str, source_kind: str) -> ConversionJob:
    ensure_cache_dirs()

    job_suffix = uuid.uuid4().hex[:6]
    job_id = f"job-{time.strftime('%Y%m%d-%H%M%S')}-{job_suffix}"
    job_dir = CONVERSIONS_ROOT / job_id
    dicom_dir = job_dir / "dicom"
    output_dir = job_dir / "artifacts"
    output_stl = output_dir / "mesh.stl"
    output_meta = output_dir / "metadata.json"
    dicom_metadata_txt = output_dir / "dicom2stl_meta.txt"

    for path in (job_dir, dicom_dir, output_dir):
        path.mkdir(parents=True, exist_ok=True)

    return ConversionJob(
        job_id=job_id,
        label=label,
        job_dir=job_dir,
        dicom_dir=dicom_dir,
        output_dir=output_dir,
        output_stl=output_stl,
        output_meta=output_meta,
        dicom_metadata_txt=dicom_metadata_txt,
        created_at=time.time(),
        source_kind=source_kind,
    )


def _infer_upload_label(files: Sequence[UploadedFile]) -> str:
    names = [Path(getattr(file, "name", "upload")).stem for file in files if getattr(file, "name", "")]
    if not names:
        return "Upload · Untitled"
    if len(names) == 1:
        return f"Upload · {names[0]}"
    return f"Upload · {names[0]} +{len(names) - 1}"


def _read_uploaded_file(file_obj: UploadedFile) -> bytes:
    if hasattr(file_obj, "getbuffer"):
        buffer = file_obj.getbuffer()
        data = bytes(buffer)
    else:
        data = file_obj.read()
    try:
        file_obj.seek(0)
    except Exception:  # pragma: no cover - not all uploaders support seek
        pass
    return data


def _extract_zip(payload: bytes, target_dir: Path) -> int:
    extracted = 0
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = Path(member.filename)
            if _should_skip(member_path):
                continue
            safe_target = _safe_join(target_dir, member_path)
            safe_target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, safe_target.open("wb") as dest:
                shutil.copyfileobj(source, dest)
            extracted += 1
    return extracted


def _write_file(payload: bytes, target_dir: Path, filename: str, index: int) -> int:
    safe_name = _sanitize_filename(filename) or f"slice-{index:04d}.dcm"
    target_path = _safe_join(target_dir, Path(safe_name))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("wb") as dest:
        dest.write(payload)
    return 1


def _sanitize_filename(name: str) -> str:
    keep = [char for char in name if char.isalnum() or char in {".", "-", "_"}]
    sanitized = "".join(keep).strip("._")
    return sanitized or "upload.dcm"


def _should_skip(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(part.startswith("__macosx") for part in parts)


def _safe_join(base: Path, relative: Path) -> Path:
    cleaned_parts = [part for part in relative.parts if part not in ("", ".", "..")]
    candidate = base.joinpath(*cleaned_parts)
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    if base_resolved not in candidate_resolved.parents and candidate_resolved != base_resolved:
        raise PipelineError(f"Archive entry escapes staging directory: {relative}")
    return candidate_resolved


def _count_dicom_files(path: Path) -> int:
    if not path.exists():
        return 0
    suffixes = {".dcm", ".dicom"}
    return sum(1 for file in path.rglob("*") if file.is_file() and file.suffix.lower() in suffixes)


def _parse_dicom_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    metadata: dict[str, Any] = {}
    with path.open("r") as handle:
        for line in handle:
            line = line.strip()
            if not line or " " not in line:
                continue
            key, value = line.split(" ", 1)
            metadata[key] = value.strip()
    return metadata


def _write_metadata(result: ConversionResult) -> None:
    result.job.output_meta.parent.mkdir(parents=True, exist_ok=True)
    result.job.output_meta.write_text(json.dumps(result.as_dict(), indent=2))


def _session_jobs() -> list[ConversionResult]:
    if st is None:
        return []
    jobs = st.session_state.get("dicom_jobs", [])
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, ConversionResult)]


def _load_jobs_from_disk(limit: int) -> list[ConversionResult]:
    if not CONVERSIONS_ROOT.exists():
        return []

    metadata_files = sorted(
        CONVERSIONS_ROOT.glob("*/artifacts/metadata.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    results: list[ConversionResult] = []
    for meta_path in metadata_files:
        try:
            payload = json.loads(meta_path.read_text())
            results.append(ConversionResult.from_dict(payload))
        except Exception:
            continue
        if len(results) >= limit:
            break

    return list(reversed(results))


__all__ = [
    "ConversionJob",
    "ConversionOptions",
    "ConversionResult",
    "PipelineError",
    "ingest_uploaded_files",
    "list_sample_series",
    "load_recent_jobs",
    "push_job_to_session",
    "run_conversion_job",
    "stage_sample_series",
]


