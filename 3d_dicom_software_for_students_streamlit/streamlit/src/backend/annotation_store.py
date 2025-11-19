"""Disk-backed helpers for persisting STL annotations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import CONVERSIONS_ROOT


def _sanitize_job_id(job_id: str) -> str:
    return job_id.strip().replace("/", "_").replace("\\", "_")


def _annotation_file(job_id: str) -> Path:
    safe_id = _sanitize_job_id(job_id)
    return CONVERSIONS_ROOT / safe_id / "artifacts" / "annotations.json"


def load_annotations(job_id: str) -> list[dict]:
    """Return saved annotations for a job (empty list if none)."""

    path = _annotation_file(job_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
        if isinstance(payload, list):
            return [ann for ann in payload if isinstance(ann, dict)]
    except Exception:
        return []
    return []


def save_annotations(job_id: str, annotations: list[dict]) -> None:
    """Persist annotations for a job."""

    path = _annotation_file(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    for ann in annotations:
        ann.setdefault("job_id", job_id)
    path.write_text(json.dumps(annotations, indent=2))


def list_all_annotations(job_ids: Iterable[str] | None = None) -> list[dict]:
    """Aggregate annotations across jobs (bounded by optional job_ids)."""

    results: list[dict] = []
    if job_ids is None:
        pattern = CONVERSIONS_ROOT.glob("*/artifacts/annotations.json")
        files = sorted(pattern, key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        files = [_annotation_file(job_id) for job_id in job_ids]

    for path in files:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        if isinstance(payload, list):
            for ann in payload:
                if isinstance(ann, dict):
                    ann.setdefault("job_id", path.parents[1].name)
                    results.append(ann)
    return results

