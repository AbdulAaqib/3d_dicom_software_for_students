"""Combined STL workspace + GPT assistant."""

from __future__ import annotations

from functools import lru_cache
import os
import textwrap
from typing import Any, Dict, List, Optional

import streamlit as st

try:  # pragma: no cover - optional dependency
    from openai import OpenAI, AzureOpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore[assignment]
    AzureOpenAI = None  # type: ignore[assignment]

from backend import load_recent_jobs
from backend.mcp_registry import execute_tool, get_tool_schemas
from .viewer import render_viewer_panel


SYSTEM_PROMPT = textwrap.dedent(
    """
    You are the 3D DICOM Studio copilot. You help users reason about CT volumes,
    STL meshes, and annotations captured in Streamlit. Before answering, inspect
    the latest conversion metadata and snapshots via the provided MCP tools:
    - list_conversions
    - get_conversion_detail
    - list_snapshots
    - get_snapshot

    Use these tools whenever the user references meshes, patients, slices, or
    annotations so your answers reflect the newest state. When the user attaches
    images, describe what you see and link your reasoning back to the STL data.
    """
).strip()

def render_chatbot_page(embed: bool = False) -> None:
    """Render the STL viewer + conversational UI."""

    latest_job = _get_latest_job()

    if embed:
        _render_chat_panel(compact=True)
        return

    st.title("Workspace")
    col_viewer, col_chat = st.columns((2, 1), gap="large")
    with col_viewer:
        render_viewer_panel(latest_job)
    with col_chat:
        _render_chat_panel(compact=False)


def _render_context_metrics() -> None:
    jobs = load_recent_jobs(limit=5)
    snapshots = st.session_state.get("stl_snapshots", [])
    col_jobs, col_snaps = st.columns(2)
    col_jobs.metric("Recent conversions", len(jobs))
    col_snaps.metric("Saved snapshots", len(snapshots))


def _render_chat_panel(compact: bool) -> None:
    if OpenAI is None:
        st.warning("Install the `openai` package to enable the chatbot (`pip install openai`).")
        return

    config = _resolve_client_config()
    if not config:
        st.warning(
            "Provide either Azure OpenAI credentials (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, "
            "AZURE_OPENAI_API_VERSION, AZURE_OPENAI_CHAT_DEPLOYMENT) or standard OPENAI_API_KEY."
        )
        return

    client = _get_cached_client(
        config["provider"],
        config["api_key"],
        config.get("endpoint"),
        config.get("api_version"),
        config.get("base_url"),
    )

    _init_chat_state()
    if not compact:
        _render_context_metrics()

    snapshots = st.session_state.get("stl_snapshots", [])
    snapshot_options = {snap["snapshot_id"]: _format_snapshot_label(snap) for snap in snapshots}
    selected_snapshots = st.multiselect(
        "Attach snapshots to your next question (optional)",
        options=list(snapshot_options.keys()),
        format_func=lambda sid: snapshot_options.get(sid, sid),
        key="chat-selected-snapshots",
    )

    _render_history()

    if prompt := st.chat_input("Ask about the STL, annotations, or DICOM metadata"):
        st.session_state["chat_display_messages"].append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        attachments = [_resolve_snapshot(sid) for sid in selected_snapshots if _resolve_snapshot(sid)]
        response_text = _run_conversation(prompt, attachments, client, config["model"])

        if response_text:
            st.session_state["chat_display_messages"].append(
                {"role": "assistant", "content": response_text}
            )
            st.chat_message("assistant").write(response_text)


def _render_history() -> None:
    for message in st.session_state.get("chat_display_messages", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])


