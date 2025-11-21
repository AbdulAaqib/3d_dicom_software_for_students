"""Disk-backed helpers for persisting STL annotations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import CONVERSIONS_ROOT


_SUPPORTED_KINDS = {"marker", "arrow", "label"}


def _infer_kind(annotation: dict) -> str:
    kind = annotation.get("kind")
    if isinstance(kind, str) and kind.lower() in _SUPPORTED_KINDS:
        return kind.lower()

    # Backward compatibility: annotations previously stored without kind
    direction = annotation.get("direction") or {}
    if isinstance(direction, dict):
        magnitude = sum(float(direction.get(axis, 0.0)) ** 2 for axis in ("u", "v", "w"))
        if magnitude > 1e-6:
            return "arrow"

    text_only = annotation.get("text")
    if isinstance(text_only, str) and not annotation.get("point"):
        return "label"

    return "marker"


def _normalize_vector(vector: dict | None) -> dict:
    if not isinstance(vector, dict):
        return {"u": 0.0, "v": 0.0, "w": 0.0}
    try:
        return {
            "u": float(vector.get("u", 0.0)),
            "v": float(vector.get("v", 0.0)),
            "w": float(vector.get("w", 0.0)),
        }
    except (TypeError, ValueError):
        return {"u": 0.0, "v": 0.0, "w": 0.0}


def _normalize_point(point: dict | None) -> dict:
    if not isinstance(point, dict):
        return {}
    try:
        return {
            "x": float(point.get("x", 0.0)),
            "y": float(point.get("y", 0.0)),
            "z": float(point.get("z", 0.0)),
        }
    except (TypeError, ValueError):
        return {}


def _normalize_annotation(annotation: dict, job_id: str) -> dict:
    normalized = dict(annotation)
    normalized["job_id"] = job_id
    normalized["kind"] = _infer_kind(normalized)
    normalized["point"] = _normalize_point(normalized.get("point"))
    normalized["tip_point"] = _normalize_point(normalized.get("tip_point"))
    if normalized["kind"] in {"marker", "arrow"}:
        normalized.setdefault("label", normalized.get("label", ""))
        normalized.setdefault("notes", normalized.get("notes", ""))
        normalized["direction"] = _normalize_vector(normalized.get("direction"))
    elif normalized["kind"] == "label":
        text = normalized.get("text") or normalized.get("label") or ""
        normalized["text"] = str(text)
        normalized.setdefault("label", str(text))
        normalized.setdefault("color", normalized.get("color", "#ffffff"))
        normalized["direction"] = _normalize_vector(normalized.get("direction"))
        try:
            normalized["size"] = float(normalized.get("size", 18.0))
        except (TypeError, ValueError):
            normalized["size"] = 18.0
    return normalized


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
            records: list[dict] = []
            for ann in payload:
                if isinstance(ann, dict):
                    records.append(_normalize_annotation(ann, job_id))
            return records
    except Exception:
        return []
    return []


def save_annotations(job_id: str, annotations: list[dict]) -> None:
    """Persist annotations for a job."""

    path = _annotation_file(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized: list[dict] = []
    for ann in annotations:
        if isinstance(ann, dict):
            normalized.append(_normalize_annotation(ann, job_id))
    path.write_text(json.dumps(normalized, indent=2))


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
                    results.append(_normalize_annotation(ann, path.parents[1].name))
    return results


def _snapshot_file(job_id: str) -> Path:
    safe_id = _sanitize_job_id(job_id)
    return CONVERSIONS_ROOT / safe_id / "artifacts" / "snapshots.json"


def load_snapshots(job_id: str) -> list[dict]:
    """Return saved snapshots for a job (empty list if none)."""

    path = _snapshot_file(job_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
        if isinstance(payload, list):
            return [snap for snap in payload if isinstance(snap, dict)]
    except Exception:
        return []
    return []


def save_snapshots(job_id: str, snapshots: list[dict]) -> None:
    """Persist snapshot entries for a job."""

    path = _snapshot_file(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    for snap in snapshots:
        snap.setdefault("job_id", job_id)
    path.write_text(json.dumps(snapshots, indent=2))


def list_all_snapshots(job_ids: Iterable[str] | None = None) -> list[dict]:
    """Aggregate snapshots across jobs."""

    results: list[dict] = []
    if job_ids is None:
        pattern = CONVERSIONS_ROOT.glob("*/artifacts/snapshots.json")
        files = sorted(pattern, key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        files = [_snapshot_file(job_id) for job_id in job_ids]

    for path in files:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        if isinstance(payload, list):
            for snap in payload:
                if isinstance(snap, dict):
                    snap.setdefault("job_id", path.parents[1].name)
                    results.append(snap)
    return results

