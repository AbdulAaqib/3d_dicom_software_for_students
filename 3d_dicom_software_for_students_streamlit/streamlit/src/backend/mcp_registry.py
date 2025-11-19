"""Lightweight MCP-style tool registry shared by the chatbot and tools page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import json

import streamlit as st

from .dicom_pipeline import ConversionResult
from .annotation_store import (
    load_annotations as load_annotations_from_disk,
    list_all_annotations as list_all_annotations_from_disk,
)


ToolHandler = Callable[[dict], dict]


@dataclass
class McpTool:
    name: str
    description: str
    parameters: dict
    handler: ToolHandler


def _get_conversions() -> list[ConversionResult]:
    jobs = st.session_state.get("dicom_jobs", [])
    return jobs if isinstance(jobs, list) else []


def _get_snapshots() -> list[dict]:
    snapshots = st.session_state.get("stl_snapshots", [])
    return snapshots if isinstance(snapshots, list) else []


def _get_annotations(job_id: str | None = None) -> list[dict]:
    if job_id:
        return list(load_annotations_from_disk(job_id))

    conversions = _get_conversions()
    job_ids = {conversion.job.job_id for conversion in conversions if conversion.job}
    if job_ids:
        annotations: list[dict] = []
        for jid in job_ids:
            annotations.extend(load_annotations_from_disk(jid))
        return annotations

    return list_all_annotations_from_disk()


def _list_conversions(_: dict) -> dict:
    return {"conversions": [job.as_dict() for job in _get_conversions()]}


def _get_conversion_detail(payload: dict) -> dict:
    job_id = payload.get("job_id")
    if not job_id:
        raise ValueError("job_id is required")
    for job in _get_conversions():
        if job.job.job_id == job_id:
            return job.as_dict()
    raise ValueError(f"No conversion found for job_id={job_id}")


def _list_snapshots(payload: dict) -> dict:
    job_id = payload.get("job_id")
    snapshots = _get_snapshots()
    if job_id:
        snapshots = [snap for snap in snapshots if snap.get("job_id") == job_id]
    return {"snapshots": snapshots}


def _get_snapshot(payload: dict) -> dict:
    snapshot_id = payload.get("snapshot_id")
    if not snapshot_id:
        raise ValueError("snapshot_id is required")
    for snap in _get_snapshots():
        if snap.get("snapshot_id") == snapshot_id:
            return snap
    raise ValueError(f"No snapshot found for id={snapshot_id}")


def _list_annotations(payload: dict) -> dict:
    job_id = payload.get("job_id")
    annotations = _get_annotations(job_id)
    return {"annotations": annotations}


def _get_annotation(payload: dict) -> dict:
    annotation_id = payload.get("annotation_id")
    if not annotation_id:
        raise ValueError("annotation_id is required")
    for annotation in _get_annotations():
        if annotation.get("annotation_id") == annotation_id:
            return annotation
    raise ValueError(f"No annotation found for id={annotation_id}")


_TOOLS: dict[str, McpTool] = {
    "list_conversions": McpTool(
        name="list_conversions",
        description="List processed DICOM studies with their metadata and STL paths.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_list_conversions,
    ),
    "get_conversion_detail": McpTool(
        name="get_conversion_detail",
        description="Fetch metadata and file paths for a specific conversion job.",
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string", "description": "Conversion job ID"}},
            "required": ["job_id"],
        },
        handler=_get_conversion_detail,
    ),
    "list_snapshots": McpTool(
        name="list_snapshots",
        description="Return saved STL snapshots/annotations, optionally filtered by job_id.",
        parameters={
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Optional job ID to filter by conversion.",
                }
            },
        },
        handler=_list_snapshots,
    ),
    "get_snapshot": McpTool(
        name="get_snapshot",
        description="Retrieve a single snapshot (image + notes) by snapshot_id.",
        parameters={
            "type": "object",
            "properties": {
                "snapshot_id": {"type": "string", "description": "Snapshot identifier"},
            },
            "required": ["snapshot_id"],
        },
        handler=_get_snapshot,
    ),
    "list_annotations": McpTool(
        name="list_annotations",
        description="List saved STL annotations (markers/arrows) optionally filtered by job_id.",
        parameters={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Optional conversion job ID filter"}
            },
        },
        handler=_list_annotations,
    ),
    "get_annotation": McpTool(
        name="get_annotation",
        description="Fetch a specific STL annotation by its identifier.",
        parameters={
            "type": "object",
            "properties": {
                "annotation_id": {"type": "string", "description": "Annotation identifier"}
            },
            "required": ["annotation_id"],
        },
        handler=_get_annotation,
    ),
}


def get_tool_schemas() -> list[dict]:
    """Return OpenAI-compatible tool schemas."""

    schemas: list[dict] = []
    for tool in _TOOLS.values():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
        )
    return schemas


def execute_tool(name: str, arguments_json: str | None) -> str:
    """Execute a registered tool and return a JSON string."""

    tool = _TOOLS.get(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")

    if arguments_json:
        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid arguments for {name}: {exc}") from exc
    else:
        args = {}

    result = tool.handler(args)
    return json.dumps(result, indent=2, default=str)


def list_registered_tools() -> list[McpTool]:
    """Expose registry for the MCP Tools UI."""

    return list(_TOOLS.values())
