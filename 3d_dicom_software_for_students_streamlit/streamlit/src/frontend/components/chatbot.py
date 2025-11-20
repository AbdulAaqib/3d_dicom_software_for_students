"""Combined STL workspace + GPT assistant."""

from __future__ import annotations

from functools import lru_cache
import os
import textwrap
from typing import Any, Optional

import streamlit as st

try:  # pragma: no cover - optional dependency
    from openai import AzureOpenAI
except ImportError:  # pragma: no cover - optional dependency
    AzureOpenAI = None  # type: ignore[assignment]

from backend import load_recent_jobs
from .viewer import render_viewer_panel


SYSTEM_PROMPT = textwrap.dedent(
    """
    You are the 3D DICOM Studio copilot. Help users reason about CT volumes, STL
    meshes, and annotated snapshots captured in Streamlit. Reference the most
    recent conversion metadata visible to you, and when the user attaches images,
    explain what you observe and relate it to the mesh or annotations they
    mention. Keep responses concise, actionable, and grounded in the provided
    context.
    """
).strip()

CHAT_LAYOUT_CSS = """
<style>
.chat-surface {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}
.chat-surface div[data-testid="stChatMessageList"] {
    flex: 1;
    overflow-y: auto;
    max-height: none;
    scroll-behavior: smooth;
    padding-bottom: 1rem;
}
.chat-surface div[data-testid="stVerticalBlock"] {
    flex: 1;
    display: flex;
    flex-direction: column;
}
div[data-testid="stChatInput"] > div:first-child {
    position: sticky;
    bottom: 0;
    background: rgba(24,24,24,0.85);
    border-top: 1px solid rgba(148, 163, 184, 0.4);
    box-shadow: 0 -8px 20px rgba(15, 23, 42, 0.25);
}
</style>
"""

CHAT_SNAPSHOT_BUFFER_KEY = "chat-selected-snapshots-buffer"
CHAT_COMPLETION_MAX_TOKENS = 4096


def render_chatbot_page(embed: bool = False) -> None:
    """Render the conversational UI (viewer + GPT assistant)."""

    latest_job = _get_latest_job()

    if embed:
        render_chat_panel(compact=True)
        return

    if latest_job is None:
        st.title("Workspace")
        st.warning("Upload a DICOM study on the Upload & Convert page to unlock the chatbot.")
        if st.button("Go to Upload & Convert", type="primary"):
            st.session_state["active_page"] = "Uploader"
            st.rerun()
        return

    st.markdown(CHAT_LAYOUT_CSS, unsafe_allow_html=True)
    st.title("Workspace")

    snapshots = st.session_state.get("stl_snapshots", [])
    snapshot_options = {snap["snapshot_id"]: _format_snapshot_label(snap) for snap in snapshots}

    chat_col, viewer_col = st.columns((3, 2), gap="large")

    with chat_col:
        st.markdown('<div class="chat-surface">', unsafe_allow_html=True)
        selected_snapshots = _render_snapshot_selector(
            snapshot_options,
            label="Attach snapshots (optional)",
            show_preview=True,
        )
        render_chat_panel(
            compact=False,
            snapshot_options=snapshot_options,
            selected_snapshots=selected_snapshots,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with viewer_col:
        render_viewer_panel(latest_job)
        _render_context_metrics()


def _render_context_metrics() -> None:
    jobs = load_recent_jobs(limit=5)
    snapshots = st.session_state.get("stl_snapshots", [])
    col_jobs, col_snaps = st.columns(2)
    col_jobs.metric("Recent conversions", len(jobs))
    col_snaps.metric("Saved snapshots", len(snapshots))


def render_chat_panel(
    compact: bool,
    snapshot_options: dict[str, str] | None = None,
    selected_snapshots: list[str] | None = None,
) -> None:
    if AzureOpenAI is None:
        st.warning("Install the `openai` package to enable the chatbot (`pip install openai`).")
        return

    config = _resolve_azure_client_config()
    if not config:
        st.warning(
            "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION, "
            "and AZURE_OPENAI_CHAT_DEPLOYMENT to use the chatbot."
        )
        return

    client = _get_cached_azure_client(
        api_key=config["api_key"],
        endpoint=config["endpoint"],
        api_version=config["api_version"],
    )

    _init_chat_state()
    snapshots = st.session_state.get("stl_snapshots", [])
    if snapshot_options is None:
        snapshot_options = {snap["snapshot_id"]: _format_snapshot_label(snap) for snap in snapshots}

    if compact:
        selected_snapshots = _render_snapshot_selector(
            snapshot_options,
            label="Attach snapshots (optional)",
            show_preview=True,
        )
    else:
        selected_snapshots = selected_snapshots or list(
            st.session_state.get(CHAT_SNAPSHOT_BUFFER_KEY, [])
        )
    selected_snapshots = list(selected_snapshots)

    _render_history()
    st.markdown(
        """
        <script>
        const chatList = window.parent.document.querySelector('div[data-testid="stChatMessageList"]');
        if (chatList) { chatList.scrollTop = chatList.scrollHeight; }
        </script>
        """,
        unsafe_allow_html=True,
    )

    if prompt := st.chat_input("Ask about the STL, annotations, or DICOM metadata"):
        st.session_state["chat_last_snapshot_ids"] = list(selected_snapshots)
        st.session_state["chat_display_messages"].append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        attachments = [_resolve_snapshot(sid) for sid in selected_snapshots if _resolve_snapshot(sid)]
        response_text = _run_conversation(
            prompt,
            attachments,
            client,
            config["deployment"],
        )

        if response_text:
            st.session_state["chat_display_messages"].append(
                {"role": "assistant", "content": response_text}
            )
            st.chat_message("assistant").write(response_text)

        _clear_snapshot_selection()
        st.rerun()


def _render_snapshot_selector(
    snapshot_options: dict[str, str],
    *,
    label: str = "Attach snapshots (optional)",
    show_preview: bool = True,
) -> list[str]:
    buffer = st.session_state.get(CHAT_SNAPSHOT_BUFFER_KEY)
    if not isinstance(buffer, list):
        buffer = []
    valid_buffer = [sid for sid in buffer if sid in snapshot_options]
    selected_snapshots = st.multiselect(
        label,
        options=list(snapshot_options.keys()),
        format_func=lambda sid: snapshot_options.get(sid, sid),
        default=valid_buffer,
    )
    selected_snapshots = list(selected_snapshots)
    st.session_state[CHAT_SNAPSHOT_BUFFER_KEY] = selected_snapshots
    if show_preview and selected_snapshots:
        st.caption(f"{len(selected_snapshots)} snapshot(s) queued for the next message.")
        preview_cols = st.columns(min(len(selected_snapshots), 3) or 1)
        for idx, snapshot_id in enumerate(selected_snapshots[:3]):
            snap = _resolve_snapshot(snapshot_id)
            if not snap:
                continue
            data_url = _snapshot_data_url(snap)
            if not data_url:
                continue
            target_col = preview_cols[min(idx, len(preview_cols) - 1)]
            with target_col:
                st.image(
                    data_url,
                    caption=snapshot_options.get(snapshot_id, snapshot_id),
                    width="stretch",
                )
    elif show_preview and not snapshot_options:
        st.caption("Capture a snapshot from the STL viewer to attach it here.")
    return selected_snapshots


def _render_history() -> None:
    for message in st.session_state.get("chat_display_messages", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])


