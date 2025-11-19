"""Path helpers and constants shared by backend modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STREAMLIT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_ROOT = PROJECT_ROOT / "dcm_examples"
SAMPLES_ROOT = DATASETS_ROOT / "big_dicom"
CACHE_ROOT = STREAMLIT_ROOT / ".cache"
CONVERSIONS_ROOT = CACHE_ROOT / "dicom_sessions"
VENV_BIN = PROJECT_ROOT / "3d_dicom_software_for_students_streamlit" / "venv" / "bin"


def ensure_cache_dirs() -> None:
    """Create cache directories on demand."""

    for path in (CACHE_ROOT, CONVERSIONS_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def resolve_dicom2stl_bin() -> str | None:
    """Return the dicom2stl executable path if available."""

    candidate_env = shutil.which("dicom2stl")
    if candidate_env:
        return candidate_env

    candidate_local = VENV_BIN / "dicom2stl"
    if candidate_local.exists():
        return str(candidate_local)

    return None


@dataclass(frozen=True)
class SampleSeries:
    """Metadata for a built-in sample DICOM series."""

    name: str
    path: Path
    file_count: int


def discover_samples(max_depth: int = 1) -> list[SampleSeries]:
    """Return a list of bundled sample datasets."""

    if not SAMPLES_ROOT.exists():
        return []

    samples: list[SampleSeries] = []

    for child in sorted(SAMPLES_ROOT.iterdir()):
        if child.is_dir():
            file_count = sum(1 for _ in child.rglob("*.dcm"))
            samples.append(SampleSeries(name=child.name, path=child, file_count=file_count))

    return samples