def _run_conversation(
    prompt: str, attachments: list[dict], client: OpenAI, model_name: str
) -> str:
    with st.spinner("Querying GPT via MCP tools…"):
        messages = st.session_state["chat_api_messages"]

        user_content = [{"type": "text", "text": prompt}]
        for snap in attachments:
            if snap.get("notes"):
                user_content.append(
                    {"type": "text", "text": f"Snapshot note: {snap['notes']}"}
                )
            data_url = f"data:{snap.get('mime_type','image/png')};base64,{snap['data_base64']}"
            user_content.append({"type": "input_image", "image_url": {"url": data_url}})

        messages.append({"role": "user", "content": user_content})

        tool_schemas = get_tool_schemas()

        try:
            while True:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                )
                message = response.choices[0].message

                if message.tool_calls:
                    assistant_payload: Dict[str, Any] = {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": message.tool_calls,
                    }
                    messages.append(assistant_payload)

                    for tool_call in message.tool_calls:
                        tool_response = execute_tool(
                            tool_call.function.name,
                            tool_call.function.arguments,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_response,
                            }
                        )
                    continue

                assistant_text = _content_to_text(message.content)
                messages.append({"role": "assistant", "content": message.content})
                return assistant_text
        except Exception as exc:  # pragma: no cover - network/runtime errors
            st.error(f"Chat request failed: {exc}")
            return ""


def _init_chat_state() -> None:
    if "chat_display_messages" not in st.session_state:
        st.session_state["chat_display_messages"] = [
            {
                "role": "assistant",
                "content": "👋 I'm your DICOM/STL copilot. Ask how to tweak dicom2stl, "
                "summarize meshes, or interpret annotated snapshots. I can call MCP tools "
                "to look up conversions or attachments.",
            }
        ]

    if "chat_api_messages" not in st.session_state:
        st.session_state["chat_api_messages"] = [{"role": "system", "content": SYSTEM_PROMPT}]


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if part.get("type") == "text"]
        return "\n".join(parts).strip()
    return ""


def _resolve_snapshot(snapshot_id: str) -> dict | None:
    snapshots = st.session_state.get("stl_snapshots", [])
    for snap in snapshots:
        if snap.get("snapshot_id") == snapshot_id:
            return snap
    return None


def _format_snapshot_label(snapshot: dict) -> str:
    notes = snapshot.get("notes") or "No notes"
    return f"{snapshot.get('filename','image')} · {notes[:50]}"


def _get_latest_job():
    jobs = load_recent_jobs(limit=1)
    return jobs[-1] if jobs else None


def _get_secret(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value:
        return value
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - secrets not configured
        secrets = None
    if secrets is not None:
        try:
            return secrets[name]
        except Exception:
            return None
    return None


def _resolve_client_config() -> Optional[dict]:
    azure_endpoint = _get_secret("AZURE_OPENAI_ENDPOINT")
    azure_key = _get_secret("AZURE_OPENAI_KEY")
    azure_version = _get_secret("AZURE_OPENAI_API_VERSION")
    azure_deployment = _get_secret("AZURE_OPENAI_CHAT_DEPLOYMENT")

    if all([azure_endpoint, azure_key, azure_version, azure_deployment]):
        if AzureOpenAI is None:
            st.error("Upgrade the `openai` package to a version that includes AzureOpenAI support.")
            return None
        return {
            "provider": "azure",
            "api_key": azure_key,
            "endpoint": azure_endpoint,
            "api_version": azure_version,
            "model": azure_deployment,
        }

    api_key = _get_secret("OPENAI_API_KEY")
    if not api_key:
        return None

    return {
        "provider": "openai",
        "api_key": api_key,
        "base_url": _get_secret("OPENAI_BASE_URL"),
        "model": _get_secret("OPENAI_MODEL") or "gpt-4o-mini",
    }


@lru_cache(maxsize=2)
def _get_cached_client(
    provider: str,
    api_key: str,
    endpoint: str | None,
    api_version: str | None,
    base_url: str | None,
) -> OpenAI:
    if provider == "azure":
        if AzureOpenAI is None:
            raise RuntimeError("AzureOpenAI client unavailable; upgrade openai package.")
        return AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)