def _run_conversation(
    prompt: str,
    attachments: list[dict],
    client: AzureOpenAI,
    deployment_name: str,
) -> str:
    with st.spinner("Querying GPT…"):
        api_messages: list[dict] = st.session_state["chat_api_messages"]
        user_content = _build_user_content(prompt, attachments)
        request_messages = api_messages + [{"role": "user", "content": user_content}]

        try:
            response = client.chat.completions.create(
                model=deployment_name,
                messages=request_messages,
                max_completion_tokens=CHAT_COMPLETION_MAX_TOKENS,
                stream=False,
            )
        except Exception as exc:  # pragma: no cover - network/runtime errors
            st.error(f"Chat request failed: {exc}")
            if attachments:
                st.warning(
                    "Attachment-heavy requests can fail on GPT. "
                    "Try re-running with fewer snapshots or verify your deployment's multimodal support."
                )
            return ""

        message = response.choices[0].message
        assistant_text = _content_to_text(message.content)

        api_messages.append({"role": "user", "content": user_content})
        api_messages.append({"role": "assistant", "content": message.content})

        return assistant_text


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
        st.session_state["chat_api_messages"] = [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                    }
                ],
            }
        ]

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


def _build_user_content(prompt: str, attachments: list[dict]) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": prompt}]
    max_attachments = 5
    for snap in attachments[:max_attachments]:
        notes = snap.get("notes")
        if notes:
            content.append({"type": "text", "text": f"Snapshot note: {notes}"})
        data_url = _snapshot_data_url(snap)
        if not data_url:
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": data_url,
                    "detail": "auto",
                },
            }
        )
    return content


def _snapshot_data_url(snapshot: dict[str, Any]) -> str | None:
    payload = snapshot.get("annotated_base64") or snapshot.get("data_base64")
    if not payload:
        return None
    mime_type = snapshot.get("mime_type", "image/png")
    return f"data:{mime_type};base64,{payload}"


def _clear_snapshot_selection() -> None:
    st.session_state[CHAT_SNAPSHOT_BUFFER_KEY] = []


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


def _resolve_azure_client_config() -> Optional[dict]:
    endpoint = _get_secret("AZURE_OPENAI_ENDPOINT")
    api_key = _get_secret("AZURE_OPENAI_KEY")
    api_version = _get_secret("AZURE_OPENAI_API_VERSION")
    deployment = _get_secret("AZURE_OPENAI_CHAT_DEPLOYMENT")

    if all([endpoint, api_key, api_version, deployment]):
        if AzureOpenAI is None:
            st.error("Upgrade the `openai` package to a version that includes AzureOpenAI support.")
            return None
        return {
            "endpoint": endpoint,
            "api_key": api_key,
            "api_version": api_version,
            "deployment": deployment,
        }

    return None


@lru_cache(maxsize=2)
def _get_cached_azure_client(
    *, api_key: str, endpoint: str, api_version: str
) -> AzureOpenAI:
    if AzureOpenAI is None:
        raise RuntimeError("AzureOpenAI client unavailable; upgrade openai package.")
    return AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint,
    )
