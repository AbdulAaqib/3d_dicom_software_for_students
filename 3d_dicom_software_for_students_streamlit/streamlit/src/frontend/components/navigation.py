"""Sidebar navigation for the Streamlit DICOM workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st


@dataclass(frozen=True)
class PageEntry:
    name: str
    label: str


DEFAULT_PAGES: tuple[PageEntry, ...] = (
    PageEntry("Uploader", "📤 Upload & Convert"),
    PageEntry("Workspace", "🧱 Workspace"),
    PageEntry("MCP Tools", "🧰 Tools & Automations"),
)


def render_navigation(entries: Iterable[PageEntry] | None = None) -> str:
    """Render the sidebar navigation and return the selected page key."""

    entries = tuple(entries or DEFAULT_PAGES)

    if not entries:
        raise ValueError("Navigation requires at least one page entry.")

    with st.sidebar:
        st.markdown("### 3D DICOM Studio")
        st.caption("Upload, convert, analyze, and chat about 3D volumes.")
        st.markdown("---")

        jobs = st.session_state.get("dicom_jobs")
        has_conversions = False
        if isinstance(jobs, list):
            has_conversions = any(getattr(job, "success", False) for job in jobs)

        if "active_page" not in st.session_state:
            st.session_state["active_page"] = entries[0].name

        active = st.session_state["active_page"]

        for entry in entries:
            button_type = "primary" if active == entry.name else "secondary"
            disabled = entry.name == "Workspace" and not has_conversions
            if st.button(entry.label, width="stretch", type=button_type, disabled=disabled):
                active = entry.name
                st.session_state["active_page"] = entry.name
                st.rerun()
            if disabled:
                st.caption("Upload a DICOM and finish conversion to unlock the workspace.")

        st.markdown("---")
        st.caption("Need help? Ask the GPT assistant anytime.")

    return active

